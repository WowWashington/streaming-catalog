# Backlog

In progress / future work.

> Component detail. Start at `STATE.md` in the project root.

## What's In Progress

Nothing actively in progress.

---

## What's NOT Implemented (Future Work)

- **Additional services**: Apple TV, Amazon Video, Plex
- **Tests**: `tests/` directory exists in pyproject.toml but is empty. Unit tests for `_build_fts_query`, `dedupe_videos`, `_parse_response`, and the MA JSON-LD parser would be high-value
- **Watched-status tracking**: services don't expose this, but the user could mark it manually in the UI
- **Rental availability cross-reference**: "what can I rent that I don't own" via JustWatch or similar
- **GitHub Actions CI**: lint + smoke tests on push
- **Headless login fallback**: deferred (Chrome profile is always the auth path now)

---
