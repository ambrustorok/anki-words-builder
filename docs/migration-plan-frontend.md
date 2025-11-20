# Frontend & UX Migration Plan

## Objectives
- Deliver a FastAPI + Jinja + HTMX (minimal JS) experience that runs comfortably on Raspberry Pi.
- Provide authenticated multi-user flows tied to Cloudflare headers.
- Let users manage decks (single target language each), define dynamic fields + prompts, create cards in both directions, and browse/search paginated results.
- Capture onboarding requirements (native language selection) and prep for future features (deck sharing, trending/favorites, recommendations).

## Current Baseline
- FastAPI skeleton with templates replacing the former Gradio UI.
- Decks, prompts, and card flows still basic; dynamic fields/prompt editors, BYO keys, and advanced search yet to be implemented.

## UX Architecture
1. **Server-rendered layout**
   - Base template with Tailwind CSS (CDN) to keep markup lean yet attractive on every page (dashboard, decks, onboarding, profile) and automatically honor the browser’s light/dark preference.
   - HTMX snippets for partial updates (e.g., card tables, prompt previews) to avoid custom JS.
2. **Session banner**
   - Display signed-in email + native language status.
   - Highlight if onboarding required.
3. **Scoped dashboards**
   - Dashboard shows deck summaries, recent cards, and quick actions.
   - Deck detail pages surface field schema, prompts, and per-deck card lists.

## Feature Areas & Implementation Steps

### Onboarding & Profile
- **Native language selection**: redirect new users to onboarding form before they can access decks.
- **Profile view**: list primary + secondary emails, native language, UUID, delete-account control.
- **Email management**: forms to add/remove aliases; enforce uniqueness within the UI using HTMX validation pings, plus the ability to promote any alias to primary so Cloudflare sign-ins stay consistent.
- **User data deletion**: button to purge decks/cards/api keys/emails, then log the user out via Cloudflare sign-out URL.

### Deck Management (single-language)
- **Deck list**: table with name, target language, card count, favorite/share indicators (future-ready).
- **Create deck**: wizard capturing name, target language, field schema template, prompt presets.
- **Field schema editor**: allow adding/removing field rows (label, key, type, placement) without JS bundlers; HTMX can clone partial forms.
- **Prompt builder**: textareas with syntax hints (`{{field_key}}`, `{{target_language}}`, `{{native_language}}`) plus preview via HTMX call; defaults stored per deck but always editable inline as plain text.
- **OpenAI TTS guidance**: surface per-deck instructions (model, voice, endpoint) next to audio-related prompts so users know how audio files are produced.
- **Sharing prep**: surfaces read-only badges for "Shared with me" (future `deck_access` data).

- **Deck selector required**; UX shows deck’s target language + field schema context.
- **Single user input**: only the foreign phrase is mandatory; native translation, dictionary notes, example sentence, and audio auto-fill after generation but remain editable.
- **Generate details button**: visible only during new-card creation; triggers LLM + TTS calls to populate all other fields, never shown in edit mode.
- **Dynamic field inputs**: render form fields based on schema; allow optional custom field values and manual overrides after generation.
- **Dual-direction toggle**: checkboxes defaulting to both forward/backward generation, plus per-entry direction controls on the edit page so users can disable/switch directions after cards exist.
- **Structured payload**: display serialized view before submission so users know what will be stored.
- **Prompt usage**: show which prompt template will run (pulled from the deck settings) but keep editing centralized on the deck edit page to avoid noisy card forms.
- **Audio controls**: inputs for voice selection (alloy/ash/ballad/coral/echo/fable/nova/onyx/sage/shimmer/random) and instruction text so users can match tone, with defaults saved per request; doc the OpenAI streaming snippet referencing `whisper-1`.

### Card Browser & Search
- **Filters**: deck dropdown, language pair badges, date range.
- **Search modes**: exact vs fuzzy toggle (HTMX updates table via API).
- **Pagination**: cursor buttons + keyboard shortcuts; fallback to classic pagination on browsers without JS.
- **Card detail drawer**: server-rendered partial showing structured data and rendered front/back; edit/delete/actions available.

### BYO API Keys & Settings
- **Settings page**: provider dropdown, masked inputs, last-used metadata.
- **Validation**: HTMX call to test key before saving.
- **Fallback messaging**: highlight when system key is being used vs personal key.

### Future Enhancements
- **Deck sharing UI**: invitation modals, access roles, accept/decline flows.
- **Trending/favorites**: badges + sections on dashboard; ability to star decks/cards.
- **Recommendations**: panels showing suggested decks based on usage telemetry.

## Delivery Phases
1. **Phase A – FastAPI layout & onboarding**
   - Base templates, navigation, native-language flow, simple deck listing.
2. **Phase B – Deck schema & prompts**
   - Field editor, prompt builder, enforcement of single target language per deck.
3. **Phase C – Card creation + dual direction**
   - Dynamic form rendering, prompt-driven generation, structured storage preview, single-input UX, auto-populate button, audio voice/instruction controls, Tailwind grid layouts, and deck-level prompt editing.
4. **Phase D – Card browser upgrades**
   - Search, filters, pagination, HTMX partials, card drawer.
5. **Phase E – Profile, emails, BYO API keys**
   - Email alias management, API key forms, delete account.
6. **Phase F – Sharing & discovery groundwork**
   - Deck sharing UI, favorites/trending scaffolding, recommendation hooks.

## Dependencies & Integrations
- FastAPI routes returning HTML + JSON partials.
- HTMX for progressive enhancement without custom JS code.
- Tailwind/PicoCSS (CDN) for consistent styling.
- Cloudflare header already available to backend; frontend only displays context (no client auth logic).

## Testing Strategy
- Unit tests for field schema rendering + prompt substitution.
- Integration tests (pytest + httpx) covering onboarding, deck creation, card CRUD with auth headers.
- Playwright smoke tests for navigation + deck/card flows (minimal JS; HTMX-friendly).

## Risks
- Dynamic forms without heavy JS may become cumbersome – mitigate via HTMX components + partial templates.
- Raspberry Pi constraints require minimal asset sizes – rely on CDN CSS + avoid bundlers.
- User-defined prompts/fields must be validated to prevent template injection – enforce whitelist and preview.
- Auto-generated field values must clearly indicate when they were last refreshed; warn before rerunning population to avoid data loss.

## Export Templates
- **Direction one (native front)**:
  - `FRONT`: English phrase.
  - `BACK`: Foreign phrase followed by example sentence, dictionary notes, and audio link.
- **Other direction (foreign front)**:
  - `FRONT`: Foreign phrase with the English translation inline.
  - `BACK`: Example sentence, dictionary notes, and audio link.
- Keep this structure consistent between UI previews and actual Anki exports.
