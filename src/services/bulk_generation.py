"""
Bulk card generation service.

Architecture (all optimised to minimise LLM calls):
  Phase 1 — generate_cell():     1 call per constraint cell → raw candidates
  Phase 2 — dedup_candidates():  0 tokens — backend set comparison
  Phase 3 — batch_enrich():      1 call total → dictionary_entry for all cards
  Phase 4 — batch_infer_tags():  1 call total → tags for all cards
"""

import json
import re
import unicodedata
from typing import Dict, List, Optional, Set

from openai import OpenAI

from ..settings import OPENAI_MODEL


# ---------------------------------------------------------------------------
# Phase 1 — generate raw candidates for one constraint cell
# ---------------------------------------------------------------------------


def generate_cell(
    client: OpenAI,
    *,
    card_type: str,  # "word" | "sentence"
    target_language: str,
    native_language: str,
    description: Optional[str],  # user's free-text topic
    constraint_tags: List[Dict],  # [{name, category}] — exclusive constraints
    count: int,
    model: Optional[str] = None,
) -> List[Dict]:
    """
    Generate `count` raw candidates for one combination of exclusive constraints.
    Returns [{foreign_phrase, native_phrase, example_sentence}].
    Never raises — returns [] on failure.
    """
    m = model or OPENAI_MODEL

    # Build constraint description
    constraint_parts = []
    for tag in constraint_tags:
        constraint_parts.append(f"{tag['category']} level {tag['name']}")
    constraint_str = ", ".join(constraint_parts) if constraint_parts else "any level"

    if card_type == "sentence":
        item_desc = (
            f"complete {target_language} sentences a learner could use in conversation"
        )
        field_hint = (
            "foreign_phrase: the full sentence in " + target_language + ", "
            "native_phrase: its " + native_language + " translation, "
            "example_sentence: a variant or follow-up sentence"
        )
    else:
        item_desc = f"{target_language} vocabulary words or short phrases"
        field_hint = (
            "foreign_phrase: the word/phrase in " + target_language + ", "
            "native_phrase: its " + native_language + " translation, "
            "example_sentence: a short natural sentence using the word"
        )

    topic_line = f'Topic/context: "{description}"' if description else ""

    user_prompt = (
        f"Generate exactly {count} {item_desc} appropriate for {constraint_str} learners.\n"
        + (topic_line + "\n" if topic_line else "")
        + f"For each item return: {field_hint}.\n"
        "Return ONLY a valid JSON array. No explanation, no markdown.\n"
        'Format: [{"foreign_phrase":"...","native_phrase":"...","example_sentence":"..."}]'
    )

    try:
        response = client.chat.completions.create(
            model=m,
            temperature=0.7,
            max_completion_tokens=2000,
            messages=[
                {
                    "role": "system",
                    "content": "You generate language learning flashcard content. Always respond with valid JSON only.",
                },
                {"role": "user", "content": user_prompt},
            ],
        )
        raw = response.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```[a-z]*\n?", "", raw).rstrip("`").strip()
        candidates = json.loads(raw)
        if not isinstance(candidates, list):
            return []
        result = []
        for item in candidates:
            if not isinstance(item, dict):
                continue
            fp = str(item.get("foreign_phrase", "")).strip()
            np_ = str(item.get("native_phrase", "")).strip()
            es = str(item.get("example_sentence", "")).strip()
            if fp:
                result.append(
                    {
                        "foreign_phrase": fp,
                        "native_phrase": np_,
                        "example_sentence": es,
                    }
                )
        return result
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Phase 2 — dedup (zero tokens)
# ---------------------------------------------------------------------------


def _normalise(text: str) -> str:
    """Lowercase, strip accents, strip leading articles (Danish/English common)."""
    t = unicodedata.normalize("NFD", text.lower())
    t = "".join(
        c for c in t if unicodedata.category(c) != "Mn"
    )  # strip combining chars
    # Strip common leading articles
    for article in ("den ", "det ", "de ", "en ", "et ", "the ", "a ", "an "):
        if t.startswith(article):
            t = t[len(article) :]
            break
    return t.strip()


def dedup_candidates(
    candidates: List[Dict],
    existing_phrases: Set[str],
) -> List[Dict]:
    """
    Mark each candidate as duplicate or possible_duplicate.
    existing_phrases is a set of normalised foreign_phrase values from the deck.
    Mutates candidates in-place and returns them.
    """
    existing_normalised = {_normalise(p) for p in existing_phrases}
    for c in candidates:
        fp = c.get("foreign_phrase", "")
        exact = fp.lower() in {p.lower() for p in existing_phrases}
        normalised = _normalise(fp) in existing_normalised
        c["is_duplicate"] = exact
        c["is_possible_duplicate"] = normalised and not exact
    return candidates


# ---------------------------------------------------------------------------
# Phase 3 — batch dictionary enrichment (1 LLM call for all cards)
# ---------------------------------------------------------------------------


def batch_enrich_dictionary(
    client: OpenAI,
    candidates: List[Dict],
    target_language: str,
    model: Optional[str] = None,
) -> List[Dict]:
    """
    Fill dictionary_entry for all candidates in one LLM call.
    Skips if no candidates. Returns candidates with dictionary_entry set.
    """
    if not candidates:
        return candidates
    m = model or OPENAI_MODEL

    words = [c["foreign_phrase"] for c in candidates]
    words_list = "\n".join(f"- {w}" for w in words)

    user_prompt = (
        f"For each of the following {target_language} words/phrases, write a brief dictionary entry.\n"
        "Include: part of speech, grammatical notes, 1-2 short usage notes.\n"
        "Use only these HTML tags: <div>, <br>, <b>, <i>, <ul>, <li>.\n"
        "Keep each entry short (3-5 lines).\n\n"
        f"Words:\n{words_list}\n\n"
        'Return ONLY a valid JSON object: {"word": "<div>...</div>", ...}\n'
        "Use the exact word as the key."
    )

    try:
        response = client.chat.completions.create(
            model=m,
            temperature=0.2,
            max_completion_tokens=3000,
            messages=[
                {
                    "role": "system",
                    "content": "You write concise dictionary entries in HTML. Always respond with valid JSON only.",
                },
                {"role": "user", "content": user_prompt},
            ],
        )
        raw = response.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```[a-z]*\n?", "", raw).rstrip("`").strip()
        entries: Dict[str, str] = json.loads(raw)
        if isinstance(entries, dict):
            for c in candidates:
                key = c["foreign_phrase"]
                if key in entries:
                    c["dictionary_entry"] = entries[key]
    except Exception:
        pass  # dictionary_entry stays missing — not critical

    return candidates


# ---------------------------------------------------------------------------
# Phase 4 — batch tag inference (1 LLM call for all cards)
# ---------------------------------------------------------------------------


def batch_infer_tags(
    client: OpenAI,
    candidates: List[Dict],
    target_language: str,
    available_tags: List[Dict],
    prefilled_tag_names: Optional[Dict[str, List[str]]] = None,
    model: Optional[str] = None,
) -> List[Dict]:
    """
    Infer non-constrained tags for all candidates in one LLM call.

    prefilled_tag_names: {foreign_phrase: [tag_name, ...]}
        Constraint tags locked by the user's cell selection. These are
        ALWAYS applied as-is — the AI never sees or overrides them.
        The AI only infers tags from categories NOT represented in each
        candidate's own constraint tags.

    Strategy: find the union of all constrained categories across all
    candidates, exclude those from the AI prompt entirely, then merge
    AI results with locked constraint tags (locked tags always win).
    """
    if not candidates or not available_tags:
        for c in candidates:
            c.setdefault("suggested_tag_names", [])
        return candidates

    m = model or OPENAI_MODEL
    prefilled = prefilled_tag_names or {}

    # Build a lookup: tag_name → category
    name_to_category: Dict[str, str] = {
        t["name"]: (t.get("category") or "General") for t in available_tags
    }

    # Find categories that are constrained for ANY candidate.
    # These are excluded from the AI prompt — we never ask the AI to infer
    # them because some candidates already have them locked.
    constrained_categories: Set[str] = set()
    for tag_names in prefilled.values():
        for tn in tag_names:
            if tn in name_to_category:
                constrained_categories.add(name_to_category[tn])

    # Build the AI tag menu: only categories NOT constrained by any cell
    inferrable: Dict[str, List[str]] = {}
    for tag in available_tags:
        cat = tag.get("category") or "General"
        if cat not in constrained_categories:
            inferrable.setdefault(cat, []).append(tag["name"])

    if not inferrable:
        # Everything is constrained — just lock in the prefilled tags
        for c in candidates:
            c["suggested_tag_names"] = list(prefilled.get(c["foreign_phrase"], []))
        return candidates

    tag_list_text = "\n".join(
        f"- {cat}: {', '.join(names)}" for cat, names in inferrable.items()
    )
    words_list = "\n".join(f"- {c['foreign_phrase']}" for c in candidates)

    user_prompt = (
        f"Language: {target_language}\n\n"
        f"Available tags to assign:\n{tag_list_text}\n\n"
        "For exclusive categories (where only one tag per item makes sense), assign at most one.\n\n"
        f"Words/phrases:\n{words_list}\n\n"
        'Return ONLY a valid JSON object: {"word": ["tag1", "tag2"], ...}\n'
        "Use [] if no tags clearly apply. Only use tags from the list above."
    )

    tag_map: Dict[str, List[str]] = {}
    try:
        response = client.chat.completions.create(
            model=m,
            temperature=0.1,
            max_completion_tokens=1000,
            messages=[
                {
                    "role": "system",
                    "content": "You assign tags to language flashcards. Always respond with valid JSON only.",
                },
                {"role": "user", "content": user_prompt},
            ],
        )
        raw = response.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```[a-z]*\n?", "", raw).rstrip("`").strip()
        tag_map = json.loads(raw)
    except Exception:
        pass  # tag_map stays empty — fall through to prefilled-only

    valid_names = {t["name"] for t in available_tags}
    for c in candidates:
        fp = c["foreign_phrase"]
        locked = list(prefilled.get(fp, []))  # constraint tags — always kept
        inferred = [
            n
            for n in tag_map.get(fp, [])
            if n in valid_names and n not in locked  # AI tags — never override locked
        ]
        c["suggested_tag_names"] = list(dict.fromkeys(locked + inferred))

    return candidates


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def get_existing_phrases(owner_id, deck_id) -> Set[str]:
    """Fetch all foreign_phrase values for a deck. Used for dedup."""
    import uuid as _uuid_mod
    from psycopg2.extras import RealDictCursor
    from ..db.core import get_connection

    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT DISTINCT payload->>'foreign_phrase' AS fp
                FROM cards
                WHERE owner_id = %s AND deck_id = %s
                  AND payload->>'foreign_phrase' IS NOT NULL
                """,
                (str(owner_id), str(deck_id)),
            )
            rows = cur.fetchall()
    return {row["fp"] for row in rows if row["fp"]}
