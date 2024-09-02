import genanki
import os

def add_card_to_anki_deck(deck_id, model_id, note_id, front_text, back_text, audio_file_path, deck_name="Default Deck"):
    # Define the Anki model
    my_model = genanki.Model(
        model_id,
        'Simple Model with Audio',
        fields=[
            {'name': 'Front'},
            {'name': 'Back'},
        ],
        templates=[
            {
                'name': 'Card 1',
                'qfmt': '{{Front}}',
                'afmt': '{{FrontSide}}<hr id="answer">{{Back}}',
            },
        ],
        css='''
        .card {
            font-family: Arial, sans-serif;
            font-size: 20px;
            text-align: center;
        }
        '''
    )

    # Define the Anki deck
    my_deck = genanki.Deck(
        deck_id,
        deck_name
    )

    # Define the Anki note with audio file
    if not os.path.isfile(audio_file_path):
        raise FileNotFoundError(f"The audio file '{audio_file_path}' does not exist.")

    my_note = genanki.Note(
        model=my_model,
        fields=[front_text, back_text],
        tags=[],
        audio=[{
            'url': audio_file_path,
            'filename': os.path.basename(audio_file_path),
            'fields': ['Front']
        }]
    )

    # Add the note to the deck
    my_deck.add_note(my_note)

    # Create an Anki package
    my_package = genanki.Package(my_deck)
    
    # Define the output file name
    output_file = 'output.apkg'
    
    # Save the package to a file
    my_package.write_to_file(output_file)
    
    print(f"Deck '{deck_name}' with the new card has been created and saved as '{output_file}'")

# Example usage:
# add_card_to_anki_deck(
#     deck_id=1725308120368,
#     model_id=9876543210,
#     note_id=1122334455,
#     front_text="What is the capital of France?",
#     back_text="The capital of France is Paris.",
#     audio_file_path="path/to/audio/file.mp3"
# )
