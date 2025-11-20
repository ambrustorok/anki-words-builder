# Migration Status Tracker

_Last updated: 2025-11-20 (UTC)_

## Phase Overview
| Phase | Description | Status | Link |
| --- | --- | --- | --- |
| A | FastAPI stack transition + onboarding | [ ] | `docs/migration-plan-frontend.md#delivery-phases` |
| B | Auth & schema hardening (Cloudflare header, users, decks, structured payloads) | [ ] | `docs/migration-plan-backend.md` |
| C | Deck schema + prompts + dual-direction cards | [ ] | `docs/migration-plan-frontend.md#deck-management` |
| D | Search, pagination, and discovery groundwork | [ ] | `docs/migration-plan-frontend.md#card-browser--search` |
| E | Profile, emails, BYO API keys, sharing prep | [ ] | `docs/migration-plan-frontend.md#onboarding--profile` |

## Detailed Checklist

### Multi-User & Auth
- [ ] Capture Cloudflare `Cf-Access-Authenticated-User-Email` via FastAPI dependency; gate all routes.
- [ ] Provide explicit local fallback toggle for offline development.
- [ ] Create `users` + `user_emails` tables (UUID PK, unique emails) and seed `local_user`.
- [ ] Collect native language on first login before showing decks.
- [ ] Enforce per-user scoping for decks/cards plus future sharing ACLs.
- [ ] Add delete-profile flow that cascades user data removal.

### Decks & Prompts
- [ ] Introduce `decks` table with single target language + field schema JSON.
- [ ] Require deck selection for every card creation; default prompts per deck.
- [ ] Allow dynamic field definitions + prompt templates via UI.
- [ ] Persist option to generate two cards (forward/backward) per payload.
- [ ] Prepare for deck sharing (future) with `deck_access` scaffolding.

### BYO API Keys
- [ ] Create encrypted storage for user-supplied API keys.
- [ ] Frontend form for adding/removing keys with provider selection.
- [ ] Runtime selection logic (prefer user key, fallback to system).
- [ ] Error surfacing if BYO key invalid or missing.

### Search, Pagination, Card Browser
- [ ] Add trigram/cursor indexes for `payload` fields.
- [ ] Implement paginated, filtered card APIs scoped to user/deck.
- [ ] Build server-rendered tables with HTMX pagination + search toggles.
- [ ] Surface trending/favorite scaffolding for future recommendations.

### Profile & Email Management
- [ ] Profile page showing UUID + email list.
- [ ] Ability to add/remove secondary emails (with uniqueness enforcement).
- [ ] Confirmation UX for destructive actions (remove email, delete profile).
- [ ] Settings page for BYO API keys and prompt defaults.

## Notes & Next Actions
- FastAPI rewrite + onboarding flow underway; update checklist as code lands.
- Align upcoming sprints with the phase table before implementing schema migrations beyond Phase A.
- ✅ Single-input card creation form now live: foreign phrase is the only required field, “Generate all fields” fills translation/dictionary/example/audio, and prompt overrides are editable inline per submission.
- ✅ Default export templates now match the requested English-front/Foreign-front layouts, with audio rendered on the correct side and new UI copy documenting the OpenAI TTS flow.
- ✅ UI now uses Tailwind CSS across every page (dashboard, deck CRUD, onboarding, profile, card form) so the experience looks polished without hand-written CSS.
- ✅ Audio generation honors per-request voice selection (alloy/ash/ballad/coral/echo/fable/nova/onyx/sage/shimmer/random) plus freeform instructions, streaming through `whisper-1` as required.
- ✅ Tailwind UI now follows the user’s system light/dark preference automatically (no extra toggle required).
- ✅ Audio pipeline now calls the supported `gpt-4o-mini-tts` endpoint, so random voice selection works without 404 errors.
- ✅ Profile page now manages multiple Cloudflare emails, offers a delete-data button that cascades decks/cards/api keys, and exposes a Cloudflare Zero Trust sign-out link.
- Next: wire the new UI into HTMX-powered partial refreshes and land pagination/search (Phase D) once the card flow stabilizes.
