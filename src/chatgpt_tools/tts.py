import os
import tempfile
import numpy as np
import soundfile as sf
import random


def add_silence(input_file, output_file, silence_duration_sec=0.5):
    data, samplerate = sf.read(input_file)
    silence_samples = int(silence_duration_sec * samplerate)
    silence = (
        np.zeros((silence_samples, data.shape[1]))
        if data.ndim > 1
        else np.zeros(silence_samples)
    )
    new_data = np.concatenate((silence, data), axis=0)
    sf.write(output_file, new_data, samplerate)


def remove_audio_start(input_file, output_file, duration_sec):
    # Read the audio file
    data, samplerate = sf.read(input_file)

    # Calculate the number of samples to remove
    samples_to_remove = int(duration_sec * samplerate)

    # Remove the first x seconds
    new_data = data[samples_to_remove:]

    # Write the modified audio to the output file
    sf.write(output_file, new_data, samplerate)


def get_audio(
    client, text, lang="da", output_dir="/mnt/d/OneDrive/Projects/data/anki_audio"
):
    voices = ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]
    selected_voice = random.choice(voices)
    prompt = f"Læs dette på dansk: '{text}'"

    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as temp_audio_file:
        temp_audio_path = temp_audio_file.name
        with client.audio.speech.with_streaming_response.create(
            model="tts-1",
            voice=selected_voice,
            input=prompt,
        ) as response:
            response.stream_to_file(temp_audio_path)

    os.makedirs(output_dir, exist_ok=True)
    output_file_path = os.path.join(output_dir, f"audio_{text}.mp3")
    add_silence(temp_audio_path, output_file_path, silence_duration_sec=0)
    remove_audio_start(temp_audio_path, output_file_path, duration_sec=1.07)
    os.remove(temp_audio_path)
    return output_file_path
