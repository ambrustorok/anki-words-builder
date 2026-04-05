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

_AUDIO_MODEL_HINTS = ("tts",)
_EXCLUDE_HINTS = (
    "tts", "realtime", "transcribe", "whisper",
    "dall", "embedding", "search", "audio-preview",
)


class APIKeyPayload(BaseModel):
    api_key: str = Field(..., alias="apiKey")


class EmailPayload(BaseModel):
    email: str
    make_primary: bool = Field(False, alias="makePrimary")


class ModelPrefsPayload(BaseModel):
    text_model: Optional[str] = Field(None, alias="textModel")
    audio_model: Optional[str] = Field(None, alias="audioModel")


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
    if not api_key_service.user_can_generate(user["id"]):
        raise HTTPException(
            status_code=400,
            detail="Add an OpenAI API key on your profile before selecting a model.",
        )
    try:
        client = api_key_service.get_openai_client_for_user(user["id"])
        all_models = client.models.list()
        model_ids = sorted(
            (m.id for m in all_models.data),
            key=lambda x: x.lower(),
        )
    except Exception as exc:
        logger.warning("Failed to fetch OpenAI model list: %s", exc)
        raise HTTPException(
            status_code=502, detail="Could not retrieve model list from OpenAI."
        ) from exc

    text_models = [
        m for m in model_ids
        if not any(hint in m.lower() for hint in _EXCLUDE_HINTS)
        and ("gpt" in m.lower() or m.lower().startswith("o1") or m.lower().startswith("o3") or m.lower().startswith("o4"))
    ]
    audio_models = [
        m for m in model_ids
        if any(hint in m.lower() for hint in _AUDIO_MODEL_HINTS)
    ]

    return {
        "textModels": text_models,
        "audioModels": audio_models,
        "defaultTextModel": OPENAI_MODEL,
        "defaultAudioModel": "gpt-4o-mini-tts",
    }


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
        user_service.add_user_email(user["id"], payload.email, make_primary=payload.make_primary)
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
