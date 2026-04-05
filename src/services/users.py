import re
import uuid
from typing import Iterable, List, Optional

from psycopg2.extras import RealDictCursor

from ..db.core import get_connection

_EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,253}\.[^@.\s]{2,}$")


def _uuid(value: uuid.UUID) -> str:
    return str(value)


def ensure_user(email: str, auto_admin_emails: Optional[Iterable[str]] = None) -> dict:
    """
    Look up (or create) the user associated with the given email.
    Returns a dict containing id, native_language, primary_email.
    """
    normalized_email = email.strip().lower()
    auto_admin = {item.strip().lower() for item in (auto_admin_emails or []) if item}
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT u.id, u.native_language, u.created_at, u.is_admin,
                       u.text_model, u.audio_model, u.theme,
                       ue.email AS primary_email
                FROM user_emails ue
                JOIN users u ON u.id = ue.user_id
                WHERE LOWER(ue.email) = %s
                """,
                (normalized_email,),
            )
            row = cur.fetchone()
            if row:
                user = {
                    "id": row["id"],
                    "native_language": row["native_language"],
                    "primary_email": row["primary_email"],
                    "is_admin": row["is_admin"],
                    "text_model": row.get("text_model"),
                    "audio_model": row.get("audio_model"),
                    "theme": row.get("theme") or "system",
                }
                should_be_admin = normalized_email in auto_admin
                if should_be_admin and not row["is_admin"]:
                    cur.execute(
                        "UPDATE users SET is_admin = TRUE WHERE id = %s",
                        (_uuid(row["id"]),),
                    )
                    user["is_admin"] = True
                    conn.commit()
                return user

            user_id = uuid.uuid4()
            email_id = uuid.uuid4()
            is_admin = normalized_email in auto_admin
            cur.execute(
                """
                INSERT INTO users (id, is_admin)
                VALUES (%s, %s)
                """,
                (_uuid(user_id), is_admin),
            )
            cur.execute(
                """
                INSERT INTO user_emails (id, user_id, email, is_primary)
                VALUES (%s, %s, %s, TRUE)
                """,
                (_uuid(email_id), _uuid(user_id), normalized_email),
            )
            conn.commit()
            return {
                "id": user_id,
                "native_language": None,
                "primary_email": normalized_email,
                "is_admin": is_admin,
                "text_model": None,
                "audio_model": None,
                "theme": "system",
            }


def set_native_language(user_id: uuid.UUID, language: str):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET native_language = %s WHERE id = %s",
                (language.strip(), _uuid(user_id)),
            )
        conn.commit()


def get_user(user_id: uuid.UUID) -> Optional[dict]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT u.id, u.native_language, u.is_admin,
                       u.text_model, u.audio_model, u.theme,
                       ue.email AS primary_email
                FROM users u
                LEFT JOIN user_emails ue ON ue.user_id = u.id AND ue.is_primary = TRUE
                WHERE u.id = %s
                """,
                (_uuid(user_id),),
            )
            row = cur.fetchone()
            if not row:
                return None
            return {
                "id": row["id"],
                "native_language": row["native_language"],
                "primary_email": row.get("primary_email"),
                "is_admin": row["is_admin"],
                "text_model": row.get("text_model"),
                "audio_model": row.get("audio_model"),
                "theme": row.get("theme") or "system",
            }


def set_user_theme(user_id: uuid.UUID, theme: str) -> None:
    if theme not in ("light", "dark", "system"):
        raise ValueError("theme must be 'light', 'dark', or 'system'.")
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET theme = %s WHERE id = %s",
                (theme, _uuid(user_id)),
            )
        conn.commit()


def set_user_models(
    user_id: uuid.UUID,
    *,
    text_model: Optional[str] = None,
    audio_model: Optional[str] = None,
) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE users
                SET text_model  = COALESCE(%s, text_model),
                    audio_model = COALESCE(%s, audio_model)
                WHERE id = %s
                """,
                (text_model or None, audio_model or None, _uuid(user_id)),
            )
        conn.commit()


def list_user_emails(user_id: uuid.UUID) -> List[dict]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, email, is_primary, created_at
                FROM user_emails
                WHERE user_id = %s
                ORDER BY is_primary DESC, created_at ASC
                """,
                (_uuid(user_id),),
            )
            rows = cur.fetchall()
    return rows


def add_user_email(user_id: uuid.UUID, email: str, *, make_primary: bool = False):
    normalized = (email or "").strip().lower()
    if not normalized or not _EMAIL_RE.match(normalized):
        raise ValueError("Enter a valid email address.")
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT 1 FROM user_emails WHERE LOWER(email) = %s
                """,
                (normalized,),
            )
            if cur.fetchone():
                raise ValueError("That email is already linked to an account.")
            email_id = str(uuid.uuid4())
            cur.execute(
                """
                INSERT INTO user_emails (id, user_id, email, is_primary)
                VALUES (%s, %s, %s, FALSE)
                """,
                (email_id, _uuid(user_id), normalized),
            )
            if make_primary:
                cur.execute(
                    "UPDATE user_emails SET is_primary = FALSE WHERE user_id = %s",
                    (_uuid(user_id),),
                )
                cur.execute(
                    "UPDATE user_emails SET is_primary = TRUE WHERE id = %s",
                    (email_id,),
                )
        conn.commit()


def remove_user_email(user_id: uuid.UUID, email_id: uuid.UUID):
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, is_primary
                FROM user_emails
                WHERE user_id = %s AND id = %s
                """,
                (_uuid(user_id), _uuid(email_id)),
            )
            row = cur.fetchone()
            if not row:
                raise ValueError("Email not found.")
            if row["is_primary"]:
                raise ValueError("Cannot remove the primary email.")
            cur.execute(
                "DELETE FROM user_emails WHERE id = %s",
                (_uuid(email_id),),
            )
        conn.commit()


def set_primary_email(user_id: uuid.UUID, email_id: uuid.UUID):
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id FROM user_emails
                WHERE user_id = %s AND id = %s
                """,
                (_uuid(user_id), _uuid(email_id)),
            )
            row = cur.fetchone()
            if not row:
                raise ValueError("Email not found.")
            cur.execute(
                "UPDATE user_emails SET is_primary = FALSE WHERE user_id = %s",
                (_uuid(user_id),),
            )
            cur.execute(
                "UPDATE user_emails SET is_primary = TRUE WHERE id = %s",
                (_uuid(email_id),),
            )
        conn.commit()


def delete_user(user_id: uuid.UUID) -> bool:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM users WHERE id = %s", (_uuid(user_id),))
            deleted = cur.rowcount > 0
        conn.commit()
    return deleted


def set_admin_status(user_id: uuid.UUID, is_admin: bool):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET is_admin = %s WHERE id = %s",
                (is_admin, _uuid(user_id)),
            )
        conn.commit()


def list_all_users(page: int = 1, limit: int = 50) -> dict:
    offset = (page - 1) * limit
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT COUNT(*) AS total FROM users WHERE deleted_at IS NULL")
            total = cur.fetchone()["total"]
            cur.execute(
                """
                SELECT
                    u.id,
                    u.native_language,
                    u.is_admin,
                    u.created_at,
                    (SELECT email FROM user_emails WHERE user_id = u.id AND is_primary = TRUE LIMIT 1) AS primary_email,
                    COUNT(ue.id) AS email_count
                FROM users u
                LEFT JOIN user_emails ue ON ue.user_id = u.id
                WHERE u.deleted_at IS NULL
                GROUP BY u.id
                ORDER BY u.created_at DESC
                LIMIT %s OFFSET %s
                """,
                (limit, offset),
            )
            rows = cur.fetchall()
    import math

    return {
        "users": rows,
        "total": total,
        "page": page,
        "limit": limit,
        "pages": math.ceil(total / limit) if limit > 0 else 1,
    }


def get_user_by_email(email: str) -> Optional[dict]:
    normalized = (email or "").strip().lower()
    if not normalized:
        return None
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT u.id, u.native_language, u.is_admin, ue.email AS primary_email
                FROM user_emails ue
                JOIN users u ON u.id = ue.user_id
                WHERE LOWER(ue.email) = %s
                """,
                (normalized,),
            )
            row = cur.fetchone()
            if not row:
                return None
    return {
        "id": row["id"],
        "native_language": row["native_language"],
        "primary_email": row["primary_email"],
        "is_admin": row["is_admin"],
    }


def update_user_email(email_id: uuid.UUID, new_email: str):
    normalized = (new_email or "").strip().lower()
    if not normalized or not _EMAIL_RE.match(normalized):
        raise ValueError("Enter a valid email address.")
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT user_id FROM user_emails WHERE id = %s",
                (_uuid(email_id),),
            )
            row = cur.fetchone()
            if not row:
                raise ValueError("Email not found.")
            cur.execute(
                "SELECT 1 FROM user_emails WHERE LOWER(email) = %s AND id <> %s",
                (normalized, _uuid(email_id)),
            )
            if cur.fetchone():
                raise ValueError("That email is already linked to an account.")
            cur.execute(
                "UPDATE user_emails SET email = %s WHERE id = %s",
                (normalized, _uuid(email_id)),
            )
        conn.commit()
