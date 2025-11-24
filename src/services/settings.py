from typing import Any, Optional

from psycopg2.extras import Json, RealDictCursor

from ..db.core import get_connection


def get_json_setting(key: str) -> Optional[dict]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT value FROM app_settings WHERE key = %s", (key,))
            row = cur.fetchone()
    if not row:
        return None
    return row["value"]


def set_json_setting(key: str, value: Any) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO app_settings (key, value)
                VALUES (%s, %s)
                ON CONFLICT (key) DO UPDATE
                SET value = EXCLUDED.value,
                    updated_at = NOW()
                """,
                (key, Json(value)),
            )
        conn.commit()
