import re
from typing import Dict, List, Optional

from openai import OpenAI

from ..chatgpt_tools.tts import generate_audio_binary

DEFAULT_PROMPTS = {
    "translation": {
        "system": "You translate between languages and respond concisely.",
        "user": "Translate '{foreign_phrase}' from {target_language} to {native_language}. Respond with only the translation.",
    },
    "dictionary": {
        "system": "You provide dictionary-style explanations in lightweight HTML.",
        "user": (
            "Explain '{foreign_phrase}' ({target_language}) as a dictionary entry. "
            "Include part of speech, grammatical notes, and 2 short usage notes. "
            "Respond with HTML using <div>, <br>, <ul>, <li>, <b>, <i> only."
        ),
    },
    "sentence": {
        "system": "You craft short, natural example sentences.",
        "user": (
            "Write a short {target_language} sentence that includes '{foreign_phrase}'. "
            "Keep it natural and respond with only the sentence."
        ),
    },
}


def _format_prompt(prompt_cfg: Dict[str, str], context: Dict[str, str]) -> Dict[str, str]:
    system_prompt = prompt_cfg.get("system") or DEFAULT_PROMPTS["translation"]["system"]
    user_template = prompt_cfg.get("user") or DEFAULT_PROMPTS["translation"]["user"]
    user_prompt = user_template.format(**context)
    return {"system": system_prompt, "user": user_prompt}


def _run_completion(client: OpenAI, prompt_cfg: Dict[str, str], context: Dict[str, str]) -> str:
    prompts = _format_prompt(prompt_cfg, context)
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.2,
        messages=[
            {"role": "system", "content": prompts["system"]},
            {"role": "user", "content": prompts["user"]},
        ],
    )
    return response.choices[0].message.content.strip()


def _should_generate_sentence(text: str) -> bool:
    # If it's a longer sentence already, skip generation.
    if len(text.split()) >= 6:
        return False
    if bool(re.search(r"[.!?]$", text.strip())) and len(text.split()) >= 4:
        return False
    return True


def generate_translation(client: OpenAI, prompts: Dict[str, Dict[str, str]], context: Dict[str, str]) -> str:
    prompt_cfg = prompts.get("translation") or DEFAULT_PROMPTS["translation"]
    return _run_completion(client, prompt_cfg, context)


def generate_dictionary(client: OpenAI, prompts: Dict[str, Dict[str, str]], context: Dict[str, str]) -> str:
    prompt_cfg = prompts.get("dictionary") or DEFAULT_PROMPTS["dictionary"]
    return _run_completion(client, prompt_cfg, context)


def generate_sentence(client: OpenAI, prompts: Dict[str, Dict[str, str]], context: Dict[str, str]) -> str:
    prompt_cfg = prompts.get("sentence") or DEFAULT_PROMPTS["sentence"]
    return _run_completion(client, prompt_cfg, context)


def _can_generate_field(field_schema: Optional[List[dict]], field_key: str) -> bool:
    for field in field_schema or []:
        if field.get("key") == field_key:
            return bool(field.get("auto_generate"))
    return False


def enrich_payload(
    client: OpenAI,
    payload: Dict[str, str],
    foreign_phrase_key: str,
    target_language: str,
    native_language: str,
    generation_prompts: Dict[str, Dict[str, str]],
    field_schema: Optional[List[dict]] = None,
) -> Dict[str, str]:
    foreign_phrase = payload.get(foreign_phrase_key, "").strip()
    if not foreign_phrase:
        raise ValueError("Foreign phrase is required for generation.")

    context = {
        "foreign_phrase": foreign_phrase,
        "target_language": target_language,
        "native_language": native_language,
    }

    if _can_generate_field(field_schema, "native_phrase") and not payload.get("native_phrase"):
        payload["native_phrase"] = generate_translation(client, generation_prompts, context)

    if _can_generate_field(field_schema, "dictionary_entry") and not payload.get("dictionary_entry"):
        payload["dictionary_entry"] = generate_dictionary(client, generation_prompts, context)

    if _can_generate_field(field_schema, "example_sentence") and not payload.get("example_sentence"):
        if _should_generate_sentence(foreign_phrase):
            payload["example_sentence"] = generate_sentence(client, generation_prompts, context)
        else:
            payload["example_sentence"] = foreign_phrase

    return payload


def regenerate_field(
    client: OpenAI,
    field: str,
    payload: Dict[str, str],
    foreign_phrase_key: str,
    target_language: str,
    native_language: str,
    generation_prompts: Dict[str, Dict[str, str]],
    field_schema: Optional[List[dict]] = None,
) -> Dict[str, str]:
    context = {
        "foreign_phrase": payload.get(foreign_phrase_key, "").strip(),
        "target_language": target_language,
        "native_language": native_language,
    }
    if not context["foreign_phrase"]:
        raise ValueError("Provide a foreign phrase before regenerating.")

    if not _can_generate_field(field_schema, field):
        raise ValueError("Generation is disabled for this field in deck settings.")

    if field == "native_phrase":
        payload["native_phrase"] = generate_translation(client, generation_prompts, context)
    elif field == "dictionary_entry":
        payload["dictionary_entry"] = generate_dictionary(client, generation_prompts, context)
    elif field == "example_sentence":
        payload["example_sentence"] = generate_sentence(client, generation_prompts, context)
    else:
        raise ValueError("Unsupported field regeneration.")
    return payload


def generate_audio_for_phrase(
    client: OpenAI,
    text: str,
    *,
    voice: str = "random",
    instructions: str = "",
) -> Optional[bytes]:
    if not text.strip():
        return None
    return generate_audio_binary(
        client,
        text.strip(),
        voice=voice,
        instructions=instructions,
    )
