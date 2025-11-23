#!/usr/bin/env python
"""
One-off helper that copies data from the legacy (<=0.2.1) Postgres instance into
the current database defined in this repository.

Usage:
    uv run python scripts/import_legacy_db.py

Environment variables (all optional):
    LEGACY_POSTGRES_HOST  (default: localhost)
    LEGACY_POSTGRES_PORT  (default: 6543)
    LEGACY_POSTGRES_DB    (default: POSTGRES_DB env or "postgres")
    LEGACY_POSTGRES_USER  (default: POSTGRES_USER env)
    LEGACY_POSTGRES_PASSWORD (default: POSTGRES_PASSWORD env)
    POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD
        (fall back to the values consumed by the current app, defaults align
         with docker-compose.yaml and .env.example)
"""

from __future__ import annotations

import os
import sys
from contextlib import contextmanager
from typing import Dict, List, Tuple

import psycopg2
from dotenv import load_dotenv
from psycopg2 import sql
from psycopg2.extras import Json, RealDictCursor

load_dotenv()

LEGACY_DEFAULT_PORT = "6543"
CURRENT_DEFAULT_PORT = "7654"

TABLES: List[Tuple[str, str]] = [
    ("users", "id"),
    ("user_emails", "id"),
    ("user_api_keys", "id"),
    ("decks", "id"),
    ("cards", "id"),
    ("audio_files", "id"),
]


def build_db_config(prefix: str, defaults: Dict[str, str]) -> Dict[str, str]:
    return {
        "host": os.getenv(f"{prefix}_POSTGRES_HOST", defaults["host"]),
        "port": os.getenv(f"{prefix}_POSTGRES_PORT", defaults["port"]),
        "dbname": os.getenv(f"{prefix}_POSTGRES_DB", defaults["dbname"]),
        "user": os.getenv(f"{prefix}_POSTGRES_USER", defaults["user"]),
        "password": os.getenv(f"{prefix}_POSTGRES_PASSWORD", defaults["password"]),
    }


def get_current_defaults() -> Dict[str, str]:
    return {
        "host": os.getenv("POSTGRES_HOST", "localhost"),
        "port": os.getenv("POSTGRES_PORT", CURRENT_DEFAULT_PORT),
        "dbname": os.getenv("POSTGRES_DB", "postgres"),
        "user": os.getenv("POSTGRES_USER", "postgres"),
        "password": os.getenv("POSTGRES_PASSWORD", "postgres"),
    }


def get_legacy_config(current_defaults: Dict[str, str]) -> Dict[str, str]:
    defaults = {
        "host": current_defaults["host"],
        "port": LEGACY_DEFAULT_PORT,
        "dbname": current_defaults["dbname"],
        "user": current_defaults["user"],
        "password": current_defaults["password"],
    }
    return build_db_config("LEGACY", defaults)


@contextmanager
def db_connection(config: Dict[str, str]):
    conn = psycopg2.connect(**config)
    try:
        yield conn
    finally:
        conn.close()


def get_columns(conn, table: str) -> List[str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = %s
            ORDER BY ordinal_position
            """,
            (table,),
        )
        return [row[0] for row in cur.fetchall()]


def copy_table(src_conn, dst_conn, table: str, pk: str) -> Tuple[int, int]:
    legacy_columns = get_columns(src_conn, table)
    current_columns = get_columns(dst_conn, table)
    shared_columns = [col for col in current_columns if col in legacy_columns]

    if not shared_columns:
        print(f"[skip] No shared columns for {table}")
        return 0, 0

    with src_conn.cursor(cursor_factory=RealDictCursor) as src_cur:
        select_sql = sql.SQL("SELECT {fields} FROM {table}").format(
            fields=sql.SQL(", ").join(map(sql.Identifier, shared_columns)),
            table=sql.Identifier(table),
        )
        src_cur.execute(select_sql)
        rows = src_cur.fetchall()

    if not rows:
        print(f"[ok] {table}: nothing to import")
        return 0, 0

    inserted = 0
    skipped = 0

    insert_sql = sql.SQL(
        "INSERT INTO {table} ({fields}) VALUES ({placeholders}) "
        "ON CONFLICT ({pk}) DO NOTHING"
    ).format(
        table=sql.Identifier(table),
        fields=sql.SQL(", ").join(map(sql.Identifier, shared_columns)),
        placeholders=sql.SQL(", ").join(sql.Placeholder() for _ in shared_columns),
        pk=sql.Identifier(pk),
    )

    def prepare_value(value):
        if isinstance(value, (dict, list)):
            return Json(value)
        return value

    with dst_conn.cursor() as dst_cur:
        for row in rows:
            values = [prepare_value(row[col]) for col in shared_columns]
            dst_cur.execute(insert_sql, values)
            if dst_cur.rowcount == 1:
                inserted += 1
            else:
                skipped += 1
        dst_conn.commit()

    print(f"[ok] {table}: inserted {inserted}, skipped {skipped}")
    return inserted, skipped


def run():
    current_defaults = get_current_defaults()
    legacy_config = get_legacy_config(current_defaults)
    current_config = current_defaults.copy()

    total_inserted = 0
    total_skipped = 0

    with db_connection(legacy_config) as legacy_conn, db_connection(current_config) as current_conn:
        for table, pk in TABLES:
            inserted, skipped = copy_table(legacy_conn, current_conn, table, pk)
            total_inserted += inserted
            total_skipped += skipped

    print(
        f"[done] Imported {total_inserted} rows "
        f"(skipped {total_skipped} existing rows) from legacy database."
    )


if __name__ == "__main__":
    try:
        run()
    except psycopg2.Error as exc:
        print(f"[error] Database operation failed: {exc}")
        sys.exit(1)
