import logging
import os
import uuid
from typing import Optional

from openai import OpenAI
from psycopg2.extras import RealDictCursor

from ..db.core import get_connection
from ..utils.encryption import decrypt, encrypt

logger = logging.getLogger(__name__)

SYSTEM_OPENAI_KEY = os.getenv("OPENAI_API_KEY")


def _uuid(value: uuid.UUID) -> str:
    return str(value)


def get_user_api_key(user_id: uuid.UUID, provider: str = "openai") -> Optional[str]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, key_ciphertext
                FROM user_api_keys
                WHERE user_id = %s AND provider = %s
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (_uuid(user_id), provider),
            )
            row = cur.fetchone()
            if not row:
                return None
            raw = row["key_ciphertext"]
            if not raw:
                return None
            # Update last_used_at
            cur.execute(
                "UPDATE user_api_keys SET last_used_at = NOW() WHERE id = %s",
                (str(row["id"]),),
            )
        conn.commit()
    try:
        return decrypt(raw)
    except ValueError:
        logger.warning(
            "API key for user %s is stored as plaintext; it will be re-encrypted on next save.",
            user_id,
        )
        return raw


def set_user_api_key(user_id: uuid.UUID, api_key: str, provider: str = "openai"):
    ciphertext = encrypt(api_key.strip())
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM user_api_keys
                WHERE user_id = %s AND provider = %s
                """,
                (_uuid(user_id), provider),
            )
            cur.execute(
                """
                INSERT INTO user_api_keys (id, user_id, provider, key_ciphertext)
                VALUES (%s, %s, %s, %s)
                """,
                (str(uuid.uuid4()), _uuid(user_id), provider, ciphertext),
            )
        conn.commit()


def delete_user_api_key(user_id: uuid.UUID, provider: str = "openai"):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM user_api_keys
                WHERE user_id = %s AND provider = %s
                """,
                (_uuid(user_id), provider),
            )
        conn.commit()


class MissingAPIKeyError(RuntimeError):
    pass


def has_system_api_key() -> bool:
    return bool(SYSTEM_OPENAI_KEY)


def user_can_generate(user_id: uuid.UUID) -> bool:
    return bool(get_user_api_key(user_id)) or has_system_api_key()


def get_openai_client_for_user(user_id: uuid.UUID) -> OpenAI:
    user_key = get_user_api_key(user_id)
    if user_key:
        return OpenAI(api_key=user_key)
    if SYSTEM_OPENAI_KEY:
        return OpenAI(api_key=SYSTEM_OPENAI_KEY)
    raise MissingAPIKeyError(
        "No OpenAI API key configured. Add one on the profile page."
    )


def get_api_key_summary(user_id: uuid.UUID) -> dict:
    key = get_user_api_key(user_id)
    if not key:
        return {"has_key": False}
    masked = f"...{key[-4:]}" if len(key) > 4 else "****"
    return {"has_key": True, "masked": masked}
