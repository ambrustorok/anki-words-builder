import os
import tempfile
import uuid
from typing import List

import genanki


def _anki_id(seed: str) -> int:
    return uuid.uuid5(uuid.NAMESPACE_OID, seed).int & 0x7FFFFFFF


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
            if card.get("front_audio"):
                filename = card.get("audio_filename") or f"{card['id']}_front.mp3"
                file_path = written_files.get(filename)
                if not file_path:
                    file_path = os.path.join(temp_dir, filename)
                    with open(file_path, "wb") as media_file:
                        media_file.write(card["front_audio"])
                    media_files.append(file_path)
                    written_files[filename] = file_path
                front_audio_tag = f"<br>[sound:{filename}]"

            if card.get("back_audio"):
                filename = card.get("audio_filename") or f"{card['id']}_back.mp3"
                file_path = written_files.get(filename)
                if not file_path:
                    file_path = os.path.join(temp_dir, filename)
                    with open(file_path, "wb") as media_file:
                        media_file.write(card["back_audio"])
                    media_files.append(file_path)
                    written_files[filename] = file_path
                back_audio_tag = f"<br>[sound:{filename}]"

            note = genanki.Note(
                model=model,
                fields=[
                    f"{card['front']}{front_audio_tag}",
                    f"{card['back']}{back_audio_tag}",
                ],
            )
            anki_deck.add_note(note)

        package = genanki.Package(anki_deck)
        package.media_files = media_files
        output_path = os.path.join(temp_dir, "deck.apkg")
        package.write_to_file(output_path)
        with open(output_path, "rb") as apkg:
            return apkg.read()
