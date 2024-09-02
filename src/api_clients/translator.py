from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI()


def translate_text(text, source_lang="da", target_lang="en"):
    """
    Translates text from a source language to a target language using OpenAI's GPT model.

    Args:
        text (str): The text to be translated.
        source_lang (str): The language code of the source language (default is "da" for Danish).
        target_lang (str): The language code of the target language (default is "en" for English).

    Returns:
        str: The translated text.

    Example:
        >>> translate_text("kat", source_lang="da", target_lang="en")
        'cat'
    """
    prompt = f"""Translate the following text from {source_lang} to {target_lang}. 
    Do not return anything else, only the resulting text. 
    Make sure that the text you return appears in dictionary form. 
    That is it should include and declensions or conjugations, adjectives or different tense forms.
    
    Text: '''{text}'''"""

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {
                "role": "system",
                "content": "You are a translation assistant. You will help translate text between languages.",
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.7,
        max_tokens=100,
        top_p=1,
        frequency_penalty=0,
        presence_penalty=0,
    )

    translated_text = response.choices[0].message.content.strip()
    return translated_text


def generate_sentence(word, lang="da"):
    """
    Generates a sentence in a specified language using a given word in context with OpenAI's GPT model.

    Args:
        word (str): The word to be used in the sentence.
        lang (str): The language code in which to generate the sentence (default is "da" for Danish).

    Returns:
        str: A sentence containing the specified word in the given language.

    Example:
        >>> generate_sentence("kat", lang="da")
        'Jeg har en kat.'
    """
    prompt = f"Provide a single sentence in {lang} using the word '{word}' naturally in context."

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {
                "role": "system",
                "content": "You are an assistant helping to generate example sentences for language learners.",
            },
            {"role": "user", "content": prompt},
        ],
        temperature=1,
        max_tokens=50,
        top_p=1,
        frequency_penalty=0,
        presence_penalty=0,
    )

    sentence = response.choices[0].message.content.strip()
    return sentence


# Example usage:
# translate_text("kat", source_lang="da", target_lang="en")
# generate_sentence("kat", lang="da")
