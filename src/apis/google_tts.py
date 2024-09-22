import requests
import urllib.parse


def construct_tts_link(text, lang_code):
    base_url = "https://translate.google.com/translate_tts"
    params = {"ie": "UTF-8", "tl": lang_code, "client": "tw-ob", "q": text}

    # Encode the query parameters
    query_string = urllib.parse.urlencode(params)

    # Construct the full URL
    tts_url = f"{base_url}?{query_string}"

    return tts_url


# Example usage for Danish (language code 'da'):
text = "God morgen, hvordan har du det?"
lang_code = "da"


def save_tts_to_file(text, lang_code, filename):
    # Construct the TTS link
    tts_url = construct_tts_link(text, lang_code)

    # Make a request to get the audio content
    response = requests.get(tts_url)

    # Check if the request was successful
    if response.status_code == 200:
        # Write the audio content to a file
        with open(filename, "wb") as file:
            file.write(response.content)
        print(f"MP3 saved to {filename}")
    else:
        print(f"Failed to retrieve audio: {response.status_code}")
