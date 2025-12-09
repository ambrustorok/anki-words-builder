import io
import json
import uuid
import zipfile
from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional, Set
from uuid import UUID

from . import cards as card_service
from . import decks as deck_service

BACKUP_VERSION = 2
SUPPORTED_BACKUP_VERSIONS: Set[int] = {1, 2}
MANIFEST_FILENAME = "manifest.json"
MEDIA_PREFIX = "media"


class DeckImportPolicy(str, Enum):
    OVERRIDE = "override"
    PREFER_NEWEST = "prefer_newest"
    ONLY_NEW = "only_new"


class DeckImportConflict(Exception):
    def __init__(self, payload: dict):
        super().__init__(payload.get("message") or "Deck import conflict.")
        self.payload = payload


def _coerce_policy(value: Optional[str]) -> Optional[DeckImportPolicy]:
    if value is None:
        return None
    try:
        return DeckImportPolicy(value)
    except ValueError as exc:
        raise ValueError("Unsupported import policy.") from exc


def _conflict_payload(
    existing: dict,
    incoming: dict,
    deck_anki_id: Optional[uuid.UUID],
    incoming_entry_count: int,
    incoming_card_count: int,
) -> dict:
    return {
        "code": "DECK_IMPORT_CONFLICT",
        "message": (
            "A deck with the same Anki ID already exists. Choose how to handle the import."
        ),
        "existingDeck": {
            "id": str(existing.get("id")),
            "name": existing.get("name"),
            "updated_at": _serialize_timestamp(existing.get("updated_at")),
            "anki_id": str(existing.get("anki_id")) if existing.get("anki_id") else None,
        },
        "incomingDeck": {
            "name": incoming.get("name"),
            "anki_id": str(deck_anki_id) if deck_anki_id else None,
            "updated_at": incoming.get("updated_at"),
            "entry_count": incoming_entry_count,
            "card_count": incoming_card_count,
        },
        "options": [
            {
                "policy": DeckImportPolicy.OVERRIDE.value,
                "label": "Override existing deck",
                "description": "Replace the entire deck with the imported backup.",
            },
            {
                "policy": DeckImportPolicy.PREFER_NEWEST.value,
                "label": "Accept newest per entry",
                "description": "Keep whichever version of each entry has the latest update.",
            },
            {
                "policy": DeckImportPolicy.ONLY_NEW.value,
                "label": "Import new entries only",
                "description": "Only add entries that do not exist yet.",
            },
        ],
    }


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


def _entry_anki_uuid(card: dict) -> uuid.UUID:
    candidate = card.get("entry_anki_id") or card.get("card_group_id") or card.get("id")
    try:
        return uuid.UUID(str(candidate))
    except (ValueError, TypeError, AttributeError):
        seed = str(card.get("id") or uuid.uuid4())
        return uuid.uuid5(uuid.NAMESPACE_URL, f"backup-entry-{seed}")


def _sanitize_deck(deck: dict) -> dict:
    return {
        "id": deck.get("id"),
        "anki_id": str(deck.get("anki_id")) if deck.get("anki_id") else None,
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
            entry_uuid = _entry_anki_uuid(card)
            entry = {
                "id": card_id,
                "card_group_id": str(card["card_group_id"]),
                "entry_anki_id": str(entry_uuid),
                "anki_card_id": card_service.stable_card_guid(entry_uuid, card["direction"]),
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


def import_backup(owner_id: UUID, archive_bytes: bytes, policy: Optional[str] = None) -> dict:
    selected_policy = _coerce_policy(policy)
    buffer = io.BytesIO(archive_bytes)
    with zipfile.ZipFile(buffer, mode="r") as archive:
        try:
            manifest_data = archive.read(MANIFEST_FILENAME)
        except KeyError as exc:
            raise ValueError("Invalid backup file.") from exc
        manifest = json.loads(manifest_data.decode("utf-8"))
        version = manifest.get("version") or 1
        if version not in SUPPORTED_BACKUP_VERSIONS:
            raise ValueError("Unsupported backup version.")
        deck_info = manifest.get("deck") or {}
        cards_info = manifest.get("cards") or []
        name = deck_info.get("name")
        target_language = deck_info.get("target_language")
        if not name or not target_language:
            raise ValueError("Backup is missing deck metadata.")
        field_schema = deck_info.get("field_schema")
        prompt_templates = deck_info.get("prompt_templates")
        deck_anki_uuid = None
        deck_anki_id = deck_info.get("anki_id")
        if deck_anki_id:
            try:
                deck_anki_uuid = uuid.UUID(str(deck_anki_id))
            except (ValueError, TypeError) as exc:
                raise ValueError("Invalid Anki deck identifier in backup.") from exc
        cards_payload = []
        entry_ids = set()
        for card in cards_info:
            direction = card.get("direction")
            if direction not in ("forward", "backward"):
                continue
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
            entry_uuid = _entry_anki_uuid(card)
            entry_ids.add(str(entry_uuid))
            cards_payload.append(
                {
                    "card_group_id": card.get("card_group_id"),
                    "entry_anki_id": str(entry_uuid),
                    "direction": direction,
                    "payload": card.get("payload") or {},
                    "audio_filename": card.get("audio_filename"),
                    "created_at": _parse_timestamp(card.get("created_at")),
                    "updated_at": _parse_timestamp(card.get("updated_at")),
                    "front_audio": front_audio,
                    "back_audio": back_audio,
                }
            )

    incoming_entry_count = len(entry_ids)
    incoming_card_count = len(cards_payload)
    existing_deck = None
    if deck_anki_uuid:
        existing_deck = deck_service.get_deck_by_anki_id(owner_id, deck_anki_uuid)

    if existing_deck:
        if selected_policy is None:
            payload = _conflict_payload(
                existing_deck,
                deck_info,
                deck_anki_uuid,
                incoming_entry_count,
                incoming_card_count,
            )
            raise DeckImportConflict(payload)
        deck_id = existing_deck["id"]
        if selected_policy in (DeckImportPolicy.OVERRIDE, DeckImportPolicy.PREFER_NEWEST):
            deck_service.apply_backup_metadata(
                owner_id,
                deck_id,
                name=name,
                target_language=target_language,
                field_schema=field_schema,
                prompt_templates=prompt_templates,
            )
        mode = {
            DeckImportPolicy.OVERRIDE: "replace",
            DeckImportPolicy.PREFER_NEWEST: "prefer_newest",
            DeckImportPolicy.ONLY_NEW: "only_new",
        }[selected_policy]
        card_service.restore_cards_with_policy(owner_id, deck_id, cards_payload, mode=mode)
        return deck_service.get_deck(deck_id, owner_id)

    created_deck = deck_service.create_deck(
        owner_id=owner_id,
        name=name,
        target_language=target_language,
        field_schema=field_schema,
        prompt_templates=prompt_templates,
        anki_id=deck_anki_uuid,
    )
    card_service.restore_cards_with_policy(owner_id, created_deck["id"], cards_payload, mode="replace")
    return created_deck
