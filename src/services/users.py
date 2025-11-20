import uuid
from typing import List, Optional

from psycopg2.extras import RealDictCursor

from ..db.core import get_connection


def _uuid(value: uuid.UUID) -> str:
    return str(value)


def ensure_user(email: str) -> dict:
    """
    Look up (or create) the user associated with the given email.
    Returns a dict containing id, native_language, primary_email.
    """
    normalized_email = email.strip().lower()
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT u.id, u.native_language, u.created_at, ue.email AS primary_email
                FROM user_emails ue
                JOIN users u ON u.id = ue.user_id
                WHERE LOWER(ue.email) = %s
                """,
                (normalized_email,),
            )
            row = cur.fetchone()
            if row:
                return {
                    "id": row["id"],
                    "native_language": row["native_language"],
                    "primary_email": row["primary_email"],
                }

            user_id = uuid.uuid4()
            email_id = uuid.uuid4()
            cur.execute(
                """
                INSERT INTO users (id)
                VALUES (%s)
                """,
                (_uuid(user_id),),
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
                SELECT u.id, u.native_language, ue.email AS primary_email
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
            }


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


def add_user_email(user_id: uuid.UUID, email: str):
    normalized = (email or "").strip().lower()
    if not normalized or "@" not in normalized:
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
            cur.execute(
                """
                INSERT INTO user_emails (id, user_id, email, is_primary)
                VALUES (%s, %s, %s, FALSE)
                """,
                (str(uuid.uuid4()), _uuid(user_id), normalized),
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
