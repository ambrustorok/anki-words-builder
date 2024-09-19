import genanki
import os
import logging


class AnkiLanguageDeckCreator:
    def __init__(self, deck_id, deck_name, model_id, model_name, logger=None):
        self.deck_id = deck_id
        self.deck_name = deck_name
        self.model_id = model_id
        self.model_name = model_name
        self.model = self._create_model()
        self.deck = self._create_or_get_deck()
        self.media_files = []

        # Set up logger
        self.logger = logger or logging.getLogger(__name__)

    def _create_model(self):
        fields = [
            {"name": "Front"},
            {"name": "Back"},
            {"name": "Audio"},
        ]
        templates = [
            {
                "name": "Card 1",
                "qfmt": "{{Front}}<br>{{Audio}}",
                "afmt": '{{FrontSide}}<hr id="answer">{{Back}}',
            },
        ]
        return genanki.Model(
            self.model_id, self.model_name, fields=fields, templates=templates
        )

    def _create_or_get_deck(self):
        return genanki.Deck(self.deck_id, self.deck_name)

    def add_card(self, front, back, audio_path):
        audio_filename = os.path.basename(audio_path)
        note = genanki.Note(
            model=self.model, fields=[front, back, f"[sound:{audio_filename}]"]
        )
        self.deck.add_note(note)
        self.media_files.append(audio_path)
        self.logger.info(
            f"Added card: Front='{front}', Back='{back}', Audio='{audio_filename}'"
        )

    def save_deck(self, output_path):
        package = genanki.Package(self.deck)
        package.media_files = self.media_files
        package.write_to_file(output_path)
        self.logger.info(f"Deck saved to {output_path}")
