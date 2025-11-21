import base64
import io
import os
import uuid
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from urllib.parse import quote_plus

from .db.core import init_db
from .services import api_keys as api_key_service
from .services import cards as card_service
from .services import decks as deck_service
from .services import generation as generation_service
from .services import exporter as export_service
from .services import users as user_service
from .utils.admins import get_auto_admin_emails

load_dotenv()

BASE_DIR = Path(__file__).parent
app = FastAPI(title="Anki Words Builder")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

static_dir = BASE_DIR / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

LOCAL_USER_EMAIL = os.getenv("LOCAL_USER_EMAIL", "local@example.com")
ALLOW_LOCAL_USER = os.getenv("ALLOW_LOCAL_USER", "true").lower() in {"1", "true", "yes"}
ALWAYS_ADMIN_EMAILS = get_auto_admin_emails(LOCAL_USER_EMAIL)
NATIVE_LANGUAGE_OPTIONS = ["English"]
TARGET_LANGUAGE_OPTIONS = ["Danish", "Hungarian"]
def _build_logout_url(request: Request) -> str:
    base = f"{request.url.scheme}://{request.url.netloc}"
    return f"{base}/cdn-cgi/access/logout"


AUDIO_VOICES = [
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
DEFAULT_AUDIO_INSTRUCTIONS_TEMPLATE = deck_service.DEFAULT_AUDIO_INSTRUCTIONS_TEMPLATE
FALLBACK_AUDIO_INSTRUCTIONS = DEFAULT_AUDIO_INSTRUCTIONS_TEMPLATE.replace(
    "{target_language}", "the target language"
)

templates.env.globals["logout_url"] = _build_logout_url


@app.on_event("startup")
def startup_event():
    init_db()


def get_authenticated_email(request: Request) -> str:
    header_email = request.headers.get("Cf-Access-Authenticated-User-Email")
    if header_email:
        return header_email
    if ALLOW_LOCAL_USER:
        return LOCAL_USER_EMAIL
    raise HTTPException(status_code=401, detail="Missing Cloudflare authentication header.")


def get_current_user(request: Request, email: str = Depends(get_authenticated_email)):
    user = user_service.ensure_user(email, auto_admin_emails=ALWAYS_ADMIN_EMAILS)
    request.state.user = user
    return user


def require_admin(user=Depends(get_current_user)):
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required.")
    return user


def _resolve_optional_user(request: Request) -> Optional[dict]:
    """Best-effort helper used outside normal dependency flow."""
    try:
        email = get_authenticated_email(request)
        user = user_service.ensure_user(email, auto_admin_emails=ALWAYS_ADMIN_EMAILS)
    except HTTPException:
        return None
    except Exception:
        return None
    request.state.user = user
    return user


def _ensure_native_language_set(user: dict) -> bool:
    return bool(user.get("native_language"))


def _parse_uuid(value: str, *, entity: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(value))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=f"{entity} not found") from exc


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


def _default_audio_preferences(deck: Optional[dict] = None) -> dict:
    instructions = FALLBACK_AUDIO_INSTRUCTIONS
    if deck:
        instructions = deck_service.get_audio_instructions(deck)
    return {"voice": "random", "instructions": instructions}


def _audio_preferences_from_form(form, deck: Optional[dict]) -> dict:
    defaults = _default_audio_preferences(deck)
    if not form:
        return defaults
    voice = (form.get("audio_voice") or "random").strip().lower()
    if voice not in AUDIO_VOICES:
        voice = "random"
    instructions = (form.get("audio_instructions") or "").strip()
    if not instructions:
        instructions = defaults["instructions"]
    return {"voice": voice, "instructions": instructions}


def _card_form_context(
    request: Request,
    user: dict,
    deck: dict,
    payload: dict,
    directions: list[str],
    *,
    error: Optional[str] = None,
    info: Optional[str] = None,
    audio_preview_b64: str = "",
    mode: str = "create",
    form_action: Optional[str] = None,
    submit_label: str = "Save cards",
    audio_preferences: Optional[dict] = None,
    generation_enabled: bool = True,
):
    context = {
        "request": request,
        "user": user,
        "deck": deck,
        "form_payload": payload,
        "directions": directions,
        "error": error,
        "info": info,
        "key_summary": api_key_service.get_api_key_summary(user["id"]),
        "audio_preview_b64": audio_preview_b64,
        "mode": mode,
        "form_action": form_action or ("/cards" if mode == "create" else ""),
        "submit_label": submit_label,
        "audio_preferences": audio_preferences or _default_audio_preferences(deck),
        "audio_voice_options": ["random"] + AUDIO_VOICES,
        "generation_disabled": not generation_enabled,
        "audio_enabled": deck_service.is_audio_enabled(deck),
    }
    return context


def _build_payload_from_form(deck: dict, form) -> dict:
    payload = {}
    for field in deck.get("field_schema", []):
        payload[field["key"]] = form.get(field["key"], "").strip()
    return payload


def _build_field_schema_from_form(form, existing_schema: Optional[List[dict]] = None) -> List[dict]:
    field_options = deck_service.get_field_library()
    known_keys = {option["key"] for option in field_options}
    preserved = []
    for field in existing_schema or []:
        if field.get("key") not in known_keys:
            preserved.append(field)
    schema: List[dict] = []
    for option in field_options:
        key = option["key"]
        include = True
        if option.get("allow_disable", True):
            include = form.get(f"field_{key}_enabled") == "on"
        if not include:
            continue
        auto_enabled = False
        if option.get("supports_generation"):
            auto_enabled = form.get(f"field_{key}_auto") == "on"
        schema.append(
            {
                "key": key,
                "label": option["label"],
                "required": option.get("required", False),
                "description": option.get("description", ""),
                "auto_generate": auto_enabled,
            }
        )
    schema.extend(preserved)
    return deck_service.normalize_field_schema(schema)


def _field_state_map(schema: Optional[List[dict]]) -> dict:
    state = {}
    if schema:
        for field in schema:
            key = field.get("key")
            if key:
                state[key] = field
    return state


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


def _get_directions_from_form(form, default_if_empty: Optional[list[str]] = None) -> list[str]:
    directions: list[str] = []
    if form.get("direction_forward") == "on":
        directions.append("forward")
    if form.get("direction_backward") == "on":
        directions.append("backward")
    if not directions:
        if default_if_empty is None:
            return []
        return list(default_if_empty)
    return directions


def _redirect_with_feedback(path: str, *, msg: Optional[str] = None, error: Optional[str] = None):
    params: list[str] = []
    if msg:
        params.append(f"msg={quote_plus(msg)}")
    if error:
        params.append(f"error={quote_plus(error)}")
    if params:
        return RedirectResponse(f"{path}?{'&'.join(params)}", status_code=303)
    return RedirectResponse(path, status_code=303)


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request, user=Depends(get_current_user)):
    if not _ensure_native_language_set(user):
        return RedirectResponse("/onboarding", status_code=302)

    recent_decks = deck_service.list_recent_decks(user["id"], limit=3)
    recent_cards = card_service.list_recent_cards(user["id"], user.get("native_language"), limit=10)
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "user": user,
            "recent_decks": recent_decks,
            "recent_cards": recent_cards,
        },
    )


@app.get("/onboarding", response_class=HTMLResponse)
def onboarding(request: Request, user=Depends(get_current_user)):
    if _ensure_native_language_set(user):
        return RedirectResponse("/", status_code=302)
    return templates.TemplateResponse(
        "onboarding.html",
        {
            "request": request,
            "user": user,
            "native_languages": NATIVE_LANGUAGE_OPTIONS,
        },
    )


@app.post("/onboarding")
async def set_native_language(
    request: Request,
    user=Depends(get_current_user),
    native_language: str = Form(...),
):
    language = native_language.strip()
    if not language or language not in NATIVE_LANGUAGE_OPTIONS:
        return templates.TemplateResponse(
            "onboarding.html",
            {
                "request": request,
                "user": user,
                "error": "Please pick a supported native language.",
                "native_languages": NATIVE_LANGUAGE_OPTIONS,
            },
            status_code=400,
        )
    user_service.set_native_language(user["id"], language)
    updated = user_service.get_user(user["id"])
    request.state.user = updated
    return RedirectResponse("/", status_code=303)


@app.get("/profile", response_class=HTMLResponse)
def profile(request: Request, user=Depends(get_current_user)):
    fresh_user = user_service.get_user(user["id"]) or user
    api_key_info = api_key_service.get_api_key_summary(user["id"])
    message = request.query_params.get("msg")
    error = request.query_params.get("error")
    email_message = request.query_params.get("email_msg")
    email_error = request.query_params.get("email_error")
    emails = user_service.list_user_emails(user["id"])
    return templates.TemplateResponse(
        "profile.html",
        {
            "request": request,
            "user": fresh_user,
            "api_key": api_key_info,
            "emails": emails,
            "message": message,
            "error": error,
            "email_message": email_message,
            "email_error": email_error,
        },
    )


@app.post("/profile/api-key")
def set_api_key(
    request: Request,
    user=Depends(get_current_user),
    api_key: str = Form(...),
):
    key = api_key.strip()
    if not key:
        return RedirectResponse("/profile?error=Enter+a+valid+key", status_code=303)
    api_key_service.set_user_api_key(user["id"], key)
    return RedirectResponse("/profile?msg=API+key+saved", status_code=303)


@app.post("/profile/api-key/delete")
def delete_api_key(request: Request, user=Depends(get_current_user)):
    api_key_service.delete_user_api_key(user["id"])
    return RedirectResponse("/profile?msg=API+key+removed", status_code=303)


@app.post("/profile/emails")
def add_profile_email(
    request: Request,
    user=Depends(get_current_user),
    email: str = Form(...),
    make_primary: Optional[str] = Form(None),
):
    make_primary_flag = bool(make_primary)
    try:
        user_service.add_user_email(user["id"], email, make_primary=make_primary_flag)
    except ValueError as exc:
        return RedirectResponse(
            f"/profile?email_error={quote_plus(str(exc))}", status_code=303
        )
    success = "Email added"
    if make_primary_flag:
        success = "Email added and set as primary"
    return RedirectResponse(f"/profile?email_msg={quote_plus(success)}", status_code=303)


@app.post("/profile/emails/{email_id}/delete")
def remove_profile_email(email_id: str, user=Depends(get_current_user)):
    email_uuid = _parse_uuid(email_id, entity="Email")
    try:
        user_service.remove_user_email(user["id"], email_uuid)
    except ValueError as exc:
        return RedirectResponse(
            f"/profile?email_error={quote_plus(str(exc))}", status_code=303
        )
    return RedirectResponse("/profile?email_msg=Email+removed", status_code=303)


@app.post("/profile/emails/{email_id}/primary")
def make_email_primary(email_id: str, user=Depends(get_current_user)):
    email_uuid = _parse_uuid(email_id, entity="Email")
    try:
        user_service.set_primary_email(user["id"], email_uuid)
    except ValueError as exc:
        return RedirectResponse(
            f"/profile?email_error={quote_plus(str(exc))}", status_code=303
        )
    return RedirectResponse("/profile?email_msg=Primary+email+updated", status_code=303)


@app.post("/profile/delete-account")
def delete_account(request: Request, user=Depends(get_current_user)):
    user_service.delete_user(user["id"])
    return RedirectResponse(_build_logout_url(request), status_code=303)


@app.get("/admin/users", response_class=HTMLResponse)
def admin_users(request: Request, user=Depends(require_admin)):
    roster = user_service.list_all_users()
    message = request.query_params.get("msg")
    error = request.query_params.get("error")
    return templates.TemplateResponse(
        "admin/users.html",
        {
            "request": request,
            "user": user,
            "users": roster,
            "message": message,
            "error": error,
        },
    )


@app.get("/admin/users/{user_id}", response_class=HTMLResponse)
def admin_user_detail(request: Request, user_id: str, user=Depends(require_admin)):
    user_uuid = _parse_uuid(user_id, entity="User")
    managed = user_service.get_user(user_uuid)
    if not managed:
        raise HTTPException(status_code=404, detail="User not found.")
    emails = user_service.list_user_emails(user_uuid)
    message = request.query_params.get("msg")
    error = request.query_params.get("error")
    return templates.TemplateResponse(
        "admin/user_detail.html",
        {
            "request": request,
            "user": user,
            "managed_user": managed,
            "emails": emails,
            "message": message,
            "error": error,
            "always_admin_emails": ALWAYS_ADMIN_EMAILS,
        },
    )


@app.post("/admin/users/{user_id}/delete")
def admin_delete_user(user_id: str, user=Depends(require_admin)):
    user_uuid = _parse_uuid(user_id, entity="User")
    managed = user_service.get_user(user_uuid)
    if not managed:
        raise HTTPException(status_code=404, detail="User not found.")
    primary = (managed.get("primary_email") or "").lower()
    if primary and primary in ALWAYS_ADMIN_EMAILS:
        return _redirect_with_feedback(
            f"/admin/users/{user_id}",
            error="Cannot delete a protected admin profile.",
        )
    user_service.delete_user(user_uuid)
    return _redirect_with_feedback(
        "/admin/users",
        msg="Profile deleted.",
    )


@app.post("/admin/users/{user_id}/emails")
def admin_add_user_email(
    user_id: str,
    user=Depends(require_admin),
    email: str = Form(...),
    make_primary: Optional[str] = Form(None),
):
    user_uuid = _parse_uuid(user_id, entity="User")
    managed = user_service.get_user(user_uuid)
    if not managed:
        raise HTTPException(status_code=404, detail="User not found.")
    try:
        user_service.add_user_email(user_uuid, email, make_primary=bool(make_primary))
    except ValueError as exc:
        return _redirect_with_feedback(
            f"/admin/users/{user_id}",
            error=str(exc),
        )
    message = "Email added."
    if make_primary:
        message = "Email added and set as primary."
    return _redirect_with_feedback(
        f"/admin/users/{user_id}",
        msg=message,
    )


@app.post("/admin/users/{user_id}/emails/{email_id}/update")
def admin_update_user_email(
    user_id: str,
    email_id: str,
    user=Depends(require_admin),
    new_email: str = Form(...),
):
    _ = _parse_uuid(user_id, entity="User")
    email_uuid = _parse_uuid(email_id, entity="Email")
    try:
        user_service.update_user_email(email_uuid, new_email)
    except ValueError as exc:
        return _redirect_with_feedback(
            f"/admin/users/{user_id}",
            error=str(exc),
        )
    return _redirect_with_feedback(
        f"/admin/users/{user_id}",
        msg="Email updated.",
    )


@app.post("/admin/users/{user_id}/emails/{email_id}/delete")
def admin_delete_user_email(user_id: str, email_id: str, user=Depends(require_admin)):
    user_uuid = _parse_uuid(user_id, entity="User")
    email_uuid = _parse_uuid(email_id, entity="Email")
    try:
        user_service.remove_user_email(user_uuid, email_uuid)
    except ValueError as exc:
        return _redirect_with_feedback(
            f"/admin/users/{user_id}",
            error=str(exc),
        )
    return _redirect_with_feedback(
        f"/admin/users/{user_id}",
        msg="Email removed.",
    )


@app.post("/admin/users/{user_id}/emails/{email_id}/primary")
def admin_set_primary_email(user_id: str, email_id: str, user=Depends(require_admin)):
    user_uuid = _parse_uuid(user_id, entity="User")
    email_uuid = _parse_uuid(email_id, entity="Email")
    try:
        user_service.set_primary_email(user_uuid, email_uuid)
    except ValueError as exc:
        return _redirect_with_feedback(
            f"/admin/users/{user_id}",
            error=str(exc),
        )
    return _redirect_with_feedback(
        f"/admin/users/{user_id}",
        msg="Primary email updated.",
    )


@app.post("/admin/users/{user_id}/admin")
def admin_toggle_admin(
    user_id: str,
    action: str = Form(...),
    user=Depends(require_admin),
):
    user_uuid = _parse_uuid(user_id, entity="User")
    managed = user_service.get_user(user_uuid)
    if not managed:
        raise HTTPException(status_code=404, detail="User not found.")
    desired_state = None
    if action == "grant":
        desired_state = True
    elif action == "revoke":
        desired_state = False
    else:
        return _redirect_with_feedback(
            f"/admin/users/{user_id}",
            error="Unknown admin action.",
        )
    primary = (managed.get("primary_email") or "").lower()
    if primary and primary in ALWAYS_ADMIN_EMAILS and not desired_state:
        return _redirect_with_feedback(
            f"/admin/users/{user_id}",
            error="Cannot revoke admin from a protected account.",
        )
    user_service.set_admin_status(user_uuid, desired_state)
    status_text = "Admin access granted." if desired_state else "Admin access revoked."
    return _redirect_with_feedback(
        f"/admin/users/{user_id}",
        msg=status_text,
    )


@app.get("/decks", response_class=HTMLResponse)
def decks_page(request: Request, user=Depends(get_current_user)):
    decks = deck_service.list_decks(user["id"])
    return templates.TemplateResponse(
        "decks.html",
        {
            "request": request,
            "user": user,
            "decks": decks,
        },
    )


@app.get("/decks/new", response_class=HTMLResponse)
def new_deck(request: Request, user=Depends(get_current_user)):
    if not _ensure_native_language_set(user):
        return RedirectResponse("/onboarding", status_code=302)
    default_schema = deck_service.default_field_schema()
    return templates.TemplateResponse(
        "deck_new.html",
        {
            "request": request,
            "user": user,
            "default_schema": default_schema,
            "field_options": deck_service.get_field_library(),
            "field_state": _field_state_map(default_schema),
            "custom_fields": [],
            "form_values": {
                "name": "",
                "target_language": "",
                "audio_instructions": DEFAULT_AUDIO_INSTRUCTIONS_TEMPLATE,
                "audio_enabled": True,
            },
            "audio_placeholder": DEFAULT_AUDIO_INSTRUCTIONS_TEMPLATE,
            "target_languages": TARGET_LANGUAGE_OPTIONS,
        },
    )


@app.post("/decks")
async def create_deck(request: Request, user=Depends(get_current_user)):
    form = await request.form()
    name = (form.get("name") or "").strip()
    target_language = (form.get("target_language") or "").strip()
    audio_instructions_raw = form.get("audio_instructions")
    audio_instructions = audio_instructions_raw.strip() if audio_instructions_raw is not None else None
    audio_enabled = form.get("audio_enabled") == "on"
    field_schema = _build_field_schema_from_form(form)
    field_state = _field_state_map(field_schema)
    form_values = {
        "name": name,
        "target_language": target_language,
        "audio_instructions": audio_instructions_raw if audio_instructions_raw is not None else DEFAULT_AUDIO_INSTRUCTIONS_TEMPLATE,
        "audio_enabled": audio_enabled,
    }

    def render_form(error: Optional[str], status_code: int = 400):
        return templates.TemplateResponse(
            "deck_new.html",
            {
                "request": request,
                "user": user,
                "default_schema": deck_service.default_field_schema(),
                "error": error,
                "target_languages": TARGET_LANGUAGE_OPTIONS,
                "field_options": deck_service.get_field_library(),
                "field_state": field_state,
                "form_values": form_values,
                "audio_placeholder": DEFAULT_AUDIO_INSTRUCTIONS_TEMPLATE,
                "custom_fields": [],
            },
            status_code=status_code,
        )

    if not name:
        return render_form("Deck name cannot be empty.")
    if not target_language:
        return render_form("Target language is required.")
    if target_language not in TARGET_LANGUAGE_OPTIONS:
        return render_form("Select one of the supported target languages.")

    deck = deck_service.create_deck(
        owner_id=user["id"],
        name=name,
        target_language=target_language,
        field_schema=field_schema,
        audio_instructions=audio_instructions,
        audio_enabled=audio_enabled,
    )
    return RedirectResponse(f"/decks/{deck['id']}", status_code=303)


@app.get("/decks/{deck_id}/edit", response_class=HTMLResponse)
def edit_deck_page(request: Request, deck_id: str, user=Depends(get_current_user)):
    deck_uuid = _parse_uuid(deck_id, entity="Deck")
    deck = deck_service.get_deck(deck_uuid, user["id"])
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found.")
    generation_prompts = deck_service.get_generation_prompts(deck)
    field_options = deck_service.get_field_library()
    library_keys = {field["key"] for field in field_options}
    custom_fields = [field for field in deck["field_schema"] if field["key"] not in library_keys]
    form_values = {
        "name": deck["name"],
        "target_language": deck["target_language"],
        "audio_instructions": deck_service.get_audio_prompt_template(deck),
        "audio_enabled": deck_service.is_audio_enabled(deck),
    }
    return templates.TemplateResponse(
        "deck_edit.html",
        {
            "request": request,
            "user": user,
            "deck": deck,
            "generation_prompts": generation_prompts,
            "target_languages": TARGET_LANGUAGE_OPTIONS,
            "field_options": field_options,
            "field_state": _field_state_map(deck["field_schema"]),
            "custom_fields": custom_fields,
            "form_values": form_values,
            "audio_placeholder": DEFAULT_AUDIO_INSTRUCTIONS_TEMPLATE,
        },
    )


@app.post("/decks/{deck_id}/edit")
async def update_deck(request: Request, deck_id: str, user=Depends(get_current_user)):
    form = await request.form()
    deck_uuid = _parse_uuid(deck_id, entity="Deck")
    deck = deck_service.get_deck(deck_uuid, user["id"])
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found.")

    name = (form.get("name") or "").strip()
    target_language = (form.get("target_language") or "").strip()
    audio_instructions_raw = form.get("audio_instructions")
    audio_instructions = audio_instructions_raw.strip() if audio_instructions_raw is not None else None
    audio_enabled = form.get("audio_enabled") == "on"
    field_schema = _build_field_schema_from_form(form, deck.get("field_schema"))
    field_state = _field_state_map(field_schema)
    field_options = deck_service.get_field_library()
    library_keys = {option["key"] for option in field_options}
    custom_fields = [field for field in field_schema if field.get("key") not in library_keys]
    generation_prompts = {
        "translation": {
            "system": (form.get("translation_system") or "").strip(),
            "user": (form.get("translation_user") or "").strip(),
        },
        "dictionary": {
            "system": (form.get("dictionary_system") or "").strip(),
            "user": (form.get("dictionary_user") or "").strip(),
        },
        "sentence": {
            "system": (form.get("sentence_system") or "").strip(),
            "user": (form.get("sentence_user") or "").strip(),
        },
    }
    form_values = {
        "name": name,
        "target_language": target_language,
        "audio_instructions": audio_instructions_raw if audio_instructions_raw is not None else deck_service.get_audio_prompt_template(deck),
        "audio_enabled": audio_enabled,
    }
    deck_preview = {
        **deck,
        "name": name or deck["name"],
        "target_language": target_language or deck["target_language"],
        "field_schema": field_schema,
    }

    def render_form(error: Optional[str], status_code: int = 400):
        return templates.TemplateResponse(
            "deck_edit.html",
            {
                "request": request,
                "user": user,
                "deck": deck_preview,
                "generation_prompts": generation_prompts,
                "target_languages": TARGET_LANGUAGE_OPTIONS,
                "field_options": field_options,
                "field_state": field_state,
                "custom_fields": custom_fields,
                "form_values": form_values,
                "error": error,
                "audio_placeholder": DEFAULT_AUDIO_INSTRUCTIONS_TEMPLATE,
            },
            status_code=status_code,
        )

    if not name:
        return render_form("Deck name cannot be empty.")
    if not target_language:
        return render_form("Target language is required.")
    if target_language not in TARGET_LANGUAGE_OPTIONS:
        return render_form("Select one of the supported target languages.")

    updated = deck_service.update_deck(
        user["id"],
        deck_uuid,
        name=name,
        target_language=target_language,
        field_schema=field_schema,
        generation_prompts=generation_prompts,
        audio_instructions=audio_instructions,
        audio_enabled=audio_enabled,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Deck not found.")
    return RedirectResponse(f"/decks/{deck_id}", status_code=303)


@app.post("/decks/{deck_id}/delete")
def delete_deck(deck_id: str, user=Depends(get_current_user)):
    deck_uuid = _parse_uuid(deck_id, entity="Deck")
    deck_service.delete_deck(user["id"], deck_uuid)
    return RedirectResponse("/decks", status_code=303)


@app.get("/decks/{deck_id}", response_class=HTMLResponse)
def deck_detail(request: Request, deck_id: str, user=Depends(get_current_user)):
    if not _ensure_native_language_set(user):
        return RedirectResponse("/onboarding", status_code=302)
    deck_uuid = _parse_uuid(deck_id, entity="Deck")
    deck = deck_service.get_deck(deck_uuid, user["id"])
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found.")
    cards = card_service.list_cards_for_deck(user["id"], deck, user.get("native_language"))
    generation_prompts = deck_service.get_generation_prompts(deck)
    entry_count = len(cards)
    card_count = sum(len(group.get("directions", [])) for group in cards)
    deck_last_modified = deck.get("updated_at")
    if cards:
        most_recent_card = max(
            (card.get("updated_at") for card in cards if card.get("updated_at")),
            default=None,
        )
        if most_recent_card:
            if deck_last_modified:
                deck_last_modified = max(deck_last_modified, most_recent_card)
            else:
                deck_last_modified = most_recent_card
    return templates.TemplateResponse(
        "deck_detail.html",
        {
            "request": request,
            "user": user,
            "deck": deck,
            "cards": cards,
            "generation_prompts": generation_prompts,
            "just_saved": request.query_params.get("saved") == "1",
            "entry_count": entry_count,
            "card_count": card_count,
            "deck_last_modified": deck_last_modified,
        },
    )


@app.get("/decks/{deck_id}/export")
def export_deck(deck_id: str, user=Depends(get_current_user)):
    deck_uuid = _parse_uuid(deck_id, entity="Deck")
    deck = deck_service.get_deck(deck_uuid, user["id"])
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found.")

    cards = card_service.get_cards_for_export(
        user["id"], deck, user.get("native_language")
    )
    if not cards:
        raise HTTPException(status_code=400, detail="No cards to export yet.")

    binary = export_service.export_deck(deck, cards)
    filename_slug = deck["name"].lower().replace(" ", "_")
    return StreamingResponse(
        io.BytesIO(binary),
        media_type="application/vnd.anki",
        headers={
            "Content-Disposition": f'attachment; filename="{filename_slug}.apkg"'
        },
    )


@app.get("/cards/new", response_class=HTMLResponse)
def new_card(request: Request, deck_id: str, user=Depends(get_current_user)):
    deck_uuid = _parse_uuid(deck_id, entity="Deck")
    deck = deck_service.get_deck(deck_uuid, user["id"])
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found.")
    audio_preferences = _default_audio_preferences(deck)
    generation_allowed = api_key_service.user_can_generate(user["id"])
    return templates.TemplateResponse(
        "card_form.html",
        _card_form_context(
            request,
            user,
            deck,
            {},
            ["forward", "backward"],
            mode="create",
            form_action="/cards",
            submit_label="Save cards",
            audio_preferences=audio_preferences,
            generation_enabled=generation_allowed,
        ),
    )


@app.exception_handler(404)
async def not_found_handler(request: Request, exc: HTTPException):
    user = _resolve_optional_user(request)
    return templates.TemplateResponse(
        "404.html",
        {
            "request": request,
            "user": user,
            "missing_path": request.url.path,
            "title": "Page not found",
        },
        status_code=404,
    )


@app.post("/cards")
async def create_card(request: Request, user=Depends(get_current_user)):
    form = await request.form()
    deck_id = form.get("deck_id")
    if not deck_id:
        raise HTTPException(status_code=400, detail="Deck is required.")
    deck_uuid = _parse_uuid(deck_id, entity="Deck")
    deck = deck_service.get_deck(deck_uuid, user["id"])
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found.")

    payload = _build_payload_from_form(deck, form)
    directions = _get_directions_from_form(form, default_if_empty=["forward", "backward"])
    foreign_field_key = _get_foreign_field_key(deck)
    audio_preview_b64 = form.get("audio_preview_b64", "")
    audio_bytes = _decode_audio_preview(audio_preview_b64)
    submit_action = form.get("submit_action", "save")
    generation_allowed = api_key_service.user_can_generate(user["id"])
    client = (
        api_key_service.get_openai_client_for_user(user["id"]) if generation_allowed else None
    )
    generation_prompts = deck_service.get_generation_prompts(deck)
    audio_preferences = _audio_preferences_from_form(form, deck)
    audio_allowed = deck_service.is_audio_enabled(deck)

    if not foreign_field_key:
        raise HTTPException(status_code=400, detail="Deck is missing a foreign phrase field.")

    def render_form(error: Optional[str] = None, info: Optional[str] = None, status_code: int = 200):
        return templates.TemplateResponse(
            "card_form.html",
            _card_form_context(
                request,
                user,
                deck,
                payload,
                directions,
                error=error,
                info=info,
                audio_preview_b64=audio_preview_b64,
                mode="create",
                form_action="/cards",
                submit_label="Save cards",
                audio_preferences=audio_preferences,
                generation_enabled=generation_allowed,
            ),
            status_code=status_code,
        )

    if submit_action != "save" and submit_action != "regen_audio":
        if not payload.get(foreign_field_key):
            return render_form(error="Please enter a foreign phrase first.", status_code=400)

    def require_generation():
        if not generation_allowed or client is None:
            return render_form(
                error="Add an OpenAI API key on your profile before generating fields.",
                status_code=400,
            )
        return None

    if submit_action == "regen_native_phrase":
        missing = require_generation()
        if missing:
            return missing
        try:
            generation_service.regenerate_field(
                client,
                "native_phrase",
                payload,
                foreign_field_key,
                deck["target_language"],
                user.get("native_language") or "English",
                generation_prompts,
                deck.get("field_schema"),
            )
        except Exception as err:
            return render_form(error=str(err), status_code=400)
        return render_form(info="Translation updated.")
    elif submit_action == "regen_dictionary_entry":
        missing = require_generation()
        if missing:
            return missing
        try:
            generation_service.regenerate_field(
                client,
                "dictionary_entry",
                payload,
                foreign_field_key,
                deck["target_language"],
                user.get("native_language") or "English",
                generation_prompts,
                deck.get("field_schema"),
            )
        except Exception as err:
            return render_form(error=str(err), status_code=400)
        return render_form(info="Dictionary entry updated.")
    elif submit_action == "regen_example_sentence":
        missing = require_generation()
        if missing:
            return missing
        try:
            generation_service.regenerate_field(
                client,
                "example_sentence",
                payload,
                foreign_field_key,
                deck["target_language"],
                user.get("native_language") or "English",
                generation_prompts,
                deck.get("field_schema"),
            )
        except Exception as err:
            return render_form(error=str(err), status_code=400)
        return render_form(info="Example sentence updated.")
    elif submit_action == "regen_audio":
        if not audio_allowed:
            return render_form(error="Audio is disabled for this deck. Enable it from the deck settings.", status_code=400)
        missing = require_generation()
        if missing:
            return missing
        if not payload.get(foreign_field_key):
            return render_form(error="Enter a foreign phrase before generating audio.", status_code=400)
        try:
            audio_bytes = generation_service.generate_audio_for_phrase(
                client,
                payload.get(foreign_field_key, ""),
                voice=audio_preferences["voice"],
                instructions=audio_preferences["instructions"],
            )
            audio_preview_b64 = _encode_audio_preview(audio_bytes)
        except Exception as err:
            return render_form(error=f"Audio generation failed: {err}", status_code=500)
        return render_form(info="Audio regenerated.")
    elif submit_action == "populate_all":
        missing = require_generation()
        if missing:
            return missing
        try:
            payload = generation_service.enrich_payload(
                client,
                payload,
                foreign_field_key,
                deck["target_language"],
                user.get("native_language") or "English",
                generation_prompts,
                deck.get("field_schema"),
            )
        except Exception as err:
            return render_form(error=f"Generation failed: {err}", status_code=500)
        if audio_allowed:
            try:
                audio_bytes = generation_service.generate_audio_for_phrase(
                    client,
                    payload.get(foreign_field_key, ""),
                    voice=audio_preferences["voice"],
                    instructions=audio_preferences["instructions"],
                )
                audio_preview_b64 = _encode_audio_preview(audio_bytes)
            except Exception as err:
                return render_form(error=f"Audio generation failed: {err}", status_code=500)
        return render_form(info="All fields populated. Review and save when ready.")

    if submit_action == "save" and not directions:
        return render_form(error="Select at least one direction.", status_code=400)

    if not payload.get(foreign_field_key):
        return render_form(error="Please provide a foreign phrase to generate from.", status_code=400)

    auto_generate = generation_allowed and client is not None

    if auto_generate:
        try:
            payload = generation_service.enrich_payload(
                client,
                payload,
                foreign_field_key,
                deck["target_language"],
                user.get("native_language") or "English",
                generation_prompts,
                deck.get("field_schema"),
            )
        except Exception as err:
            return render_form(error=f"Generation failed: {err}", status_code=500)

        if audio_allowed and audio_bytes is None:
            try:
                audio_bytes = generation_service.generate_audio_for_phrase(
                    client,
                    payload.get(foreign_field_key, ""),
                    voice=audio_preferences["voice"],
                    instructions=audio_preferences["instructions"],
                )
            except Exception as err:
                return render_form(error=f"Audio generation failed: {err}", status_code=500)

    try:
        card_service.create_cards(
            user["id"],
            deck,
            payload,
            directions,
            user.get("native_language"),
            audio_bytes=audio_bytes,
        )
    except ValueError as err:
        return render_form(error=str(err), status_code=400)

    return RedirectResponse(f"/decks/{deck_id}?saved=1", status_code=303)


@app.get("/cards/{group_id}/edit", response_class=HTMLResponse)
def edit_card(request: Request, group_id: str, user=Depends(get_current_user)):
    group_uuid = _parse_uuid(group_id, entity="Card")
    group = card_service.get_card_group(user["id"], group_uuid)
    if not group:
        raise HTTPException(status_code=404, detail="Card not found.")
    deck = group["deck"]
    payload = group["payload"]
    audio_preview_b64 = _encode_audio_preview(group["audio"])
    directions = [row["direction"] for row in group["rows"]]
    generation_allowed = api_key_service.user_can_generate(user["id"])
    return templates.TemplateResponse(
        "card_form.html",
        _card_form_context(
            request,
            user,
            deck,
            payload,
            directions,
            audio_preview_b64=audio_preview_b64,
            mode="edit",
            form_action=f"/cards/{group_id}",
            submit_label="Save changes",
            audio_preferences=_default_audio_preferences(deck),
            generation_enabled=generation_allowed,
        ),
    )


@app.post("/cards/{group_id}")
async def update_card(request: Request, group_id: str, user=Depends(get_current_user)):
    form = await request.form()
    group_uuid = _parse_uuid(group_id, entity="Card")
    group = card_service.get_card_group(user["id"], group_uuid)
    if not group:
        raise HTTPException(status_code=404, detail="Card not found.")
    deck = group["deck"]
    payload = _build_payload_from_form(deck, form)
    directions = [row["direction"] for row in group["rows"]]
    foreign_field_key = _get_foreign_field_key(deck)
    audio_preview_b64 = form.get("audio_preview_b64", "")
    audio_bytes = _decode_audio_preview(audio_preview_b64) or group["audio"]
    submit_action = form.get("submit_action", "save")
    generation_allowed = api_key_service.user_can_generate(user["id"])
    client = (
        api_key_service.get_openai_client_for_user(user["id"]) if generation_allowed else None
    )
    generation_prompts = deck_service.get_generation_prompts(deck)
    audio_preferences = _audio_preferences_from_form(form, deck)
    audio_allowed = deck_service.is_audio_enabled(deck)
    selected_directions = _get_directions_from_form(form, default_if_empty=None)
    if selected_directions:
        directions = selected_directions

    if not foreign_field_key:
        raise HTTPException(status_code=400, detail="Deck is missing a foreign phrase field.")

    def render_form(error: Optional[str] = None, info: Optional[str] = None, status_code: int = 200):
        return templates.TemplateResponse(
            "card_form.html",
            _card_form_context(
                request,
                user,
                deck,
                payload,
                directions,
                error=error,
                info=info,
                audio_preview_b64=audio_preview_b64,
                mode="edit",
                form_action=f"/cards/{group_id}",
                submit_label="Save changes",
                audio_preferences=audio_preferences,
                generation_enabled=generation_allowed,
            ),
            status_code=status_code,
        )

    if submit_action != "save" and submit_action != "regen_audio":
        if not payload.get(foreign_field_key):
            return render_form(error="Please enter a foreign phrase first.", status_code=400)

    def require_generation():
        if not generation_allowed or client is None:
            return render_form(
                error="Add an OpenAI API key on your profile before generating fields.",
                status_code=400,
            )
        return None

    if submit_action == "regen_native_phrase":
        missing = require_generation()
        if missing:
            return missing
        try:
            generation_service.regenerate_field(
                client,
                "native_phrase",
                payload,
                foreign_field_key,
                deck["target_language"],
                user.get("native_language") or "English",
                generation_prompts,
                deck.get("field_schema"),
            )
        except Exception as err:
            return render_form(error=str(err), status_code=400)
        return render_form(info="Translation updated.")
    elif submit_action == "regen_dictionary_entry":
        missing = require_generation()
        if missing:
            return missing
        try:
            generation_service.regenerate_field(
                client,
                "dictionary_entry",
                payload,
                foreign_field_key,
                deck["target_language"],
                user.get("native_language") or "English",
                generation_prompts,
                deck.get("field_schema"),
            )
        except Exception as err:
            return render_form(error=str(err), status_code=400)
        return render_form(info="Dictionary entry updated.")
    elif submit_action == "regen_example_sentence":
        missing = require_generation()
        if missing:
            return missing
        try:
            generation_service.regenerate_field(
                client,
                "example_sentence",
                payload,
                foreign_field_key,
                deck["target_language"],
                user.get("native_language") or "English",
                generation_prompts,
                deck.get("field_schema"),
            )
        except Exception as err:
            return render_form(error=str(err), status_code=400)
        return render_form(info="Example sentence updated.")
    elif submit_action == "regen_audio":
        if not audio_allowed:
            return render_form(
                error="Audio is disabled for this deck. Enable it from the deck settings.",
                status_code=400,
            )
        missing = require_generation()
        if missing:
            return missing
        if not payload.get(foreign_field_key):
            return render_form(error="Enter a foreign phrase before generating audio.", status_code=400)
        try:
            audio_bytes = generation_service.generate_audio_for_phrase(
                client,
                payload.get(foreign_field_key, ""),
                voice=audio_preferences["voice"],
                instructions=audio_preferences["instructions"],
            )
            audio_preview_b64 = _encode_audio_preview(audio_bytes)
        except Exception as err:
            return render_form(error=f"Audio generation failed: {err}", status_code=500)
        return render_form(info="Audio regenerated.")

    if not payload.get(foreign_field_key):
        return render_form(error="Please provide a foreign phrase to generate from.", status_code=400)

    auto_generate = generation_allowed and client is not None

    if auto_generate:
        try:
            payload = generation_service.enrich_payload(
                client,
                payload,
                foreign_field_key,
                deck["target_language"],
                user.get("native_language") or "English",
                generation_prompts,
                deck.get("field_schema"),
            )
        except Exception as err:
            return render_form(error=f"Generation failed: {err}", status_code=500)

        if audio_allowed and audio_bytes is None:
            try:
                audio_bytes = generation_service.generate_audio_for_phrase(
                    client,
                    payload.get(foreign_field_key, ""),
                    voice=audio_preferences["voice"],
                    instructions=audio_preferences["instructions"],
                )
                audio_preview_b64 = _encode_audio_preview(audio_bytes)
            except Exception as err:
                return render_form(error=f"Audio generation failed: {err}", status_code=500)

    try:
        success = card_service.update_card_group(
            user["id"],
            group_uuid,
            deck,
            payload,
            directions,
            audio_bytes,
        )
    except ValueError as err:
        return render_form(error=str(err), status_code=400)
    if not success:
        raise HTTPException(status_code=404, detail="Card not found.")
    return RedirectResponse(f"/decks/{deck['id']}?saved=1", status_code=303)


@app.post("/cards/{group_id}/delete")
def delete_card(group_id: str, user=Depends(get_current_user)):
    group_uuid = _parse_uuid(group_id, entity="Card")
    group = card_service.get_card_group(user["id"], group_uuid)
    if not group:
        raise HTTPException(status_code=404, detail="Card not found.")
    card_service.delete_card_group(user["id"], group_uuid)
    deck_id = group["deck"]["id"]
    return RedirectResponse(f"/decks/{deck_id}?deleted=1", status_code=303)


@app.get("/cards/{card_id}/audio")
def card_audio(card_id: str, side: str = "front", user=Depends(get_current_user)):
    card_uuid = _parse_uuid(card_id, entity="Card")
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
