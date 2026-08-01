# Agent Instructions (Anki Words Builder)

## First steps (run + entrypoints)
- Start dev in Docker: `docker compose up --build` (API on `:8100`, UI on `:5173`, hot-reload via mounted repo).
- Backend without Docker: `uv venv && source .venv/bin/activate && uv pip install -e . && uv run uvicorn src.app:app --reload --port 8100`.
- Frontend without Docker: `cd frontend && npm install && npm run dev`.

## Authoritative commands
- Admin CLI (inside backend container):
  - List users: `docker compose exec backend uv run python -m src.cli users list`.
  - Grant admin: `docker compose exec backend uv run python -m src.cli users grant-admin user@example.com`.
  - Revoke admin: `docker compose exec backend uv run python -m src.cli users revoke-admin user@example.com`.
  - Delete user: `docker compose exec backend uv run python -m src.cli users delete user@example.com`.

## Auth + API shape (avoid guessing)
- Auth identity comes from header `Cf-Access-Authenticated-User-Email`; if it’s missing, backend falls back only when `ALLOW_LOCAL_USER=true`.
- Frontend calls backend under `/api`; Vite proxies `/api` to `VITE_API_PROXY_TARGET` (docker default: `http://backend:8100`).

## Deck export (Anki scheduling gotchas)
- Export endpoint: `GET /decks/{deck_id}/export?mode=incremental|full`.
- Re-import endpoint: `POST /decks/{deck_id}/import-anki` with the `.apkg` as multipart field `file`.
- Use `mode=incremental` to avoid overwriting Anki learning progress.
- `due` scheduling is persisted in the DB (`cards.anki_due`) and is bucketed by card difficulty: `A1=0..9999`, `A2=10000..19999`, `B1=20000..`, etc.
- New cards get stable randomized placement within their CEFR bucket; re-exports reuse persisted `anki_due` for already assigned cards.
- `mode=incremental` exports only cards created/modified since the deck’s last export (`decks.last_exported_at`).
- Difficulty bucketing uses `cards.difficulty` only; tags like `politics` affect Anki tags but not `due` bucketing.
- Anki re-import matches stable note GUIDs, retains changed Anki faces as overrides, and persists Anki scheduling in `cards.anki_scheduling` for future in-app learning.

## Card difficulty (CEFR only)
- Card difficulty is a dedicated `cards.difficulty` field (`A1..C2`), shared by both directions of an entry.
- AI assigns difficulty during generation; users can correct it in card review/editing.
- Tags are for topics/custom labels only; category `CEFR` is rejected.
