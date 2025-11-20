import psycopg2

from ..setup import database, host, password, port, user


def save_audio_to_postgres(text, audio_binary):
    conn = psycopg2.connect(
        host=host,
        database=database,
        user=user,
        password=password,
        port=port,
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
