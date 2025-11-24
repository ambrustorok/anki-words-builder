import psycopg2

from ..settings import POSTGRES_DB, POSTGRES_HOST, POSTGRES_PASSWORD, POSTGRES_PORT, POSTGRES_USER


def save_audio_to_postgres(text, audio_binary):
    conn = psycopg2.connect(
        host=POSTGRES_HOST,
        database=POSTGRES_DB,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
        port=POSTGRES_PORT,
    )
    cur = conn.cursor()
    cur.execute(
        """CREATE TABLE IF NOT EXISTS audio_files (
            id SERIAL PRIMARY KEY,
            text TEXT,
            audio_data BYTEA
        )"""
    )
    cur.execute(
        "INSERT INTO audio_files (text, audio_data) VALUES (%s, %s)",
        (text, psycopg2.Binary(audio_binary)),
    )
    conn.commit()
    cur.close()
    conn.close()
