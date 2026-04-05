import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from ..services import api_keys as api_key_service
from ..services import users as user_service
from ..settings import NATIVE_LANGUAGE_OPTIONS, OPENAI_MODEL
from .dependencies import get_current_user, parse_uuid
from .session import _build_logout_url

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/profile")

DEFAULT_AUDIO_MODEL = "gpt-4o-mini-tts"

# Curated list shown when the API can't be reached or returns nothing useful.
_FALLBACK_TEXT_MODELS = [
    "gpt-4o",
    "gpt-4o-mini",
    "o4-mini",
    "o3",
    "o1",
    "chatgpt-4o-latest",
]
_FALLBACK_AUDIO_MODELS = [
    "gpt-4o-mini-tts",
    "tts-1",
    "tts-1-hd",
]

# ---- ID-pattern classification (best available without capability metadata) ----
_TEXT_INCLUDE = ("gpt-", "o1", "o3", "o4", "chatgpt")
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
_AUDIO_INCLUDE = ("tts",)


class APIKeyPayload(BaseModel):
    api_key: str = Field(..., alias="apiKey")


class EmailPayload(BaseModel):
    email: str
    make_primary: bool = Field(False, alias="makePrimary")


class ModelPrefsPayload(BaseModel):
    text_model: Optional[str] = Field(None, alias="textModel")
    audio_model: Optional[str] = Field(None, alias="audioModel")


class ThemePayload(BaseModel):
    theme: str  # 'light' | 'dark' | 'system'


class ModelTestPayload(BaseModel):
    text_model: str = Field(..., alias="textModel")
    audio_model: str = Field(..., alias="audioModel")


@router.get("")
def profile_detail(user=Depends(get_current_user)):
    fresh_user = user_service.get_user(user["id"]) or user
    emails = user_service.list_user_emails(user["id"])
    return {
        "user": {
            "id": str(fresh_user["id"]),
            "nativeLanguage": fresh_user.get("native_language"),
            "primaryEmail": fresh_user.get("primary_email"),
            "isAdmin": bool(fresh_user.get("is_admin")),
            "textModel": fresh_user.get("text_model"),
            "audioModel": fresh_user.get("audio_model"),
            "theme": fresh_user.get("theme") or "system",
        },
        "emails": emails,
        "apiKey": api_key_service.get_api_key_summary(user["id"]),
        "nativeLanguageOptions": NATIVE_LANGUAGE_OPTIONS,
    }


@router.post("/api-key")
def set_api_key(payload: APIKeyPayload, user=Depends(get_current_user)):
    key = payload.api_key.strip()
    if not key:
        raise HTTPException(status_code=400, detail="API key cannot be empty.")
    api_key_service.set_user_api_key(user["id"], key)
    return {"status": "ok"}


@router.delete("/api-key")
def delete_api_key(user=Depends(get_current_user)):
    api_key_service.delete_user_api_key(user["id"])
    return {"status": "ok"}


@router.get("/models/available")
def available_models(user=Depends(get_current_user)):
    """
    Return model lists for the dropdown. Uses the OpenAI /models endpoint
    when a key is available, falls back to a curated list otherwise.
    The API returns only id/created/object/owned_by — no capability field —
    so we classify by ID pattern.
    """

    def _is_text(mid: str) -> bool:
        m = mid.lower()
        return any(m.startswith(i) or i in m for i in _TEXT_INCLUDE) and not any(
            e in m for e in _TEXT_EXCLUDE
        )

    def _is_audio(mid: str) -> bool:
        return any(i in mid.lower() for i in _AUDIO_INCLUDE)

    if not api_key_service.user_can_generate(user["id"]):
        return {
            "textModels": _FALLBACK_TEXT_MODELS,
            "audioModels": _FALLBACK_AUDIO_MODELS,
            "defaultTextModel": OPENAI_MODEL,
            "defaultAudioModel": DEFAULT_AUDIO_MODEL,
        }

    try:
        client = api_key_service.get_openai_client_for_user(user["id"])
        all_ids = sorted((m.id for m in client.models.list().data), key=str.lower)
    except Exception as exc:
        logger.warning("Could not fetch model list: %s", exc)
        return {
            "textModels": _FALLBACK_TEXT_MODELS,
            "audioModels": _FALLBACK_AUDIO_MODELS,
            "defaultTextModel": OPENAI_MODEL,
            "defaultAudioModel": DEFAULT_AUDIO_MODEL,
        }

    text_models = [m for m in all_ids if _is_text(m)]
    audio_models = [m for m in all_ids if _is_audio(m)]

    # Ensure the curated defaults always appear at the top
    for m in reversed(_FALLBACK_TEXT_MODELS):
        if m not in text_models:
            text_models.insert(0, m)
    for m in reversed(_FALLBACK_AUDIO_MODELS):
        if m not in audio_models:
            audio_models.insert(0, m)

    return {
        "textModels": text_models,
        "audioModels": audio_models,
        "defaultTextModel": OPENAI_MODEL,
        "defaultAudioModel": DEFAULT_AUDIO_MODEL,
    }


@router.post("/models/test")
def test_models(payload: ModelTestPayload, user=Depends(get_current_user)):
    """
    Validate that the given text and audio model IDs actually work.
    Uses the cheapest possible API calls to minimise cost.
    Returns per-model ok/error without raising — the UI decides what to do.
    """
    if not api_key_service.user_can_generate(user["id"]):
        raise HTTPException(
            status_code=400,
            detail="Add an OpenAI API key before testing models.",
        )

    client = api_key_service.get_openai_client_for_user(user["id"])

    # --- Text model: cheapest possible call ---
    # Try max_completion_tokens first (required by gpt-5, o-series and newer).
    # If that fails for any reason, retry with legacy max_tokens.
    # Only report failure if both attempts fail.
    # --- Text model: cheapest possible call ---
    # Don't set any token limit — 1 token causes some models to 400 saying
    # they couldn't finish. We only care that the API accepts the request.
    text_ok = False
    text_error: Optional[str] = None
    _model = payload.text_model.strip()
    try:
        client.chat.completions.create(
            model=_model,
            messages=[{"role": "user", "content": "Hi"}],
        )
        text_ok = True
    except Exception as exc:
        text_error = _extract_openai_error(exc)

    # --- Audio model: shortest possible TTS input ---
    audio_ok = False
    audio_error: Optional[str] = None
    try:
        resp = client.audio.speech.create(
            model=payload.audio_model.strip(),
            voice="alloy",
            input=".",
            response_format="mp3",
        )
        # Read and immediately discard — we only care if it didn't error.
        _ = resp.content
        audio_ok = True
    except Exception as exc:
        audio_error = _extract_openai_error(exc)

    return {
        "textModel": {"ok": text_ok, "error": text_error},
        "audioModel": {"ok": audio_ok, "error": audio_error},
    }


def _extract_openai_error(exc: Exception) -> str:
    """Pull the most useful message out of an OpenAI (or generic) exception."""
    # openai SDK wraps errors in APIStatusError / APIConnectionError etc.
    msg = getattr(exc, "message", None) or str(exc)
    # Trim long stack traces that sometimes appear in the message
    return msg.split("\n")[0][:200]


@router.put("/theme")
def set_theme(payload: ThemePayload, user=Depends(get_current_user)):
    try:
        user_service.set_user_theme(user["id"], payload.theme)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "ok", "theme": payload.theme}


@router.put("/models")
def set_model_preferences(payload: ModelPrefsPayload, user=Depends(get_current_user)):
    user_service.set_user_models(
        user["id"],
        text_model=payload.text_model,
        audio_model=payload.audio_model,
    )
    return {"status": "ok"}


@router.post("/emails")
def add_email(payload: EmailPayload, user=Depends(get_current_user)):
    try:
        user_service.add_user_email(
            user["id"], payload.email, make_primary=payload.make_primary
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    emails = user_service.list_user_emails(user["id"])
    return {"status": "ok", "emails": emails}


@router.delete("/emails/{email_id}")
def delete_email(email_id: str, user=Depends(get_current_user)):
    email_uuid = parse_uuid(email_id, entity="Email")
    try:
        user_service.remove_user_email(user["id"], email_uuid)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    emails = user_service.list_user_emails(user["id"])
    return {"status": "ok", "emails": emails}


@router.post("/emails/{email_id}/primary")
def set_primary_email(email_id: str, user=Depends(get_current_user)):
    email_uuid = parse_uuid(email_id, entity="Email")
    try:
        user_service.set_primary_email(user["id"], email_uuid)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    emails = user_service.list_user_emails(user["id"])
    return {"status": "ok", "emails": emails}


@router.delete("")
def delete_account(request: Request, user=Depends(get_current_user)):
    user_service.delete_user(user["id"])
    return {"status": "ok", "logoutUrl": _build_logout_url(request)}
