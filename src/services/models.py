import logging
from typing import Optional

from ..settings import OPENAI_MODEL
from . import api_keys as api_key_service

logger = logging.getLogger(__name__)

DEFAULT_AUDIO_MODEL = "gpt-4o-mini-tts"
_FALLBACK_TEXT_MODELS = [
    "gpt-5.4-nano",
    "gpt-4o",
    "gpt-4o-mini",
    "o4-mini",
    "o3",
    "o1",
    "chatgpt-4o-latest",
]
_FALLBACK_AUDIO_MODELS = ["gpt-4o-mini-tts", "tts-1", "tts-1-hd"]
_TEXT_INCLUDE = ("gpt-", "o1", "o3", "o4", "o5", "chatgpt")
_TEXT_EXCLUDE = (
    "tts",
    "realtime",
    "transcribe",
    "whisper",
    "dall",
    "embedding",
    "search",
    "moderation",
    "audio",
    "instruct",
    "vision-preview",
)


def available_models(user_id) -> dict:
    fallback = {
        "textModels": _FALLBACK_TEXT_MODELS,
        "audioModels": _FALLBACK_AUDIO_MODELS,
        "defaultTextModel": OPENAI_MODEL,
        "defaultAudioModel": DEFAULT_AUDIO_MODEL,
    }
    if not api_key_service.user_can_generate(user_id):
        return fallback
    try:
        ids = sorted(
            (
                model.id
                for model in api_key_service.get_openai_client_for_user(
                    user_id
                ).models.list().data
            ),
            key=str.lower,
        )
    except Exception as exc:
        logger.warning("Could not fetch model list: %s", exc)
        return fallback
    text = [model for model in ids if _is_text(model)]
    audio = [model for model in ids if "tts" in model.lower()]
    for model in reversed(_FALLBACK_TEXT_MODELS):
        if model not in text:
            text.insert(0, model)
    for model in reversed(_FALLBACK_AUDIO_MODELS):
        if model not in audio:
            audio.insert(0, model)
    return {**fallback, "textModels": text, "audioModels": audio}


def test_models(user_id, text_model: str, audio_model: str) -> dict:
    client = api_key_service.get_openai_client_for_user(user_id)
    text_error: Optional[str] = None
    audio_error: Optional[str] = None
    try:
        client.chat.completions.create(
            model=text_model.strip(),
            messages=[{"role": "user", "content": "Hi"}],
            max_completion_tokens=10,
        )
    except Exception as exc:
        text_error = _error_message(exc)
    try:
        client.audio.speech.create(
            model=audio_model.strip(),
            voice="alloy",
            input=".",
            response_format="mp3",
        ).content
    except Exception as exc:
        audio_error = _error_message(exc)
    return {
        "textModel": {"ok": text_error is None, "error": text_error},
        "audioModel": {"ok": audio_error is None, "error": audio_error},
    }


def _error_message(exc: Exception) -> str:
    return (getattr(exc, "message", None) or str(exc)).split("\n")[0][:200]


def _is_text(model: str) -> bool:
    model = model.lower()
    return (model.startswith(_TEXT_INCLUDE) or any(prefix in model for prefix in _TEXT_INCLUDE)) and not any(
        excluded in model for excluded in _TEXT_EXCLUDE
    )
