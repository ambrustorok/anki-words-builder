import genanki
import os
import threading
import psycopg2
from contextlib import contextmanager
import tempfile
import uuid

from setup import host, database, user, password, port
from utils import convert_audio_to_numpy


class AnkiDeckManager:
    def __init__(self, deck_name, model_id, model_name, db_path):
        self.deck_name = deck_name
        self.model_id = model_id
        self.model_name = model_name
        self.db_path = db_path
        self.thread_local = threading.local()
        self._init_db()

    @contextmanager
    def _get_connection(self):
        conn = psycopg2.connect(
            host=host,
            database=database,
            user=user,
            password=password,
            port=port,
        )
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self):
        with self._get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """CREATE TABLE IF NOT EXISTS cards (
                        id SERIAL PRIMARY KEY,
                        front TEXT NOT NULL,
                        back TEXT NOT NULL,
                        front_audio BYTEA,
                        back_audio BYTEA,
                        filename TEXT
                    )"""
                )
                conn.commit()

    # The add_card method now accepts binary data for audio
    def add_card(
        self, front=None, back=None, front_audio=None, back_audio=None, filename=None
    ):
        front = front or ""
        back = back or ""
        with self._get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO cards (front, back, front_audio, back_audio, filename) VALUES (%s, %s, %s, %s, %s)",
                    (
                        front,
                        back,
                        psycopg2.Binary(front_audio) if front_audio else None,
                        psycopg2.Binary(back_audio) if back_audio else None,
                        filename,
                    ),
                )
                conn.commit()

    def load_cards_from_db(self):
        with self._get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id, front, back FROM cards")
                return cursor.fetchall()

    def get_card_by_id(self, card_id):
        with self._get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT id, front, back, front_audio, back_audio FROM cards WHERE id = %s",
                    (card_id,),
                )
                card = cursor.fetchone()
                if card:
                    # Convert memoryview to bytes for audio data if present
                    front_audio_bytes = bytes(card[3]) if card[3] is not None else None
                    back_audio_bytes = bytes(card[4]) if card[4] is not None else None

                    # Convert audio bytes to numpy array format
                    front_audio = convert_audio_to_numpy(front_audio_bytes) if front_audio_bytes else None
                    back_audio = convert_audio_to_numpy(back_audio_bytes) if back_audio_bytes else None

                    return {
                        "id": card[0],
                        "front": card[1],
                        "back": card[2],
                        "front_audio": front_audio,
                        "back_audio": back_audio,
                    }
                return None
    def update_card(
        self, card_id, front, back, front_audio_binary=None, back_audio_binary=None
    ):
        filename = f"{uuid.uuid4().hex}.mp3"
        with self._get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """UPDATE cards 
                    SET front = %s, back = %s, front_audio = %s, back_audio = %s, filename = %s
                    WHERE id = %s""",
                    (
                        front,
                        back,
                        front_audio_binary,
                        back_audio_binary,
                        filename,
                        card_id,
                    ),
                )
                conn.commit()
                if cursor.rowcount == 0:
                    raise Exception(f"No card found with id {card_id}")

    def delete_card(self, card_id):
        with self._get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM cards WHERE id = %s", (card_id,))
                conn.commit()
                if cursor.rowcount == 0:
                    raise Exception(f"No card found with id {card_id}")

    def search_cards(self, query):
        with self._get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """SELECT id, front, back 
                    FROM cards 
                    WHERE front LIKE %s OR back LIKE %s""",
                    (f"%{query}%", f"%{query}%"),
                )
                return cursor.fetchall()

    def export_to_apkg(self):
        # Create a unique deck ID and model ID
        deck = genanki.Deck(1607392319, self.deck_name)
        model = genanki.Model(
            self.model_id,
            self.model_name,
            fields=[
                {"name": "Front"},
                {"name": "Back"},
                {"name": "FrontAudio"},
                {"name": "BackAudio"},
            ],
            templates=[
                {
                    "name": "Card 1",
                    "qfmt": "{{Front}}<br>{{FrontAudio}}",
                    "afmt": "{{FrontSide}}<hr id='answer'>{{Back}}<br>{{BackAudio}}",
                },
            ],
        )

        package = genanki.Package(deck)
        media_files = []

        with self._get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT front, back, front_audio, back_audio, filename FROM cards"
                )
                cards = cursor.fetchall()

                with tempfile.TemporaryDirectory() as temp_dir:
                    temp_apkg = os.path.join(temp_dir, "deck.apkg")
                    for front, back, front_audio, back_audio, filename in cards:
                        front_audio_tag = ""
                        back_audio_tag = ""

                        # Handle front audio if exists
                        if front_audio:
                            front_audio_filename = (
                                filename
                                if filename
                                else f"front_audio_{uuid.uuid4().hex}.mp3"
                            )
                            front_audio_path = os.path.join(
                                temp_dir, front_audio_filename
                            )
                            with open(front_audio_path, "wb") as f:
                                f.write(front_audio)
                            front_audio_tag = f"[sound:{front_audio_filename}]"
                            media_files.append(front_audio_path)

                        # Handle back audio if exists
                        if back_audio:
                            back_audio_filename = (
                                filename
                                if filename
                                else f"back_audio_{uuid.uuid4().hex}.mp3"
                            )
                            back_audio_path = os.path.join(
                                temp_dir, back_audio_filename
                            )
                            with open(back_audio_path, "wb") as f:
                                f.write(back_audio)
                            back_audio_tag = f"[sound:{back_audio_filename}]"
                            media_files.append(back_audio_path)

                        note = genanki.Note(
                            model=model,
                            fields=[
                                front,
                                back,
                                front_audio_tag,
                                back_audio_tag,
                            ],
                        )
                        deck.add_note(note)

                    package.media_files = media_files
                    package.write_to_file(temp_apkg)

                    with open(temp_apkg, "rb") as f:
                        return f.read()
