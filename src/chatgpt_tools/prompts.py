def translate_word(client, word, source_lang="da", target_lang="en"):
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {
                "role": "system",
                "content": f"""You are a translator from {source_lang} to {target_lang}. """,
            },
            {"role": "user", "content": f"Translate the word: {word}"},
        ],
    )
    return response.choices[0].message.content.strip()


def dictionarize_word(client, word, source_lang="da", english_translation=None):
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {
                "role": "system",
                "content": f"""You are a dictionary assistant in lanuage {source_lang}. 
             You will get a word and you have to provide the primitive form of given word and make it look like the way it is in a dictionary.
             Make sure to start by listing the words primitive form!
             Include plural cases, verb forms, genders, cases and other relevant information.
             Use the following template:
             ```
             {{Word}} (Part of Speech)
                Meaning in English: {{English translation}}
                Bøjning: {{Inflections}}
                Udtale: {{Pronunciation}}
                    Additional forms/pronunciation (if applicable): {{Additional Pronunciation}}
                    Oprindelse: {{Origin/etymology}}
            ```
            Examples using the template:
            ``` 
            være (verbum)
            Meaning in English: to be
            Bøjning: er, var, -t (talesprogsefterlignende også: vær')
            Udtale: [ˈvεːʌ]

                præsens: [ˈæɐ̯]
                præteritum: [ˈvɑ]
                præteritum participium: [ˈvεːʌð]
                vær', i la' vær': [ˈvεɐ̯ˀ]
                Oprindelse: norrønt vera, vesa, oldengelsk wesan, ikke beslægtet med præsens er, som er indoeuropæisk: norrønt es, er, engelsk is, latin est
            ```
            ```
            hund (substantiv, fælleskøn)

            Åbn overblik
            Vis overblik
            Meaning in English: dog
            Bøjning: -en, -e, -ene
            Udtale: [ˈhunˀ]

                i sammensætning hunde-: [ˈhunə-]
                Oprindelse: norrønt hundr, tysk Hund, beslægtet med græsk kynos, af uvis oprindelse
            ```
             """,
            },
            {
                "role": "user",
                "content": f"Transform the word: {word}. The user wanted to use the following English translation: {english_translation or 'No translation provided.'}",
            },
        ],
    )
    return response.choices[0].message.content.strip()


def generate_sentence(client, word, language="en"):
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {
                "role": "system",
                "content": f"You are a sentence generator in language {language}.",
            },
            {
                "role": "user",
                "content": f"Generate a simple sentence using the word: {word}",
            },
        ],
    )
    return response.choices[0].message.content.strip()