import uuid
from typing import List, Optional

from psycopg2.extras import RealDictCursor

from ..db.core import get_connection


def _uuid(value) -> str:
    return str(value)


# ---------------------------------------------------------------------------
# Default tag presets offered to users as inspiration
# ---------------------------------------------------------------------------

DEFAULT_TAG_PRESETS = [
    {
        "category": "CEFR",
        "exclusive": True,
        "tags": [
            {"name": "A1", "color": "#86efac"},
            {"name": "A2", "color": "#4ade80"},
            {"name": "B1", "color": "#fde047"},
            {"name": "B2", "color": "#fb923c"},
            {"name": "C1", "color": "#f97316"},
            {"name": "C2", "color": "#ef4444"},
        ],
    },
    {
        "category": "Topic",
        "exclusive": False,
        "tags": [
            {"name": "politics", "color": "#a78bfa"},
            {"name": "free_time", "color": "#34d399"},
            {"name": "family", "color": "#f472b6"},
            {"name": "work", "color": "#60a5fa"},
            {"name": "travel", "color": "#fbbf24"},
            {"name": "food", "color": "#f87171"},
        ],
    },
]


# ---------------------------------------------------------------------------
# Tag definition CRUD (deck-scoped)
# ---------------------------------------------------------------------------


def list_deck_tags(deck_id: uuid.UUID) -> List[dict]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, deck_id, name, category, color, sort_order, category_exclusive, created_at
                FROM deck_tags
                WHERE deck_id = %s
                ORDER BY category, sort_order, name
                """,
                (_uuid(deck_id),),
            )
            rows = cur.fetchall()
    return [dict(row) for row in rows]


def create_tag(
    deck_id: uuid.UUID,
    *,
    name: str,
    category: str = "",
    color: str = "#6366f1",
    sort_order: int = 0,
    category_exclusive: bool = False,
) -> dict:
    tag_id = uuid.uuid4()
    safe_name = name.strip().replace(" ", "_")
    if not safe_name:
        raise ValueError("Tag name cannot be empty.")
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO deck_tags (id, deck_id, name, category, color, sort_order, category_exclusive)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (deck_id, name) DO NOTHING
                RETURNING id, deck_id, name, category, color, sort_order, category_exclusive, created_at
                """,
                (
                    _uuid(tag_id),
                    _uuid(deck_id),
                    safe_name,
                    category.strip(),
                    color.strip() or "#6366f1",
                    sort_order,
                    category_exclusive,
                ),
            )
            row = cur.fetchone()
        conn.commit()
    if not row:
        raise ValueError(f"Tag '{safe_name}' already exists in this deck.")
    return dict(row)


def bulk_create_tags(deck_id: uuid.UUID, tags: List[dict]) -> List[dict]:
    """Create multiple tags at once (used for preset seeding)."""
    created = []
    for tag in tags:
        try:
            result = create_tag(
                deck_id,
                name=tag.get("name", ""),
                category=tag.get("category", ""),
                color=tag.get("color", "#6366f1"),
                sort_order=tag.get("sort_order", 0),
                category_exclusive=bool(tag.get("category_exclusive", False)),
            )
            created.append(result)
        except ValueError:
            pass  # skip duplicates
    return created


def update_tag(
    tag_id: uuid.UUID,
    deck_id: uuid.UUID,
    *,
    name: Optional[str] = None,
    category: Optional[str] = None,
    color: Optional[str] = None,
    sort_order: Optional[int] = None,
    category_exclusive: Optional[bool] = None,
) -> Optional[dict]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT id FROM deck_tags WHERE id = %s AND deck_id = %s",
                (_uuid(tag_id), _uuid(deck_id)),
            )
            if not cur.fetchone():
                return None
            updates = []
            params = []
            if name is not None:
                safe_name = name.strip().replace(" ", "_")
                updates.append("name = %s")
                params.append(safe_name)
            if category is not None:
                updates.append("category = %s")
                params.append(category.strip())
            if color is not None:
                updates.append("color = %s")
                params.append(color.strip() or "#6366f1")
            if sort_order is not None:
                updates.append("sort_order = %s")
                params.append(sort_order)
            if category_exclusive is not None:
                updates.append("category_exclusive = %s")
                params.append(category_exclusive)
            if not updates:
                cur.execute(
                    "SELECT id, deck_id, name, category, color, sort_order, category_exclusive, created_at FROM deck_tags WHERE id = %s",
                    (_uuid(tag_id),),
                )
                return dict(cur.fetchone())
            params.append(_uuid(tag_id))
            cur.execute(
                f"UPDATE deck_tags SET {', '.join(updates)} WHERE id = %s RETURNING id, deck_id, name, category, color, sort_order, category_exclusive, created_at",
                params,
            )
            row = cur.fetchone()
        conn.commit()
    return dict(row) if row else None


def delete_tag(tag_id: uuid.UUID, deck_id: uuid.UUID) -> bool:
    with get_connection() as conn:
        with conn.cursor() as cur:
            # card_tags rows cascade-delete via FK
            cur.execute(
                "DELETE FROM deck_tags WHERE id = %s AND deck_id = %s",
                (_uuid(tag_id), _uuid(deck_id)),
            )
            deleted = cur.rowcount > 0
        conn.commit()
    return deleted


# ---------------------------------------------------------------------------
# Card-group tag assignment
# ---------------------------------------------------------------------------


def get_card_group_tags(card_group_id: uuid.UUID) -> List[dict]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT dt.id, dt.name, dt.category, dt.color, dt.sort_order, dt.category_exclusive
                FROM card_tags ct
                JOIN deck_tags dt ON dt.id = ct.tag_id
                WHERE ct.card_group_id = %s
                ORDER BY dt.category, dt.sort_order, dt.name
                """,
                (_uuid(card_group_id),),
            )
            rows = cur.fetchall()
    return [dict(row) for row in rows]


def set_card_group_tags(
    card_group_id: uuid.UUID, tag_ids: List[uuid.UUID]
) -> List[dict]:
    """Replace all tags for a card group (idempotent full replace)."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "DELETE FROM card_tags WHERE card_group_id = %s",
                (_uuid(card_group_id),),
            )
            if tag_ids:
                for tag_id in tag_ids:
                    cur.execute(
                        "INSERT INTO card_tags (card_group_id, tag_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                        (_uuid(card_group_id), _uuid(tag_id)),
                    )
            cur.execute(
                """
                SELECT dt.id, dt.name, dt.category, dt.color, dt.sort_order, dt.category_exclusive
                FROM card_tags ct
                JOIN deck_tags dt ON dt.id = ct.tag_id
                WHERE ct.card_group_id = %s
                ORDER BY dt.category, dt.sort_order, dt.name
                """,
                (_uuid(card_group_id),),
            )
            rows = cur.fetchall()
        conn.commit()
    return [dict(row) for row in rows]


def get_tags_for_card_groups(card_group_ids: List[str]) -> dict:
    """Batch-fetch tags for multiple card groups. Returns {group_id: [tags]}."""
    if not card_group_ids:
        return {}
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            placeholders = ",".join(["%s"] * len(card_group_ids))
            cur.execute(
                f"""
                 SELECT ct.card_group_id, dt.id, dt.name, dt.category, dt.color, dt.sort_order, dt.category_exclusive
                 FROM card_tags ct
                 JOIN deck_tags dt ON dt.id = ct.tag_id
                 WHERE ct.card_group_id IN ({placeholders})
                 ORDER BY dt.category, dt.sort_order, dt.name
                """,
                [str(gid) for gid in card_group_ids],
            )
            rows = cur.fetchall()
    result: dict = {str(gid): [] for gid in card_group_ids}
    for row in rows:
        gid = str(row["card_group_id"])
        result[gid].append(
            {
                "id": str(row["id"]),
                "name": row["name"],
                "category": row["category"],
                "color": row["color"],
                "sort_order": row["sort_order"],
                "category_exclusive": bool(row["category_exclusive"]),
            }
        )
    return result


def get_tag_names_for_export(card_group_id: uuid.UUID) -> List[str]:
    """Return just the tag name strings for Anki export."""
    tags = get_card_group_tags(card_group_id)
    return [t["name"] for t in tags]


# ---------------------------------------------------------------------------
# Tag mode on deck
# ---------------------------------------------------------------------------


def get_deck_tag_mode(deck: dict) -> str:
    """Returns 'off', 'manual', or 'auto'."""
    mode = deck.get("tag_mode") or "off"
    if mode not in ("off", "manual", "auto"):
        return "off"
    return mode
