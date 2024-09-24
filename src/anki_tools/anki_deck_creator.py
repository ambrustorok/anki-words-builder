import genanki
import os
import json
import sqlite3
import shutil


def create_model(model_id, model_name):
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
    return genanki.Model(model_id, model_name, fields=fields, templates=templates)


def create_note(model, front, back, front_audio_filename, back_audio_filename):
    return genanki.Note(
        model=model,
        fields=[
            front,
            back,
            f"[sound:{front_audio_filename}]" if front_audio_filename else "",
            f"[sound:{back_audio_filename}]" if back_audio_filename else "",
        ],
    )


def create_or_get_deck(deck_id, deck_name, output_path):
    # Check if the file exists
    if os.path.exists(output_path):
        print(f"Deck file {output_path} already exists, updating it.")
        # Load the existing deck
        with open(output_path, 'rb') as f:
            deck = genanki.Deck(deck_id, deck_name)
            # You can handle deck restoration from the saved file if needed here
    else:
        print(f"Deck file {output_path} does not exist, creating a new one.")
        deck = genanki.Deck(deck_id, deck_name)

    return deck



def add_card_to_deck(deck, note):
    deck.add_note(note)


def save_deck(deck, media_files, output_path):
    package = genanki.Package(deck)
    package.media_files = media_files
    package.write_to_file(output_path)


def insert_or_create_anki_deck(
    deck_id, deck_name, model_id, model_name, cards, output_path
):
    model = create_model(model_id, model_name)
    deck = create_or_get_deck(deck_id, deck_name, output_path)

    media_files = []
    existing_notes = set(deck.notes)

    print(f"Adding {len(cards)} cards to the deck...")
    for i, card in enumerate(cards, 1):
        print(f"Processing card {i}/{len(cards)}")

        if card.get("front_audio_path"):
            front_audio_filename = os.path.basename(card["front_audio_path"])
            if front_audio_filename:
                media_files.append(card["front_audio_path"])
        else:
            front_audio_filename = None

        if card.get("back_audio_path"):
            back_audio_filename = os.path.basename(card["back_audio_path"])
            if back_audio_filename:
                media_files.append(card["back_audio_path"])
        else:
            back_audio_filename = None

        note = create_note(
            model,
            card["front"],
            card["back"],
            front_audio_filename,
            back_audio_filename,
        )

        # Add only unique cards (compared to the existing deck)
        if note not in existing_notes:
            add_card_to_deck(deck, note)
            existing_notes.add(note)

    # Save the new or updated deck
    save_deck(deck, media_files, output_path)
    print(f"Deck saved to {output_path}")
    print(f"Total cards in deck: {len(deck.notes)}")

    return deck
