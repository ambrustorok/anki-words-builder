import csv
from .anki_connect import add_anki_card

# Function to create a CSV file for Anki flashcard import
def create_flashcard_csv(cards, filename="flashcards.csv"):
    with open(filename, mode="w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["Front", "Back", "Audio"])  # Headers
        for card in cards:
            writer.writerow([card['front'], card['back'], card['audio']])

# Function to create Anki flashcards directly using AnkiConnect
def create_anki_flashcards(cards):
    for card in cards:
        add_anki_card(card['front'], card['back'], card['audio'])

# Example usage:
# cards = [{"front": "Hello", "back": "Hej", "audio": "static/audio/hej.mp3"}]
# create_flashcard_csv(cards) or create_anki_flashcards(cards)
