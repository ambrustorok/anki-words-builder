# Anki Words Builder Requirements

## Core Platform
- FastAPI backend exposes a JSON API for deck, card, profile, and admin operations; data persists in Postgres.
- React (Vite) frontend consumes the API, provides SPA navigation, and offers a user-controlled light/dark theme toggle persisted in localStorage.
- Authentication relies on Cloudflare Access headers (`Cf-Access-Authenticated-User-Email`); development mode may fall back to `LOCAL_USER_EMAIL`.
- Users can manage personal data (native language onboarding, OpenAI API keys, linked emails, account deletion) and admins can manage all profiles.
- Adding a profile email is a two-step flow: add the address first, then mark it as primary from the email list if desired.
- When a user has an API key on file, the profile must show a masked/truncated version so they know a key exists without revealing the full secret.
- Automatic content generation (translations, dictionary notes, example sentences, TTS audio) leverages per-user or server OpenAI API keys and deck-specific prompt templates.
- Audio handling supports uploading/fetching MP3 previews and generation of audio assets stored per card group.

## Deck & Card Management
- Decks define target language, field schema (built-in + optional custom fields), generation prompts, and audio settings.
- Card creation workflow:
  - User chooses whether to supply a foreign or native phrase. Only that input field is shown initially.
  - “Process input” runs generation to translate/fill every configured field (and should work regardless of whether the initial text was native or foreign).
  - After processing, users can edit all generated text/audio, preview audio (auto-play when refreshed), and then click Save to persist the learning card.
  - Export directions (forward/backward) strictly control which cards will be included when exporting to Anki; they are separate from the chosen input language.
- Card editing keeps previously generated content editable, supports regeneration per field, audio fetch/generation, and previewing before saving.
- Cards export to `.apkg` with both directions rendered per deck prompt templates.
- Deck deletion is a deliberate action and must only be available on the deck edit screen.

## Dashboard & List Views
- Dashboard must highlight the 3 least recently updated decks in a table showing Name, Entries, Language, Cards, Created, Last Updated, and quick actions (“Add cards”, “View”, “Edit”). Deletion is intentionally omitted here.
- Dashboard must also display the 4 most recently modified card entries with their rendered faces.
- Deck list (“/decks”) must display the same columns/actions as the dashboard deck table (Name, Entries, Language, Cards, Created, Last Updated, “Add cards / View / Edit”) and must not surface delete actions.

## Development & Tooling
- Application runs in Docker (FastAPI API + React SPA + Postgres) with hot-reload volumes and a single named Postgres volume for development data.
- Frontend env var `VITE_API_URL` points to the API base (default `http://localhost:8000/api`); backend `FRONTEND_ORIGINS` controls CORS.
- Use Tailwind for styling, sticking to class-based theming (`dark:`) for both light and dark modes.
