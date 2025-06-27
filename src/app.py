import uuid
import gradio as gr
from dotenv import load_dotenv
from openai import OpenAI
import random
import threading
import tempfile
import numpy as np
import soundfile as sf
import io
from chatgpt_tools.prompts import translate_word, generate_sentence, dictionarize_word
from chatgpt_tools.tts import generate_audio_binary
from anki_tools.anki_deck_creator import AnkiDeckManager
from utils.utils import convert_string_to_html
import os

load_dotenv()
client = OpenAI()

languages = ["Danish"]
thread_local = threading.local()


def get_deck_manager():
    if not hasattr(thread_local, "deck_manager"):
        thread_local.deck_manager = AnkiDeckManager(
            deck_name="Danish Learning Deck",
            model_id=1607392319,
            model_name="Danish with Audio",
            db_path="not_used",  # This parameter is no longer used with PostgreSQL
        )
    return thread_local.deck_manager


def process_word(foreign_word, custom_sentence="", language="Danish"):
    translation = translate_word(client, foreign_word, source_lang=language)
    sentence = (
        custom_sentence
        if custom_sentence
        else generate_sentence(client, foreign_word, language)
    )
    dictionary_form = dictionarize_word(client, foreign_word, language)

    audio_binary = regenerate_audio(language, foreign_word)
    return translation, sentence, audio_binary, dictionary_form


def save_to_database(danish_word, translation, sentence, audio, dictionary_form):
    filename = f"{uuid.uuid4().hex}.mp3"
    try:
        audio_binary = extract_audio_binary(audio)
        deck_manager = get_deck_manager()
        deck_manager.add_card(
            front=f"<div>{danish_word}</div>",
            back=f"<div>{translation}</div><div>{sentence}</div><div>{dictionary_form}</div>",
            front_audio=audio_binary,
            back_audio=None,
            filename=filename,
        )
        deck_manager.add_card(
            front=f"<div>{translation}</div>",
            back=f"<div>{danish_word}</div><div>{sentence}</div><div>{dictionary_form}</div>",
            front_audio=None,
            back_audio=audio_binary,
            filename=filename,
        )
        return f'"{danish_word}" saved successfully. Card added to the deck.'
    except Exception as e:
        return f'Error adding card "{danish_word}" to deck: {e}'


def export_deck():
    try:

        deck_manager = get_deck_manager()
        binary_data = deck_manager.export_to_apkg()

        # Create a temporary file to store the binary data
        temp_dir = tempfile.mkdtemp()
        temp_path = os.path.join(temp_dir, "anki_danish_deck.apkg")

        # Write the binary data to the temporary file
        with open(temp_path, "wb") as f:
            f.write(binary_data)

        return "Your download is ready", temp_path
    except Exception as e:
        return f"Error exporting deck: {e}", None


def get_existing_cards():
    deck_manager = get_deck_manager()
    return deck_manager.load_cards_from_db()


def load_card(card_id):
    deck_manager = get_deck_manager()
    card = deck_manager.get_card_by_id(card_id)
    if card:
        return (
            card["front"],
            card["back"],
            (44100, card["front_audio"]) if card["front_audio"] is not None else None,
            (44100, card["back_audio"]) if card["back_audio"] is not None else None,
        )
    return None, None, None, None


def update_card(card_id, front, back, front_audio, back_audio):
    try:
        front_audio_binary = extract_audio_binary(front_audio) if front_audio else None
        back_audio_binary = extract_audio_binary(back_audio) if back_audio else None
        deck_manager = get_deck_manager()
        deck_manager.update_card(
            card_id,
            front,
            back,
            front_audio_binary,
            back_audio_binary,
        )
        return f"Card {card_id} updated successfully."
    except Exception as e:
        return f"Error updating card: {e}"


def delete_card(card_id):
    try:
        deck_manager = get_deck_manager()
        deck_manager.delete_card(card_id)
        return f"Card {card_id} deleted successfully."
    except Exception as e:
        return f"Error deleting card: {e}"


def search_cards(query):
    deck_manager = get_deck_manager()
    return deck_manager.search_cards(query)


def extract_audio_binary(audio_value):
    """
    Extract binary audio data from a Gradio audio component value.

    Args:
        audio_value: Value from gr.Audio component, can be tuple(sample_rate, data) or str (filepath)

    Returns:
        bytes: Binary audio data
    """
    if isinstance(audio_value, tuple):
        # If it's a tuple, it contains (sample_rate, data)
        sample_rate, data = audio_value

        # Create an in-memory binary buffer
        buffer = io.BytesIO()

        # Write the audio data to the buffer as MP3
        sf.write(buffer, data, sample_rate, format="mp3")

        # Get the binary content
        buffer.seek(0)
        return buffer.read()

    elif isinstance(audio_value, str):
        # If it's a string, it's a file path
        with open(audio_value, "rb") as f:
            return f.read()

    raise ValueError("Unsupported audio value format")


# Update the Gradio interface
with gr.Blocks() as iface:
    gr.Markdown("# Danish-English Language Learning App")
    gr.Markdown(
        "Enter a Danish word to get its English translation, dictionary form, a sample sentence, and pronunciation."
    )

    with gr.Tab("Add New Word"):
        with gr.Row():
            danish_word = gr.Textbox(label="Danish Word")
            language = gr.Dropdown(
                choices=languages, value="Danish", label="Source Language"
            )

        process_btn = gr.Button("Process Word")

        with gr.Column():
            with gr.Row():
                translation = gr.Textbox(label="Translation", interactive=True, scale=4)
                regenerate_translation_btn = gr.Button(
                    "Regenerate Translation", scale=1
                )

            with gr.Row():
                # Keep the main dictionary form textbox for editing
                with gr.Column(scale=4):
                    dictionary_form = gr.Textbox(
                        label="Dictionary Form", interactive=True
                    )

                    # Add a collapsible interface for the HTML view
                    with gr.Accordion("HTML Preview", open=False):
                        dictionary_form_html = gr.HTML()

                    # Update HTML content when dictionary form changes
                    dictionary_form.change(
                        lambda x: x, dictionary_form, dictionary_form_html
                    )

                regenerate_dictionary_btn = gr.Button(
                    "Regenerate Dictionary Form", scale=1
                )

            with gr.Row():
                sentence = gr.Textbox(
                    label="Generated Sentence", interactive=True, scale=4
                )
                regenerate_sentence_btn = gr.Button("Regenerate Sentence", scale=1)

            with gr.Row():
                audio = gr.Audio(label="Pronunciation", autoplay=True, scale=4)
                regenerate_audio_btn = gr.Button("Regenerate Audio", scale=1)

            audio_path = gr.Textbox(label="Audio Path", visible=False)

        save_btn = gr.Button("Save to Database and Anki")
        save_result = gr.Textbox(label="Save Result")

    with gr.Tab("Browse and Edit Cards"):
        with gr.Row():
            refresh_btn = gr.Button("Refresh Card List")
            search_input = gr.Textbox(label="Search Cards")
            search_btn = gr.Button("Search")

        card_list = gr.Dataframe(
            headers=["ID", "Front", "Back"],
            label="Existing Cards",
        )

        with gr.Row():
            card_id_input = gr.Number(label="Card ID to Edit", precision=0)
            load_card_btn = gr.Button("Load Card")

        with gr.Column():
            edit_front = gr.Textbox(label="Front")
            edit_back = gr.Textbox(label="Back")

            with gr.Row():
                loaded_front_audio = gr.Audio(
                    label="Pronunciation", autoplay=False, scale=4
                )
                regenerate_loaded_front_audio_btn = gr.Button(
                    "Regenerate Audio", scale=1
                )

            with gr.Row():
                loaded_back_audio = gr.Audio(
                    label="Pronunciation", autoplay=False, scale=4
                )
                regenerate_loaded_back_audio_btn = gr.Button(
                    "Regenerate Audio", scale=1
                )

        with gr.Row():
            update_btn = gr.Button("Update Card")
            delete_btn = gr.Button("Delete Card")

        edit_result = gr.Textbox(label="Edit Result")

    with gr.Tab("Export Deck"):
        export_btn = gr.Button("Export Anki Deck")
        export_result = gr.Textbox(label="Export Result")
        export_file_output = gr.File(label="Download exported file")

    def process_and_display(lang, word):
        trans, sent, audio_binary, dict_form = process_word(word, language=lang)
        return trans, dict_form, sent, audio_binary

    def regenerate_translation(lang, word):
        translation = translate_word(client, word, source_lang=lang)
        return translation

    def regenerate_dictionary_form(lang, word):
        dictionary_form = convert_string_to_html(dictionarize_word(client, word, lang))
        return dictionary_form

    def regenerate_sentence(lang, word):
        sentence = generate_sentence(client, word, lang)
        return sentence

    def regenerate_audio(lang, word):
        audio_binary = generate_audio_binary(client, word)
        return audio_binary

    # Update click handlers
    process_btn.click(
        process_and_display,
        inputs=[language, danish_word],
        outputs=[translation, dictionary_form, sentence, audio],
    )

    regenerate_audio_btn.click(
        regenerate_audio, inputs=[language, danish_word], outputs=[audio]
    )

    regenerate_translation_btn.click(
        regenerate_translation, inputs=[language, danish_word], outputs=[translation]
    )

    regenerate_dictionary_btn.click(
        regenerate_dictionary_form,
        inputs=[language, danish_word],
        outputs=[dictionary_form],
    )

    regenerate_sentence_btn.click(
        regenerate_sentence, inputs=[language, danish_word], outputs=[sentence]
    )

    regenerate_loaded_front_audio_btn.click(
        regenerate_audio, inputs=[language, edit_front], outputs=[loaded_front_audio]
    )

    regenerate_loaded_back_audio_btn.click(
        regenerate_audio, inputs=[language, edit_back], outputs=[loaded_back_audio]
    )

    save_btn.click(
        save_to_database,
        inputs=[danish_word, translation, sentence, audio, dictionary_form],
        outputs=save_result,
    )

    refresh_btn.click(get_existing_cards, outputs=card_list)

    def load_card_to_form(card_id):
        front, back, front_audio, back_audio = load_card(card_id)
        if front is not None:
            return front, back, front_audio, back_audio, ""
        return "", "", "", "", "Card not found"

    load_card_btn.click(
        load_card_to_form,
        inputs=[card_id_input],
        outputs=[
            edit_front,
            edit_back,
            loaded_front_audio,
            loaded_back_audio,
            edit_result,
        ],
    )

    update_btn.click(
        update_card,
        inputs=[
            card_id_input,
            edit_front,
            edit_back,
            loaded_front_audio,
            loaded_back_audio,
        ],
        outputs=edit_result,
    )

    delete_btn.click(delete_card, inputs=[card_id_input], outputs=edit_result)

    export_btn.click(export_deck, outputs=[export_result, export_file_output])

    search_btn.click(search_cards, inputs=[search_input], outputs=[card_list])

if __name__ == "__main__":
    iface.launch(server_name="0.0.0.0", server_port=7860)
