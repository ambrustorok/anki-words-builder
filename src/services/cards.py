import io
import re
import sqlite3
import tempfile
import uuid
import zipfile
from datetime import datetime
from typing import Dict, Iterable, List, Optional, Tuple

from jinja2 import Template
from psycopg2 import Binary
from psycopg2.extras import Json, RealDictCursor

from ..db.core import get_connection
from . import decks as deck_service
from . import tags as tag_service

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

DIFFICULTY_LEVELS = ("A1", "A2", "B1", "B2", "C1", "C2")


CARD_GUID_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_DNS, "anki-words-builder/card")
ANKI_SOUND_TAG = re.compile(r"(?:<br\s*/?>)?\s*\[sound:[^\]]+\]", re.IGNORECASE)


def _attach_tags_to_groups(groups: List[dict]) -> List[dict]:
    """Batch-fetch tags for a list of card groups and attach them in-place."""
    if not groups:
        return groups
    group_ids = [g["group_id"] for g in groups]
    tags_by_group = tag_service.get_tags_for_card_groups(group_ids)
    for group in groups:
        group["tags"] = tags_by_group.get(str(group["group_id"]), [])
    return groups


def _uuid(value: uuid.UUID) -> str:
    return str(value)


def generate_entry_anki_id() -> uuid.UUID:
    return uuid.uuid4()


def stable_card_uuid(entry_anki_id: uuid.UUID, direction: str) -> uuid.UUID:
    normalized_direction = (
        direction if direction in ("forward", "backward") else "forward"
    )
    try:
        entry_uuid = uuid.UUID(str(entry_anki_id))
    except (TypeError, ValueError, AttributeError):
        entry_uuid = uuid.uuid4()
    seed = f"{entry_uuid}:{normalized_direction}"
    return uuid.uuid5(CARD_GUID_NAMESPACE, seed)


def stable_card_guid(entry_anki_id: uuid.UUID, direction: str) -> str:
    return stable_card_uuid(entry_anki_id, direction).hex


def strip_anki_sound_tags(face: str) -> str:
    return ANKI_SOUND_TAG.sub("", face).rstrip()


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
    difficulty: Optional[str] = None,
) -> uuid.UUID:
    _validate_payload(payload, deck.get("field_schema", []))
    valid_directions = [d for d in directions if d in ("forward", "backward")]
    if not valid_directions:
        raise ValueError("Select at least one direction to generate cards.")
    if difficulty is not None and difficulty not in DIFFICULTY_LEVELS:
        raise ValueError("Unsupported card difficulty.")

    group_id = uuid.uuid4()
    entry_anki_id = generate_entry_anki_id()
    audio_filename = f"{uuid.uuid4().hex}.mp3" if audio_bytes else None
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            for direction in valid_directions:
                card_id = uuid.uuid4()
                card_anki_id = stable_card_uuid(entry_anki_id, direction)
                front_audio = None
                back_audio = audio_bytes if audio_bytes else None
                cur.execute(
                    """
                    INSERT INTO cards (
                        id, card_group_id, entry_anki_id, deck_id, owner_id, direction,
                        payload, front_audio, back_audio, audio_filename, anki_id, difficulty
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        _uuid(card_id),
                        _uuid(group_id),
                        _uuid(entry_anki_id),
                        _uuid(deck["id"]),
                        _uuid(owner_id),
                        direction,
                        Json(payload),
                        Binary(front_audio) if front_audio else None,
                        Binary(back_audio) if back_audio else None,
                        audio_filename,
                        _uuid(card_anki_id),
                        difficulty,
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
                       c.deck_id,
                       c.direction,
                       c.payload,
                       c.difficulty,
                       c.anki_front_override,
                       c.anki_back_override,
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
                "difficulty": row.get("difficulty"),
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "directions": [],
                "audio_card": None,
                "audio_side": None,
                "prompt_templates": row["prompt_templates"],
                "field_schema": deck_service.normalize_field_schema(
                    row.get("field_schema")
                ),
            },
        )
        group["created_at"] = min(group["created_at"], row["created_at"])
        group["updated_at"] = max(group["updated_at"], row["updated_at"])

        deck_info = {
            "target_language": row["target_language"],
            "prompt_templates": row["prompt_templates"],
            "field_schema": row["field_schema"],
        }
        faces = _render_card(
            deck_info, row["payload"], row["direction"], native_language
        )
        faces["front"] = row.get("anki_front_override") or faces["front"]
        faces["back"] = row.get("anki_back_override") or faces["back"]

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

    # Sort by the order we got from the first query (timestamp)
    ordered_groups = []
    group_map = {g["group_id"]: g for g in grouped.values()}
    for grid in group_ids:
        if grid in group_map:
            ordered_groups.append(group_map[grid])

    return _attach_tags_to_groups(ordered_groups)


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
                       c.difficulty,
                       c.anki_front_override,
                       c.anki_back_override,
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
                "difficulty": row.get("difficulty"),
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
        faces["front"] = row.get("anki_front_override") or faces["front"]
        faces["back"] = row.get("anki_back_override") or faces["back"]
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
        key=lambda g: g["updated_at"],
        reverse=True,
    )
    return _attach_tags_to_groups(list(ordered))


def list_cards_for_deck_paginated(
    owner_id: uuid.UUID,
    deck: dict,
    native_language: Optional[str],
    page: int = 1,
    limit: int = 50,
    search_query: Optional[str] = None,
    tag_names: Optional[List[str]] = None,
    difficulties: Optional[List[str]] = None,
) -> dict:
    offset = (page - 1) * limit
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # 1. Get paginated group IDs
            query_params: list = [_uuid(owner_id), _uuid(deck["id"])]
            search_clause = ""
            tag_clause = ""
            difficulty_clause = ""

            if search_query:
                search_clause = "AND payload::text ILIKE %s"
                query_params.append(f"%{search_query}%")

            if tag_names:
                # Only include groups that have ALL the requested tags
                placeholders = ",".join(["%s"] * len(tag_names))
                tag_clause = f"""
                    AND card_group_id IN (
                        SELECT ct.card_group_id
                        FROM card_tags ct
                        JOIN deck_tags dt ON dt.id = ct.tag_id
                        WHERE dt.deck_id = %s AND dt.name IN ({placeholders})
                        GROUP BY ct.card_group_id
                        HAVING COUNT(DISTINCT dt.name) = %s
                    )
                """
                query_params.append(_uuid(deck["id"]))
                query_params.extend(tag_names)
                query_params.append(len(tag_names))

            if difficulties:
                valid = [level for level in difficulties if level in DIFFICULTY_LEVELS]
                if valid:
                    placeholders = ",".join(["%s"] * len(valid))
                    difficulty_clause = f"AND difficulty IN ({placeholders})"
                    query_params.extend(valid)

            count_sql = f"""
                SELECT COUNT(DISTINCT card_group_id) as total
                FROM cards
                WHERE owner_id = %s AND deck_id = %s {search_clause} {tag_clause} {difficulty_clause}
            """
            cur.execute(count_sql, tuple(query_params))
            total_groups = cur.fetchone()["total"]

            groups_sql = f"""
                SELECT card_group_id, MAX(updated_at) as max_updated
                FROM cards
                WHERE owner_id = %s AND deck_id = %s {search_clause} {tag_clause} {difficulty_clause}
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
                    "pages": 0,
                }

            group_ids = [row["card_group_id"] for row in group_rows]

            # 2. Fetch cards for these groups
            placeholders = ",".join(["%s"] * len(group_ids))
            cards_sql = f"""
                SELECT c.card_group_id,
                       c.id,
                       c.direction,
                       c.payload,
                       c.difficulty,
                       c.anki_front_override,
                       c.anki_back_override,
                       c.created_at,
                       c.updated_at,
                       c.front_audio IS NOT NULL AS has_front_audio,
                       c.back_audio IS NOT NULL AS has_back_audio
                FROM cards c
                WHERE c.owner_id = %s 
                  AND c.card_group_id IN ({placeholders})
                ORDER BY c.card_group_id, c.direction
            """
            cur.execute(
                cards_sql, (_uuid(owner_id), *[_uuid(gid) for gid in group_ids])
            )
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
                "difficulty": row.get("difficulty"),
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
        faces["front"] = row.get("anki_front_override") or faces["front"]
        faces["back"] = row.get("anki_back_override") or faces["back"]
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

    # Sort by the order we got from the pagination query
    ordered_groups = []
    group_map = {g["group_id"]: g for g in grouped.values()}
    for grid in group_ids:
        if grid in group_map:
            ordered_groups.append(group_map[grid])

    ordered_groups = _attach_tags_to_groups(ordered_groups)

    import math

    return {
        "cards": ordered_groups,
        "total": total_groups,
        "page": page,
        "limit": limit,
        "pages": math.ceil(total_groups / limit) if limit > 0 else 1,
    }


def get_cards_for_export(
    owner_id: uuid.UUID,
    deck: dict,
    native_language: Optional[str],
    *,
    since: Optional[datetime] = None,
) -> List[dict]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            where_since = ""
            params: List[object] = [_uuid(owner_id), _uuid(deck["id"])]
            if since is not None:
                where_since = " AND c.updated_at > %s "
                params.append(since)

            cur.execute(
                f"""
                SELECT c.id,
                       c.card_group_id,
                       c.entry_anki_id,
                       c.direction,
                       c.payload,
                       c.difficulty,
                       c.created_at,
                       c.updated_at,
                       c.anki_due,
                       c.anki_front_override,
                       c.anki_back_override,
                       c.anki_front_exported,
                       c.anki_back_exported,
                       c.front_audio,
                       c.back_audio,
                       c.audio_filename
                FROM cards c
                WHERE c.owner_id = %s AND c.deck_id = %s
                {where_since}
                ORDER BY c.created_at ASC
                """,
                tuple(params),
            )
            rows = cur.fetchall()

    export_rows = []
    for row in rows:
        faces = _render_card(deck, row["payload"], row["direction"], native_language)
        export_rows.append(
            {
                **row,
                "entry_anki_id": row.get("entry_anki_id"),
                "front": faces["front"],
                "back": faces["back"],
                "anki_due": row.get("anki_due"),
                "difficulty": row.get("difficulty"),
                "anki_front_override": row.get("anki_front_override"),
                "anki_back_override": row.get("anki_back_override"),
                "anki_front_exported": row.get("anki_front_exported"),
                "anki_back_exported": row.get("anki_back_exported"),
                "front_audio": bytes(row["front_audio"])
                if row["front_audio"]
                else None,
                "back_audio": bytes(row["back_audio"]) if row["back_audio"] else None,
                "audio_filename": row.get("audio_filename"),
                "updated_at": row.get("updated_at"),
            }
        )
    return export_rows


def record_anki_export_faces(owner_id: uuid.UUID, cards: List[dict]) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            for card in cards:
                cur.execute(
                    """
                    UPDATE cards
                    SET anki_front_exported = %s, anki_back_exported = %s
                    WHERE id = %s AND owner_id = %s
                    """,
                    (
                        card.get("_anki_front_exported"),
                        card.get("_anki_back_exported"),
                        _uuid(card["id"]),
                        _uuid(owner_id),
                    ),
                )
        conn.commit()


def import_anki_package(owner_id: uuid.UUID, cards: List[dict], package: bytes) -> dict:
    """Apply Anki note edits and scheduling state to known exported cards."""
    by_guid = {
        stable_card_guid(
            uuid.UUID(str(card["entry_anki_id"])), card.get("direction") or "forward"
        ): card
        for card in cards
        if card.get("entry_anki_id")
    }
    try:
        with zipfile.ZipFile(io.BytesIO(package)) as archive:
            collection_name = next(
                name for name in archive.namelist() if name in {"collection.anki2", "collection.anki21"}
            )
            collection = archive.read(collection_name)
    except (KeyError, StopIteration, zipfile.BadZipFile) as exc:
        raise ValueError("Upload a valid Anki .apkg file.") from exc

    with tempfile.NamedTemporaryFile() as database:
        database.write(collection)
        database.flush()
        with sqlite3.connect(database.name) as conn:
            rows = conn.execute(
                """
                SELECT n.guid, n.flds, n.mod,
                       c.type, c.queue, c.due, c.ivl, c.factor, c.reps, c.lapses,
                       c.left, c.odue, c.odid
                FROM notes n JOIN cards c ON c.nid = n.id
                """
            ).fetchall()

    matched = 0
    changed = 0
    with get_connection() as conn:
        with conn.cursor() as cur:
            for row in rows:
                card = by_guid.get(row[0])
                fields = row[1].split("\x1f")
                if not card or len(fields) < 2:
                    continue
                matched += 1
                front, back = fields[:2]
                faces_changed = (
                    card.get("anki_front_exported") is None
                    or card.get("anki_back_exported") is None
                    or front != card.get("anki_front_exported")
                    or back != card.get("anki_back_exported")
                )
                scheduling = {
                    "modified_at": row[2],
                    "type": row[3],
                    "queue": row[4],
                    "due": row[5],
                    "interval": row[6],
                    "ease_factor": row[7],
                    "repetitions": row[8],
                    "lapses": row[9],
                    "left": row[10],
                    "original_due": row[11],
                    "original_deck_id": row[12],
                }
                cur.execute(
                    """
                    UPDATE cards
                    SET anki_front_override = CASE WHEN %s THEN %s ELSE anki_front_override END,
                        anki_back_override = CASE WHEN %s THEN %s ELSE anki_back_override END,
                        anki_scheduling = %s,
                        updated_at = CASE WHEN %s THEN NOW() ELSE updated_at END
                    WHERE id = %s AND owner_id = %s
                    """,
                    (
                        faces_changed,
                        strip_anki_sound_tags(front),
                        faces_changed,
                        strip_anki_sound_tags(back),
                        Json(scheduling),
                        faces_changed,
                        _uuid(card["id"]),
                        _uuid(owner_id),
                    ),
                )
                changed += int(faces_changed)
        conn.commit()
    return {"matched": matched, "changed": changed}


def assign_anki_due_for_export(
    *,
    owner_id: uuid.UUID,
    deck_id: uuid.UUID,
    cards: List[dict],
) -> None:
    """Assign stable Anki `due` positions for cards that haven't been exported before.

    Dues are bucketed by the card's CEFR difficulty.
    Bucket bases are: A1=0.., A2=10000.., ..., C2=50000.. (each bucket size=10000).
    """

    # Fast path: nothing to assign.
    missing = [c for c in cards if c.get("anki_due") is None]
    if not missing:
        return

    DUE_BUCKET_SIZE = 10_000

    def _bucket_id(card: dict) -> int:
        try:
            return DIFFICULTY_LEVELS.index(card.get("difficulty"))
        except ValueError:
            return len(DIFFICULTY_LEVELS)  # unknown difficulty bucket after C2

    bucket_existing_counts: dict[int, int] = {}
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT (anki_due / %s) AS bucket, COUNT(*)::int AS cnt
                FROM cards
                WHERE owner_id = %s AND deck_id = %s AND anki_due IS NOT NULL
                GROUP BY bucket
                """,
                (DUE_BUCKET_SIZE, _uuid(owner_id), _uuid(deck_id)),
            )
            for row in cur.fetchall():
                bucket_existing_counts[int(row["bucket"]) ] = int(row["cnt"])

        # Assign and persist dues in a second step to keep a single connection lifecycle.
        with conn.cursor() as cur:
            to_update = []
            # Group missing cards by bucket.
            new_by_bucket: dict[int, List[dict]] = {}
            for card in missing:
                b = _bucket_id(card)
                new_by_bucket.setdefault(b, []).append(card)

            import hashlib

            for bucket_id, new_cards in new_by_bucket.items():
                # Randomize within the bucket, but deterministically so new cards don't reshuffle existing ones.
                new_cards_sorted = sorted(
                    new_cards,
                    key=lambda c: int.from_bytes(
                        hashlib.sha256(
                            f"{c.get('id')}:{c.get('direction')}".encode("utf-8")
                        ).digest()[:8],
                        "big",
                    ),
                )
                next_offset = bucket_existing_counts.get(bucket_id, 0)
                for i, card in enumerate(new_cards_sorted):
                    due = bucket_id * DUE_BUCKET_SIZE + (next_offset + i)
                    to_update.append((due, _uuid(card["id"]), _uuid(owner_id)))
                    card["anki_due"] = due

            for due, card_id, o in to_update:
                cur.execute(
                    "UPDATE cards SET anki_due = %s WHERE id = %s AND owner_id = %s",
                    (due, card_id, o),
                )
        conn.commit()


def get_cards_for_backup(owner_id: uuid.UUID, deck_id: uuid.UUID) -> List[dict]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT c.id,
                       c.card_group_id,
                       c.entry_anki_id,
                       c.direction,
                       c.payload,
                       c.difficulty,
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
                "card_group_id": row["card_group_id"],
                "entry_anki_id": row.get("entry_anki_id"),
                "direction": row["direction"],
                "payload": row["payload"],
                "difficulty": row.get("difficulty"),
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "front_audio": bytes(row["front_audio"])
                if row["front_audio"]
                else None,
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
                       c.direction,
                       c.payload,
                       c.difficulty,
                       c.created_at,
                       c.updated_at,
                       c.deck_id,
                       c.audio_filename,
                       c.front_audio,
                       c.back_audio,
                       c.anki_front_override,
                       c.anki_back_override,
                       c.anki_scheduling,
                       d.name AS deck_name,
                       d.target_language,
                       d.field_schema,
                       d.prompt_templates,
                       d.tag_mode
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
        "tag_mode": rows[0].get("tag_mode", "off"),
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
        "difficulty": rows[0].get("difficulty"),
        "audio": audio_bytes,
        "audio_filename": rows[0]["audio_filename"],
        "anki_front_override": rows[0].get("anki_front_override"),
        "anki_back_override": rows[0].get("anki_back_override"),
        "anki_scheduling": rows[0].get("anki_scheduling"),
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
    difficulty: Optional[str] = None,
) -> bool:
    valid_directions = [d for d in directions if d in ("forward", "backward")]
    if not valid_directions:
        raise ValueError("Select at least one direction to keep.")
    if difficulty is not None and difficulty not in DIFFICULTY_LEVELS:
        raise ValueError("Unsupported card difficulty.")

    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, direction, entry_anki_id
                FROM cards
                WHERE owner_id = %s AND card_group_id = %s
                """,
                (_uuid(owner_id), _uuid(group_id)),
            )
            rows = cur.fetchall()
            if not rows:
                return False

            existing = {row["direction"]: row for row in rows}
            entry_anki_id = rows[0].get("entry_anki_id") or generate_entry_anki_id()
            audio_filename = f"{uuid.uuid4().hex}.mp3" if audio_bytes else None

            # Upsert desired directions
            for direction in valid_directions:
                row = existing.get(direction)
                if row:
                    params = [Json(payload), difficulty]
                    set_clauses = ["payload = %s", "difficulty = %s"]
                    if audio_bytes is not None:
                        set_clauses.extend(
                            [
                                "front_audio = %s",
                                "back_audio = %s",
                                "audio_filename = %s",
                            ]
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
                    card_id = uuid.uuid4()
                    card_anki_id = stable_card_uuid(entry_anki_id, direction)
                    back_audio = Binary(audio_bytes) if audio_bytes else None
                    audio_name = audio_filename if audio_bytes else None
                    cur.execute(
                        """
                        INSERT INTO cards (
                            id, card_group_id, entry_anki_id, deck_id, owner_id, direction,
                            payload, front_audio, back_audio, audio_filename, anki_id, difficulty
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            _uuid(card_id),
                            _uuid(group_id),
                            _uuid(entry_anki_id),
                            _uuid(deck["id"]),
                            _uuid(owner_id),
                            direction,
                            Json(payload),
                            None,
                            back_audio,
                            audio_name,
                            _uuid(card_anki_id),
                            difficulty,
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


def get_card_audio(
    owner_id: uuid.UUID, card_id: uuid.UUID, side: str
) -> Optional[bytes]:
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


def restore_cards_with_policy(
    owner_id: uuid.UUID,
    deck_id: uuid.UUID,
    cards: List[dict],
    *,
    mode: str = "replace",
) -> int:
    """
    mode options:
      - replace: delete all current cards for the deck before inserting
      - prefer_newest: compare by entry+direction timestamps and keep the newest version
      - only_new: only insert entries that do not already exist
    """
    normalized_entries = _group_restore_payload(cards)
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            if mode == "replace":
                cur.execute(
                    "DELETE FROM cards WHERE owner_id = %s AND deck_id = %s",
                    (_uuid(owner_id), _uuid(deck_id)),
                )
                existing_entries: Dict[str, dict] = {}
            else:
                existing_entries = _load_existing_entries(cur, owner_id, deck_id)
            inserted = 0
            for entry in normalized_entries:
                inserted += _apply_entry_restore(
                    cur,
                    owner_id,
                    deck_id,
                    entry,
                    mode,
                    existing_entries,
                )
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


def _group_restore_payload(cards: List[dict]) -> List[dict]:
    grouped: Dict[str, dict] = {}
    for card in cards:
        direction = card.get("direction")
        if direction not in ("forward", "backward"):
            continue
        entry_id = (
            card.get("entry_anki_id")
            or card.get("card_group_id")
            or card.get("id")
            or uuid.uuid4()
        )
        entry_key = str(entry_id)
        bucket = grouped.setdefault(
            entry_key,
            {"entry_anki_id": entry_key, "cards": {}},
        )
        normalized_card = {
            "direction": direction,
            "payload": card.get("payload") or {},
            "difficulty": card.get("difficulty"),
            "created_at": card.get("created_at"),
            "updated_at": card.get("updated_at") or card.get("created_at"),
            "front_audio": card.get("front_audio"),
            "back_audio": card.get("back_audio"),
            "audio_filename": card.get("audio_filename"),
        }
        bucket["cards"][direction] = normalized_card
    return list(grouped.values())


def _load_existing_entries(
    cur, owner_id: uuid.UUID, deck_id: uuid.UUID
) -> Dict[str, dict]:
    cur.execute(
        """
        SELECT id,
               card_group_id,
               entry_anki_id,
               direction,
               updated_at
        FROM cards
        WHERE owner_id = %s AND deck_id = %s
        """,
        (_uuid(owner_id), _uuid(deck_id)),
    )
    rows = cur.fetchall()
    entries: Dict[str, dict] = {}
    for row in rows:
        entry_id = row["entry_anki_id"] or row["card_group_id"]
        entry_key = str(entry_id)
        entry = entries.setdefault(
            entry_key,
            {"group_id": row["card_group_id"], "cards": {}},
        )
        entry["cards"][row["direction"]] = {
            "id": row["id"],
            "updated_at": row["updated_at"],
        }
    return entries


def _apply_entry_restore(
    cur,
    owner_id: uuid.UUID,
    deck_id: uuid.UUID,
    entry: dict,
    mode: str,
    existing_entries: Dict[str, dict],
) -> int:
    entry_anki_id = entry.get("entry_anki_id")
    entry_uuid = _safe_uuid(entry_anki_id)
    entry_key = str(entry_uuid)
    existing = existing_entries.get(entry_key)

    if mode == "only_new" and existing:
        return 0

    if mode == "prefer_newest" and existing:
        return _merge_entry(
            cur, owner_id, deck_id, entry_uuid, existing, entry["cards"]
        )

    group_id = existing["group_id"] if existing else uuid.uuid4()
    if existing and mode != "replace":
        cur.execute(
            "DELETE FROM cards WHERE owner_id = %s AND deck_id = %s AND card_group_id = %s",
            (_uuid(owner_id), _uuid(deck_id), _uuid(existing["group_id"])),
        )
    inserted, inserted_cards = _insert_entry_cards(
        cur,
        owner_id,
        deck_id,
        group_id,
        entry_uuid,
        entry["cards"],
    )
    existing_entries[entry_key] = {
        "group_id": group_id,
        "cards": inserted_cards,
    }
    return inserted


def _merge_entry(
    cur,
    owner_id: uuid.UUID,
    deck_id: uuid.UUID,
    entry_uuid: uuid.UUID,
    existing_entry: dict,
    incoming_cards: Dict[str, dict],
) -> int:
    inserted = 0
    for direction, card in incoming_cards.items():
        existing_card = existing_entry["cards"].get(direction)
        if not existing_card:
            new_card_id = _insert_entry_card(
                cur,
                owner_id,
                deck_id,
                existing_entry["group_id"],
                entry_uuid,
                card,
            )
            existing_entry["cards"][direction] = {
                "id": new_card_id,
                "updated_at": card.get("updated_at"),
            }
            inserted += 1
            continue
        incoming_updated = card.get("updated_at")
        existing_updated = existing_card.get("updated_at")
        if incoming_updated and (
            not existing_updated or incoming_updated > existing_updated
        ):
            cur.execute(
                "DELETE FROM cards WHERE id = %s", (_uuid(existing_card["id"]),)
            )
            new_card_id = _insert_entry_card(
                cur,
                owner_id,
                deck_id,
                existing_entry["group_id"],
                entry_uuid,
                card,
            )
            existing_entry["cards"][direction] = {
                "id": new_card_id,
                "updated_at": card.get("updated_at"),
            }
            inserted += 1
    return inserted


def _insert_entry_cards(
    cur,
    owner_id: uuid.UUID,
    deck_id: uuid.UUID,
    group_id: uuid.UUID,
    entry_uuid: uuid.UUID,
    cards: Dict[str, dict],
) -> Tuple[int, Dict[str, dict]]:
    inserted = 0
    inserted_cards: Dict[str, dict] = {}
    for direction, card in cards.items():
        card_id = _insert_entry_card(cur, owner_id, deck_id, group_id, entry_uuid, card)
        inserted_cards[direction] = {
            "id": card_id,
            "updated_at": card.get("updated_at"),
        }
        inserted += 1
    return inserted, inserted_cards


def _insert_entry_card(
    cur,
    owner_id: uuid.UUID,
    deck_id: uuid.UUID,
    group_id: uuid.UUID,
    entry_uuid: uuid.UUID,
    card: dict,
) -> str:
    card_id = uuid.uuid4()
    payload = card.get("payload") or {}
    created_at = card.get("created_at")
    updated_at = card.get("updated_at") or created_at
    front_audio = card.get("front_audio")
    back_audio = card.get("back_audio")
    direction = card.get("direction")
    card_anki_uuid = stable_card_uuid(entry_uuid, direction)
    cur.execute(
        """
        INSERT INTO cards (
            id,
            card_group_id,
            entry_anki_id,
            deck_id,
            owner_id,
            direction,
            payload,
            front_audio,
            back_audio,
            audio_filename,
            created_at,
            updated_at,
            anki_id,
            difficulty
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            _uuid(card_id),
            _uuid(group_id),
            _uuid(entry_uuid),
            _uuid(deck_id),
            _uuid(owner_id),
            direction,
            Json(payload),
            Binary(front_audio) if front_audio else None,
            Binary(back_audio) if back_audio else None,
            card.get("audio_filename"),
            created_at,
            updated_at,
            _uuid(card_anki_uuid),
            card.get("difficulty"),
        ),
    )
    return str(card_id)


def _safe_uuid(value) -> uuid.UUID:
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError, AttributeError):
        return uuid.uuid4()
