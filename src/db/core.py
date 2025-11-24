import uuid
from contextlib import contextmanager

import psycopg2
from psycopg2.extras import RealDictCursor

from ..settings import POSTGRES_DB, POSTGRES_HOST, POSTGRES_PASSWORD, POSTGRES_PORT, POSTGRES_USER


@contextmanager
def get_connection():
    conn = psycopg2.connect(
        host=POSTGRES_HOST,
        database=POSTGRES_DB,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
        port=POSTGRES_PORT,
    )
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    """
    Create the core tables required for multi-user FastAPI flows.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            # Users + emails
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id UUID PRIMARY KEY,
                    native_language TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    deleted_at TIMESTAMPTZ,
                    is_admin BOOLEAN NOT NULL DEFAULT FALSE
                )
                """
            )
            cur.execute(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_admin BOOLEAN NOT NULL DEFAULT FALSE"
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS user_emails (
                    id UUID PRIMARY KEY,
                    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    email TEXT NOT NULL UNIQUE,
                    is_primary BOOLEAN NOT NULL DEFAULT FALSE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )

            # API keys
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS user_api_keys (
                    id UUID PRIMARY KEY,
                    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    provider TEXT NOT NULL,
                    key_ciphertext TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    last_used_at TIMESTAMPTZ
                )
                """
            )

            # Decks
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS decks (
                    id UUID PRIMARY KEY,
                    owner_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    name TEXT NOT NULL,
                    target_language TEXT NOT NULL,
                    field_schema JSONB NOT NULL DEFAULT '[]'::jsonb,
                    prompt_templates JSONB NOT NULL DEFAULT '{}'::jsonb,
                    is_shared BOOLEAN NOT NULL DEFAULT FALSE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            cur.execute(
                "ALTER TABLE decks ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()"
            )

            # Cards
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS cards (
                    id UUID PRIMARY KEY,
                    deck_id UUID NOT NULL REFERENCES decks(id) ON DELETE CASCADE,
                    owner_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    direction TEXT NOT NULL CHECK (direction IN ('forward','backward')),
                    payload JSONB NOT NULL,
                    front_audio BYTEA,
                    back_audio BYTEA,
                    audio_filename TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            cur.execute(
                "ALTER TABLE cards ADD COLUMN IF NOT EXISTS front_audio BYTEA"
            )
            cur.execute(
                "ALTER TABLE cards ADD COLUMN IF NOT EXISTS back_audio BYTEA"
            )
            cur.execute(
                "ALTER TABLE cards ADD COLUMN IF NOT EXISTS audio_filename TEXT"
            )
            cur.execute(
                "ALTER TABLE cards ADD COLUMN IF NOT EXISTS card_group_id UUID"
            )
            cur.execute(
                "ALTER TABLE cards ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()"
            )
            cur.execute(
                """
                UPDATE cards
                SET card_group_id = id
                WHERE card_group_id IS NULL
                """
            )

            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_user_emails_user_id ON user_emails (user_id)"
            )
            cur.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_user_emails_email ON user_emails (LOWER(email))"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_decks_owner ON decks (owner_id)"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_cards_owner ON cards (owner_id, created_at DESC)"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_cards_deck ON cards (deck_id, created_at DESC)"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_cards_group ON cards (card_group_id)"
            )

            # App-level settings
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS app_settings (
                    key TEXT PRIMARY KEY,
                    value JSONB NOT NULL DEFAULT '{}'::jsonb,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )

            conn.commit()
