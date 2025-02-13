from setup import openai_model


def translate_word(client, word, source_lang="da", target_lang="en"):
    response = client.chat.completions.create(
        model=openai_model,
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
        model=openai_model,
        messages=[
            {
                "role": "system",
                "content": f"""You are a comprehensive dictionary and grammar assistant for {source_lang}. Analyze the given input and determine if it's a word or sentence. Provide detailed linguistic information using these formats:

FOR WORDS:
```
{{Word}} ({{Part of Speech}})
    Base Form: {{primitive/lemma}}
    Article: {{definite and indefinite articles if applicable}}
    Gender: {{grammatical gender if applicable}}
    Pronunciation: {{IPA}}
    Etymology: {{origin}}
    
    Inflections:
        {{detailed list of all applicable forms}}
        - Include all article + gender combinations
        - List all case forms with their articles
    
    Variations:
        {{list of regional/dialectal forms}}
    
    Exceptions:
        {{list of any irregular patterns}}
    
    Usage Notes:
        {{register, collocations, domain}}
```

Example for German "Haus":
```
Haus (noun, neuter)
    Base Form: das Haus
    Article: definite: das, indefinite: ein
    Gender: neuter
    Pronunciation: /haʊs/
    Etymology: Old High German hūs
    
    Inflections:
        Nominative: das Haus (sg), die Häuser (pl)
        Accusative: das Haus (sg), die Häuser (pl)
        Dative: dem Haus (sg), den Häusern (pl)
        Genitive: des Hauses (sg), der Häuser (pl)
    
    Variations:
        Regional: Häusl (Bavarian diminutive)
        
    Compounds:
        Hausarbeit (f), Hausaufgabe (f), Haustür (f)
    
    Usage Notes:
        Register: Standard
        Common Phrases: zu Hause, nach Hause
```

FOR SENTENCES:
```
Sentence Analysis:
    Original: {{sentence}}
    
    Grammatical Structure:
        - Clause Type: {{main/subordinate/relative etc.}}
        - Word Order: {{e.g., SVO, SOV, VSO}}
        - Tense: {{present/past/future etc.}}
        - Mood: {{indicative/subjunctive/imperative}}
        - Voice: {{active/passive}}
    
    Components:
        - Subject: {{identify + type}}
        - Predicate: {{identify + type}}
        - Objects: {{direct/indirect + type}}
        - Modifiers: {{adjectives/adverbs + their roles}}
        - Prepositions: {{list + their functions}}
    
    Special Features:
        - Complex Structures: {{dependent clauses, embedded phrases}}
        - Idiomatic Elements: {{if any}}
        - Register: {{formal/informal/colloquial}}
```

Example for "The cat quickly caught the mouse in the garden":
```
Sentence Analysis:
    Original: The cat quickly caught the mouse in the garden
    
    Grammatical Structure:
        - Clause Type: Simple independent clause
        - Word Order: SVO
        - Tense: Past simple
        - Mood: Indicative
        - Voice: Active
    
    Components:
        - Subject: "The cat" (definite noun phrase)
        - Predicate: "caught" (transitive verb)
        - Direct Object: "the mouse" (definite noun phrase)
        - Adverbial Modifier: "quickly" (manner)
        - Prepositional Phrase: "in the garden" (location)
    
    Special Features:
        - Structure: Basic SVO with adverbial and prepositional modifiers
        - Register: Neutral/standard
```""",
            },
            {
                "role": "user",
                "content": f"Analyze this: {word_or_sentence}",
            },
        ],
    )
    return response.choices[0].message.content.strip()


def generate_sentence(client, word, language="en"):
    response = client.chat.completions.create(
        model=openai_model,
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
