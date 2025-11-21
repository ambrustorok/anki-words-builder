import os
import tempfile
import uuid
from datetime import datetime
from typing import List, Optional

import genanki


def _anki_id(seed: str) -> int:
    return uuid.uuid5(uuid.NAMESPACE_OID, seed).int & 0x7FFFFFFF


class TimestampedNote(genanki.Note):
    def __init__(self, *args, updated_at: Optional[datetime] = None, **kwargs):
        self._note_timestamp = None
        if updated_at:
            if hasattr(updated_at, "timestamp"):
                self._note_timestamp = updated_at.timestamp()
            else:
                try:
                    self._note_timestamp = float(updated_at)
                except (TypeError, ValueError):
                    self._note_timestamp = None
        super().__init__(*args, **kwargs)

    def write_to_db(self, cursor, timestamp: float, deck_id, id_gen):
        effective_timestamp = (
            self._note_timestamp if self._note_timestamp is not None else timestamp
        )
        super().write_to_db(cursor, effective_timestamp, deck_id, id_gen)


def export_deck(deck: dict, cards: List[dict]) -> bytes:
    deck_identifier = _anki_id(f"deck-{deck['id']}")
    model_identifier = _anki_id(f"model-{deck['id']}")

    anki_deck = genanki.Deck(deck_identifier, f"{deck['name']} ({deck['target_language']})")
    model = genanki.Model(
        model_identifier,
        "Structured Two-Sided",
        fields=[
            {"name": "Front"},
            {"name": "Back"},
        ],
        templates=[
            {
                "name": "Card",
                "qfmt": "{{Front}}",
                "afmt": "{{Front}}<hr id='answer'>{{Back}}",
            }
        ],
    )

    media_files: List[str] = []
    written_files = {}

    with tempfile.TemporaryDirectory() as temp_dir:
        for card in cards:
            front_audio_tag = ""
            back_audio_tag = ""
            front_audio = card.get("front_audio")
            back_audio = card.get("back_audio")

            # Most cards only store audio on the back; move it to the front when the front
            # contains the foreign text (forward direction) so pronunciation plays immediately.
            if card.get("direction") == "forward" and not front_audio and back_audio:
                front_audio = back_audio
                back_audio = None

            if front_audio:
                filename = card.get("audio_filename") or f"{card['id']}_front.mp3"
                file_path = written_files.get(filename)
                if not file_path:
                    file_path = os.path.join(temp_dir, filename)
                    with open(file_path, "wb") as media_file:
                        media_file.write(front_audio)
                    media_files.append(file_path)
                    written_files[filename] = file_path
                front_audio_tag = f"<br>[sound:{filename}]"

            if back_audio:
                filename = card.get("audio_filename") or f"{card['id']}_back.mp3"
                file_path = written_files.get(filename)
                if not file_path:
                    file_path = os.path.join(temp_dir, filename)
                    with open(file_path, "wb") as media_file:
                        media_file.write(back_audio)
                    media_files.append(file_path)
                    written_files[filename] = file_path
                back_audio_tag = f"<br>[sound:{filename}]"

            note_guid = card["id"].replace("-", "")
            note = TimestampedNote(
                model=model,
                fields=[
                    f"{card['front']}{front_audio_tag}",
                    f"{card['back']}{back_audio_tag}",
                ],
                guid=note_guid,
                updated_at=card.get("updated_at"),
            )
            anki_deck.add_note(note)

        package = genanki.Package(anki_deck)
        package.media_files = media_files
        output_path = os.path.join(temp_dir, "deck.apkg")
        package.write_to_file(output_path)
        with open(output_path, "rb") as apkg:
            return apkg.read()
