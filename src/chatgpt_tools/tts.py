import os
import random
import tempfile
from typing import Optional

from openai import OpenAI

VOICES = [
    "alloy",
    "ash",
    "ballad",
    "coral",
    "echo",
    "fable",
    "nova",
    "onyx",
    "sage",
    "shimmer",
]

DEFAULT_INSTRUCTIONS = "Speak clearly and slowly so that a language learner can mimic the pronunciation."


def _pick_voice(preferred: str) -> str:
    preferred = (preferred or "").strip().lower()
    if preferred and preferred in VOICES:
        return preferred
    return random.choice(VOICES)


def generate_audio_binary(
    openai_client: OpenAI,
    text: str,
    *,
    voice: str = "random",
    instructions: str = "",
) -> Optional[bytes]:
    spoken_text = text.strip()
    if not spoken_text:
        return None

    selected_voice = _pick_voice(voice)
    prompt = instructions.strip() or DEFAULT_INSTRUCTIONS
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    temp_path = temp_file.name
    temp_file.close()
    audio_bytes: Optional[bytes] = None
    try:
        with openai_client.audio.speech.with_streaming_response.create(
            model="gpt-4o-mini-tts",
            voice=selected_voice,
            input=spoken_text,
            response_format="mp3",
            instructions=prompt,
        ) as response:
            response.stream_to_file(temp_path)

        with open(temp_path, "rb") as mp3_file:
            audio_bytes = mp3_file.read()
    finally:
        try:
            os.remove(temp_path)
        except OSError:
            pass

    return audio_bytes if audio_bytes else None
