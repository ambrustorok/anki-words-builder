"""
System-wide key/value settings stored in the app_settings table.
All values are stored as JSONB; string values are wrapped in a JSON string.
"""

from typing import Optional

from psycopg2.extras import Json, RealDictCursor

from ..db.core import get_connection

def get_openai_api_base() -> Optional[str]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT value FROM app_settings WHERE key = %s",
                ("openai_api_base",),
            )
            row = cur.fetchone()
    if not row:
        return None
    v = row["value"]
    # Stored as a JSON string — unwrap it
    if isinstance(v, str):
        return v or None
    return None


def set_openai_api_base(value: Optional[str]) -> None:
    stored = (value or "").strip()
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO app_settings (key, value, updated_at)
                VALUES (%s, %s, NOW())
                ON CONFLICT (key) DO UPDATE
                    SET value = EXCLUDED.value,
                        updated_at = NOW()
                """,
                ("openai_api_base", Json(stored)),
            )
        conn.commit()
