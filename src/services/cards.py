import uuid
from typing import Dict, Iterable, List, Optional

from jinja2 import Template
from psycopg2 import Binary
from psycopg2.extras import Json, RealDictCursor

from ..db.core import get_connection
from . import decks as deck_service

LEGACY_PROMPT_TEMPLATES = {
    "forward": [
        {
            "front": "{{foreign_phrase}}",
            "back": "{{native_phrase}}\n{{dictionary_entry}}",
        },
        {
            "front": (
                "<div class='foreign'>{{foreign_phrase}}</div>"
                "<div class='native'>{{native_phrase}}</div>"
                "<div class='example'>{{example_sentence}}</div>"
                "<div class='dictionary'>{{dictionary_entry}}</div>"
            ),
            "back": "{{foreign_phrase}}",
        },
    ],
    "backward": [
        {
            "front": "{{native_phrase}}",
            "back": "{{foreign_phrase}}\n{{dictionary_entry}}",
        },
        {
            "front": "{{native_phrase}}",
            "back": (
                "<div class='foreign'>{{foreign_phrase}}</div>"
                "<div class='example'>{{example_sentence}}</div>"
                "<div class='dictionary'>{{dictionary_entry}}</div>"
            ),
        },
    ],
}


def _uuid(value: uuid.UUID) -> str:
    return str(value)


def _validate_payload(payload: dict, field_schema: List[dict]):
    missing = []
    for field in field_schema:
        if field.get("key") == "native_phrase":
            continue
        if field.get("required") and not payload.get(field["key"]):
            missing.append(field["label"])
    if missing:
        raise ValueError(f"Missing required fields: {', '.join(missing)}")


def _render_face(template_text: str, context: dict) -> str:
    tmpl = Template(template_text)
    return tmpl.render(**context).strip()


def _render_card(
    deck: dict, payload: dict, direction: str, native_language: Optional[str]
):
    default_templates = deck_service.default_prompt_templates()
    templates = deck.get("prompt_templates") or default_templates
    prompt = templates.get(direction) or default_templates.get(direction)
    legacy_candidates = LEGACY_PROMPT_TEMPLATES.get(direction, [])
    if any(prompt == candidate for candidate in legacy_candidates):
        prompt = default_templates.get(direction)
    context = {
        **payload,
        "direction": direction,
        "target_language": deck.get("target_language"),
        "native_language": native_language,
    }
    return {
        "front": _render_face(prompt["front"], context),
        "back": _render_face(prompt["back"], context),
    }


NAMESPACE_ANKI_CARDS = uuid.UUID("6b9a8963-8e7c-4054-94c6-2c9769341b52")

def get_deterministic_card_id(group_id: uuid.UUID, direction: str) -> uuid.UUID:
    """Generate a deterministic UUID based on group_id and direction."""
    return uuid.uuid5(NAMESPACE_ANKI_CARDS, f"{str(group_id)}-{direction}")

def create_cards(
    owner_id: uuid.UUID,
    deck: dict,
    payload: dict,
    directions: Iterable[str],
    native_language: Optional[str],
    audio_bytes: Optional[bytes] = None,
) -> uuid.UUID:
    _validate_payload(payload, deck.get("field_schema", []))
    valid_directions = [d for d in directions if d in ("forward", "backward")]
    if not valid_directions:
        raise ValueError("Select at least one direction to generate cards.")

    # Deterministic ID based on deck_id and foreign_phrase
    foreign_phrase = payload.get("foreign_phrase")
    if not foreign_phrase:
         # Should have been caught by validation, but fallback
         group_id = uuid.uuid4()
    else:
         # deck_id is in deck dict, assume it's UUID object or string?
         # deck["id"] usually comes from DB, check type.
         # In other functions _uuid() is used, implying it's UUID.
         # But safely handle it.
         d_id = deck["id"]
         if isinstance(d_id, str):
             d_id = uuid.UUID(d_id)
         group_id = uuid.uuid5(d_id, foreign_phrase.strip())

    audio_filename = f"{uuid.uuid4().hex}.mp3" if audio_bytes else None
    
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Stable Anki ID: Generate random for new card
                card_anki_id = uuid.uuid4()
                
                cur.execute(
                    """
                    INSERT INTO cards (
                        id, card_group_id, deck_id, owner_id, direction,
                        payload, front_audio, back_audio, audio_filename, updated_at, anki_id
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), %s)
                    ON CONFLICT (id) DO UPDATE SET
                         payload = EXCLUDED.payload,
                         front_audio = COALESCE(EXCLUDED.front_audio, cards.front_audio),
                         back_audio = COALESCE(EXCLUDED.back_audio, cards.back_audio),
                         audio_filename = COALESCE(EXCLUDED.audio_filename, cards.audio_filename),
                         updated_at = NOW(),
                         anki_id = COALESCE(cards.anki_id, EXCLUDED.anki_id)
                    """,
                    (
                        _uuid(card_id),
                        _uuid(group_id),
                        _uuid(deck["id"]),
                        _uuid(owner_id),
                        direction,
                        Json(payload),
                        Binary(front_audio) if front_audio else None,
                        Binary(back_audio) if back_audio else None,
                        audio_filename,
                        _uuid(card_anki_id),
                    ),
                )
        conn.commit()

    return group_id


def list_recent_cards(
    owner_id: uuid.UUID, native_language: Optional[str], limit: int = 10
) -> List[dict]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # 1. Fetch recent distinct group IDs
            cur.execute(
                """
                SELECT card_group_id, MAX(updated_at) as max_updated
                FROM cards
                WHERE owner_id = %s
                GROUP BY card_group_id
                ORDER BY max_updated DESC
                LIMIT %s
                """,
                (_uuid(owner_id), limit),
            )
            group_rows = cur.fetchall()
            
            if not group_rows:
                return []
            
            group_ids = [row["card_group_id"] for row in group_rows]
            placeholders = ",".join(["%s"] * len(group_ids))
            
            # 2. Fetch full details for these groups
            cur.execute(
                f"""
                SELECT c.card_group_id,
                       c.id,
                       c.anki_id,
                       c.deck_id,
                       c.direction,
                       c.payload,
                       c.created_at,
                       c.updated_at,
                       c.front_audio IS NOT NULL AS has_front_audio,
                       c.back_audio IS NOT NULL AS has_back_audio,
                       d.name AS deck_name,
                       d.target_language,
                       d.prompt_templates,
                       d.field_schema
                FROM cards c
                JOIN decks d ON d.id = c.deck_id
                WHERE c.owner_id = %s AND c.card_group_id IN ({placeholders})
                ORDER BY c.card_group_id, c.direction
                """,
                (_uuid(owner_id), *[_uuid(gid) for gid in group_ids]),
            )
            rows = cur.fetchall()

    grouped: Dict[str, dict] = {}
    for row in rows:
        group_id = row["card_group_id"]
        group = grouped.setdefault(
            group_id,
            {
                "group_id": group_id,
                "deck_id": row["deck_id"],
                "deck_name": row["deck_name"],
                "target_language": row["target_language"],
                "payload": row["payload"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "directions": [],
                "audio_card": None,
                "audio_side": None,
                "prompt_templates": row["prompt_templates"],
                "field_schema": deck_service.normalize_field_schema(row.get("field_schema")),
            },
        )
        group["created_at"] = min(group["created_at"], row["created_at"])
        group["updated_at"] = max(group["updated_at"], row["updated_at"])
        
        deck_info = {
            "target_language": row["target_language"],
            "prompt_templates": row["prompt_templates"],
            "field_schema": row["field_schema"],
        }
        faces = _render_card(deck_info, row["payload"], row["direction"], native_language)
        
        group["directions"].append(
            {
                "id": row["id"],
                "anki_id": row["anki_id"],
                "direction": row["direction"],
                "front": faces["front"],
                "back": faces["back"],
                "has_front_audio": row["has_front_audio"],
                "has_back_audio": row["has_back_audio"],
            }
        )
        if row["has_front_audio"] and not group["audio_card"]:
            group["audio_card"] = row["id"]
            group["audio_side"] = "front"
        elif row["has_back_audio"] and not group["audio_card"]:
            group["audio_card"] = row["id"]
            group["audio_side"] = "back"
            
    # Sort by the order we got from the first query (timestamp)
    ordered_groups = []
    group_map = {g["group_id"]: g for g in grouped.values()}
    for grid in group_ids:
        if grid in group_map:
            ordered_groups.append(group_map[grid])
            
    return ordered_groups


def list_cards_for_deck(
    owner_id: uuid.UUID, deck: dict, native_language: Optional[str]
) -> List[dict]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT c.card_group_id,
                       c.id,
                       c.anki_id,
                       c.direction,
                       c.payload,
                       c.created_at,
                       c.updated_at,
                       c.front_audio IS NOT NULL AS has_front_audio,
                       c.back_audio IS NOT NULL AS has_back_audio
                FROM cards c
                WHERE c.owner_id = %s AND c.deck_id = %s
                ORDER BY c.card_group_id, c.direction
                """,
                (_uuid(owner_id), _uuid(deck["id"])),
            )
            rows = cur.fetchall()

    grouped: Dict[str, dict] = {}
    for row in rows:
        group_id = row["card_group_id"]
        group = grouped.setdefault(
            group_id,
            {
                "group_id": group_id,
                "payload": row["payload"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "directions": [],
                "audio_card": None,
                "audio_side": None,
            },
        )
        group["created_at"] = min(group["created_at"], row["created_at"])
        group["updated_at"] = max(group["updated_at"], row["updated_at"])
        faces = _render_card(deck, row["payload"], row["direction"], native_language)
        group["directions"].append(
            {
                "id": row["id"],
                "anki_id": row["anki_id"],
                "direction": row["direction"],
                "front": faces["front"],
                "back": faces["back"],
                "has_front_audio": row["has_front_audio"],
                "has_back_audio": row["has_back_audio"],
            }
        )
        if row["has_front_audio"] and not group["audio_card"]:
            group["audio_card"] = row["id"]
            group["audio_side"] = "front"
        elif row["has_back_audio"] and not group["audio_card"]:
            group["audio_card"] = row["id"]
            group["audio_side"] = "back"
    ordered = sorted(
        grouped.values(),
        key=lambda g: g["updated_at"],
        reverse=True,
    )
    return ordered


def list_cards_for_deck_paginated(
    owner_id: uuid.UUID,
    deck: dict,
    native_language: Optional[str],
    page: int = 1,
    limit: int = 50,
    search_query: Optional[str] = None,
) -> dict:
    offset = (page - 1) * limit
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # 1. Get paginated group IDs
            query_params = [_uuid(owner_id), _uuid(deck["id"])]
            search_clause = ""
            if search_query:
                search_clause = "AND payload::text ILIKE %s"
                query_params.append(f"%{search_query}%")

            count_sql = f"""
                SELECT COUNT(DISTINCT card_group_id) as total
                FROM cards
                WHERE owner_id = %s AND deck_id = %s {search_clause}
            """
            cur.execute(count_sql, tuple(query_params))
            total_groups = cur.fetchone()["total"]

            groups_sql = f"""
                SELECT card_group_id, MAX(updated_at) as max_updated
                FROM cards
                WHERE owner_id = %s AND deck_id = %s {search_clause}
                GROUP BY card_group_id
                ORDER BY max_updated DESC
                LIMIT %s OFFSET %s
            """
            cur.execute(groups_sql, tuple(query_params + [limit, offset]))
            group_rows = cur.fetchall()
            
            if not group_rows:
                return {
                    "cards": [],
                    "total": 0,
                    "page": page,
                    "limit": limit,
                    "pages": 0
                }

            group_ids = [row["card_group_id"] for row in group_rows]
            
            # 2. Fetch cards for these groups
            placeholders = ",".join(["%s"] * len(group_ids))
            cards_sql = f"""
                SELECT c.card_group_id,
                       c.id,
                       c.anki_id,
                       c.direction,
                       c.payload,
                       c.created_at,
                       c.updated_at,
                       c.front_audio IS NOT NULL AS has_front_audio,
                       c.back_audio IS NOT NULL AS has_back_audio
                FROM cards c
                WHERE c.owner_id = %s 
                  AND c.card_group_id IN ({placeholders})
                ORDER BY c.card_group_id, c.direction
            """
            cur.execute(cards_sql, (_uuid(owner_id), *[_uuid(gid) for gid in group_ids]))
            rows = cur.fetchall()

    # Reuse the grouping logic
    grouped: Dict[str, dict] = {}
    for row in rows:
        group_id = row["card_group_id"]
        group = grouped.setdefault(
            group_id,
            {
                "group_id": group_id,
                "payload": row["payload"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "directions": [],
                "audio_card": None,
                "audio_side": None,
            },
        )
        group["created_at"] = min(group["created_at"], row["created_at"])
        group["updated_at"] = max(group["updated_at"], row["updated_at"])
        faces = _render_card(deck, row["payload"], row["direction"], native_language)
        group["directions"].append(
            {
                "id": row["id"],
                "anki_id": row["anki_id"],
                "direction": row["direction"],
                "front": faces["front"],
                "back": faces["back"],
                "has_front_audio": row["has_front_audio"],
                "has_back_audio": row["has_back_audio"],
            }
        )
        if row["has_front_audio"] and not group["audio_card"]:
            group["audio_card"] = row["id"]
            group["audio_side"] = "front"
        elif row["has_back_audio"] and not group["audio_card"]:
            group["audio_card"] = row["id"]
            group["audio_side"] = "back"
            
    # Sort by the order we got from the pagination query
    ordered_groups = []
    group_map = {g["group_id"]: g for g in grouped.values()}
    for grid in group_ids:
        if grid in group_map:
            ordered_groups.append(group_map[grid])

    import math
    return {
        "cards": ordered_groups,
        "total": total_groups,
        "page": page,
        "limit": limit,
        "pages": math.ceil(total_groups / limit) if limit > 0 else 1
    }


def get_cards_for_export(
    owner_id: uuid.UUID, deck: dict, native_language: Optional[str]
) -> List[dict]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT c.id,
                       c.anki_id,
                       c.card_group_id,
                       c.direction,
                       c.payload,
                       c.created_at,
                       c.updated_at,
                       c.front_audio,
                       c.back_audio,
                       c.audio_filename
                FROM cards c
                WHERE c.owner_id = %s AND c.deck_id = %s
                ORDER BY c.created_at ASC
                """,
                (_uuid(owner_id), _uuid(deck["id"])),
            )
            rows = cur.fetchall()

    export_rows = []
    for row in rows:
        faces = _render_card(deck, row["payload"], row["direction"], native_language)
        export_rows.append(
            {
                **row,
                "front": faces["front"],
                "back": faces["back"],
                "front_audio": bytes(row["front_audio"]) if row["front_audio"] else None,
                "back_audio": bytes(row["back_audio"]) if row["back_audio"] else None,
                "audio_filename": row.get("audio_filename"),
                "updated_at": row.get("updated_at"),
            }
        )
    return export_rows


def get_cards_for_backup(owner_id: uuid.UUID, deck_id: uuid.UUID) -> List[dict]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT c.id,
                       c.anki_id,
                       c.card_group_id,
                       c.direction,
                       c.payload,
                       c.created_at,
                       c.updated_at,
                       c.front_audio,
                       c.back_audio,
                       c.audio_filename
                FROM cards c
                WHERE c.owner_id = %s AND c.deck_id = %s
                ORDER BY c.created_at ASC
                """,
                (_uuid(owner_id), _uuid(deck_id)),
            )
            rows = cur.fetchall()
    cards = []
    for row in rows:
        cards.append(
            {
                "id": row["id"],
                "anki_id": row["anki_id"],
                "card_group_id": row["card_group_id"],
                "direction": row["direction"],
                "payload": row["payload"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "front_audio": bytes(row["front_audio"]) if row["front_audio"] else None,
                "back_audio": bytes(row["back_audio"]) if row["back_audio"] else None,
                "audio_filename": row.get("audio_filename"),
            }
        )
    return cards


def get_card_group(owner_id: uuid.UUID, group_id: uuid.UUID) -> Optional[dict]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT c.card_group_id,
                       c.id,
                       c.anki_id,
                       c.direction,
                       c.payload,
                       c.created_at,
                       c.updated_at,
                       c.deck_id,
                       c.audio_filename,
                       c.front_audio,
                       c.back_audio,
                       d.name AS deck_name,
                       d.target_language,
                       d.field_schema,
                       d.prompt_templates
                FROM cards c
                JOIN decks d ON d.id = c.deck_id
                WHERE c.owner_id = %s AND c.card_group_id = %s
                """,
                (_uuid(owner_id), _uuid(group_id)),
            )
            rows = cur.fetchall()

    if not rows:
        return None

    deck = {
        "id": rows[0]["deck_id"],
        "name": rows[0]["deck_name"],
        "target_language": rows[0]["target_language"],
        "field_schema": deck_service.normalize_field_schema(rows[0]["field_schema"]),
        "prompt_templates": rows[0]["prompt_templates"],
    }
    payload = rows[0]["payload"]
    audio_bytes = None
    created_at = rows[0]["created_at"]
    updated_at = rows[0]["updated_at"]
    for row in rows:
        created_at = min(created_at, row["created_at"])
        updated_at = max(updated_at, row["updated_at"])
        if row["front_audio"]:
            audio_bytes = bytes(row["front_audio"])
            break
        if row["back_audio"]:
            audio_bytes = bytes(row["back_audio"])
            break

    return {
        "group_id": rows[0]["card_group_id"],
        "rows": rows,
        "deck": deck,
        "payload": payload,
        "audio": audio_bytes,
        "audio_filename": rows[0]["audio_filename"],
        "created_at": created_at,
        "updated_at": updated_at,
    }


def update_card_group(
    owner_id: uuid.UUID,
    group_id: uuid.UUID,
    deck: dict,
    payload: dict,
    directions: List[str],
    audio_bytes: Optional[bytes],
) -> bool:
    valid_directions = [d for d in directions if d in ("forward", "backward")]
    if not valid_directions:
        raise ValueError("Select at least one direction to keep.")

    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, direction
                FROM cards
                WHERE owner_id = %s AND card_group_id = %s
                """,
                (_uuid(owner_id), _uuid(group_id)),
            )
            rows = cur.fetchall()
            if not rows:
                return False

            existing = {row["direction"]: row for row in rows}
            audio_filename = f"{uuid.uuid4().hex}.mp3" if audio_bytes else None

            # Upsert desired directions
            for direction in valid_directions:
                row = existing.get(direction)
                if row:
                    params = [Json(payload)]
                    set_clauses = ["payload = %s"]
                    if audio_bytes is not None:
                        set_clauses.extend(
                            ["front_audio = %s", "back_audio = %s", "audio_filename = %s"]
                        )
                        params.extend(
                            [
                                None,
                                Binary(audio_bytes),
                                audio_filename,
                            ]
                        )
                    set_clauses.append("updated_at = NOW()")
                    sql = f"UPDATE cards SET {', '.join(set_clauses)} WHERE id = %s"
                    params.append(row["id"])
                    cur.execute(sql, params)
                else:
                    card_id = get_deterministic_card_id(group_id, direction)
                    card_anki_id = uuid.uuid4()
                    back_audio = Binary(audio_bytes) if audio_bytes else None
                    audio_name = audio_filename if audio_bytes else None
                    cur.execute(
                        """
                        INSERT INTO cards (
                            id, card_group_id, deck_id, owner_id, direction,
                            payload, front_audio, back_audio, audio_filename, anki_id
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            _uuid(card_id),
                            _uuid(group_id),
                            _uuid(deck["id"]),
                            _uuid(owner_id),
                            direction,
                            Json(payload),
                            None,
                            back_audio,
                            audio_name,
                            _uuid(card_anki_id),
                        ),
                    )

            # Remove directions that are no longer selected
            for direction, row in existing.items():
                if direction not in valid_directions:
                    cur.execute("DELETE FROM cards WHERE id = %s", (row["id"],))
        conn.commit()
    return True


def delete_card_group(owner_id: uuid.UUID, group_id: uuid.UUID) -> bool:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM cards WHERE owner_id = %s AND card_group_id = %s",
                (_uuid(owner_id), _uuid(group_id)),
            )
            deleted = cur.rowcount > 0
        conn.commit()
    return deleted


def get_card_audio(owner_id: uuid.UUID, card_id: uuid.UUID, side: str) -> Optional[bytes]:
    column = "front_audio" if side == "front" else "back_audio"
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT {column} FROM cards WHERE owner_id = %s AND id = %s",
                (_uuid(owner_id), _uuid(card_id)),
            )
            row = cur.fetchone()
            if not row or not row[0]:
                return None
            return bytes(row[0])


def restore_cards(
    owner_id: uuid.UUID, 
    deck_id: uuid.UUID, 
    cards: List[dict], 
    merge_strategy: str = "overwrite"
) -> int:
    if not cards:
        return 0
    group_map: Dict[str, uuid.UUID] = {}
    inserted = 0
    
    # Validation
    if merge_strategy not in ("overwrite", "newest"):
        merge_strategy = "overwrite"

    with get_connection() as conn:
        with conn.cursor() as cur:
            for card in cards:
                direction = card.get("direction")
                if direction not in ("forward", "backward"):
                    continue
                original_group = card.get("card_group_id")
                if original_group:
                    target_group = uuid.UUID(str(original_group))
                    group_key = str(original_group)
                else:
                    target_group = uuid.uuid4()
                    group_key = str(target_group)

                mapped_group = group_map.setdefault(group_key, target_group)
                new_card_id = get_deterministic_card_id(mapped_group, direction)
                
                anki_id = card.get("anki_id")
                if anki_id:
                    new_anki_id = uuid.UUID(str(anki_id))
                else:
                     new_anki_id = uuid.uuid4()

                payload = card.get("payload") or {}
                created_at = card.get("created_at")
                updated_at = card.get("updated_at") or created_at
                front_audio = card.get("front_audio")
                back_audio = card.get("back_audio")
                
                # Build SQL based on strategy
                update_condition = ""
                if merge_strategy == "newest":
                    # Only update if the excluded (new) updated_at is OLDER (greater) than existing?
                    # No, Newest wins means: If Incoming.updated_at > Existing.updated_at, then Update.
                    update_condition = "WHERE EXCLUDED.updated_at > cards.updated_at"
                    
                cur.execute(
                    f"""
                    INSERT INTO cards (
                        id,
                        card_group_id,
                        deck_id,
                        owner_id,
                        direction,
                        payload,
                        front_audio,
                        back_audio,
                        audio_filename,
                        created_at,
                        updated_at,
                        anki_id
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        card_group_id = EXCLUDED.card_group_id,
                        deck_id = EXCLUDED.deck_id,
                        owner_id = EXCLUDED.owner_id,
                        direction = EXCLUDED.direction,
                        payload = EXCLUDED.payload,
                        front_audio = COALESCE(EXCLUDED.front_audio, cards.front_audio),
                        back_audio = COALESCE(EXCLUDED.back_audio, cards.back_audio),
                        audio_filename = EXCLUDED.audio_filename,
                        created_at = EXCLUDED.created_at,
                        updated_at = EXCLUDED.updated_at,
                        anki_id = COALESCE(cards.anki_id, EXCLUDED.anki_id)
                    {update_condition}
                    """,
                    (
                        _uuid(new_card_id),
                        _uuid(mapped_group),
                        _uuid(deck_id),
                        _uuid(owner_id),
                        direction,
                        Json(payload),
                        Binary(front_audio) if front_audio else None,
                        Binary(back_audio) if back_audio else None,
                        card.get("audio_filename"),
                        created_at,
                        updated_at,
                        _uuid(new_anki_id),
                    ),
                )
                inserted += 1
        conn.commit()

    return inserted


def count_cards_in_deck(owner_id: uuid.UUID, deck_id: uuid.UUID) -> int:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM cards WHERE owner_id = %s AND deck_id = %s",
                (_uuid(owner_id), _uuid(deck_id)),
            )
            count = cur.fetchone()[0]
    return count
