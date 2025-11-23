# Anki Words Builder
Anki Words Builder is a FastAPI + React language learning companion that helps you create structured, multi-language decks for [Anki](https://apps.ankiweb.net/). The backend now exposes a JSON API and the new React frontend consumes it for a responsive SPA experience while keeping the original feature set (deck/card CRUD, Cloudflare-authenticated profiles, per-field generation, exports, and admin tooling).

## Features

- **Multi-user, Cloudflare-authenticated access** (via `Cf-Access-Authenticated-User-Email`).
- **Deck-per-language structure** so prompts stay consistent for each learning language.
- **Dynamic fields & prompts** stored as JSON so cards can be rendered forward/backward on demand.
- **Auto-generation** of translations, dictionary entries, example sentences, and TTS audio using OpenAI (per-user API keys supported).
- **Custom TTS controls** so you can pick one of the OpenAI voices (alloy/ash/ballad/coral/echo/fable/nova/onyx/sage/shimmer or random) and set streaming instructions per card.
- **Opinionated exports** that output English-front and Foreign-front directions exactly as described (including example sentences, dictionary notes, and audio on the requested side).
- **Full deck/card CRUD** with inline regeneration of every field, audio previews, and editable per-deck prompt templates.
- **FastAPI JSON API + React SPA** so the UI can evolve independently and stay responsive during heavy generation tasks.
- **Tailwind-powered components** for the dashboard, deck editor, card workflow, and admin console with automatic light/dark theming.
- **Built-in theme toggle** so you can switch between light and dark styles without reloading.
- **Multi-email + data control** so you can link multiple Cloudflare-approved addresses to one account and wipe everything (decks, cards, keys) in a single click when needed.
- **Admin console + CLI tooling** so protected emails (like `local@example.com`) can audit, edit, or delete any profile and grant admin access from the command line.

## Development setup

The project now runs as two services (FastAPI API + React SPA) coordinated through Docker with hot-reload volumes, so you rarely rebuild the containers while iterating.

### 1. Environment

Create a `.env` file with the Postgres credentials (and optional overrides already supported by the legacy stack):

```dotenv
POSTGRES_USER=anki
POSTGRES_PASSWORD=anki
POSTGRES_DB=anki_words
OPENAI_API_KEY=your_server_default_key
```

The backend still supports `LOCAL_USER_EMAIL`, `ALLOW_LOCAL_USER`, `LOCAL_ALWAYS_ADMIN_EMAIL`, and `ADDITIONAL_ADMIN_EMAILS`. You can also override `FRONTEND_ORIGINS` (comma-separated list) if you run the SPA from a different host than `http://localhost:5173`.

### 2. Docker (recommended)

```bash
docker compose up --build
```

- API: http://localhost:8100 (JSON endpoints live under `/api`).
- SPA: http://localhost:5173 (Vite dev server with HMR).
- Database: Postgres 16 with a named volume (`postgres_data`) so you can destroy/recreate containers without losing data.

Because the compose file mounts the repo into the containers and uses `uvicorn --reload` / `vite --host`, code edits are picked up instantly without rebuilding.

### 3. Local development without Docker

Backend (requires [uv](https://docs.astral.sh/uv/#getting-started)):

```bash
uv venv
source .venv/bin/activate
uv pip install -e .
uv run uvicorn src.app:app --reload --port 8100
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Set `VITE_API_URL` if you need a custom base URL; by default the frontend targets `http(s)://<current-host>:8100/api`, which works for both `localhost` and remote IP access.

## Legacy (CLI-only) installation

To install Anki Words Builder, follow these steps:

1. **Clone the Repository**:
    ```bash
    git clone https://github.com/ambrustorok/anki-words-builder.git
    cd anki-words-builder
    ```

2. **Set Up the Environment File**:
    Create a `.env` file in the root directory and add the necessary environment variables:
    ```plaintext
    OPENAI_API_KEY=your_openai_api_key
    ```
    Optional overrides:
    - `LOCAL_USER_EMAIL` (defaults to `local@example.com` for development)
    - `LOCAL_ALWAYS_ADMIN_EMAIL` (email that must always stay an admin)
    - `ADDITIONAL_ADMIN_EMAILS` (comma-separated list of extra protected admin emails)

3. Install [uv](https://docs.astral.sh/uv/#getting-started) if you haven't already:
    ```bash
    curl -LsSf https://astral.sh/uv/install.sh | sh
    ```

   You'll also need system packages for `psycopg2` and audio encoding:
   ```bash
   sudo apt install libpq-dev build-essential ffmpeg
   ```

4. **Create the uv Virtual Environment**:
    ```bash
    uv venv
    source .venv/bin/activate
    ```

5. **Install Python Dependencies** (same command Docker uses):
    ```bash
    uv pip install -e .
    ```

6. **Run the Application**:
    ```bash
uv run uvicorn src.app:app --reload --port 8100
    ```

## Usage

1. **Sign in via Cloudflare** (or use `LOCAL_USER_EMAIL` for offline development).
2. **Pick your native language** the first time you log in.
3. **Optionally add your own OpenAI API key** on the Profile page (fallbacks to the server key if configured).
4. **Create decks** for each target language and configure the fields/prompts you want (including custom generation prompts per deck).
5. **Add or edit cards** with the new single-input workflow: type only the foreign phrase, click “Generate all fields” to populate translation, dictionary notes, example sentence, and TTS audio, then pick the desired TTS voice/instructions before saving (prompt tweaks live on the deck settings page).
6. **Browse, edit, and delete cards** inline, then export a deck to `.apkg` whenever you’re ready.
7. **Browse & export** only the decks you own (sharing + recommendations will arrive in future releases).
8. **Manage linked emails or delete data** from the Profile page—aliases let multiple Cloudflare identities reuse the same decks, and the danger-zone button wipes everything then signs you out.
9. **Admin users** (e.g., `local@example.com`) can open `/admin/users` for a full profile overview, edit any user’s email addresses, delete accounts, or promote more admins directly from the UI or CLI.

## Command-line profile management

The Typer-powered CLI mirrors the admin UI so you can script profile changes without opening the browser:

```bash
# List every profile (add --admins-only for just admins)
uv run python -m src.cli users list

# Delete a profile by any linked email (with confirmation)
uv run python -m src.cli users delete someone@example.com

# Rename an email (and optionally make it primary)
uv run python -m src.cli users update-email old@example.com new@example.com --set-primary

# Add or promote admins
uv run python -m src.cli users grant-admin teammate@example.com
uv run python -m src.cli users revoke-admin teammate@example.com
```

Additional helpers (`users add-email`, etc.) are available via `uv run python -m src.cli --help`.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Background

This project started as a side project for learning Danish and is gradually evolving into a multi-user deck builder that can grow with new language pairs and collaboration features.
