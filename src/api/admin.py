import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ..services import api_keys as api_key_service
from ..services import app_settings as app_settings_service
from ..services import decks as deck_service
from ..services import users as user_service
from ..settings import ALWAYS_ADMIN_EMAILS, NATIVE_LANGUAGE_OPTIONS
from .dependencies import get_current_user, parse_uuid, require_admin
from .profile import (
    DEFAULT_AUDIO_MODEL,
    _AUDIO_INCLUDE,
    _FALLBACK_AUDIO_MODELS,
    _FALLBACK_TEXT_MODELS,
    _TEXT_EXCLUDE,
    _TEXT_INCLUDE,
    _extract_openai_error,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin")


class AdminEmailPayload(BaseModel):
    email: str
    make_primary: bool = Field(False, alias="makePrimary")


class AdminEmailUpdatePayload(BaseModel):
    email: str


class AdminTogglePayload(BaseModel):
    make_admin: bool = Field(..., alias="makeAdmin")


class PromptTemplatePayload(BaseModel):
    prompt_templates: dict = Field(..., alias="promptTemplates")


class AdminApiKeyPayload(BaseModel):
    api_key: str = Field(..., alias="apiKey")


class AdminUserSettingsPayload(BaseModel):
    text_model: Optional[str] = Field(None, alias="textModel")
    audio_model: Optional[str] = Field(None, alias="audioModel")
    native_language: Optional[str] = Field(None, alias="nativeLanguage")
    theme: Optional[str] = None
    models_locked: Optional[bool] = Field(None, alias="modelsLocked")


class AdminModelTestPayload(BaseModel):
    text_model: str = Field(..., alias="textModel")
    audio_model: str = Field(..., alias="audioModel")


class SystemSettingsPayload(BaseModel):
    openai_api_base: Optional[str] = Field(None, alias="openaiApiBase")


@router.get("/users")
def list_users(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    user=Depends(require_admin),
):
    result = user_service.list_all_users(page=page, limit=limit)
    return {
        **result,
        "protectedEmails": list(ALWAYS_ADMIN_EMAILS),
    }


@router.get("/users/{user_id}")
def user_detail(user_id: str, user=Depends(require_admin)):
    user_uuid = parse_uuid(user_id, entity="User")
    managed = user_service.get_user(user_uuid)
    if not managed:
        raise HTTPException(status_code=404, detail="User not found.")
    emails = user_service.list_user_emails(user_uuid)
    return {
        "user": managed,
        "emails": emails,
        "protectedEmails": list(ALWAYS_ADMIN_EMAILS),
        "apiKey": api_key_service.get_api_key_summary(user_uuid),
    }


@router.delete("/users/{user_id}")
def delete_user(user_id: str, user=Depends(require_admin)):
    user_uuid = parse_uuid(user_id, entity="User")
    managed = user_service.get_user(user_uuid)
    if not managed:
        raise HTTPException(status_code=404, detail="User not found.")
    primary = (managed.get("primary_email") or "").lower()
    if primary and primary in ALWAYS_ADMIN_EMAILS:
        raise HTTPException(
            status_code=400, detail="Cannot delete a protected admin profile."
        )
    user_service.delete_user(user_uuid)
    return {"status": "ok"}


@router.post("/users/{user_id}/emails")
def add_user_email(
    user_id: str, payload: AdminEmailPayload, user=Depends(require_admin)
):
    user_uuid = parse_uuid(user_id, entity="User")
    if not user_service.get_user(user_uuid):
        raise HTTPException(status_code=404, detail="User not found.")
    try:
        user_service.add_user_email(
            user_uuid, payload.email, make_primary=payload.make_primary
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    emails = user_service.list_user_emails(user_uuid)
    return {"status": "ok", "emails": emails}


@router.patch("/users/{user_id}/emails/{email_id}")
def update_user_email(
    user_id: str,
    email_id: str,
    payload: AdminEmailUpdatePayload,
    user=Depends(require_admin),
):
    user_uuid = parse_uuid(user_id, entity="User")
    email_uuid = parse_uuid(email_id, entity="Email")
    try:
        user_service.update_user_email(email_uuid, payload.email)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    managed = user_service.get_user(user_uuid)
    emails = user_service.list_user_emails(user_uuid)
    return {"status": "ok", "user": managed, "emails": emails}


@router.delete("/users/{user_id}/emails/{email_id}")
def delete_user_email(user_id: str, email_id: str, user=Depends(require_admin)):
    user_uuid = parse_uuid(user_id, entity="User")
    email_uuid = parse_uuid(email_id, entity="Email")
    try:
        user_service.remove_user_email(user_uuid, email_uuid)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    emails = user_service.list_user_emails(user_uuid)
    return {"status": "ok", "emails": emails}


@router.post("/users/{user_id}/emails/{email_id}/primary")
def set_primary_email(user_id: str, email_id: str, user=Depends(require_admin)):
    user_uuid = parse_uuid(user_id, entity="User")
    email_uuid = parse_uuid(email_id, entity="Email")
    try:
        user_service.set_primary_email(user_uuid, email_uuid)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    emails = user_service.list_user_emails(user_uuid)
    return {"status": "ok", "emails": emails}


@router.post("/users/{user_id}/admin")
def toggle_admin(
    user_id: str, payload: AdminTogglePayload, user=Depends(require_admin)
):
    user_uuid = parse_uuid(user_id, entity="User")
    managed = user_service.get_user(user_uuid)
    if not managed:
        raise HTTPException(status_code=404, detail="User not found.")
    primary = (managed.get("primary_email") or "").lower()
    if primary and primary in ALWAYS_ADMIN_EMAILS and not payload.make_admin:
        raise HTTPException(
            status_code=400, detail="Cannot revoke admin from a protected account."
        )
    user_service.set_admin_status(user_uuid, payload.make_admin)
    updated = user_service.get_user(user_uuid)
    return {"status": "ok", "user": updated}


@router.post("/users/{user_id}/api-key")
def set_user_api_key(
    user_id: str, payload: AdminApiKeyPayload, user=Depends(require_admin)
):
    user_uuid = parse_uuid(user_id, entity="User")
    managed = user_service.get_user(user_uuid)
    if not managed:
        raise HTTPException(status_code=404, detail="User not found.")
    key = payload.api_key.strip()
    if not key:
        raise HTTPException(status_code=400, detail="API key cannot be empty.")
    api_key_service.set_user_api_key(user_uuid, key)
    return {"status": "ok", "apiKey": api_key_service.get_api_key_summary(user_uuid)}


@router.delete("/users/{user_id}/api-key")
def delete_user_api_key(user_id: str, user=Depends(require_admin)):
    user_uuid = parse_uuid(user_id, entity="User")
    managed = user_service.get_user(user_uuid)
    if not managed:
        raise HTTPException(status_code=404, detail="User not found.")
    api_key_service.delete_user_api_key(user_uuid)
    return {"status": "ok", "apiKey": api_key_service.get_api_key_summary(user_uuid)}


@router.put("/users/{user_id}/settings")
def update_user_settings(
    user_id: str, payload: AdminUserSettingsPayload, user=Depends(require_admin)
):
    user_uuid = parse_uuid(user_id, entity="User")
    managed = user_service.get_user(user_uuid)
    if not managed:
        raise HTTPException(status_code=404, detail="User not found.")

    if payload.native_language is not None:
        lang = payload.native_language.strip()
        if lang and lang not in NATIVE_LANGUAGE_OPTIONS:
            raise HTTPException(status_code=400, detail="Unsupported native language.")
        if lang:
            user_service.set_native_language(user_uuid, lang)

    if payload.theme is not None:
        try:
            user_service.set_user_theme(user_uuid, payload.theme)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    if payload.text_model is not None or payload.audio_model is not None:
        user_service.set_user_models(
            user_uuid,
            text_model=payload.text_model,
            audio_model=payload.audio_model,
        )

    if payload.models_locked is not None:
        user_service.set_models_locked(user_uuid, payload.models_locked)

    updated = user_service.get_user(user_uuid)
    return {"status": "ok", "user": updated}


@router.get("/users/{user_id}/models/available")
def user_available_models(user_id: str, user=Depends(require_admin)):
    """Return available models using the managed user's API key."""
    from ..settings import OPENAI_MODEL

    user_uuid = parse_uuid(user_id, entity="User")
    if not user_service.get_user(user_uuid):
        raise HTTPException(status_code=404, detail="User not found.")

    def _is_text(mid: str) -> bool:
        m = mid.lower()
        return any(m.startswith(i) or i in m for i in _TEXT_INCLUDE) and not any(
            e in m for e in _TEXT_EXCLUDE
        )

    def _is_audio(mid: str) -> bool:
        return any(i in mid.lower() for i in _AUDIO_INCLUDE)

    if not api_key_service.user_can_generate(user_uuid):
        return {
            "textModels": list(_FALLBACK_TEXT_MODELS),
            "audioModels": list(_FALLBACK_AUDIO_MODELS),
            "defaultTextModel": OPENAI_MODEL,
            "defaultAudioModel": DEFAULT_AUDIO_MODEL,
        }

    try:
        client = api_key_service.get_openai_client_for_user(user_uuid)
        all_ids = sorted((m.id for m in client.models.list().data), key=str.lower)
    except Exception as exc:
        logger.warning("Could not fetch model list for user %s: %s", user_id, exc)
        return {
            "textModels": list(_FALLBACK_TEXT_MODELS),
            "audioModels": list(_FALLBACK_AUDIO_MODELS),
            "defaultTextModel": OPENAI_MODEL,
            "defaultAudioModel": DEFAULT_AUDIO_MODEL,
        }

    text_models = [m for m in all_ids if _is_text(m)]
    audio_models = [m for m in all_ids if _is_audio(m)]
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


@router.post("/users/{user_id}/models/test")
def test_user_models(
    user_id: str, payload: AdminModelTestPayload, user=Depends(require_admin)
):
    """Test models using the managed user's API key."""
    user_uuid = parse_uuid(user_id, entity="User")
    if not user_service.get_user(user_uuid):
        raise HTTPException(status_code=404, detail="User not found.")
    if not api_key_service.user_can_generate(user_uuid):
        raise HTTPException(
            status_code=400,
            detail="This user has no API key. Grant one first.",
        )

    client = api_key_service.get_openai_client_for_user(user_uuid)

    text_ok = False
    text_error: Optional[str] = None
    try:
        client.chat.completions.create(
            model=payload.text_model.strip(),
            messages=[{"role": "user", "content": "Hi"}],
            max_completion_tokens=10,
        )
        text_ok = True
    except Exception as exc:
        text_error = _extract_openai_error(exc)

    audio_ok = False
    audio_error: Optional[str] = None
    try:
        resp = client.audio.speech.create(
            model=payload.audio_model.strip(),
            voice="alloy",
            input=".",
            response_format="mp3",
        )
        _ = resp.content
        audio_ok = True
    except Exception as exc:
        audio_error = _extract_openai_error(exc)

    return {
        "textModel": {"ok": text_ok, "error": text_error},
        "audioModel": {"ok": audio_ok, "error": audio_error},
    }


@router.get("/default-prompts")
def get_default_prompts(user=Depends(require_admin)):
    prompts = deck_service.default_prompt_templates()
    return {"promptTemplates": prompts}


@router.put("/default-prompts")
def update_default_prompts(payload: PromptTemplatePayload, user=Depends(require_admin)):
    prompts = deck_service.update_default_prompt_templates(payload.prompt_templates)
    return {"promptTemplates": prompts}


@router.get("/system-settings")
def get_system_settings(user=Depends(require_admin)):
    return {
        "openaiApiBase": app_settings_service.get_openai_api_base() or "",
    }


@router.put("/system-settings")
def update_system_settings(payload: SystemSettingsPayload, user=Depends(require_admin)):
    url = (payload.openai_api_base or "").strip()
    # Basic validation — must be empty or a plausible URL
    if url and not url.startswith(("http://", "https://")):
        raise HTTPException(
            status_code=400,
            detail="API base URL must start with http:// or https://, or be empty to use the default.",
        )
    app_settings_service.set_openai_api_base(url or None)
    return {"openaiApiBase": url}
