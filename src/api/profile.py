from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from ..services import api_keys as api_key_service
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
