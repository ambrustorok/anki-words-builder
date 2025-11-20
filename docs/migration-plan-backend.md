# Backend Migration Plan

## Context
- App is being rewritten from a single-user Gradio tool into a FastAPI + Jinja/HTMX web app that runs well on Raspberry Pi and scales to more users.
- We must lean on Cloudflare Zero Trust for authentication (via `Cf-Access-Authenticated-User-Email`) and fall back to a deterministic `local_user` only for offline development.
- Each deck belongs to exactly one target language; users select decks when creating cards so we can choose the correct prompts and field schema.
- Data must stay structured (fields such as `foreign_phrase`, `native_phrase`, `dictionary`, plus user-defined fields) and only rendered into front/back faces when serving clients or exporting.
- Users should be able to dynamically define both the fields and prompt templates per deck, support dual-direction card generation (forward/backward), handle any language pair, and capture the user’s native language on first login.
- Longer-term roadmap adds deck sharing, trending/favorites/recommendations, so the model must anticipate ACLs and activity metrics even if not implemented immediately.

## Guiding Principles
1. **FastAPI-first** – HTTP pipeline, middleware, dependency injection, and templating all go through FastAPI. No leftover Gradio artifacts.
2. **Header-based auth** – Trust Cloudflare for identity; never prompt for passwords. Missing header results in local dev fallback only when explicitly enabled.
3. **Data isolation + shareability** – Scope cards to their owners by default, but design tables so decks can later be shared with ACL rows without rewriting everything.
4. **Structured storage** – Persist normalized field payloads (JSONB) plus metadata; formatting into Anki-style front/back happens at read time.
5. **Language clarity** – Decks store target language, users store native language, prompts reference both to support any language pair.

## Target Data Model

| Table | Purpose | Key Columns / Constraints |
| --- | --- | --- |
| `users` | Primary identity keyed by UUID | `id UUID PK`, `native_language TEXT`, `created_at`, `deleted_at` |
| `user_emails` | Multiple emails per user | `id UUID PK`, `user_id FK -> users`, `email UNIQUE`, `is_primary BOOL` |
| `user_api_keys` | BYO model providers | `id UUID PK`, `user_id FK`, `provider TEXT`, `key_ciphertext`, `last_used_at` |
| `decks` | Deck metadata (language, sharing) | `id UUID PK`, `owner_id FK -> users`, `name`, `target_language`, `field_schema JSONB`, `prompt_templates JSONB`, `is_shared BOOL`, timestamps |
| `deck_access` (future) | Sharing + permissions | `id UUID PK`, `deck_id FK`, `user_id FK`, `role ENUM('owner','editor','viewer')` |
| `cards` | Structured entries per direction | `id UUID PK`, `deck_id FK`, `owner_id FK`, `direction ENUM('forward','backward')`, `payload JSONB`, `render_cache JSONB`, `created_at` |
| `search_index` (optional) | Denormalized terms | `card_id FK`, `term_vector tsvector`, `trgm_term TEXT` |

Additional tables (`deck_prompts`, `deck_field_templates`) can be kept separate if we outgrow JSONB storage, but JSONB lets us iterate quickly while requirements are still evolving.

### Migration Steps
1. **Baseline audit**
   - Snapshot existing `cards` table; plan data transform to structured JSON.
2. **Bootstrap FastAPI schema**
   - Create new tables listed above via Alembic or SQL scripts.
   - Seed a `local_user` + default deck for existing rows.
3. **Data migration**
   - Convert legacy cards into `payload` format (`foreign_phrase`, `native_phrase`, etc.).
   - Generate both directions where missing.
4. **Field & prompt configurability**
   - Add APIs for managing `field_schema` and `prompt_templates`.
5. **Search + pagination**
   - Enable `pg_trgm` + indexes on `(owner_id, created_at)` and `(deck_id, created_at)`.
   - Add JSON path indexes for frequently queried fields (e.g., `payload->>'foreign_phrase'`).
6. **Future deck sharing groundwork**
   - Introduce `deck_access` + event tables even if UI not ready, so trending/favorites can aggregate later.

## Authentication & User Lifecycle
- FastAPI dependency reads `Cf-Access-Authenticated-User-Email`. If absent and `ALLOW_LOCAL_USER` flag set, use deterministic local email; otherwise reject.
- `ensure_user(email)`:
  1. Look up `user_emails.email`.
  2. If missing, create `users` row (UUIDv4), set `native_language=NULL`, and insert primary email.
  3. After login, redirect to onboarding if `native_language` missing; store choice.
- Multiple emails:
  - Provide endpoints to add/remove emails with uniqueness enforcement.
  - Cloudflare handles verification; backend ensures no cross-user reuse.
- Delete profile:
  - Delete `users` row → cascades remove emails, decks, cards, API keys.

## Business Logic Changes

### Decks & Languages
- Deck creation requires `target_language` and default field schema.
- Ensure prompts know both `target_language` (deck) and `native_language` (user).
- Enforce single language per deck and require deck selection before card creation.

### Structured Fields & Prompts
- `field_schema` describes allowed dynamic fields (key, label, type, placement).
- `prompt_templates` define how to call LLMs and how to render front/back.
- Users can append new field definitions without schema migrations.
- Rendering pipeline composes fields into HTML only when returning to frontend/export.
- Provide defaults that require only `foreign_phrase`, while other fields remain optional + auto-fillable; expose these templates so the frontend can render editable textareas fed directly from deck config.

### Card Generation
- Card creation workflow:
  1. Collect structured payload for chosen deck.
  2. Optionally call model using deck prompt templates (per field).
  3. Persist payload once; generate two `cards` rows (`forward`, `backward`) referencing same payload.
- Allow manual editing of either direction later.
- Support toggling directions during editing (add the missing direction row or delete the extra one when users uncheck it).
- Support a “generate details” operation that uses only the foreign phrase as input, then calls translation/dictionary/example prompts plus OpenAI TTS to fill the remaining fields; suppress this helper when editing existing cards.
- Persist audio generation metadata (model, voice, timestamp) so users know how audio was produced and we can present TTS instructions alongside prompts.
- Audio generation must respect per-request voice selection (alloy, ash, ballad, coral, echo, fable, nova, onyx, sage, shimmer, or “random”) and a freeform instructions string (e.g., “Speak in a cheerful tone”). Call the OpenAI streaming helper:
  ```python
  response = client.audio.speech.create(
      model="gpt-4o-mini-tts",
      voice=user_voice_selection,
      input=text,
      response_format="mp3",
      instructions=user_instructions,
  )
  audio_bytes = response.content
  ```
  Store the chosen voice/instructions with the payload metadata for auditability.

### BYO API Keys
- Store encrypted provider keys linked to user.
- Execution pipeline prefers user key, falls back to system key (configurable).
- Log per-call metadata for rate-limiting/future recommendations.

### Search, Pagination, Analytics
- Provide paginated endpoints (cursor-based) for cards and decks filtered by owner or share ACL.
- Implement fuzzy search using trigram index on `payload->>'foreign_phrase'` and `payload->>'native_phrase'`.
- Capture per-card engagement metrics for future trending/favorites features.

### Export Formatting
- Codify two renderers:
  - **Forward** (`front=foreign`): front shows only the foreign phrase; back includes translation, example sentence, dictionary note, and audio reference.
  - **Backward** (`front=native`): front surfaces the English/native phrase; back shows the foreign phrase along with example/dictionary/audio data.
- Keep exporters + render caches aligned with this schema so Anki decks remain predictable.

### User Management
- Support multiple user emails (aliases) so Cloudflare Zero Trust can map any approved address to the same account.
- Provide delete-user API that cascades decks/cards/audio/API keys/emails, then signs the user out (redirect to Cloudflare logout endpoint).
- Expose email CRUD + delete-account actions on the profile page, with backend validation for uniqueness and ownership.

## Rollout Plan
1. **Phase 0 – Stack transition**
   - Replace Gradio runtime with FastAPI templates; deploy minimal deck/card flow.
2. **Phase 1 – Auth + schema**
   - Stand up new tables, Cloudflare middleware, onboarding (native language).
3. **Phase 2 – Deck & field management**
   - APIs + UI for field schema and prompts per deck; enforce single language per deck.
4. **Phase 3 – Card lifecycle**
   - Structured storage, dual-direction generation, pagination, search.
5. **Phase 4 – Enhancements**
   - BYO API keys, prompt customization, deck sharing scaffolding, favorites/trending instrumentation.
6. **Phase 5 – Cleanup & migrations**
   - Deprecate legacy tables, finalize Alembic history, document backups.

## Risks & Mitigations
- **Header omissions** – guard endpoints and log when Cloudflare header missing; require explicit config to allow fallback.
- **Data model drift** – keep JSON schema version in each deck’s field definitions for future migrations.
- **Raspberry Pi constraints** – keep DB queries simple, use connection pooling, avoid unnecessary background threads.
- **Unbounded dynamic fields** – enforce reasonable limits (field count, size) and validate template placeholders.
- **Auto-fill overwrite** – API must warn before regenerating fields that the user already edited and let clients choose per-field overrides.

## Open Questions
- Exact format for future sharing ACLs (public vs invite-only vs org-based).
- How to rank “trending” decks (usage, favorites, completion rates?).
- Need for multilingual prompts beyond OpenAI (local models, offline TTS) on Raspberry Pi deployments?
