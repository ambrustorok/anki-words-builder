import gradio as gr
import os
import tempfile
import numpy as np
import soundfile as sf
from dotenv import load_dotenv
from openai import OpenAI
import random

from chatgpt_tools.prompts import translate_word, generate_sentence, dictionarize_word
from chatgpt_tools.tts import get_audio
from anki_tools.anki_deck_creator import create_anki_deck

load_dotenv()
client = OpenAI()

languages = ["Danish", "English"]


def save_into_database(word, translation, sentence, audio_path, dictionary_form):
    # Implement your database saving logic here
    print(
        f"Saving to database: {word}, {translation}, {sentence}, {audio_path}, {dictionary_form}"
    )
    return "Data saved successfully"


def process_word(danish_word, custom_sentence="", language="Danish"):
    translation = translate_word(client, danish_word, source_lang=language)
    sentence = (
        custom_sentence
        if custom_sentence
        else generate_sentence(client, danish_word, language)
    )
    dictionary_form = dictionarize_word(client, danish_word, language)
    audio_path = get_audio(client, danish_word, language)

    return translation, sentence, audio_path, dictionary_form


def regenerate_sentence(word, language):
    return generate_sentence(client, word, language)


def save_to_database(danish_word, translation, sentence, audio_path, dictionary_form):
    print(audio_path)
    deck_id = 2059400110
    deck_name = "Danish"
    model_id = 1607392319
    model_name = "Danish with Audio"

    cards = [
        {
            "front": f"<div>{danish_word}</div><div>{sentence}</div>",
            "back": f"<div>{translation}</div><div>{dictionary_form}</div>",
            "audio_path": audio_path,
        },
        {
            "front": f"<div>{translation}</div>",
            "back": f"<div>{danish_word}</div><div>{sentence}</div><div>{dictionary_form}</div>",
            "audio_path": audio_path,
        },
    ]

    output_path = "danish_deck.apkg"

    create_anki_deck(deck_id, deck_name, model_id, model_name, cards, output_path)
    return save_into_database(
        danish_word, translation, sentence, audio_path, dictionary_form
    )


# Gradio interface
with gr.Blocks() as iface:
    gr.Markdown("# Danish-English Language Learning App")
    gr.Markdown(
        "Enter a Danish word to get its English translation, dictionary form, a sample sentence, and pronunciation."
    )

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
    save_btn = gr.Button("Save to Database")
    save_result = gr.Textbox(label="Database Save Result")

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

if __name__ == "__main__":
    iface.launch()
