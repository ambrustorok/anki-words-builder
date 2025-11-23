import uuid
from typing import Iterable, Optional

from fastapi import Depends, HTTPException, Request

from ..services import users as user_service
from ..settings import ALLOW_LOCAL_USER, LOCAL_USER_EMAIL, ALWAYS_ADMIN_EMAILS


def get_authenticated_email(request: Request) -> str:
    header_email = request.headers.get("Cf-Access-Authenticated-User-Email")
    if header_email:
        return header_email
    if ALLOW_LOCAL_USER:
        return LOCAL_USER_EMAIL
    raise HTTPException(status_code=401, detail="Missing Cloudflare authentication header.")


def get_current_user(request: Request, email: str = Depends(get_authenticated_email)):
    user = user_service.ensure_user(email, auto_admin_emails=ALWAYS_ADMIN_EMAILS)
    request.state.user = user
    return user


def require_admin(user=Depends(get_current_user)):
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required.")
    return user


def parse_uuid(value: str, *, entity: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(value))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=f"{entity} not found") from exc
