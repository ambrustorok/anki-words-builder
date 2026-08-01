from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from ..services import api_keys as api_key_service
from ..services import models as model_service
from ..services import users as user_service
from ..settings import NATIVE_LANGUAGE_OPTIONS
from .dependencies import get_current_user, parse_uuid
from .session import _build_logout_url

router = APIRouter(prefix="/profile")


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


class NativeLanguagePayload(BaseModel):
    native_language: str = Field(..., alias="nativeLanguage")


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
            "modelsLocked": bool(fresh_user.get("models_locked")),
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


@router.put("/native-language")
def update_native_language(
    payload: NativeLanguagePayload, user=Depends(get_current_user)
):
    language = payload.native_language.strip()
    if not language:
        raise HTTPException(status_code=400, detail="Language cannot be empty.")
    if language not in NATIVE_LANGUAGE_OPTIONS:
        raise HTTPException(status_code=400, detail="Unsupported native language.")
    user_service.set_native_language(user["id"], language)
    fresh = user_service.get_user(user["id"]) or user
    return {
        "status": "ok",
        "user": {
            "id": str(fresh["id"]),
            "nativeLanguage": fresh.get("native_language"),
        },
    }


@router.get("/models/available")
def available_models(user=Depends(get_current_user)):
    return model_service.available_models(user["id"])


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

    return model_service.test_models(user["id"], payload.text_model, payload.audio_model)


@router.put("/theme")
def set_theme(payload: ThemePayload, user=Depends(get_current_user)):
    try:
        user_service.set_user_theme(user["id"], payload.theme)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "ok", "theme": payload.theme}


@router.put("/models")
def set_model_preferences(payload: ModelPrefsPayload, user=Depends(get_current_user)):
    fresh = user_service.get_user(user["id"]) or user
    if fresh.get("models_locked"):
        raise HTTPException(
            status_code=403,
            detail="Your model settings are managed by an administrator.",
        )
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
