from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..services import users as user_service
from ..settings import ALWAYS_ADMIN_EMAILS
from .dependencies import get_current_user, parse_uuid, require_admin

router = APIRouter(prefix="/admin")


class AdminEmailPayload(BaseModel):
    email: str
    make_primary: bool = Field(False, alias="makePrimary")


class AdminEmailUpdatePayload(BaseModel):
    email: str


class AdminTogglePayload(BaseModel):
    make_admin: bool = Field(..., alias="makeAdmin")


@router.get("/users")
def list_users(user=Depends(require_admin)):
    users = user_service.list_all_users()
    return {"users": users, "protectedEmails": list(ALWAYS_ADMIN_EMAILS)}


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
    }


@router.delete("/users/{user_id}")
def delete_user(user_id: str, user=Depends(require_admin)):
    user_uuid = parse_uuid(user_id, entity="User")
    managed = user_service.get_user(user_uuid)
    if not managed:
        raise HTTPException(status_code=404, detail="User not found.")
    primary = (managed.get("primary_email") or "").lower()
    if primary and primary in ALWAYS_ADMIN_EMAILS:
        raise HTTPException(status_code=400, detail="Cannot delete a protected admin profile.")
    user_service.delete_user(user_uuid)
    return {"status": "ok"}


@router.post("/users/{user_id}/emails")
def add_user_email(user_id: str, payload: AdminEmailPayload, user=Depends(require_admin)):
    user_uuid = parse_uuid(user_id, entity="User")
    if not user_service.get_user(user_uuid):
        raise HTTPException(status_code=404, detail="User not found.")
    try:
        user_service.add_user_email(user_uuid, payload.email, make_primary=payload.make_primary)
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
def toggle_admin(user_id: str, payload: AdminTogglePayload, user=Depends(require_admin)):
    user_uuid = parse_uuid(user_id, entity="User")
    managed = user_service.get_user(user_uuid)
    if not managed:
        raise HTTPException(status_code=404, detail="User not found.")
    primary = (managed.get("primary_email") or "").lower()
    if primary and primary in ALWAYS_ADMIN_EMAILS and not payload.make_admin:
        raise HTTPException(status_code=400, detail="Cannot revoke admin from a protected account.")
    user_service.set_admin_status(user_uuid, payload.make_admin)
    updated = user_service.get_user(user_uuid)
    return {"status": "ok", "user": updated}
