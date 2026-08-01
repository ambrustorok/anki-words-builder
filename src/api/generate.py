import uuid
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from ..services import api_keys as api_key_service
from ..services import bulk_generation as bulk_gen
from ..services import cards as card_service
from ..services import decks as deck_service
from ..services import generation as generation_service
from ..services import tags as tag_service
from .dependencies import get_current_user, parse_uuid

router = APIRouter(prefix="/generate")

MAX_CARDS_PER_CELL = 10
MAX_CELLS = 30  # hard cap: exclusive_tag_count ≤ 30
MAX_TOTAL_CARDS = 50  # hard cap across all cells


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class PreviewRequest(BaseModel):
    deck_id: str = Field(..., alias="deckId")
    card_type: str = Field("word", alias="cardType")  # "word" | "sentence"
    description: Optional[str] = Field(None, max_length=500)
    # {category_name: [tag_id, ...]} — empty list = all tags in that category
    exclusive_constraints: Dict[str, List[str]] = Field(
        default_factory=dict, alias="exclusiveConstraints"
    )
    difficulties: List[str] = Field(default_factory=list)
    cards_per_cell: int = Field(2, ge=1, le=MAX_CARDS_PER_CELL, alias="cardsPerCell")
    directions: List[str] = Field(default_factory=lambda: ["forward", "backward"])

    @field_validator("card_type")
    @classmethod
    def _validate_card_type(cls, v: str) -> str:
        if v not in ("word", "sentence"):
            raise ValueError("cardType must be 'word' or 'sentence'.")
        return v

    @field_validator("difficulties")
    @classmethod
    def _validate_difficulties(cls, values: List[str]) -> List[str]:
        valid = {"A1", "A2", "B1", "B2", "C1", "C2"}
        if any(value not in valid for value in values):
            raise ValueError("difficulties must contain CEFR levels A1 through C2.")
        return list(dict.fromkeys(values))


class SaveCard(BaseModel):
    payload: Dict[str, str]
    tag_ids: List[str] = Field(default_factory=list, alias="tagIds")
    difficulty: Optional[str] = None


class SaveRequest(BaseModel):
    deck_id: str = Field(..., alias="deckId")
    directions: List[str] = Field(default_factory=lambda: ["forward", "backward"])
    cards: List[SaveCard]


# ---------------------------------------------------------------------------
# GET /generate/existing-phrases?deckId=...
# ---------------------------------------------------------------------------


@router.get("/existing-phrases")
def existing_phrases(deck_id: str, user=Depends(get_current_user)):
    deck_uuid = parse_uuid(deck_id, entity="Deck")
    deck = deck_service.get_deck(deck_uuid, user["id"])
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found.")
    phrases = bulk_gen.get_existing_phrases(user["id"], deck_uuid)
    return {"phrases": sorted(phrases)}


# ---------------------------------------------------------------------------
# POST /generate/preview
# ---------------------------------------------------------------------------


@router.post("/preview")
def preview(body: PreviewRequest, user=Depends(get_current_user)):
    deck_uuid = parse_uuid(body.deck_id, entity="Deck")
    deck = deck_service.get_deck(deck_uuid, user["id"])
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found.")

    if not api_key_service.user_can_generate(user["id"]):
        raise HTTPException(
            status_code=400,
            detail="Add an OpenAI API key on the Profile page before generating cards.",
        )

    client = api_key_service.get_openai_client_for_user(user["id"])
    model = user.get("text_model") or None
    target_language = deck["target_language"]
    native_language = user.get("native_language") or "English"
    available_tags = tag_service.list_deck_tags(deck_uuid)
    tag_by_id = {str(t["id"]): t for t in available_tags}

    # ---- Build constraint cells ----
    # Difficulty is one axis. A single topic/custom-tag category may supply the
    # other axis; each selected tag becomes one bundle in the Cartesian product.
    cells = _build_constraint_cells(
        body.difficulties, body.exclusive_constraints, tag_by_id
    )

    if len(cells) > MAX_CELLS:
        raise HTTPException(
            status_code=400,
            detail=f"Too many constraint combinations ({len(cells)}). Reduce selection to ≤{MAX_CELLS} cells.",
        )

    total_requested = len(cells) * body.cards_per_cell
    if total_requested > MAX_TOTAL_CARDS:
        raise HTTPException(
            status_code=400,
            detail=f"Requested {total_requested} cards but the limit is {MAX_TOTAL_CARDS}. Reduce cards per level or select fewer tags.",
        )

    # ---- Phase 1: generate raw candidates per cell ----
    existing_phrases = bulk_gen.get_existing_phrases(user["id"], deck_uuid)
    all_candidates: List[Dict] = []
    step_log: List[str] = []

    schema = deck.get("field_schema") or []

    for difficulty, cell_tags in cells:
        cell_label = (
            " + ".join(t["name"] for t in cell_tags) if cell_tags else "unconstrained"
        )
        if difficulty:
            cell_label = f"{difficulty} + {cell_label}"
        raw = bulk_gen.generate_cell(
            client,
            card_type=body.card_type,
            target_language=target_language,
            native_language=native_language,
            description=body.description,
            constraint_tags=cell_tags,
            difficulty=difficulty,
            count=body.cards_per_cell,
            field_schema=schema,
            model=model,
        )
        # Add ephemeral ID and cell metadata
        for item in raw:
            item["ephemeral_id"] = str(uuid.uuid4())
            item["cell_tags"] = cell_tags  # [{name, category, id}]
            item["difficulty"] = difficulty
        all_candidates.extend(raw)
        step_log.append(f"Generated {len(raw)} candidates for [{cell_label}]")

    # ---- Phase 2: dedup ----
    all_candidates = bulk_gen.dedup_candidates(all_candidates, existing_phrases)

    # ---- Phase 3: batch dictionary ----
    # Only enrich if field schema has dictionary_entry with auto_generate
    needs_dict = any(
        f.get("key") == "dictionary_entry" and f.get("auto_generate", True)
        for f in schema
    )
    if needs_dict and all_candidates:
        all_candidates = bulk_gen.batch_enrich_dictionary(
            client, all_candidates, target_language, model=model
        )
        step_log.append("Enriched dictionary entries")

    # ---- Phase 4: infer card difficulty, then topic tags ----
    missing_difficulty = [c for c in all_candidates if not c.get("difficulty")]
    if missing_difficulty:
        bulk_gen.batch_infer_difficulties(
            client, missing_difficulty, target_language, model=model
        )
        step_log.append("Inferred card difficulty")

    # Pre-fill constraint tags per phrase
    prefilled: Dict[str, List[str]] = {}
    for c in all_candidates:
        fp = c["foreign_phrase"]
        prefilled[fp] = [t["name"] for t in c.get("cell_tags", [])]

    if available_tags and all_candidates:
        all_candidates = bulk_gen.batch_infer_tags(
            client,
            all_candidates,
            target_language,
            available_tags,
            prefilled_tag_names=prefilled,
            model=model,
        )
        step_log.append("Inferred tags")

    # ---- Resolve tag names → IDs ----
    name_to_tag = {t["name"]: t for t in available_tags}
    for c in all_candidates:
        tag_names = c.get("suggested_tag_names", [])
        c["suggested_tag_ids"] = [
            str(name_to_tag[n]["id"]) for n in tag_names if n in name_to_tag
        ]
        c.pop("cell_tags", None)

    return {
        "candidates": all_candidates,
        "totalGenerated": len(all_candidates),
        "steps": step_log,
    }


# ---------------------------------------------------------------------------
# POST /generate/save
# ---------------------------------------------------------------------------


@router.post("/save")
def save(body: SaveRequest, user=Depends(get_current_user)):
    deck_uuid = parse_uuid(body.deck_id, entity="Deck")
    deck = deck_service.get_deck(deck_uuid, user["id"])
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found.")

    native_language = user.get("native_language") or "English"
    directions = [d for d in body.directions if d in ("forward", "backward")]
    if not directions:
        raise HTTPException(status_code=400, detail="Select at least one direction.")

    # Audio setup — generate for each accepted card at save time
    audio_allowed = deck_service.is_audio_enabled(deck)
    audio_client = None
    audio_instructions = deck_service.get_audio_instructions(deck) or ""
    audio_model = user.get("audio_model") or None
    if audio_allowed and api_key_service.user_can_generate(user["id"]):
        try:
            audio_client = api_key_service.get_openai_client_for_user(user["id"])
        except Exception:
            audio_allowed = False

    # Resolve foreign phrase key from field schema
    foreign_field_key = "foreign_phrase"
    for field in deck.get("field_schema") or []:
        if field.get("required"):
            foreign_field_key = field["key"]
            break

    saved = 0
    group_ids: List[str] = []

    for card in body.cards:
        try:
            payload = dict(card.payload)

            # Generate audio for this card's foreign phrase
            audio_bytes = None
            if audio_allowed and audio_client:
                phrase = payload.get(foreign_field_key, "").strip()
                if phrase:
                    try:
                        audio_bytes = generation_service.generate_audio_for_phrase(
                            audio_client,
                            phrase,
                            voice="random",
                            instructions=audio_instructions,
                            audio_model=audio_model,
                        )
                    except Exception:
                        pass  # non-critical

            group_id = card_service.create_cards(
                user["id"],
                deck,
                payload,
                directions,
                native_language,
                audio_bytes=audio_bytes,
                difficulty=card.difficulty,
            )
            group_ids.append(str(group_id))

            # Save tag assignments
            if card.tag_ids:
                valid_uuids = []
                for tid in card.tag_ids:
                    try:
                        valid_uuids.append(uuid.UUID(tid))
                    except ValueError:
                        pass
                if valid_uuids:
                    tag_service.set_card_group_tags(group_id, valid_uuids)
            saved += 1
        except Exception:
            pass  # skip invalid cards, save what we can

    return {"saved": saved, "groupIds": group_ids}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _build_constraint_cells(
    difficulties: List[str], constraints: Dict[str, List[str]], tag_by_id: Dict[str, dict]
) -> List[tuple[Optional[str], List[Dict]]]:
    selected_categories = []
    for category, tag_ids in constraints.items():
        tags = []
        for tag_id in tag_ids:
            tag = tag_by_id.get(tag_id)
            if tag:
                tags.append({"name": tag["name"], "category": tag.get("category", category), "id": tag_id})
        if tags:
            selected_categories.append(tags)
    if len(selected_categories) > 1:
        raise HTTPException(status_code=400, detail="Select tags from one category at a time when generating cards.")
    bundles = [[tag] for tag in selected_categories[0]] if selected_categories else [[]]
    return [(difficulty, bundle) for difficulty in (difficulties or [None]) for bundle in bundles]
