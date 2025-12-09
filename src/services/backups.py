import io
import json
import zipfile
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from . import decks as deck_service
from . import cards as card_service

BACKUP_VERSION = 1
MANIFEST_FILENAME = "manifest.json"
MEDIA_PREFIX = "media"


def _serialize_timestamp(value: Optional[datetime]) -> Optional[str]:
    if not value:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def _parse_timestamp(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        if value.endswith("Z"):
            try:
                return datetime.fromisoformat(value[:-1] + "+00:00")
            except ValueError:
                return None
        return None


def _sanitize_deck(deck: dict) -> dict:
    return {
        "id": deck.get("id"),
        "name": deck.get("name"),
        "target_language": deck.get("target_language"),
        "field_schema": deck.get("field_schema"),
        "prompt_templates": deck.get("prompt_templates"),
        "created_at": _serialize_timestamp(deck.get("created_at")),
        "updated_at": _serialize_timestamp(deck.get("updated_at")),
    }


def _audio_path(card_id: str, side: str) -> str:
    return f"{MEDIA_PREFIX}/{card_id}_{side}.bin"


def create_backup_archive(deck: dict, cards: List[dict]) -> bytes:
    buffer = io.BytesIO()
    manifest = {
        "version": BACKUP_VERSION,
        "generated_at": datetime.utcnow().replace(tzinfo=timezone.utc).isoformat(),
        "deck": _sanitize_deck(deck),
        "cards": [],
    }
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for card in cards:
            card_id = str(card["id"])
            entry = {
                "id": card_id,
                "card_group_id": str(card["card_group_id"]),
                "direction": card["direction"],
                "payload": card["payload"],
                "audio_filename": card.get("audio_filename"),
                "created_at": _serialize_timestamp(card.get("created_at")),
                "updated_at": _serialize_timestamp(card.get("updated_at")),
                "front_audio_path": None,
                "back_audio_path": None,
            }
            front_audio = card.get("front_audio")
            if front_audio:
                path = _audio_path(card_id, "front")
                archive.writestr(path, front_audio)
                entry["front_audio_path"] = path
            back_audio = card.get("back_audio")
            if back_audio:
                path = _audio_path(card_id, "back")
                archive.writestr(path, back_audio)
                entry["back_audio_path"] = path
            manifest["cards"].append(entry)
        archive.writestr(MANIFEST_FILENAME, json.dumps(manifest, indent=2))
    buffer.seek(0)
    return buffer.getvalue()


def import_backup(owner_id: UUID, archive_bytes: bytes) -> dict:
    buffer = io.BytesIO(archive_bytes)
    with zipfile.ZipFile(buffer, mode="r") as archive:
        try:
            manifest_data = archive.read(MANIFEST_FILENAME)
        except KeyError as exc:
            raise ValueError("Invalid backup file.") from exc
        manifest = json.loads(manifest_data.decode("utf-8"))
        if manifest.get("version") != BACKUP_VERSION:
            raise ValueError("Unsupported backup version.")
        deck_info = manifest.get("deck") or {}
        cards_info = manifest.get("cards") or []
        name = deck_info.get("name")
        target_language = deck_info.get("target_language")
        if not name or not target_language:
            raise ValueError("Backup is missing deck metadata.")
        field_schema = deck_info.get("field_schema")
        prompt_templates = deck_info.get("prompt_templates")
        new_deck = deck_service.create_deck(
            owner_id=owner_id,
            name=name,
            target_language=target_language,
            field_schema=field_schema,
            prompt_templates=prompt_templates,
        )

        cards_payload = []
        for card in cards_info:
            front_audio = None
            back_audio = None
            front_path = card.get("front_audio_path")
            back_path = card.get("back_audio_path")
            if front_path:
                try:
                    front_audio = archive.read(front_path)
                except KeyError:
                    front_audio = None
            if back_path:
                try:
                    back_audio = archive.read(back_path)
                except KeyError:
                    back_audio = None
            cards_payload.append(
                {
                    "id": card.get("id"),
                    "card_group_id": card.get("card_group_id"),
                    "direction": card.get("direction"),
                    "payload": card.get("payload") or {},
                    "audio_filename": card.get("audio_filename"),
                    "created_at": _parse_timestamp(card.get("created_at")),
                    "updated_at": _parse_timestamp(card.get("updated_at")),
                    "front_audio": front_audio,
                    "back_audio": back_audio,
                }
            )

    if cards_payload:
        card_service.restore_cards(owner_id, new_deck["id"], cards_payload)
    return new_deck
