from gtts import gTTS
import os

# Function to generate TTS pronunciation for a word
def get_pronunciation(word, lang='da', output_dir='static/audio'):
    tts = gTTS(text=word, lang=lang)
    audio_file = f"{output_dir}/{word}.mp3"
    tts.save(audio_file)
    return audio_file

# Example usage:
# get_pronunciation("hej") -> "static/audio/hej.mp3"
