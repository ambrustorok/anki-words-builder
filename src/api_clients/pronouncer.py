import tempfile
import numpy as np
import soundfile as sf
from dotenv import load_dotenv
from openai import OpenAI
import random

load_dotenv()
client = OpenAI()


def add_silence(input_file, output_file, silence_duration_sec=0.5):
    """
    Adds a specified duration of silence at the beginning of an audio file.

    Args:
        input_file (str): Path to the input audio file.
        output_file (str): Path to the output audio file with silence added.
        silence_duration_sec (float): Duration of silence to add at the beginning, in seconds. Default is 0.5 seconds.

    Returns:
        None

    Creates:
        - `output_file`: An audio file with the specified duration of silence added to the beginning of the original audio.
    """
    # Read the input audio file
    data, samplerate = sf.read(input_file)

    # Calculate the number of samples for silence
    silence_samples = int(silence_duration_sec * samplerate)

    # Create silence
    silence = (
        np.zeros((silence_samples, data.shape[1]))
        if data.ndim > 1
        else np.zeros(silence_samples)
    )

    # Concatenate silence with original audio
    new_data = np.concatenate((silence, data), axis=0)

    # Write the output file
    sf.write(output_file, new_data, samplerate)


def pronounce_text(text, lang="da"):
    """
    Converts text to speech using OpenAI's TTS model, and saves the resulting audio to a file with 1 second of silence added at the beginning.

    Args:
        text (str): The text to be converted to speech.
        lang (str): The language code for the translation (e.g., "da" for Danish). Default is "da".

    Returns:
        None

    Creates:
        - `output_with_silence.mp3`: An audio file with the TTS-generated speech and 1 second of silence added to the beginning.

    Notes:
        A temporary audio file is created during processing to store the initial TTS output. This file is deleted after the final output is created.
    """
    prompt = f"Language: {lang}\nText: '{text}'"
    voices = ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]

    # Randomly choose a model
    selected_voice = random.choice(voices)

    # Create a temporary file for the streamed audio output
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as temp_audio_file:
        temp_audio_path = temp_audio_file.name

        # Stream the TTS output to the temporary file
        with client.audio.speech.with_streaming_response.create(
            model="tts-1",
            voice=selected_voice,
            input=prompt,
        ) as response:
            response.stream_to_file(temp_audio_path)

    # Create an output file path
    output_file_path = "output_with_silence.mp3"

    # Add 1 second of silence to the audio
    add_silence(temp_audio_path, output_file_path, silence_duration_sec=1)


# Call function with Danish sentence
pronounce_text(text="Hej, hvordan har du det?", lang="da")

