import uuid
from copy import deepcopy
from typing import List, Optional

from psycopg2.extras import Json, RealDictCursor

from ..db.core import get_connection
from . import settings as settings_service


def _uuid(value: uuid.UUID) -> str:
    return str(value)


DEFAULT_AUDIO_INSTRUCTIONS_TEMPLATE = (
    "Talk in a natural tone and speed for a native {target_language} speaker."
)
PROMPT_SETTINGS_KEY = "default_prompt_templates"


def _merge_nested(defaults: dict, overrides: Optional[dict]) -> dict:
    merged = deepcopy(defaults)
    if not overrides:
        return merged
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_nested(merged[key], value)
        else:
            merged[key] = deepcopy(value)
    return merged


def _base_generation_prompts():
    return {
        "translation": {
            "system": "You are a professional translator who answers succinctly.",
            "user": "Translate '{foreign_phrase}' from {target_language} to {native_language}. Respond with only the translation.",
        },
        "reverse_translation": {
            "system": "You are a professional translator who answers succinctly.",
            "user": "Translate '{native_phrase}' from {native_language} to {target_language}. Respond with only the translation.",
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


def _base_prompt_templates():
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
        "generation": _base_generation_prompts(),
        "audio": {
            "instructions": DEFAULT_AUDIO_INSTRUCTIONS_TEMPLATE,
            "enabled": True,
        },
    }


def default_prompt_templates():
    base = _base_prompt_templates()
    stored = settings_service.get_json_setting(PROMPT_SETTINGS_KEY)
    if stored is None:
        settings_service.set_json_setting(PROMPT_SETTINGS_KEY, base)
        return deepcopy(base)
    return _merge_nested(base, stored)


def update_default_prompt_templates(overrides: Optional[dict]) -> dict:
    merged = _merge_nested(_base_prompt_templates(), overrides or {})
    settings_service.set_json_setting(PROMPT_SETTINGS_KEY, merged)
    return deepcopy(merged)


def default_generation_prompts():
    templates = default_prompt_templates()
    generation = templates.get("generation") or {}
    return _merge_nested(_base_generation_prompts(), generation)


def default_audio_instructions_template() -> str:
    templates = default_prompt_templates()
    audio_cfg = templates.get("audio") or {}
    return audio_cfg.get("instructions") or DEFAULT_AUDIO_INSTRUCTIONS_TEMPLATE


def default_card_templates() -> dict:
    templates = default_prompt_templates()
    return {
        "forward": deepcopy(templates.get("forward") or {}),
        "backward": deepcopy(templates.get("backward") or {}),
    }


def _apply_card_template_overrides(templates: dict, overrides: Optional[dict]) -> dict:
    if not overrides:
        return templates
    merged = deepcopy(templates)
    for direction in ("forward", "backward"):
        face_override = overrides.get(direction)
        if not isinstance(face_override, dict):
            continue
        face = deepcopy(merged.get(direction) or {})
        if "front" in face_override and face_override["front"] is not None:
            face["front"] = face_override["front"]
        if "back" in face_override and face_override["back"] is not None:
            face["back"] = face_override["back"]
        merged[direction] = face
    return merged


def _resolved_audio_config(deck: Optional[dict]) -> dict:
    base_audio = default_prompt_templates().get("audio") or {
        "instructions": DEFAULT_AUDIO_INSTRUCTIONS_TEMPLATE,
        "enabled": True,
    }
    prompts = (deck or {}).get("prompt_templates") or {}
    deck_audio = prompts.get("audio") or {}
    return _merge_nested(base_audio, deck_audio)


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


def _normalize_field(entry: dict) -> Optional[dict]:
    key = entry.get("key")
    if not key:
        return None
    base = FIELD_BY_KEY.get(key)
    if not base:
        return None
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
        if not normalized_field:
            continue
        normalized.append(normalized_field)
        seen_keys.add(normalized_field["key"])
    if "foreign_phrase" not in seen_keys:
        default_foreign = _normalize_field({"key": "foreign_phrase"})
        if default_foreign:
            normalized.insert(0, default_foreign)
    return normalized


def default_field_schema():
    schema: List[dict] = []
    for field in FIELD_LIBRARY:
        if not field.get("default_enabled", True):
            continue
        normalized = _normalize_field(field)
        if normalized:
            schema.append(normalized)
    return schema


def create_deck(owner_id: uuid.UUID, name: str, target_language: str,
                field_schema: Optional[List[dict]] = None,
                prompt_templates: Optional[dict] = None,
                audio_instructions: Optional[str] = None,
                audio_enabled: Optional[bool] = None,
                anki_id: Optional[uuid.UUID] = None) -> dict:
    deck_id = uuid.uuid4()
    deck_anki_id = anki_id or uuid.uuid4()
    schema = normalize_field_schema(field_schema) if field_schema else default_field_schema()
    prompts = deepcopy(prompt_templates) if prompt_templates else default_prompt_templates()
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
                INSERT INTO decks (id, owner_id, name, target_language, field_schema, prompt_templates, anki_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id, name, target_language, field_schema, prompt_templates, created_at, updated_at, anki_id
                """,
                (
                    _uuid(deck_id),
                    _uuid(owner_id),
                    name.strip(),
                    target_language.strip(),
                    Json(schema),
                    Json(prompts),
                    _uuid(deck_anki_id),
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
                       d.anki_id,
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
                       d.anki_id,
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


def list_least_recent_decks(owner_id: uuid.UUID, limit: int = 3) -> List[dict]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT d.id,
                       d.anki_id,
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
                ORDER BY last_modified_at ASC NULLS FIRST
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
                       d.anki_id,
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


def get_deck_by_anki_id(owner_id: uuid.UUID, anki_id: uuid.UUID) -> Optional[dict]:
    if not anki_id:
        return None
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT d.id,
                       d.anki_id,
                       d.name,
                       d.target_language,
                       d.field_schema,
                       d.prompt_templates,
                       d.created_at,
                       d.updated_at
                FROM decks d
                WHERE d.owner_id = %s AND d.anki_id = %s
                """,
                (_uuid(owner_id), _uuid(anki_id)),
            )
            deck = cur.fetchone()
    if not deck:
        return None
    deck["field_schema"] = normalize_field_schema(deck.get("field_schema"))
    return deck


def apply_backup_metadata(
    owner_id: uuid.UUID,
    deck_id: uuid.UUID,
    *,
    name: str,
    target_language: str,
    field_schema: Optional[List[dict]],
    prompt_templates: Optional[dict],
) -> Optional[dict]:
    schema = normalize_field_schema(field_schema) if field_schema else default_field_schema()
    prompts = deepcopy(prompt_templates) if prompt_templates else default_prompt_templates()
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                UPDATE decks
                SET name = %s,
                    target_language = %s,
                    field_schema = %s,
                    prompt_templates = %s,
                    updated_at = NOW()
                WHERE id = %s AND owner_id = %s
                RETURNING id, anki_id, name, target_language, field_schema, prompt_templates, created_at, updated_at
                """,
                (
                    name.strip(),
                    target_language.strip(),
                    Json(schema),
                    Json(prompts),
                    _uuid(deck_id),
                    _uuid(owner_id),
                ),
            )
            deck = cur.fetchone()
        conn.commit()
    if deck:
        deck["field_schema"] = normalize_field_schema(deck.get("field_schema"))
    return deck


def update_deck(
    owner_id: uuid.UUID,
    deck_id: uuid.UUID,
    *,
    name: str,
    target_language: str,
    field_schema: List[dict],
    generation_prompts: Optional[dict] = None,
    audio_instructions: Optional[str] = None,
    audio_enabled: Optional[bool] = None,
    card_templates: Optional[dict] = None,
) -> Optional[dict]:
    schema = normalize_field_schema(field_schema)
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            prompts = None
            if (
                generation_prompts is not None
                or audio_instructions is not None
                or audio_enabled is not None
                or card_templates is not None
            ):
                existing = get_deck(deck_id, owner_id)
                if not existing:
                    return None
                merged = deepcopy(existing.get("prompt_templates") or default_prompt_templates())
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
                if card_templates is not None:
                    merged = _apply_card_template_overrides(merged, card_templates)
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
    deck_templates = deck.get("prompt_templates") or {}
    generation = deck_templates.get("generation") or {}
    defaults = default_generation_prompts()
    return _merge_nested(defaults, generation)


def get_audio_prompt_template(deck: dict) -> str:
    audio_cfg = _resolved_audio_config(deck)
    return audio_cfg.get("instructions") or DEFAULT_AUDIO_INSTRUCTIONS_TEMPLATE


def get_audio_instructions(deck: dict) -> str:
    template = get_audio_prompt_template(deck)
    target_language = deck.get("target_language") or ""
    replacement = target_language or "the target language"
    return template.replace("{target_language}", replacement)


def is_audio_enabled(deck: dict) -> bool:
    audio_cfg = _resolved_audio_config(deck)
    return bool(audio_cfg.get("enabled", True))
