import genanki
import os


def create_model(model_id, model_name, fields, templates):
    return genanki.Model(model_id, model_name, fields=fields, templates=templates)


def create_note(model, front, back, audio_filename):
    return genanki.Note(model=model, fields=[front, back, f"[sound:{audio_filename}]"])


def create_or_get_deck(deck_id, deck_name):
    return genanki.Deck(deck_id, deck_name)


def add_card_to_deck(deck, note):
    deck.add_note(note)


def save_deck(deck, media_files, output_path):
    package = genanki.Package(deck)
    package.media_files = media_files
    package.write_to_file(output_path)


def create_anki_deck(deck_id, deck_name, model_id, model_name, cards, output_path):
    """TODO: ADD BACK ONLY AUDO"""
    """TODO: MAKE SURE NOT TO RECREATE FILE IF IT EXISTS"""

    print("deck_id", deck_id)
    print("deck_name", deck_name)
    print("model_id", model_id)
    print("model_name", model_name)
    print("cards", cards)
    print("output_path", output_path)
    """
    Create an Anki deck with the given parameters.

    :param deck_id: Unique identifier for the deck
    :param deck_name: Name of the deck
    :param model_id: Unique identifier for the model
    :param model_name: Name of the model
    :param cards: List of dictionaries, each containing 'front', 'back', and 'audio_path' for a card
    :param output_path: Path where the .apkg file will be saved
    """
    # Define model
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
    model = create_model(model_id, model_name, fields, templates)

    # Create or get deck
    deck = create_or_get_deck(deck_id, deck_name)

    # Add cards
    media_files = []
    for card in cards:
        audio_filename = os.path.basename(card["audio_path"])
        note = create_note(model, card["front"], card["back"], audio_filename)
        add_card_to_deck(deck, note)
        media_files.append(card["audio_path"])

    # Save the deck
    save_deck(deck, media_files, output_path)

    print(f"Deck saved to {output_path}")


# Example usage
if __name__ == "__main__":
    deck_id = 2059400110
    deck_name = "My Custom Deck"
    model_id = 1607392319
    model_name = "Simple Model with Audio"

    cards = [
        {
            "front": "<div>What is the capital of France?</div>",
            "back": "<div>Paris</div>",
            "audio_path": "/mnt/d/OneDrive/Projects/anki-words-builder/notebooks/audio_Hej, jeg hedder Rasmus.mp3",
        },
        {
            "front": "<div>What is the capital of Japan?</div>",
            "back": "<div>Tokyo</div>",
            "audio_path": "/mnt/d/OneDrive/Projects/anki-words-builder/notebooks/audio_kæreste.mp3",
        },
    ]

    output_path = "my_custom_deck.apkg"

    create_anki_deck(deck_id, deck_name, model_id, model_name, cards, output_path)
