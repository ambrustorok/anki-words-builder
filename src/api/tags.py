import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..services import api_keys as api_key_service
from ..services import cards as card_service
from ..services import decks as deck_service
from ..services import generation as generation_service
from ..services import tags as tag_service
from .dependencies import get_current_user, parse_uuid

router = APIRouter(prefix="/tags")


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class TagCreateRequest(BaseModel):
    name: str
    category: str = ""
    color: str = "#6366f1"
    sort_order: int = 0


class TagUpdateRequest(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    color: Optional[str] = None
    sort_order: Optional[int] = None


class BulkTagCreateRequest(BaseModel):
    tags: List[TagCreateRequest]


class SetCardTagsRequest(BaseModel):
    tag_ids: List[str]


class TagModeRequest(BaseModel):
    mode: str  # 'off' | 'manual' | 'auto'


# ---------------------------------------------------------------------------
# Deck-tag definition routes
# ---------------------------------------------------------------------------


@router.get("/decks/{deck_id}/tags")
def list_deck_tags(deck_id: str, user=Depends(get_current_user)):
    deck_uuid = parse_uuid(deck_id, entity="Deck")
    deck = deck_service.get_deck(deck_uuid, user["id"])
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found.")
    tags = tag_service.list_deck_tags(deck_uuid)
    return {"tags": tags, "tag_mode": deck.get("tag_mode", "off")}


@router.post("/decks/{deck_id}/tags")
def create_deck_tag(
    deck_id: str, body: TagCreateRequest, user=Depends(get_current_user)
):
    deck_uuid = parse_uuid(deck_id, entity="Deck")
    if not deck_service.get_deck(deck_uuid, user["id"]):
        raise HTTPException(status_code=404, detail="Deck not found.")
    try:
        tag = tag_service.create_tag(
            deck_uuid,
            name=body.name,
            category=body.category,
            color=body.color,
            sort_order=body.sort_order,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return tag


@router.post("/decks/{deck_id}/tags/bulk")
def bulk_create_deck_tags(
    deck_id: str, body: BulkTagCreateRequest, user=Depends(get_current_user)
):
    deck_uuid = parse_uuid(deck_id, entity="Deck")
    if not deck_service.get_deck(deck_uuid, user["id"]):
        raise HTTPException(status_code=404, detail="Deck not found.")
    tags = [t.model_dump() for t in body.tags]
    created = tag_service.bulk_create_tags(deck_uuid, tags)
    return {"tags": created}


@router.get("/decks/{deck_id}/tags/presets")
def get_tag_presets(deck_id: str, user=Depends(get_current_user)):
    deck_uuid = parse_uuid(deck_id, entity="Deck")
    if not deck_service.get_deck(deck_uuid, user["id"]):
        raise HTTPException(status_code=404, detail="Deck not found.")
    return {"presets": tag_service.DEFAULT_TAG_PRESETS}


@router.put("/decks/{deck_id}/tag-mode")
def set_deck_tag_mode(
    deck_id: str, body: TagModeRequest, user=Depends(get_current_user)
):
    deck_uuid = parse_uuid(deck_id, entity="Deck")
    if not deck_service.get_deck(deck_uuid, user["id"]):
        raise HTTPException(status_code=404, detail="Deck not found.")
    mode = body.mode
    if mode not in ("off", "manual", "auto"):
        raise HTTPException(
            status_code=400, detail="tag_mode must be 'off', 'manual', or 'auto'."
        )
    deck_service.set_deck_tag_mode(deck_uuid, user["id"], mode)
    return {"tag_mode": mode}


@router.patch("/{tag_id}")
def update_tag(tag_id: str, body: TagUpdateRequest, user=Depends(get_current_user)):
    tag_uuid = parse_uuid(tag_id, entity="Tag")
    # Look up which deck owns this tag so we can verify ownership
    deck_id = _get_deck_id_for_tag(tag_uuid, user["id"])
    if not deck_id:
        raise HTTPException(status_code=404, detail="Tag not found.")
    updated = tag_service.update_tag(
        tag_uuid,
        deck_id,
        name=body.name,
        category=body.category,
        color=body.color,
        sort_order=body.sort_order,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Tag not found.")
    return updated


@router.delete("/{tag_id}")
def delete_tag(tag_id: str, user=Depends(get_current_user)):
    tag_uuid = parse_uuid(tag_id, entity="Tag")
    deck_id = _get_deck_id_for_tag(tag_uuid, user["id"])
    if not deck_id:
        raise HTTPException(status_code=404, detail="Tag not found.")
    deleted = tag_service.delete_tag(tag_uuid, deck_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Tag not found.")
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Card-group tag assignment routes
# ---------------------------------------------------------------------------


@router.get("/groups/{group_id}/tags")
def get_card_tags(group_id: str, user=Depends(get_current_user)):
    group_uuid = parse_uuid(group_id, entity="Card")
    tags = tag_service.get_card_group_tags(group_uuid)
    return {"tags": tags}


@router.put("/groups/{group_id}/tags")
def set_card_tags(
    group_id: str, body: SetCardTagsRequest, user=Depends(get_current_user)
):
    group_uuid = parse_uuid(group_id, entity="Card")
    tag_uuids = []
    for tid in body.tag_ids:
        try:
            tag_uuids.append(uuid.UUID(tid))
        except (ValueError, AttributeError):
            raise HTTPException(status_code=400, detail=f"Invalid tag id: {tid}")
    tags = tag_service.set_card_group_tags(group_uuid, tag_uuids)
    return {"tags": tags}


# ---------------------------------------------------------------------------
# Bulk AI tagging for an entire deck
# ---------------------------------------------------------------------------


@router.post("/decks/{deck_id}/bulk-tag")
def bulk_tag_deck(deck_id: str, user=Depends(get_current_user)):
    """
    AI-infer and assign tags to every card group in the deck that has no tags yet.
    Requires tag_mode == 'auto' and an OpenAI key.
    """
    deck_uuid = parse_uuid(deck_id, entity="Deck")
    deck = deck_service.get_deck(deck_uuid, user["id"])
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found.")
    if tag_service.get_deck_tag_mode(deck) != "auto":
        raise HTTPException(
            status_code=400, detail="Tag mode must be 'auto' to bulk-tag."
        )

    if not api_key_service.user_can_generate(user["id"]):
        raise HTTPException(
            status_code=400, detail="Add an OpenAI API key before using AI tagging."
        )

    client = api_key_service.get_openai_client_for_user(user["id"])
    available_tags = tag_service.list_deck_tags(deck_uuid)
    if not available_tags:
        raise HTTPException(
            status_code=400, detail="No tags defined for this deck yet."
        )

    BULK_TAG_CARD_LIMIT = 500

    # Get all card groups (raw payload, no rendering needed)
    from ..db.core import get_connection
    from psycopg2.extras import RealDictCursor

    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT DISTINCT ON (card_group_id)
                    card_group_id,
                    payload
                FROM cards
                WHERE owner_id = %s AND deck_id = %s
                ORDER BY card_group_id, created_at ASC
                LIMIT %s
                """,
                (str(user["id"]), str(deck_uuid), BULK_TAG_CARD_LIMIT),
            )
            groups = cur.fetchall()

    if len(groups) >= BULK_TAG_CARD_LIMIT:
        raise HTTPException(
            status_code=400,
            detail=f"Bulk tagging is limited to {BULK_TAG_CARD_LIMIT} cards per request. Split into smaller batches.",
        )

    processed = 0
    skipped = 0

    for group in groups:
        group_id = group["card_group_id"]
        payload = group["payload"] or {}
        suggested = generation_service.infer_tags(
            client,
            payload,
            deck["target_language"],
            available_tags,
        )
        if not suggested:
            skipped += 1
            continue
        # Map tag names → IDs
        name_to_id = {t["name"]: t["id"] for t in available_tags}
        tag_uuids = [
            uuid.UUID(str(name_to_id[n])) for n in suggested if n in name_to_id
        ]
        if tag_uuids:
            tag_service.set_card_group_tags(uuid.UUID(str(group_id)), tag_uuids)
            processed += 1
        else:
            skipped += 1

    return {"processed": processed, "skipped": skipped}


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _get_deck_id_for_tag(tag_id: uuid.UUID, owner_id) -> Optional[uuid.UUID]:
    """Verify the tag's deck is owned by this user. Returns deck_id or None."""
    from ..db.core import get_connection
    from psycopg2.extras import RealDictCursor

    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT dt.deck_id
                FROM deck_tags dt
                JOIN decks d ON d.id = dt.deck_id
                WHERE dt.id = %s AND d.owner_id = %s
                """,
                (str(tag_id), str(owner_id)),
            )
            row = cur.fetchone()
    if not row:
        return None
    return uuid.UUID(str(row["deck_id"]))
