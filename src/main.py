import gradio as gr
# from api_clients.google_translate import translate_word
# from api_clients.wiktionary_scraper import get_word_forms
# # from api_clients.tts_pronunciation import get_pronunciation
# from api_clients.sentence_generator import generate_sentence
# from anki_integration.flashcard_generator import create_flashcard_csv

# To store cards in memory for browsing
flashcards = []

# Function that ties everything together and returns flashcard info
def process_word(word):
    # # Step 1: Get translation
    # translation = translate_word(word, src_lang="da", target_lang="en")
    # reverse_translation = translate_word(translation, src_lang="en", target_lang="da")

    # # Step 2: Get word forms
    # word_forms = get_word_forms(word)

    # # Step 3: Generate pronunciation audio
    # # audio_file = get_pronunciation(word)

    # # Step 4: Generate example sentence
    # example_sentence = generate_sentence(word)

    # # Create flashcard data and add to global list
    # card = {
    #     "front": word,
    #     "back": translation,
    #     "forms": word_forms,
    #     "sentence": example_sentence,
    #     "audio": audio_file
    # }
    # flashcards.append(card)

    # Return all information to be displayed on Gradio
    return "translation", "word_forms", "example_sentence", "audio_file"

# Function to browse flashcards
def browse_flashcards(index):
    if flashcards:
        card = flashcards[index % len(flashcards)]  # Allow cycling through cards
        return card["front"], card["back"], card["forms"], card["sentence"], card["audio"]
    else:
        return "No cards yet", "", "", "", ""

# Gradio UI layout
with gr.Blocks() as demo:
    gr.Markdown("# Danish Learning System")
    
    # Word input and processing
    with gr.Group ():
        word_input = gr.Textbox(label="Enter a Danish or English word:")
        translation_output = gr.Textbox(label="Translation:")
        forms_output = gr.JSON(label="Word Forms:")
        sentence_output = gr.Textbox(label="Example Sentence:")
        audio_output = gr.Audio(label="Pronunciation:")
        submit_btn = gr.Button("Generate Flashcard")

    # Flashcard browsing
    with gr.Group ():
        gr.Markdown("### Browse Flashcards")
        card_index = gr.Slider(minimum=0, maximum=10, step=1, label="Flashcard Index")
        browse_translation = gr.Textbox(label="Danish Word (Front):")
        browse_forms = gr.JSON(label="Word Forms (Back):")
        browse_sentence = gr.Textbox(label="Example Sentence:")
        browse_audio = gr.Audio(label="Pronunciation:")
        browse_btn = gr.Button("Browse")

    # Event handlers
    submit_btn.click(process_word, inputs=[word_input], outputs=[translation_output, forms_output, sentence_output, audio_output])
    browse_btn.click(browse_flashcards, inputs=[card_index], outputs=[browse_translation, browse_translation, browse_forms, browse_sentence, browse_audio])

# Launch the Gradio interface
demo.launch()
