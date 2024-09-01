from googletrans import Translator

# Function to translate a word
def translate_word(word, src_lang="en", target_lang="da"):
    translator = Translator()
    translation = translator.translate(word, src=src_lang, dest=target_lang)
    return translation.text

# Example usage:
# translate_word("cat", "en", "da") -> "kat"
