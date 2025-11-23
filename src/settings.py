import os
from typing import List

from dotenv import load_dotenv

from .utils.admins import get_auto_admin_emails

load_dotenv()

LOCAL_USER_EMAIL = os.getenv("LOCAL_USER_EMAIL", "local@example.com")
ALLOW_LOCAL_USER = os.getenv("ALLOW_LOCAL_USER", "true").lower() in {"1", "true", "yes"}
ALWAYS_ADMIN_EMAILS = get_auto_admin_emails(LOCAL_USER_EMAIL)

NATIVE_LANGUAGE_OPTIONS = ["English"]
TARGET_LANGUAGE_OPTIONS = ["Danish", "Hungarian"]

DEFAULT_FRONTEND_ORIGINS = ["http://localhost:5173"]
FRONTEND_ORIGINS: List[str] = [
    origin.strip()
    for origin in os.getenv("FRONTEND_ORIGINS", "").split(",")
    if origin.strip()
]
if not FRONTEND_ORIGINS:
    FRONTEND_ORIGINS = DEFAULT_FRONTEND_ORIGINS
