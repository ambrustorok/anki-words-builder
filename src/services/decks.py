import json
import uuid
from typing import List, Optional

from psycopg2.extras import Json, RealDictCursor

from ..db.core import get_connection


def _uuid(value: uuid.UUID) -> str:
    return str(value)


def default_field_schema():
    return [
        {
            "key": "foreign_phrase",
            "label": "Foreign Phrase",
            "required": True,
            "description": "Phrase in the language you are learning",
        },
        {
            "key": "native_phrase",
            "label": "Native Phrase",
            "required": False,
            "description": "Auto-generated translation in your native language (editable).",
        },
        {
            "key": "dictionary_entry",
            "label": "Dictionary / Notes",
            "required": False,
            "description": "Optional dictionary entry or grammatical notes.",
        },
        {
            "key": "example_sentence",
            "label": "Example Sentence",
            "required": False,
            "description": "Short usage sentence in the target language.",
        },
    ]


def default_generation_prompts():
    return {
        "translation": {
            "system": "You are a professional translator who answers succinctly.",
            "user": "Translate '{foreign_phrase}' from {target_language} to {native_language}. Respond with only the translation.",
        },
        "dictionary": {
            "system": "You are a linguist who explains grammar in concise HTML.",
            "user": "Provide a dictionary-style breakdown of '{foreign_phrase}' in {target_language}. Include part of speech, morphology, and 2-3 usage notes. Output HTML using only <div>, <br>, <ul>, <li>, <b>, <i>.",
        },
        "sentence": {
            "system": "You create short, natural example sentences.",
            "user": "Write a short {target_language} sentence that naturally uses '{foreign_phrase}'. Keep it simple and output only the sentence.",
        },
    }


def default_prompt_templates():
    return {
        "forward": {
            "front": "{{foreign_phrase}}",
            "back": (
                "<div class='native font-semibold text-lg mb-2'>{{native_phrase}}</div>"
                "<div class='example italic text-base mb-2'>{{example_sentence}}</div>"
                "<div class='dictionary text-sm'>{{dictionary_entry}}</div>"
            ),
        },
        "backward": {
            "front": "{{native_phrase}}",
            "back": (
                "<div class='foreign font-semibold text-lg mb-2'>{{foreign_phrase}}</div>"
                "<div class='example italic text-base mb-2'>{{example_sentence}}</div>"
                "<div class='dictionary text-sm'>{{dictionary_entry}}</div>"
            ),
        },
        "generation": default_generation_prompts(),
    }


def create_deck(owner_id: uuid.UUID, name: str, target_language: str,
                field_schema: Optional[List[dict]] = None,
                prompt_templates: Optional[dict] = None) -> dict:
    deck_id = uuid.uuid4()
    schema = field_schema or default_field_schema()
    prompts = prompt_templates or default_prompt_templates()
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO decks (id, owner_id, name, target_language, field_schema, prompt_templates)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id, name, target_language, field_schema, prompt_templates, created_at
                """,
                (
                    _uuid(deck_id),
                    _uuid(owner_id),
                    name.strip(),
                    target_language.strip(),
                    Json(schema),
                    Json(prompts),
                ),
            )
            deck = cur.fetchone()
        conn.commit()
    return deck


def _hydrate_deck_stats(rows: List[dict]) -> List[dict]:
    for row in rows:
        row["card_count"] = int(row.get("card_count", 0) or 0)
        row["entry_count"] = int(row.get("entry_count", 0) or 0)
    return rows


def list_decks(owner_id: uuid.UUID) -> List[dict]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT d.id,
                       d.name,
                       d.target_language,
                       d.field_schema,
                       d.prompt_templates,
                       d.created_at,
                       COALESCE(COUNT(c.id), 0) AS card_count,
                       COALESCE(COUNT(DISTINCT c.card_group_id), 0) AS entry_count
                FROM decks d
                LEFT JOIN cards c ON c.deck_id = d.id AND c.owner_id = %s
                WHERE d.owner_id = %s
                GROUP BY d.id
                ORDER BY d.created_at DESC
                """,
                (_uuid(owner_id), _uuid(owner_id)),
            )
            rows = cur.fetchall()
    return _hydrate_deck_stats(rows)


def list_recent_decks(owner_id: uuid.UUID, limit: int = 3) -> List[dict]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT d.id,
                       d.name,
                       d.target_language,
                       d.field_schema,
                       d.prompt_templates,
                       d.created_at,
                       COALESCE(COUNT(c.id), 0) AS card_count,
                       COALESCE(COUNT(DISTINCT c.card_group_id), 0) AS entry_count,
                       COALESCE(MAX(c.created_at), d.created_at) AS last_modified_at
                FROM decks d
                LEFT JOIN cards c ON c.deck_id = d.id AND c.owner_id = %s
                WHERE d.owner_id = %s
                GROUP BY d.id
                ORDER BY last_modified_at DESC
                LIMIT %s
                """,
                (_uuid(owner_id), _uuid(owner_id), max(1, int(limit))),
            )
            rows = cur.fetchall()
    return _hydrate_deck_stats(rows)


def get_deck(deck_id: uuid.UUID, owner_id: uuid.UUID) -> Optional[dict]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT d.id,
                       d.name,
                       d.target_language,
                       d.field_schema,
                       d.prompt_templates,
                       d.created_at
                FROM decks d
                WHERE d.id = %s AND d.owner_id = %s
                """,
                (_uuid(deck_id), _uuid(owner_id)),
            )
            return cur.fetchone()


def update_deck(owner_id: uuid.UUID, deck_id: uuid.UUID, *, name: str, target_language: str,
                field_schema: List[dict], generation_prompts: Optional[dict] = None) -> Optional[dict]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            prompts = None
            if generation_prompts is not None:
                existing = get_deck(deck_id, owner_id)
                if not existing:
                    return None
                merged = existing.get("prompt_templates") or default_prompt_templates()
                merged["generation"] = generation_prompts
                prompts = merged

            cur.execute(
                """
                UPDATE decks
                SET name = %s,
                    target_language = %s,
                    field_schema = %s
                WHERE id = %s AND owner_id = %s
                RETURNING id, name, target_language, field_schema, prompt_templates, created_at
                """,
                (name.strip(), target_language.strip(), Json(field_schema), _uuid(deck_id), _uuid(owner_id)),
            )
            updated = cur.fetchone()
            if not updated:
                return None
            if prompts is not None:
                cur.execute(
                    """
                    UPDATE decks
                    SET prompt_templates = %s
                    WHERE id = %s AND owner_id = %s
                    """,
                    (Json(prompts), _uuid(deck_id), _uuid(owner_id)),
                )
                updated["prompt_templates"] = prompts
        conn.commit()
    return updated


def delete_deck(owner_id: uuid.UUID, deck_id: uuid.UUID) -> bool:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM decks WHERE id = %s AND owner_id = %s",
                (_uuid(deck_id), _uuid(owner_id)),
            )
            deleted = cur.rowcount > 0
        conn.commit()
    return deleted


def get_generation_prompts(deck: dict) -> dict:
    templates = deck.get("prompt_templates") or default_prompt_templates()
    generation = templates.get("generation")
    if not generation:
        generation = default_generation_prompts()
    merged = default_generation_prompts()
    merged.update(generation)
    return merged
