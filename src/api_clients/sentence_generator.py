from openai import OpenAI
client = OpenAI()

# Function to generate example sentences using OpenAI GPT
def generate_sentence(word, lang="da"):
    prompt = f"You will receive a work in language {lang}. You have to return a single sentence as an example with it, where it is being used in the language. Do not return anything else, but the sentence."

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
            "role": "system",
            "content": [
                {
                "type": "text",
                "text": prompt
                }
            ]
            },
            {
            "role": "user",
            "content": [
                {
                "type": "text",
                "text": word
                }
            ]
            },
        ],
        temperature=1,
        max_tokens=256,
        top_p=1,
        frequency_penalty=0,
        presence_penalty=0,
        response_format={
            "type": "text"
        }
    )

    sentence = response['choices'][0]['message']['content']
    return sentence

# Example usage:
# generate_sentence("kat") -> "Katten ligger på bordet."
