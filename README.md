# Anki Words Builder

FastAPI + React stack for creating bilingual study decks, powered by OpenAI generation and Cloudflare Zero Trust authentication. Every request is gated by Cloudflare Access (`Cf-Access-Authenticated-User-Email`), so users never see a login form—Cloudflare injects the verified email, and the app provisions the profile automatically.

## Cloudflare Zero Trust Integration

- **Authentication**: All API calls must include the `Cf-Access-Authenticated-User-Email` header. Cloudflare Access apps add it automatically once you protect the domain/subdomain that serves this repository.
- **Local development**: Set `ALLOW_LOCAL_USER=true` and `LOCAL_USER_EMAIL=local@example.com` (or similar) if you want to bypass Cloudflare while running `docker compose` locally.
- **Always-on admins**: Populate `LOCAL_ALWAYS_ADMIN_EMAIL` and `ADDITIONAL_ADMIN_EMAILS` (comma-separated) so those identities are promoted to admin as soon as they log in. This is the easiest way to seed your first super-admin.

## Quickstart (Docker Compose)

1. **Create `.env` in the repo root**

   ```dotenv
   POSTGRES_USER=anki
   POSTGRES_PASSWORD=anki
   POSTGRES_DB=anki_words
   POSTGRES_HOST=postgres
   POSTGRES_PORT=5432

   OPENAI_API_KEY=sk-...

   # Cloudflare / onboarding helpers
   LOCAL_USER_EMAIL=local@example.com
   ALLOW_LOCAL_USER=true
   LOCAL_ALWAYS_ADMIN_EMAIL=local@example.com
   ADDITIONAL_ADMIN_EMAILS=you@example.com
   ```

   > When running behind Cloudflare, set `ALLOW_LOCAL_USER=false` and omit the `LOCAL_*` overrides.

2. **Start the stack**

   ```bash
   docker compose up --build --force-recreate --detach
   ```

   - Backend API: http://localhost:8100/api
   - Frontend SPA: http://localhost:5173
   - PostgreSQL: local container volume (`postgres_data`)

3. **Tail logs when needed**

   ```bash
   docker compose logs --follow backend
   docker compose logs --follow frontend
   ```

4. **Stop everything**

   ```bash
   docker compose down
   ```

Because the compose file mounts your working tree, edits to Python/TypeScript files hot-reload automatically (Uvicorn + Vite).

## Provisioning the First Admin

1. Ensure the person who should be the initial admin can authenticate through Cloudflare and hit the SPA once (this creates their profile).
2. Promote them via the CLI:

   ```bash
   docker compose exec backend uv run python -m src.cli users grant-admin you@example.com
   ```

   - List profiles: `docker compose exec backend uv run python -m src.cli users list`
   - Revoke admin later: `... users revoke-admin you@example.com`

   Alternatively, add the email to `ADDITIONAL_ADMIN_EMAILS` before booting; those addresses auto-promote on login.

## Configuration Reference

| Variable | Description |
| --- | --- |
| `POSTGRES_HOST/PORT/DB/USER/PASSWORD` | Database location + credentials (defaults align with `docker-compose.yaml`). |
| `OPENAI_API_KEY` | Server-side key used when a profile hasn’t provided their own. |
| `LOCAL_USER_EMAIL` | Email injected when `ALLOW_LOCAL_USER=true` (development only). |
| `LOCAL_ALWAYS_ADMIN_EMAIL` | Protected account that can’t lose admin status. |
| `ADDITIONAL_ADMIN_EMAILS` | Comma-separated list of extra always-admin accounts. |
| `FRONTEND_ORIGINS` | Comma-separated list of allowed SPA origins (defaults to `http://localhost:5173`). |
| `VITE_API_URL` (frontend) | Override API origin baked into the bundle (otherwise current origin + `/api`). |

## Development Without Docker

```bash
# Backend
uv venv && source .venv/bin/activate
uv pip install -e .
uv run uvicorn src.app:app --reload --port 8100

# Frontend
cd frontend
npm install
npm run dev
```

Use `VITE_API_URL` if the SPA is served from a different host/port than the API.

## Feature Highlights

- Deck-per-language structure with customizable schemas and prompt templates for forward/backward directions.
- Inline generation of translations, dictionary notes, example sentences, and TTS audio using user-supplied OpenAI keys (or the server default).
- Card template editor (front/back) plus global default controls for admins.
- Audio orchestration with per-deck instructions, voice selection, and optional generation.
- Cloudflare-integrated multi-email accounts, profile management UI, and admin console.
- Typer CLI for batch operations: list users, add/remove emails, grant/revoke admin access, or delete profiles.
- Export-ready data for Anki with predictable HTML structure and audio attachments.

## Cloudflare Tunnel Tips

If you front the SPA via Cloudflare Tunnel:

1. Expose only the frontend port (5173) through the tunnel.
2. Add your tunnel hostname to `FRONTEND_ORIGINS`.
3. Cloudflare Access enforces identity, injects `Cf-Access-Authenticated-User-Email`, and the SPA proxies `/api` calls back to the backend container.

## Need to Rotate Admins Later?

```bash
docker compose exec backend uv run python -m src.cli users list --admins-only
docker compose exec backend uv run python -m src.cli users revoke-admin someone@example.com
docker compose exec backend uv run python -m src.cli users delete user@example.com
```

Protected accounts (from `LOCAL_ALWAYS_ADMIN_EMAIL` or `ADDITIONAL_ADMIN_EMAILS`) cannot be revoked or deleted until you remove them from the env file and restart the stack.
