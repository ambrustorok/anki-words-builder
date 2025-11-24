import io
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, File, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ..services import cards as card_service
from ..services import decks as deck_service
from ..services import exporter as export_service
from ..services import backups as backup_service
from ..settings import TARGET_LANGUAGE_OPTIONS
from .dependencies import get_current_user, parse_uuid

router = APIRouter(prefix="/decks")


class DeckField(BaseModel):
    key: str
    label: Optional[str] = None
    required: Optional[bool] = None
    description: Optional[str] = None
    auto_generate: Optional[bool] = Field(None, alias="autoGenerate")

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "label": self.label,
            "required": self.required,
            "description": self.description,
            "auto_generate": self.auto_generate,
        }

    class Config:
        allow_population_by_field_name = True


class DeckPayload(BaseModel):
    name: str
    target_language: str = Field(..., alias="targetLanguage")
    field_schema: Optional[List[DeckField]] = Field(None, alias="fieldSchema")
    audio_instructions: Optional[str] = Field(None, alias="audioInstructions")
    audio_enabled: Optional[bool] = Field(True, alias="audioEnabled")
    generation_prompts: Optional[dict] = Field(None, alias="generationPrompts")


def _ensure_native_language(user: dict):
    if not user.get("native_language"):
        raise HTTPException(status_code=428, detail="Complete onboarding first.")


def _build_prompt_templates(overrides: Optional[dict]) -> Optional[dict]:
    if not overrides:
        return None
    templates = deck_service.default_prompt_templates()
    base_generation = templates.get("generation") or {}
    generation = {key: dict(value) for key, value in base_generation.items()}
    for key, value in overrides.items():
        if not isinstance(value, dict):
            continue
        existing = generation.get(key, {})
        updated = dict(existing)
        if "system" in value:
            updated["system"] = value["system"]
        if "user" in value:
            updated["user"] = value["user"]
        generation[key] = updated
    templates["generation"] = generation
    return templates


@router.get("/options")
def deck_options(user=Depends(get_current_user)):
    return {
        "fieldLibrary": deck_service.get_field_library(),
        "defaultFieldSchema": deck_service.default_field_schema(),
        "audioInstructionsTemplate": deck_service.DEFAULT_AUDIO_INSTRUCTIONS_TEMPLATE,
        "defaultGenerationPrompts": deck_service.default_generation_prompts(),
        "targetLanguageOptions": TARGET_LANGUAGE_OPTIONS,
    }


@router.get("")
def list_decks(user=Depends(get_current_user)):
    decks = deck_service.list_decks(user["id"])
    return {"decks": decks}


@router.post("")
def create_deck(payload: DeckPayload, user=Depends(get_current_user)):
    _ensure_native_language(user)
    target_language = payload.target_language.strip()
    if target_language not in TARGET_LANGUAGE_OPTIONS:
        raise HTTPException(status_code=400, detail="Unsupported target language.")
    field_schema = None
    if payload.field_schema:
        field_schema = [field.to_dict() for field in payload.field_schema]
    prompt_templates = _build_prompt_templates(payload.generation_prompts)
    deck = deck_service.create_deck(
        owner_id=user["id"],
        name=payload.name.strip(),
        target_language=target_language,
        field_schema=field_schema,
        prompt_templates=prompt_templates,
        audio_instructions=payload.audio_instructions,
        audio_enabled=payload.audio_enabled,
    )
    return {"deck": deck}


@router.get("/{deck_id}")
def deck_detail(deck_id: str, user=Depends(get_current_user)):
    _ensure_native_language(user)
    deck_uuid = parse_uuid(deck_id, entity="Deck")
    deck = deck_service.get_deck(deck_uuid, user["id"])
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found.")
    cards = card_service.list_cards_for_deck(user["id"], deck, user.get("native_language"))
    generation_prompts = deck_service.get_generation_prompts(deck)
    entry_count = len(cards)
    card_count = sum(len(group.get("directions", [])) for group in cards)
    last_modified = deck.get("updated_at")
    for group in cards:
        group_updated = group.get("updated_at")
        if group_updated:
            if not last_modified or group_updated > last_modified:
                last_modified = group_updated
    return {
        "deck": deck,
        "cards": cards,
        "generationPrompts": generation_prompts,
        "entryCount": entry_count,
        "cardCount": card_count,
        "lastModified": last_modified,
    }


@router.put("/{deck_id}")
def update_deck(deck_id: str, payload: DeckPayload, user=Depends(get_current_user)):
    deck_uuid = parse_uuid(deck_id, entity="Deck")
    target_language = payload.target_language.strip()
    if target_language not in TARGET_LANGUAGE_OPTIONS:
        raise HTTPException(status_code=400, detail="Unsupported target language.")
    field_schema = None
    if payload.field_schema:
        field_schema = [field.to_dict() for field in payload.field_schema]
    updated = deck_service.update_deck(
        user["id"],
        deck_uuid,
        name=payload.name.strip(),
        target_language=target_language,
        field_schema=field_schema or deck_service.default_field_schema(),
        generation_prompts=payload.generation_prompts,
        audio_instructions=payload.audio_instructions,
        audio_enabled=payload.audio_enabled,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Deck not found.")
    return {"deck": updated}


@router.delete("/{deck_id}")
def delete_deck(deck_id: str, user=Depends(get_current_user)):
    deck_uuid = parse_uuid(deck_id, entity="Deck")
    deleted = deck_service.delete_deck(user["id"], deck_uuid)
    if not deleted:
        raise HTTPException(status_code=404, detail="Deck not found.")
    return {"status": "ok"}


@router.get("/{deck_id}/export")
def export_deck(deck_id: str, user=Depends(get_current_user)):
    deck_uuid = parse_uuid(deck_id, entity="Deck")
    deck = deck_service.get_deck(deck_uuid, user["id"])
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found.")

    cards = card_service.get_cards_for_export(
        user["id"],
        deck,
        user.get("native_language"),
    )
    if not cards:
        raise HTTPException(status_code=400, detail="No cards to export yet.")

    binary = export_service.export_deck(deck, cards)
    filename_slug = deck["name"].lower().replace(" ", "_")
    return StreamingResponse(
        io.BytesIO(binary),
        media_type="application/vnd.anki",
        headers={
            "Content-Disposition": f'attachment; filename="{filename_slug}.apkg"'
        },
    )


@router.get("/{deck_id}/backup")
def backup_deck(deck_id: str, user=Depends(get_current_user)):
    deck_uuid = parse_uuid(deck_id, entity="Deck")
    deck = deck_service.get_deck(deck_uuid, user["id"])
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found.")
    cards = card_service.get_cards_for_backup(user["id"], deck_uuid)
    archive = backup_service.create_backup_archive(deck, cards)
    filename_slug = deck["name"].lower().replace(" ", "_")
    return StreamingResponse(
        io.BytesIO(archive),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{filename_slug}.awdeck"'
        },
    )


@router.post("/import")
async def import_deck(file: UploadFile = File(...), user=Depends(get_current_user)):
    contents = await file.read()
    try:
        deck = backup_service.import_backup(user["id"], contents)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"deck": deck}
