from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from ..services import api_keys as api_key_service
from ..services import cards as card_service
from ..services import decks as deck_service
from ..services import users as user_service
from ..settings import (
    NATIVE_LANGUAGE_OPTIONS,
    TARGET_LANGUAGE_OPTIONS,
)
from .dependencies import get_current_user

router = APIRouter(prefix="/session")


def _build_logout_url(request: Request) -> str:
    origin = request.headers.get("Origin")
    if origin:
        return f"{origin.rstrip('/')}/cdn-cgi/access/logout"

    forwarded_host = request.headers.get("X-Forwarded-Host")
    forwarded_proto = request.headers.get("X-Forwarded-Proto", request.url.scheme)
    if forwarded_host:
        base = f"{forwarded_proto}://{forwarded_host}"
        return f"{base.rstrip('/')}/cdn-cgi/access/logout"

    base = f"{request.url.scheme}://{request.url.netloc}"
    return f"{base}/cdn-cgi/access/logout"


class NativeLanguagePayload(BaseModel):
    native_language: str = Field(..., alias="nativeLanguage")


@router.get("")
def session_info(request: Request, user=Depends(get_current_user)):
    fresh_user = user_service.get_user(user["id"]) or user
    return {
        "user": {
            "id": str(fresh_user["id"]),
            "nativeLanguage": fresh_user.get("native_language"),
            "primaryEmail": fresh_user.get("primary_email"),
            "isAdmin": bool(fresh_user.get("is_admin")),
        },
        "logoutUrl": _build_logout_url(request),
        "canGenerate": api_key_service.user_can_generate(user["id"]),
        "needsOnboarding": not bool(fresh_user.get("native_language")),
        "nativeLanguageOptions": NATIVE_LANGUAGE_OPTIONS,
        "targetLanguageOptions": TARGET_LANGUAGE_OPTIONS,
    }


@router.post("/native-language")
def set_native_language(payload: NativeLanguagePayload, user=Depends(get_current_user)):
    language = payload.native_language.strip()
    if language not in NATIVE_LANGUAGE_OPTIONS:
        raise HTTPException(status_code=400, detail="Unsupported native language.")
    user_service.set_native_language(user["id"], language)
    updated = user_service.get_user(user["id"]) or user
    return {
        "status": "ok",
        "user": {
            "id": str(updated["id"]),
            "nativeLanguage": updated.get("native_language"),
            "primaryEmail": updated.get("primary_email"),
            "isAdmin": bool(updated.get("is_admin")),
        },
    }


@router.get("/overview")
def dashboard_overview(user=Depends(get_current_user)):
    requires_onboarding = not bool(user.get("native_language"))
    stale_decks = deck_service.list_least_recent_decks(user["id"], limit=3)
    recent_cards = card_service.list_recent_cards(
        user["id"],
        user.get("native_language"),
        limit=4,
    )
    return {
        "requiresOnboarding": requires_onboarding,
        "staleDecks": stale_decks,
        "recentEntries": recent_cards,
    }
