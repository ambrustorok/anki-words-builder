import json
import uuid
from copy import deepcopy
from typing import List, Optional

from psycopg2.extras import Json, RealDictCursor

from ..db.core import get_connection


def _uuid(value: uuid.UUID) -> str:
    return str(value)


DEFAULT_AUDIO_INSTRUCTIONS_TEMPLATE = (
    "Talk in a natural tone and speed for a native {target_language} speaker."
)


FIELD_LIBRARY = [
    {
        "key": "foreign_phrase",
        "label": "Foreign expression",
        "required": True,
        "description": "Phrase in the language you are learning.",
        "default_auto_generate": False,
        "supports_generation": False,
        "default_enabled": True,
        "allow_disable": False,
    },
    {
        "key": "native_phrase",
        "label": "Native expression",
        "required": False,
        "description": "Translation in your native language.",
        "default_auto_generate": True,
        "supports_generation": True,
        "default_enabled": True,
        "allow_disable": True,
    },
    {
        "key": "dictionary_entry",
        "label": "Dictionary / Notes",
        "required": False,
        "description": "Optional dictionary entry or grammatical notes.",
        "default_auto_generate": True,
        "supports_generation": True,
        "default_enabled": True,
        "allow_disable": True,
    },
    {
        "key": "example_sentence",
        "label": "Example sentence",
        "required": False,
        "description": "Short usage sentence in the target language.",
        "default_auto_generate": True,
        "supports_generation": True,
        "default_enabled": True,
        "allow_disable": True,
    },
]

FIELD_BY_KEY = {field["key"]: field for field in FIELD_LIBRARY}


def get_field_library() -> List[dict]:
    return [deepcopy(field) for field in FIELD_LIBRARY]


def _normalize_field(entry: dict) -> dict:
    key = entry.get("key")
    base = FIELD_BY_KEY.get(key, {})
    normalized = {
        "key": key,
        "label": entry.get("label") or base.get("label") or key,
        "required": bool(
            entry.get("required") if entry.get("required") is not None else base.get("required", False)
        ),
        "description": entry.get("description") or base.get("description") or "",
        "auto_generate": bool(
            entry.get("auto_generate")
            if entry.get("auto_generate") is not None
            else base.get("default_auto_generate", False)
        ),
    }
    return normalized


def normalize_field_schema(schema: Optional[List[dict]]) -> List[dict]:
    if schema is None:
        return default_field_schema()
    normalized: List[dict] = []
    seen_keys = set()
    for entry in schema:
        if not entry or not entry.get("key"):
            continue
        normalized_field = _normalize_field(entry)
        normalized.append(normalized_field)
        seen_keys.add(normalized_field["key"])
    if "foreign_phrase" not in seen_keys:
        normalized.insert(0, _normalize_field({"key": "foreign_phrase"}))
    return normalized


def default_field_schema():
    return [
        _normalize_field(field)
        for field in FIELD_LIBRARY
        if field.get("default_enabled", True)
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
        "audio": {
            "instructions": DEFAULT_AUDIO_INSTRUCTIONS_TEMPLATE,
            "enabled": True,
        },
    }


def create_deck(owner_id: uuid.UUID, name: str, target_language: str,
                field_schema: Optional[List[dict]] = None,
                prompt_templates: Optional[dict] = None,
                audio_instructions: Optional[str] = None,
                audio_enabled: Optional[bool] = None) -> dict:
    deck_id = uuid.uuid4()
    schema = normalize_field_schema(field_schema) if field_schema else default_field_schema()
    prompts = prompt_templates or default_prompt_templates()
    audio_cfg = prompts.get("audio") or {}
    if audio_instructions is not None:
        instructions = (audio_instructions or "").strip() or DEFAULT_AUDIO_INSTRUCTIONS_TEMPLATE
        audio_cfg["instructions"] = instructions
    if audio_enabled is not None:
        audio_cfg["enabled"] = bool(audio_enabled)
    prompts["audio"] = {
        "instructions": audio_cfg.get("instructions") or DEFAULT_AUDIO_INSTRUCTIONS_TEMPLATE,
        "enabled": audio_cfg.get("enabled", True),
    }
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO decks (id, owner_id, name, target_language, field_schema, prompt_templates)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id, name, target_language, field_schema, prompt_templates, created_at, updated_at
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
                       d.updated_at,
                       GREATEST(
                           d.updated_at,
                           COALESCE(MAX(c.updated_at), d.updated_at)
                       ) AS last_modified_at,
                       COALESCE(COUNT(c.id), 0) AS card_count,
                       COALESCE(COUNT(DISTINCT c.card_group_id), 0) AS entry_count
                FROM decks d
                LEFT JOIN cards c ON c.deck_id = d.id AND c.owner_id = %s
                WHERE d.owner_id = %s
                GROUP BY d.id
                ORDER BY last_modified_at DESC
                """,
                (_uuid(owner_id), _uuid(owner_id)),
            )
            rows = cur.fetchall()
    for row in rows:
        row["field_schema"] = normalize_field_schema(row.get("field_schema"))
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
                       d.updated_at,
                       COALESCE(COUNT(c.id), 0) AS card_count,
                       COALESCE(COUNT(DISTINCT c.card_group_id), 0) AS entry_count,
                       GREATEST(
                           d.updated_at,
                           COALESCE(MAX(c.updated_at), d.updated_at)
                       ) AS last_modified_at
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
    for row in rows:
        row["field_schema"] = normalize_field_schema(row.get("field_schema"))
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
                       d.created_at,
                       d.updated_at
                FROM decks d
                WHERE d.id = %s AND d.owner_id = %s
                """,
                (_uuid(deck_id), _uuid(owner_id)),
            )
            deck = cur.fetchone()
    if not deck:
        return None
    deck["field_schema"] = normalize_field_schema(deck.get("field_schema"))
    return deck


def update_deck(owner_id: uuid.UUID, deck_id: uuid.UUID, *, name: str, target_language: str,
                field_schema: List[dict], generation_prompts: Optional[dict] = None,
                audio_instructions: Optional[str] = None,
                audio_enabled: Optional[bool] = None) -> Optional[dict]:
    schema = normalize_field_schema(field_schema)
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            prompts = None
            if generation_prompts is not None or audio_instructions is not None or audio_enabled is not None:
                existing = get_deck(deck_id, owner_id)
                if not existing:
                    return None
                merged = existing.get("prompt_templates") or default_prompt_templates()
                if generation_prompts is not None:
                    merged["generation"] = generation_prompts
                if audio_instructions is not None:
                    instruction_text = (audio_instructions or "").strip() or DEFAULT_AUDIO_INSTRUCTIONS_TEMPLATE
                    audio_cfg = merged.get("audio") or {}
                    audio_cfg["instructions"] = instruction_text
                    merged["audio"] = audio_cfg
                if audio_enabled is not None:
                    audio_cfg = merged.get("audio") or {}
                    audio_cfg["enabled"] = bool(audio_enabled)
                    merged["audio"] = audio_cfg
                prompts = merged

            cur.execute(
                """
                UPDATE decks
                SET name = %s,
                    target_language = %s,
                    field_schema = %s,
                    updated_at = NOW()
                WHERE id = %s AND owner_id = %s
                RETURNING id, name, target_language, field_schema, prompt_templates, created_at, updated_at
                """,
                (name.strip(), target_language.strip(), Json(schema), _uuid(deck_id), _uuid(owner_id)),
            )
            updated = cur.fetchone()
            if not updated:
                return None
            updated["field_schema"] = normalize_field_schema(updated.get("field_schema"))
            if prompts is not None:
                cur.execute(
                    """
                    UPDATE decks
                    SET prompt_templates = %s,
                        updated_at = NOW()
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


def get_audio_prompt_template(deck: dict) -> str:
    templates = deck.get("prompt_templates") or default_prompt_templates()
    audio_cfg = templates.get("audio") or {}
    return audio_cfg.get("instructions") or DEFAULT_AUDIO_INSTRUCTIONS_TEMPLATE


def get_audio_instructions(deck: dict) -> str:
    template = get_audio_prompt_template(deck)
    target_language = deck.get("target_language") or ""
    replacement = target_language or "the target language"
    return template.replace("{target_language}", replacement)


def is_audio_enabled(deck: dict) -> bool:
    templates = deck.get("prompt_templates") or default_prompt_templates()
    audio_cfg = templates.get("audio") or {}
    return bool(audio_cfg.get("enabled", True))
