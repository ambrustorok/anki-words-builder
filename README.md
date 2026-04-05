# Anki Words Builder

A self-hosted, AI-powered flashcard builder for language learners. Type a word or phrase, let GPT fill in the translation, dictionary entry, example sentence, and pronunciation audio — then export a ready-to-import `.apkg` deck straight into Anki. Designed for daily use from a phone, deployed behind Cloudflare Zero Trust.

## What it does

- **AI card generation** — translate, generate a dictionary entry, write an example sentence, and record TTS audio for every card in one tap
- **Per-user model selection** — each user picks their own OpenAI text model (`gpt-4o`, `gpt-4o-mini`, `o4-mini`, …) and audio model (`gpt-4o-mini-tts`, `tts-1`, `tts-1-hd`, …) from the live OpenAI models list
- **Tags** — define CEFR levels (A1–C2), topic categories, or any custom tags per deck; AI can infer and assign them automatically; tags are exported natively into Anki
- **Custom card templates** — full control over what appears on the front and back of each Anki card using `{{variable}}` placeholders
- **Custom generation prompts** — override the system and user prompts for every AI step per deck (or globally as admin)
- **Backup & restore** — export a `.awdeck` ZIP archive and re-import it with merge/override conflict resolution; tags included
- **Anki export** — deterministic `.apkg` files; re-exporting updates existing notes in Anki instead of duplicating them
- **Multi-user** — each user has isolated decks, their own OpenAI key (encrypted at rest with Fernet), and their own model preferences
- **Cloudflare Zero Trust auth** — no login form; Cloudflare Access injects the verified user email

## Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI, Python 3.12, uv |
| Database | PostgreSQL (psycopg2) |
| AI | OpenAI Chat Completions + TTS |
| Anki export | genanki |
| Frontend | React 18, Vite, TailwindCSS, TanStack Query |
| Auth | Cloudflare Zero Trust (Access) |
| Runtime | Docker Compose |

## Quickstart

### 1. Create `.env` in the repo root

```dotenv
# Postgres
POSTGRES_USER=anki
POSTGRES_PASSWORD=changeme
POSTGRES_DB=anki_words
POSTGRES_HOST=postgres
POSTGRES_PORT=5432

# OpenAI system-wide fallback key (users can override with their own on the Profile page)
OPENAI_API_KEY=sk-...

# Fernet key for encrypting stored user API keys — generate with:
# python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
API_KEY_ENCRYPTION_KEY=...

# Default text model for new users (optional, default: gpt-4o-mini)
OPENAI_MODEL=gpt-4o-mini

# Cloudflare / local dev auth
ALLOW_LOCAL_USER=true
LOCAL_USER_EMAIL=local@example.com

# Comma-separated emails auto-promoted to admin on first login
LOCAL_ALWAYS_ADMIN_EMAIL=local@example.com
ADDITIONAL_ADMIN_EMAILS=

# Comma-separated CORS origins for the frontend
FRONTEND_ORIGINS=http://localhost:5173
```

> In production, set `ALLOW_LOCAL_USER=false` and remove the `LOCAL_*` overrides.

### 2. Start

```bash
docker compose up --build
```

- Frontend: http://localhost:5173
- API: http://localhost:8100/api
- The working tree is mounted into both containers — Python and TypeScript changes hot-reload automatically.

### 3. First admin

Add your email to `LOCAL_ALWAYS_ADMIN_EMAIL` (or `ADDITIONAL_ADMIN_EMAILS`) before starting. That email is auto-promoted to admin on first login. Alternatively use the CLI after the user has logged in once:

```bash
docker compose exec backend uv run python -m src.cli users grant-admin you@example.com
docker compose exec backend uv run python -m src.cli users list
```

## Cloudflare Zero Trust (production)

1. Create a Cloudflare Access application protecting your domain/subdomain.
2. Set `ALLOW_LOCAL_USER=false`.
3. Cloudflare injects `Cf-Access-Authenticated-User-Email` on every authenticated request — the app reads that header to identify users.
4. Expose only the frontend port through the Cloudflare Tunnel; add the tunnel hostname to `FRONTEND_ORIGINS`.

## Per-user model preferences

Each user can select on their Profile page:

- **Text model** — used for translation, dictionary, example sentence, tag inference (fetched live from OpenAI)
- **Audio model** — used for TTS pronunciation (fetched live from OpenAI)

If no preference is set the server default (`OPENAI_MODEL`) is used. Models are fetched using the user's own API key, or the system key if none is set.

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `POSTGRES_HOST/PORT/DB/USER/PASSWORD` | — | Database connection |
| `OPENAI_API_KEY` | — | System-wide fallback OpenAI key |
| `API_KEY_ENCRYPTION_KEY` | (dev key — insecure) | Fernet key for encrypting stored user keys |
| `OPENAI_MODEL` | `gpt-4o-mini` | Default text model for new users |
| `ALLOW_LOCAL_USER` | `true` | Bypass Cloudflare auth (dev only) |
| `LOCAL_USER_EMAIL` | `local@example.com` | Email used when `ALLOW_LOCAL_USER=true` |
| `LOCAL_ALWAYS_ADMIN_EMAIL` | — | Auto-admin email in local mode |
| `ADDITIONAL_ADMIN_EMAILS` | — | Comma-separated always-admin emails |
| `FRONTEND_ORIGINS` | `http://localhost:5173` | CORS-allowed origins |
| `VITE_API_URL` | current origin + `/api` | Override API URL baked into the frontend bundle |

## Backup format

`.awdeck` is a ZIP archive containing:
- `deck.json` — deck metadata, field schema, prompt templates, tag definitions, tag mode
- `cards.json` — all card payloads, directions, timestamps, tag assignments
- Audio files — one `.mp3` per card that has audio

Import policies: `override` (replace), `prefer_newest` (keep whichever side has the later `updated_at`), `only_new` (skip existing entries). A `409` is returned when a policy is not specified and the deck already exists.

## CLI reference

```bash
# List all users
docker compose exec backend uv run python -m src.cli users list

# Grant / revoke admin
docker compose exec backend uv run python -m src.cli users grant-admin user@example.com
docker compose exec backend uv run python -m src.cli users revoke-admin user@example.com

# Delete a user (cascades all decks and cards)
docker compose exec backend uv run python -m src.cli users delete user@example.com
```

## Development without Docker

```bash
# Backend
uv venv && source .venv/bin/activate
uv pip install -e .
uv run uvicorn src.app:app --reload --port 8100

# Frontend
cd frontend && npm install && npm run dev
```
