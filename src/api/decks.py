import io
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, File, Form, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
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
    card_templates: Optional["CardTemplatesPayload"] = Field(None, alias="cardTemplates")


class CardFaceTemplate(BaseModel):
    front: Optional[str] = None
    back: Optional[str] = None


class CardTemplatesPayload(BaseModel):
    forward: Optional[CardFaceTemplate] = None
    backward: Optional[CardFaceTemplate] = None

    class Config:
        arbitrary_types_allowed = True


def _ensure_native_language(user: dict):
    if not user.get("native_language"):
        raise HTTPException(status_code=428, detail="Complete onboarding first.")


DeckPayload.model_rebuild()


def _card_templates_to_dict(payload: Optional[CardTemplatesPayload]) -> Optional[dict]:
    if not payload:
        return None
    data = payload.model_dump(exclude_none=True)
    return data or None


def _build_prompt_templates(generation_overrides: Optional[dict], card_overrides: Optional[dict]) -> Optional[dict]:
    if not generation_overrides and not card_overrides:
        return None
    templates = deck_service.default_prompt_templates()
    if generation_overrides:
        base_generation = templates.get("generation") or {}
        generation = {key: dict(value) for key, value in base_generation.items()}
        for key, value in generation_overrides.items():
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
    if card_overrides:
        for direction in ("forward", "backward"):
            override = card_overrides.get(direction)
            if not isinstance(override, dict):
                continue
            current = dict(templates.get(direction) or {})
            if "front" in override and override["front"] is not None:
                current["front"] = override["front"]
            if "back" in override and override["back"] is not None:
                current["back"] = override["back"]
            templates[direction] = current
    return templates


@router.get("/options")
def deck_options(user=Depends(get_current_user)):
    return {
        "fieldLibrary": deck_service.get_field_library(),
        "defaultFieldSchema": deck_service.default_field_schema(),
        "audioInstructionsTemplate": deck_service.default_audio_instructions_template(),
        "defaultCardTemplates": deck_service.default_card_templates(),
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
    generation_overrides = payload.generation_prompts
    card_overrides = _card_templates_to_dict(payload.card_templates)
    prompt_templates = _build_prompt_templates(generation_overrides, card_overrides)
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
    # Limit cards for summary view
    paginated = card_service.list_cards_for_deck_paginated(
        user["id"], deck, user.get("native_language"), page=1, limit=5
    )
    generation_prompts = deck_service.get_generation_prompts(deck)
    
    # We still want total metrics
    entry_count = paginated["total"]
    
    # Get total count of individual card faces
    card_count = card_service.count_cards_in_deck(user["id"], deck["id"])

    last_modified = deck.get("updated_at")
    # We can use the latest updated_at from the top 5 cards as a proxy if deeper validtion is needed, 
    # but the deck's updated_at should be sufficient if we maintain it properly.
    if paginated["cards"]:
        latest_card_update = max(c["updated_at"] for c in paginated["cards"])
        if not last_modified or (latest_card_update and latest_card_update > last_modified):
            last_modified = latest_card_update

    return {
        "deck": deck,
        "cards": paginated["cards"],
        "generationPrompts": generation_prompts,
        "entryCount": entry_count,
        "cardCount": card_count, 
        "lastModified": last_modified,
    }


@router.get("/{deck_id}/cards")
def list_deck_cards(
    deck_id: str, 
    page: int = 1, 
    limit: int = 50, 
    q: Optional[str] = None,
    user=Depends(get_current_user)
):
    deck_uuid = parse_uuid(deck_id, entity="Deck")
    deck = deck_service.get_deck(deck_uuid, user["id"])
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found.")
        
    result = card_service.list_cards_for_deck_paginated(
        user["id"], 
        deck, 
        user.get("native_language"), 
        page=page, 
        limit=limit, 
        search_query=q
    )
    return result


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
        card_templates=_card_templates_to_dict(payload.card_templates),
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
async def import_deck(
    file: UploadFile = File(...),
    policy: Optional[str] = Form(None),
    user=Depends(get_current_user),
):
    contents = await file.read()
    try:
        deck = backup_service.import_backup(user["id"], contents, policy=policy)
    except backup_service.DeckImportConflict as conflict:
        return JSONResponse(status_code=409, content=conflict.payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"deck": deck}
