from ..settings import OPENAI_MODEL


def translate_word(client, word, source_lang="da", target_lang="en"):
    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {
                "role": "system",
                "content": f"""You are a translator from {source_lang} to {target_lang}. """,
            },
            {
                "role": "user",
                "content": f"Translate the word/phrase: {word}. Return the translation only.",
            },
        ],
    )
    return response.choices[0].message.content.strip()


def dictionarize_word(client, word_or_sentence, source_lang="en"):
    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {
                "role": "system",
                "content": f"""You are a concise linguistic analyzer for {source_lang}. Determine if the input is a word (including infinitives like "at skrive") or a sentence.

FORMATTING INSTRUCTIONS:
You may ONLY use these HTML elements for formatting:
- <div> for sections
- <br> for line breaks
- <ul>/<li> for lists
- <b> for bold text
- <i> for italic text
- <u> for underlined text
NO other HTML elements are permitted.

FOR WORDS (any part of speech):
- Distinguish infinitives (like "at skrive") from sentences
- For nouns: cases, articles, gender, number forms
- For verbs: key tenses, moods, persons, common phrasal verbs
- For adjectives: comparative forms, any required declensions
- Include 2-3 common phrases where this word typically appears
- Only include relevant categories for this word type in {source_lang}

FOR SENTENCES:
Provide a brief grammatical breakdown:
- Core pattern and clause structure
- Key grammatical elements
- Notable {source_lang}-specific features

Use appropriate line breaks and lists to organize information clearly. Be comprehensive about grammatical forms but concise in presentation.""",
            },
            {
                "role": "user",
                "content": f"Analyze this: {word_or_sentence}",
            },
        ],
        temperature=0.2,
    )
    return response.choices[0].message.content.strip()


def generate_sentence(client, word, language="en"):
    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {
                "role": "system",
                "content": f"""You are a sentence generator in language {language}. 
                If you are given a complete sentence, you are welcome to return the original sentence.""",
            },
            {
                "role": "user",
                "content": f"Generate a simple sentence using the word: {word}",
            },
        ],
    )
    return response.choices[0].message.content.strip()
