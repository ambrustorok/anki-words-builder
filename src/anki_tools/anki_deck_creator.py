import genanki
import sqlite3
import os
import shutil
import threading


class AnkiDeckManager:
    def __init__(self, deck_name, model_id, model_name, db_path):
        self.deck_name = deck_name
        self.model_id = model_id
        self.model_name = model_name
        self.db_path = db_path
        self.thread_local = threading.local()

        # Ensure the database and table are initialized upon instantiation
        self._ensure_db_and_table()

    def _get_connection(self):
        if not hasattr(self.thread_local, "connection"):
            self.thread_local.connection = sqlite3.connect(self.db_path)
        return self.thread_local.connection

    def _close_connection(self):
        if hasattr(self.thread_local, "connection"):
            self.thread_local.connection.close()
            del self.thread_local.connection

    def _init_db(self):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """CREATE TABLE IF NOT EXISTS cards (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            front TEXT NOT NULL,
                            back TEXT NOT NULL,
                            front_audio TEXT,
                            back_audio TEXT
                        )"""
        )
        conn.commit()

    def _ensure_db_and_table(self):
        if not os.path.exists(self.db_path):
            print(f"Database file {self.db_path} does not exist. Creating...")
        self._init_db()  # Ensure the table exists

    def create_model(self):
        fields = [
            {"name": "Front"},
            {"name": "Back"},
            {"name": "FrontAudio"},
            {"name": "BackAudio"},
        ]
        templates = [
            {
                "name": "Card 1",
                "qfmt": "{{Front}}<br>{{FrontAudio}}",
                "afmt": '{{FrontSide}}<hr id="answer">{{Back}}<br>{{BackAudio}}',
            },
        ]
        return genanki.Model(
            self.model_id, self.model_name, fields=fields, templates=templates
        )

    def create_deck(self):
        return genanki.Deck(hash(self.deck_name), self.deck_name)

    def add_card(
        self, front=None, back=None, front_audio_path=None, back_audio_path=None
    ):
        front = front or ""
        back = back or ""
        front_audio_path = front_audio_path or ""
        back_audio_path = back_audio_path or ""

        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO cards (front, back, front_audio, back_audio) VALUES (?, ?, ?, ?)",
                (front, back, front_audio_path, back_audio_path),
            )
            conn.commit()
        finally:
            self._close_connection()

    def load_cards_from_db(self):
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT id, front, back, front_audio, back_audio FROM cards")
            return cursor.fetchall()
        finally:
            self._close_connection()

    def save_deck(self, deck, media_files, file_path):
        package = genanki.Package(deck)
        package.media_files = media_files
        package.write_to_file(file_path)

    def export_to_apkg(self, file_path):
        deck = self.create_deck()
        media_files = []

        cards = self.load_cards_from_db()
        for card in cards:
            front_audio_filename = None
            back_audio_filename = None

            if card[3]:  # front_audio_path exists
                front_audio_filename = os.path.basename(card[3])
                media_files.append(card[3])  # Add full path to media files list

            if card[4]:  # back_audio_path exists
                back_audio_filename = os.path.basename(card[4])
                media_files.append(card[4])  # Add full path to media files list

            note = genanki.Note(
                model=self.create_model(),
                fields=[
                    card[1],  # front
                    card[2],  # back
                    f"[sound:{front_audio_filename}]" if front_audio_filename else "",
                    f"[sound:{back_audio_filename}]" if back_audio_filename else "",
                ],
            )
            deck.add_note(note)

        self.save_deck(deck, media_files, file_path)
        print(f"Deck exported to {file_path} with {len(deck.notes)} cards.")

    def get_windows_username(self):
        return os.getenv("USERNAME")

    def get_anki_media_folder(self):
        windows_username = self.get_windows_username()
        if not windows_username:
            return None
        anki_base_dir = f"C:/Users/{windows_username}/AppData/Roaming/Anki2"
        media_folder = os.path.join(anki_base_dir, "User 1", "collection.media")
        if not os.path.exists(media_folder):
            print(f"Anki media folder not found at: {media_folder}")
            return None
        return media_folder

    def copy_to_anki_media_folder(self, file_path):
        media_folder = self.get_anki_media_folder()
        if not media_folder:
            print("Anki installation or media folder not found.")
            return None
        try:
            shutil.copy2(file_path, media_folder)
            print(f"Copied {file_path} to {media_folder}")
        except Exception as e:
            print(f"Failed to copy {file_path} to Anki media folder: {e}")
