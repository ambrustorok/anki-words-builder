import gradio as gr
from api_clients.translator import translate_text, generate_sentence
from api_clients.pronouncer import pronounce_text


def get_word_details(word, lang):
    # Determine whether the word is in Danish or English
    if lang == "Danish":
        word_forms = {
            "singular": word,
            "plural": word + "er",
            "past_tense": word + "ede",
        }
        sentence = generate_sentence(word, lang="da")
        pronunciation_file = pronounce_text(word, lang="da")
        translation = translate_text(word, source_lang="da", target_lang="en")
    else:  # Assuming "English"
        # Placeholder for English word forms; replace with actual implementation if needed
        word_forms = {"singular": word, "plural": word + "s", "past_tense": word + "ed"}
        sentence = generate_sentence(word, lang="da")
        pronunciation_file = pronounce_text(word, lang="da")
        translation = translate_text(word, source_lang="en", target_lang="da")

    flashcards = create_flashcards(word, translation, lang)

    return word_forms, sentence, pronunciation_file, flashcards


def create_flashcards(word, translation, lang):
    # Create flashcards based on language
    if lang == "Danish":
        anki_cards = {
            "English to Danish": (word, translation),
            "Danish to English": (translation, word),
        }
    else:  # Assuming "English"
        anki_cards = {
            "Danish to English": (word, translation),
            "English to Danish": (translation, word),
        }
    return anki_cards


def ui_function(word, lang):
    word_forms, sentence, pronunciation_file, flashcards = get_word_details(word, lang)
    return word_forms, sentence, pronunciation_file, flashcards


with gr.Blocks() as app:
    with gr.Row():
        word_input = gr.Textbox(label="Enter Word")
        lang_dropdown = gr.Dropdown(
            label="Select Language", choices=["Danish", "English"], value="Danish"
        )
        submit_button = gr.Button("Process word")

    with gr.Row():
        word_forms_output = gr.JSON(label="Word Forms")
        sentence_output = gr.Textbox(label="Sentence")
        pronunciation_output = gr.Audio(label="Pronunciation")
        flashcards_output = gr.JSON(label="Anki Flashcards")

    submit_button.click(
        ui_function,
        inputs=[word_input, lang_dropdown],
        outputs=[
            word_forms_output,
            sentence_output,
            pronunciation_output,
            flashcards_output,
        ],
    )

app.launch()
