import genanki
import os
import json
import sqlite3
import subprocess
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
    print(front_audio_filename)
    print(back_audio_filename)
    return genanki.Note(
        model=model,
        fields=[
            front,
            back,
            f"[sound:{front_audio_filename}]" if front_audio_filename else "",
            f"[sound:{back_audio_filename}]" if back_audio_filename else "",
        ],
    )


def create_or_get_deck(deck_id, deck_name):
    return genanki.Deck(deck_id, deck_name)


def add_card_to_deck(deck, note):
    deck.add_note(note)


def save_deck(deck, media_files, output_path):
    package = genanki.Package(deck)
    package.media_files = media_files
    package.write_to_file(output_path)


def get_windows_username():
    try:
        result = subprocess.run(
            ["cmd.exe", "/c", "echo %USERNAME%"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        print("Failed to get Windows username")
        return None


def get_anki_base_dir():
    windows_username = get_windows_username()
    if not windows_username:
        return None
    return f"C:/Users/{windows_username}/AppData/Roaming/Anki2"


def copy_to_anki_media_folder(file_path):
    anki_base_dir = get_anki_base_dir()
    if not anki_base_dir:
        print("Anki installation not found.")
        return None

    media_folder = os.path.join(anki_base_dir, "User 1", "collection.media")
    if not os.path.exists(media_folder):
        print(f"Anki media folder not found at path: {media_folder}")
        return None

    filename = os.path.basename(file_path)
    destination = os.path.join(media_folder, filename)

    try:
        shutil.copy2(file_path, destination)
        print(f"Copied {file_path} to {destination}")
        return filename
    except Exception as e:
        print(f"Failed to copy file to Anki media folder: {e}")
        return None


def insert_or_create_anki_deck(
    deck_id, deck_name, model_id, model_name, cards, output_path
):
    model = create_model(model_id, model_name)

    # Check if deck file already exists
    if os.path.exists(output_path):
        print(f"Deck file {output_path} already exists, updating it.")

        # Open existing deck information (you may need a method to keep track of added cards)
        # For now, we assume you're managing card uniqueness through `cards` logic
        deck = genanki.Deck(deck_id, deck_name)
    else:
        print(f"Deck file {output_path} does not exist, creating a new one.")
        deck = create_or_get_deck(deck_id, deck_name)

    media_files = []

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
        # Add only unique cards (optional: check duplicates manually)
        if note not in deck.notes:  # Ensure the note isn't already in the deck
            add_card_to_deck(deck, note)

    # Save the new or updated deck
    save_deck(deck, media_files, output_path)
    print(f"Deck saved to {output_path}")
    print(f"Total cards in deck: {len(deck.notes)}")

    # Copy the deck file to Anki's collection folder
    anki_base_dir = get_anki_base_dir()
    if anki_base_dir:
        collection_folder = os.path.join(anki_base_dir, "User 1")
        if os.path.exists(collection_folder):
            destination = os.path.join(collection_folder, os.path.basename(output_path))
            shutil.copy2(output_path, destination)
            print(f"Copied deck file to Anki collection folder: {destination}")
        else:
            print(f"Anki collection folder not found: {collection_folder}")
    else:
        print(
            "Could not determine Anki collection folder. Please import the deck manually."
        )

    return deck
