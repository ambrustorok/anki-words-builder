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

    group_id = uuid.uuid4()
    audio_filename = f"{uuid.uuid4().hex}.mp3" if audio_bytes else None
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            for direction in valid_directions:
                card_id = uuid.uuid4()
                front_audio = None
                back_audio = audio_bytes if audio_bytes else None
                cur.execute(
                    """
                    INSERT INTO cards (
                        id, card_group_id, deck_id, owner_id, direction,
                        payload, front_audio, back_audio, audio_filename
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                    ),
                )
        conn.commit()

    return group_id


def list_recent_cards(
    owner_id: uuid.UUID, native_language: Optional[str], limit: int = 10
) -> List[dict]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT c.card_group_id,
                       c.id,
                       c.deck_id,
                       c.direction,
                       c.payload,
                       c.created_at,
                       d.name AS deck_name,
                       d.target_language,
                       d.prompt_templates,
                       d.field_schema
                FROM cards c
                JOIN decks d ON d.id = c.deck_id
                WHERE c.owner_id = %s
                ORDER BY c.created_at DESC
                LIMIT %s
                """,
                (_uuid(owner_id), limit),
            )
            rows = cur.fetchall()
    for row in rows:
        deck = {
            "id": row["deck_id"],
            "name": row["deck_name"],
            "target_language": row["target_language"],
            "prompt_templates": row["prompt_templates"],
            "field_schema": deck_service.normalize_field_schema(row.get("field_schema")),
        }
        faces = _render_card(deck, row["payload"], row["direction"], native_language)
        row["front"] = faces["front"]
        row["back"] = faces["back"]
    return rows


def list_cards_for_deck(
    owner_id: uuid.UUID, deck: dict, native_language: Optional[str]
) -> List[dict]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT c.card_group_id,
                       c.id,
                       c.direction,
                       c.payload,
                       c.created_at,
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
                "directions": [],
                "audio_card": None,
                "audio_side": None,
            },
        )
        faces = _render_card(deck, row["payload"], row["direction"], native_language)
        group["directions"].append(
            {
                "id": row["id"],
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
        key=lambda g: g["created_at"],
        reverse=True,
    )
    return ordered


def get_cards_for_export(
    owner_id: uuid.UUID, deck: dict, native_language: Optional[str]
) -> List[dict]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT c.id,
                       c.card_group_id,
                       c.direction,
                       c.payload,
                       c.created_at,
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
            }
        )
    return export_rows


def get_card_group(owner_id: uuid.UUID, group_id: uuid.UUID) -> Optional[dict]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT c.card_group_id,
                       c.id,
                       c.direction,
                       c.payload,
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
    for row in rows:
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
                    sql = f"UPDATE cards SET {', '.join(set_clauses)} WHERE id = %s"
                    params.append(row["id"])
                    cur.execute(sql, params)
                else:
                    card_id = uuid.uuid4()
                    back_audio = Binary(audio_bytes) if audio_bytes else None
                    audio_name = audio_filename if audio_bytes else None
                    cur.execute(
                        """
                        INSERT INTO cards (
                            id, card_group_id, deck_id, owner_id, direction,
                            payload, front_audio, back_audio, audio_filename
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
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
