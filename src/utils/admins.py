import os
from functools import lru_cache
from typing import Optional, Set


@lru_cache(maxsize=1)
def get_auto_admin_emails(local_user_email: Optional[str] = None) -> Set[str]:
    """
    Returns the set of email addresses that should always retain admin privileges.
    """
    emails: Set[str] = set()
    default_admin = os.getenv("LOCAL_ALWAYS_ADMIN_EMAIL", "local@example.com")
    for raw in (local_user_email, default_admin):
        if raw:
            emails.add(raw.strip().lower())
    extra = os.getenv("ADDITIONAL_ADMIN_EMAILS", "")
    if extra:
        for entry in extra.split(","):
            entry = entry.strip().lower()
            if entry:
                emails.add(entry)
    return emails
