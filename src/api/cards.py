import base64
import io
from typing import Dict, List, Literal, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ..services import api_keys as api_key_service
from ..services import cards as card_service
from ..services import decks as deck_service
from ..services import generation as generation_service
from .dependencies import get_current_user, parse_uuid

router = APIRouter(prefix="/cards")

AUDIO_VOICES = [
    "random",
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
MAX_REMOTE_AUDIO_BYTES = 10 * 1024 * 1024


class AudioPreferences(BaseModel):
    voice: str = "random"
    instructions: Optional[str] = None


class CardActionRequest(BaseModel):
    deck_id: str = Field(..., alias="deckId")
    group_id: Optional[str] = Field(None, alias="groupId")
    mode: Literal["create", "edit"] = "create"
    action: Literal[
        "save",
        "populate_all",
        "regen_native_phrase",
        "regen_dictionary_entry",
        "regen_example_sentence",
        "regen_audio",
        "fetch_audio",
    ] = "save"
    payload: Dict[str, str]
    directions: List[str] = Field(default_factory=lambda: ["forward", "backward"])
    audio_preview: Optional[str] = Field("", alias="audioPreview")
    audio_url: Optional[str] = Field(None, alias="audioUrl")
    audio_preferences: Optional[AudioPreferences] = Field(
        None, alias="audioPreferences"
    )
    input_mode: Literal["foreign", "native"] = Field("foreign", alias="inputMode")


def _encode_audio_preview(audio_bytes: Optional[bytes]) -> str:
    if not audio_bytes:
        return ""
    return base64.b64encode(audio_bytes).decode("utf-8")


def _decode_audio_preview(data: Optional[str]) -> Optional[bytes]:
    if not data:
        return None
    try:
        return base64.b64decode(data)
    except Exception:
        return None


def _infer_audio_format(filename: Optional[str], content_type: Optional[str]) -> Optional[str]:
    if content_type:
        normalized = content_type.split(";")[0].strip().lower()
        content_map = {
            "audio/mpeg": "mp3",
            "audio/mp3": "mp3",
            "audio/wav": "wav",
            "audio/x-wav": "wav",
            "audio/wave": "wav",
            "audio/aac": "aac",
            "audio/x-aac": "aac",
            "audio/m4a": "m4a",
            "audio/mp4": "mp4",
            "audio/ogg": "ogg",
            "audio/webm": "webm",
            "audio/flac": "flac",
        }
        if normalized in content_map:
            return content_map[normalized]
    if filename:
        ext = filename.split(".")[-1].lower()
        extension_map = {
            "mp3": "mp3",
            "wav": "wav",
            "aac": "aac",
            "m4a": "mp4",
            "mp4": "mp4",
            "ogg": "ogg",
            "opus": "ogg",
            "flac": "flac",
            "webm": "webm",
        }
        if ext in extension_map:
            return extension_map[ext]
    return None


def _convert_audio_bytes_to_mp3(data: bytes, *, source_format: Optional[str] = None) -> bytes:
    from pydub import AudioSegment
    from pydub.exceptions import CouldntDecodeError

    buffer = io.BytesIO(data)
    buffer.seek(0)
    try:
        if source_format:
            segment = AudioSegment.from_file(buffer, format=source_format)
        else:
            segment = AudioSegment.from_file(buffer)
    except CouldntDecodeError as exc:
        raise ValueError("Unable to decode the uploaded audio. Please upload a valid audio file.") from exc
    except Exception as exc:
        raise ValueError("Failed to process the uploaded audio file.") from exc
    output = io.BytesIO()
    segment.export(output, format="mp3")
    return output.getvalue()


async def _download_audio_from_url(url: str) -> bytes:
    normalized = (url or "").strip()
    if not normalized:
        raise ValueError("Enter an audio URL to fetch.")
    if not normalized.lower().startswith(("http://", "https://")):
        raise ValueError("Audio URL must start with http:// or https://.")
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(normalized)
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code if exc.response else "unknown"
        raise ValueError(f"Unable to download audio (HTTP {status}).") from exc
    except httpx.RequestError as exc:
        raise ValueError("Unable to reach the audio URL. Check the link and try again.") from exc
    data = response.content
    if not data:
        raise ValueError("Downloaded file was empty.")
    if len(data) > MAX_REMOTE_AUDIO_BYTES:
        raise ValueError("Audio file is too large. Please provide a clip under 10 MB.")
    format_hint = _infer_audio_format(normalized, response.headers.get("Content-Type"))
    return _convert_audio_bytes_to_mp3(data, source_format=format_hint)


def _get_foreign_field_key(deck: dict) -> Optional[str]:
    for field in deck.get("field_schema", []):
        if field.get("key") == "foreign_phrase":
            return field["key"]
    for field in deck.get("field_schema", []):
        if field.get("required"):
            return field["key"]
    schema = deck.get("field_schema") or []
    if schema:
        return schema[0]["key"]
    return None


def _get_native_field_key(deck: dict) -> Optional[str]:
    for field in deck.get("field_schema", []):
        if field.get("key") == "native_phrase":
            return field["key"]
    return None


def _default_audio_preferences(deck: Optional[dict]) -> dict:
    instructions = deck_service.get_audio_instructions(deck) if deck else ""
    return {"voice": "random", "instructions": instructions}


def _merge_audio_preferences(preferences: Optional[AudioPreferences], deck: dict) -> dict:
    defaults = _default_audio_preferences(deck)
    if not preferences:
        return defaults
    voice = (preferences.voice or "random").lower()
    if voice not in AUDIO_VOICES:
        voice = "random"
    instructions = (preferences.instructions or "").strip()
    if not instructions:
        instructions = defaults["instructions"]
    return {"voice": voice, "instructions": instructions}


def _normalize_payload(deck: dict, payload: Dict[str, str]) -> Dict[str, str]:
    normalized: Dict[str, str] = {}
    for field in deck.get("field_schema", []):
        value = payload.get(field["key"], "")
        if isinstance(value, str):
            normalized[field["key"]] = value.strip()
        else:
            normalized[field["key"]] = value
    return normalized


def _normalize_directions(request: CardActionRequest, group: Optional[dict]) -> List[str]:
    requested = [direction for direction in request.directions if direction in {"forward", "backward"}]
    if requested:
        return requested
    if group:
        return [row["direction"] for row in group["rows"]]
    return ["forward", "backward"]


def _require_generation(client, generation_allowed: bool):
    if not generation_allowed or client is None:
        raise HTTPException(
            status_code=400,
            detail="Add an OpenAI API key on your profile before generating fields.",
        )


async def _handle_action(
    request: CardActionRequest,
    user: dict,
) -> dict:
    deck_uuid = parse_uuid(request.deck_id, entity="Deck")
    deck = deck_service.get_deck(deck_uuid, user["id"])
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found.")

    group = None
    if request.mode == "edit":
        if not request.group_id:
            raise HTTPException(status_code=400, detail="Missing card group id.")
        group_uuid = parse_uuid(request.group_id, entity="Card")
        group = card_service.get_card_group(user["id"], group_uuid)
        if not group:
            raise HTTPException(status_code=404, detail="Card not found.")

    payload = _normalize_payload(deck, request.payload)
    directions = _normalize_directions(request, group)
    audio_preview_b64 = request.audio_preview or ""
    audio_bytes = _decode_audio_preview(audio_preview_b64)
    if audio_bytes is None and group and group.get("audio"):
        audio_bytes = group["audio"]
        audio_preview_b64 = _encode_audio_preview(audio_bytes)
    audio_preferences = _merge_audio_preferences(request.audio_preferences, deck)
    audio_allowed = deck_service.is_audio_enabled(deck)
    audio_url = (request.audio_url or "").strip()

    foreign_field_key = _get_foreign_field_key(deck)
    if not foreign_field_key:
        raise HTTPException(status_code=400, detail="Deck is missing a foreign phrase field.")
    native_field_key = _get_native_field_key(deck)

    input_mode = request.input_mode if request.input_mode in {"foreign", "native"} else "foreign"
    if input_mode == "native":
        if not native_field_key:
            raise HTTPException(status_code=400, detail="Deck is missing a native phrase field.")
        seed_field_key = native_field_key
        seed_label = "native phrase"
    else:
        seed_field_key = foreign_field_key
        seed_label = "foreign phrase"

    generation_allowed = api_key_service.user_can_generate(user["id"])
    client = (
        api_key_service.get_openai_client_for_user(user["id"]) if generation_allowed else None
    )
    generation_prompts = deck_service.get_generation_prompts(deck)
    native_language = user.get("native_language") or "English"

    def ensure_input_phrase():
        value = (payload.get(seed_field_key) or "").strip()
        if value:
            return
        raise HTTPException(status_code=400, detail=f"Enter a {seed_label} first.")

    def ensure_foreign_phrase(require_translation: bool = False):
        value = (payload.get(foreign_field_key) or "").strip()
        if value:
            return
        if seed_field_key == foreign_field_key:
            raise HTTPException(status_code=400, detail="Enter a foreign phrase first.")
        ensure_input_phrase()
        if not require_translation:
            raise HTTPException(
                status_code=400,
                detail="Add a foreign phrase before continuing or process the native input.",
            )
        _require_generation(client, generation_allowed)
        try:
            payload[foreign_field_key] = generation_service.generate_foreign_from_native(
                client,
                generation_prompts,
                payload.get(seed_field_key, ""),
                native_language,
                deck["target_language"],
            )
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Translation failed: {exc}") from exc

    if request.action == "fetch_audio":
        if not audio_allowed:
            raise HTTPException(status_code=400, detail="Audio is disabled for this deck.")
        if not audio_url:
            raise HTTPException(status_code=400, detail="Enter an audio URL to fetch.")
        audio_bytes = await _download_audio_from_url(audio_url)
        audio_preview_b64 = _encode_audio_preview(audio_bytes)
        return {
            "status": "ok",
            "message": "Audio fetched from link. Remember to save when ready.",
            "payload": payload,
            "directions": directions,
            "audioPreview": audio_preview_b64,
        }

    if request.action not in {"save", "regen_audio", "fetch_audio"}:
        ensure_foreign_phrase(require_translation=input_mode == "native")

    if request.action == "regen_native_phrase":
        _require_generation(client, generation_allowed)
        try:
            generation_service.regenerate_field(
                client,
                "native_phrase",
                payload,
                foreign_field_key,
                deck["target_language"],
                native_language,
                generation_prompts,
                deck.get("field_schema"),
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {
            "status": "ok",
            "message": "Translation updated.",
            "payload": payload,
            "directions": directions,
            "audioPreview": audio_preview_b64,
        }

    if request.action == "regen_dictionary_entry":
        _require_generation(client, generation_allowed)
        try:
            generation_service.regenerate_field(
                client,
                "dictionary_entry",
                payload,
                foreign_field_key,
                deck["target_language"],
                native_language,
                generation_prompts,
                deck.get("field_schema"),
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {
            "status": "ok",
            "message": "Dictionary entry updated.",
            "payload": payload,
            "directions": directions,
            "audioPreview": audio_preview_b64,
        }

    if request.action == "regen_example_sentence":
        _require_generation(client, generation_allowed)
        try:
            generation_service.regenerate_field(
                client,
                "example_sentence",
                payload,
                foreign_field_key,
                deck["target_language"],
                native_language,
                generation_prompts,
                deck.get("field_schema"),
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {
            "status": "ok",
            "message": "Example sentence updated.",
            "payload": payload,
            "directions": directions,
            "audioPreview": audio_preview_b64,
        }

    if request.action == "regen_audio":
        if not audio_allowed:
            raise HTTPException(status_code=400, detail="Audio is disabled for this deck.")
        _require_generation(client, generation_allowed)
        ensure_foreign_phrase(require_translation=input_mode == "native")
        try:
            audio_bytes = generation_service.generate_audio_for_phrase(
                client,
                payload.get(foreign_field_key, ""),
                voice=audio_preferences["voice"],
                instructions=audio_preferences["instructions"],
            )
            audio_preview_b64 = _encode_audio_preview(audio_bytes)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Audio generation failed: {exc}") from exc
        return {
            "status": "ok",
            "message": "Audio regenerated.",
            "payload": payload,
            "directions": directions,
            "audioPreview": audio_preview_b64,
        }

    if request.action == "populate_all":
        _require_generation(client, generation_allowed)
        try:
            payload = generation_service.enrich_payload(
                client,
                payload,
                foreign_field_key,
                deck["target_language"],
                native_language,
                generation_prompts,
                deck.get("field_schema"),
            )
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Generation failed: {exc}") from exc
        if audio_allowed:
            try:
                audio_bytes = generation_service.generate_audio_for_phrase(
                    client,
                    payload.get(foreign_field_key, ""),
                    voice=audio_preferences["voice"],
                    instructions=audio_preferences["instructions"],
                )
                audio_preview_b64 = _encode_audio_preview(audio_bytes)
            except Exception as exc:
                raise HTTPException(status_code=500, detail=f"Audio generation failed: {exc}") from exc
        return {
            "status": "ok",
            "message": "All fields populated. Review and save when ready.",
            "payload": payload,
            "directions": directions,
            "audioPreview": audio_preview_b64,
        }

    if request.action == "save":
        ensure_foreign_phrase(require_translation=input_mode == "native")
        if request.mode == "create" and not directions:
            raise HTTPException(status_code=400, detail="Select at least one direction.")
        auto_generate = generation_allowed and client is not None

        if auto_generate:
            try:
                payload = generation_service.enrich_payload(
                    client,
                    payload,
                    foreign_field_key,
                    deck["target_language"],
                    native_language,
                    generation_prompts,
                    deck.get("field_schema"),
                )
            except Exception as exc:
                raise HTTPException(status_code=500, detail=f"Generation failed: {exc}") from exc
            if audio_allowed and audio_bytes is None:
                try:
                    audio_bytes = generation_service.generate_audio_for_phrase(
                        client,
                        payload.get(foreign_field_key, ""),
                        voice=audio_preferences["voice"],
                        instructions=audio_preferences["instructions"],
                    )
                    audio_preview_b64 = _encode_audio_preview(audio_bytes)
                except Exception as exc:
                    raise HTTPException(status_code=500, detail=f"Audio generation failed: {exc}") from exc

        if request.mode == "create":
            try:
                group_id = card_service.create_cards(
                    user["id"],
                    deck,
                    payload,
                    directions,
                    native_language,
                    audio_bytes=audio_bytes,
                )
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            return {
                "status": "saved",
                "deckId": str(deck["id"]),
                "cardGroupId": str(group_id),
            }

        if not group:
            raise HTTPException(status_code=404, detail="Card not found.")
        try:
            success = card_service.update_card_group(
                user["id"],
                parse_uuid(request.group_id, entity="Card"),
                deck,
                payload,
                directions,
                audio_bytes,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if not success:
            raise HTTPException(status_code=404, detail="Card not found.")
        return {
            "status": "saved",
            "deckId": str(deck["id"]),
            "cardGroupId": request.group_id,
        }

    raise HTTPException(status_code=400, detail="Unsupported action.")


@router.post("/actions")
async def card_action(request: CardActionRequest, user=Depends(get_current_user)):
    return await _handle_action(request, user)


@router.get("/groups/{group_id}")
def get_card_group(group_id: str, user=Depends(get_current_user)):
    group_uuid = parse_uuid(group_id, entity="Card")
    group = card_service.get_card_group(user["id"], group_uuid)
    if not group:
        raise HTTPException(status_code=404, detail="Card not found.")
    deck = group["deck"]
    audio_preview = _encode_audio_preview(group.get("audio"))
    directions = [row["direction"] for row in group["rows"]]
    return {
        "deck": deck,
        "group": {
            "id": group["group_id"],
            "payload": group["payload"],
            "directions": directions,
            "created_at": group.get("created_at"),
            "updated_at": group.get("updated_at"),
        },
        "audioPreview": audio_preview,
        "audioPreferences": _default_audio_preferences(deck),
    }


@router.delete("/groups/{group_id}")
def delete_card_group(group_id: str, user=Depends(get_current_user)):
    group_uuid = parse_uuid(group_id, entity="Card")
    group = card_service.get_card_group(user["id"], group_uuid)
    if not group:
        raise HTTPException(status_code=404, detail="Card not found.")
    card_service.delete_card_group(user["id"], group_uuid)
    return {"status": "ok", "deckId": str(group["deck"]["id"])}


@router.get("/{card_id}/audio")
def card_audio(card_id: str, side: str = Query("front"), user=Depends(get_current_user)):
    card_uuid = parse_uuid(card_id, entity="Card")
    if side not in {"front", "back"}:
        side = "front"
    audio = card_service.get_card_audio(user["id"], card_uuid, side)
    if not audio:
        raise HTTPException(status_code=404, detail="Audio not found.")
    return StreamingResponse(
        io.BytesIO(audio),
        media_type="audio/mpeg",
        headers={"Cache-Control": "no-cache"},
    )
@router.get("/options")
def card_options():
    return {
        "voices": AUDIO_VOICES,
        "defaultAudioInstructions": deck_service.default_audio_instructions_template(),
    }
