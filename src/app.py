import gradio as gr
import os
import tempfile
import numpy as np
import soundfile as sf
from dotenv import load_dotenv
from openai import OpenAI
import random
import threading

from chatgpt_tools.prompts import translate_word, generate_sentence, dictionarize_word
from chatgpt_tools.tts import get_audio
from anki_tools.anki_deck_creator import AnkiDeckManager
from utils.utils import convert_string_to_html

load_dotenv()
client = OpenAI()

languages = ["Danish", "English"]
BASE_DIR = "/mnt/d/OneDrive/Projects/data/danish"
AUDIO_DIR = os.path.join(BASE_DIR, "anki_audio")
os.makedirs(AUDIO_DIR, exist_ok=True)

DB_PATH = os.path.join(BASE_DIR, "cards.db")
thread_local = threading.local()


def get_deck_manager():
    if not hasattr(thread_local, "deck_manager"):
        thread_local.deck_manager = AnkiDeckManager(
            deck_name="Danish Learning Deck",
            model_id=1607392319,
            model_name="Danish with Audio",
            db_path=DB_PATH,
        )
    return thread_local.deck_manager


def process_word(danish_word, custom_sentence="", language="Danish"):
    translation = translate_word(client, danish_word, source_lang=language)
    sentence = (
        custom_sentence
        if custom_sentence
        else generate_sentence(client, danish_word, language)
    )
    dictionary_form = convert_string_to_html(
        dictionarize_word(client, danish_word, language)
    )
    audio_path = get_audio(client, danish_word, language, output_dir=AUDIO_DIR)

    return translation, sentence, audio_path, dictionary_form


def regenerate_sentence(word, language):
    return generate_sentence(client, word, language)


def save_to_database(danish_word, translation, sentence, audio_path, dictionary_form):
    try:
        deck_manager = get_deck_manager()
        deck_manager.add_card(
            front=f"<div>{danish_word}</div>",
            back=f"<div>{translation}</div><div>{sentence}</div><div>{dictionary_form}</div>",
            front_audio_path=audio_path,
            back_audio_path="",
        )
        deck_manager.add_card(
            front=f"<div>{translation}</div>",
            back=f"<div>{danish_word}</div><div>{sentence}</div><div>{dictionary_form}</div>",
            front_audio_path="",
            back_audio_path=audio_path,
        )
        return f'"{danish_word}" saved successfully. Card added to the deck.'
    except Exception as e:
        return f'Error adding card "{danish_word}" to deck: {e}'


def export_deck():
    try:
        deck_manager = get_deck_manager()
        output_path = os.path.join(BASE_DIR, "danish_deck.apkg")
        deck_manager.export_to_apkg(output_path)
        return f"Deck exported successfully to {output_path}"
    except Exception as e:
        return f"Error exporting deck: {e}"


def get_existing_cards():
    deck_manager = get_deck_manager()
    return deck_manager.load_cards_from_db()


def load_card(card_id):
    deck_manager = get_deck_manager()
    card = deck_manager.get_card_by_id(card_id)
    if card:
        return card["front"], card["back"], card["front_audio"], card["back_audio"]
    return None, None, None, None


def update_card(card_id, front, back, front_audio, back_audio):
    try:
        deck_manager = get_deck_manager()
        deck_manager.update_card(card_id, front, back, front_audio, back_audio)
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


# Gradio interface
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
            translation = gr.Textbox(label="Translation")
            dictionary_form = gr.Textbox(label="Dictionary Form")
            sentence = gr.Textbox(label="Generated Sentence", interactive=True)
            audio = gr.Audio(label="Pronunciation")
            audio_path = gr.Textbox(label="Audio Path", visible=False)

        regenerate_btn = gr.Button("Regenerate Sentence")
        save_btn = gr.Button("Save to Database and Anki")
        save_result = gr.Textbox(label="Save Result")

    with gr.Tab("Browse and Edit Cards"):
        with gr.Row():
            refresh_btn = gr.Button("Refresh Card List")
            search_input = gr.Textbox(label="Search Cards")
            search_btn = gr.Button("Search")

        card_list = gr.Dataframe(
            headers=["ID", "Front", "Back", "Front Audio", "Back Audio"],
            label="Existing Cards",
        )

        with gr.Row():
            card_id_input = gr.Number(label="Card ID to Edit", precision=0)
            load_card_btn = gr.Button("Load Card")

        with gr.Column():
            edit_front = gr.Textbox(label="Front")
            edit_back = gr.Textbox(label="Back")
            edit_front_audio = gr.Textbox(label="Front Audio Path")
            edit_back_audio = gr.Textbox(label="Back Audio Path")

        with gr.Row():
            update_btn = gr.Button("Update Card")
            delete_btn = gr.Button("Delete Card")

        edit_result = gr.Textbox(label="Edit Result")

    with gr.Tab("Export Deck"):
        export_btn = gr.Button("Export Anki Deck")
        export_result = gr.Textbox(label="Export Result")

    def process_and_display(word, lang):
        trans, sent, audio_file_path, dict_form = process_word(word, language=lang)
        return trans, dict_form, sent, audio_file_path, audio_file_path

    process_btn.click(
        process_and_display,
        inputs=[danish_word, language],
        outputs=[translation, dictionary_form, sentence, audio, audio_path],
    )

    regenerate_btn.click(
        regenerate_sentence, inputs=[danish_word, language], outputs=sentence
    )

    save_btn.click(
        save_to_database,
        inputs=[danish_word, translation, sentence, audio_path, dictionary_form],
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
        outputs=[edit_front, edit_back, edit_front_audio, edit_back_audio, edit_result],
    )

    update_btn.click(
        update_card,
        inputs=[
            card_id_input,
            edit_front,
            edit_back,
            edit_front_audio,
            edit_back_audio,
        ],
        outputs=edit_result,
    )

    delete_btn.click(delete_card, inputs=[card_id_input], outputs=edit_result)

    export_btn.click(export_deck, outputs=export_result)

    search_btn.click(search_cards, inputs=[search_input], outputs=[card_list])


if __name__ == "__main__":
    iface.launch()
