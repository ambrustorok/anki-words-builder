import random
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

    response = openai_client.audio.speech.create(
        model="gpt-4o-mini-tts",
        voice=selected_voice,
        input=spoken_text,
        response_format="mp3",
        instructions=prompt,
    )
    return response.content
