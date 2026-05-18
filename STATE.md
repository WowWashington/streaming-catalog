# StreamingCatalog — Project State

> Resume instruction: "Read STATE.md to understand where we are in the project and what needs to happen next. Do not review the previous chat history."

## Project Overview

**StreamingCatalog** — a distributable, cross-platform tool that catalogs a user's owned movies and TV from **Fandango at Home** (Vudu) and **Movies Anywhere** into a local SQLite database with full-text search and a Flask web UI.

This is the **public, GitHub-distributable** strip-down of the user's personal **HomeProjects** project. HomeProjects remains the canonical personal instance (with Google Play scraping, launchd cron, Portal integration). StreamingCatalog is what other people use.

- **Language/Stack**: Python 3.9+ (Click CLI, Flask, Selenium, BeautifulSoup, SQLite FTS5)
- **Repo**: https://github.com/WowWashington/streaming-catalog (public)
- **Local path**: `/Users/automator/Projects/StreamingCatalog`
- **License**: MIT

---

## Intent & Use

Neither Fandango at Home nor Movies Anywhere offers a real way to *search* your owned library — just an infinite-scroll grid of posters. StreamingCatalog solves this by driving a logged-in Chrome session, scrolling the library pages to harvest item IDs, then fetching public metadata for each title. Everything ends up in a local SQLite database with a Flask search UI.

The user interacts via a Click-based CLI: `setup` once, `update` periodically, `search` to browse. Three commands cover the whole lifecycle.

Privacy is core: no credentials are stored by the tool itself. The login lives in a dedicated Chrome profile at `~/.streaming-catalog/chrome-profile/` (mode 0700 on POSIX). Nothing is uploaded anywhere.

---

## File Structure

```
StreamingCatalog/
├── pyproject.toml                  # Packaging, declares schema.sql + templates as package-data
├── README.md                       # 3 install paths (pipx / wrapper / venv) + privacy + Tailscale tip
├── LICENSE                         # MIT
├── STATE.md                        # this file
├── .gitignore                      # excludes data/, *.db, .env, etc.
├── .env.example                    # documents the override env vars
├── Dockerfile                      # optional containerized search UI
├── docker-compose.yml
├── streaming-catalog               # POSIX wrapper script (no PATH setup needed)
├── streaming-catalog.bat           # Windows wrapper script
│
├── src/streaming_catalog/
│   ├── __init__.py                 # __version__ = "0.1.0"
│   ├── __main__.py                 # python -m streaming_catalog entry
│   ├── cli.py                      # Click CLI: setup, update, search, status, export, login, collect, sync
│   ├── config.py                   # env var + .env resolution; ~/.streaming-catalog/ defaults
│   ├── db.py                       # connection helper + schema bootstrap
│   ├── collector.py                # Selenium harvester with VUDU_SCROLL_JS + MA_SCROLL_JS
│   ├── schema.sql                  # videos + video_sources + FTS5 (lives in package so wheels ship it)
│   ├── scrapers/
│   │   ├── __init__.py
│   │   ├── vudu.py                 # apicache.vudu.com metadata scraper
│   │   ├── movies_anywhere.py      # MA JSON-LD per-movie page scraper
│   │   └── sync.py                 # orchestrator + dedup (year-tolerant) + revocation
│   └── search/
│       ├── app.py                  # Flask app factory + FTS query sanitizer + pagination
│       └── templates/index.html    # search UI with poster hover zoom
│
├── docs/
│   ├── setup-chrome.md             # dedicated-profile setup explanation
│   ├── scheduling.md               # cron/launchd/Task Scheduler examples
│   ├── troubleshooting.md
│   └── linkedin-post.md            # marketing draft
│
└── examples/
    ├── crontab.example
    ├── launchd.plist
    └── task-scheduler.xml
```

---

## Architecture & Key Decisions

1. **Dedicated Chrome profile, not the user's main one.** Chrome 148+ blocks Selenium from attaching to a profile that's also being used as the user's everyday browser. We sidestep this by using a fresh profile at `~/.streaming-catalog/chrome-profile/`. User logs in once via `setup`; sessions persist across runs.

2. **Local-only data, project-local defaults.** All state lives inside the project directory: `./chrome-profile/`, `./data/`, `./.env`. DB path resolution is just two cases: `STREAMING_CATALOG_DB` env var or the cwd-relative default. The "treat the folder like a git working tree" mental model — back up the folder, get everything.

3. **Three install paths in the README, ordered by friction**: `pipx install` (recommended global), `git clone + ./streaming-catalog` (zero install via wrapper script), venv (developers). The wrappers auto-detect a local `.venv/` if present, fall back to system `python3 -m streaming_catalog`.

4. **Public APIs for metadata, browser for ownership lists.** The Vudu apicache and MA per-movie pages return rich metadata without authentication. Only the "what do I own" list requires the logged-in browser session, because that's the only way to access the user-specific library pages. This keeps the auth surface minimal.

5. **MA PageDown trick is required for MA collection.** Movies Anywhere uses an IntersectionObserver-based lazy loader that ignores programmatic `scrollTo()`. The only reliable way to load all items is to dispatch synthetic `KeyboardEvent('keydown', {keyCode: 34})` repeatedly. See `MA_SCROLL_JS` in collector.py. Chrome window must be visible.

6. **Year-tolerant dedup.** Metadata sources sometimes disagree on release years (Google's data on Clockwork Orange differs by 1 year between Vudu and MA). The dedup buckets by normalized title, then clusters within each bucket allowing year mismatches of ≤2 years OR a missing year on either side. Films with clearly different years (>2 apart, like "Awakening" 1990 vs 2011) stay separate.

7. **Revocation via Python-side diff, not SQL date filter.** `mark_missing_as_removed` compares the live `seen_ids` set against the DB rows in Python, so a same-day re-run still catches newly-revoked items (a SQL `last_seen_date != today` filter would have excluded items the first run had touched).

8. **Per-item exception handling in scrape loops.** A single malformed JSON-LD or unexpected actor shape no longer kills the whole sync — the item is logged as failed and the loop continues.

9. **FTS query sanitization.** User input is tokenized via `re.findall(r"\w+", q)` then per-token prefix-quoted. Punctuation-only or quote-containing queries (`.`, `"`, `foo"bar`) now sanitize cleanly instead of raising sqlite3 OperationalError.

10. **Connection lifecycle.** Search handler wraps the request in try/finally so the SQLite connection always closes, even if rendering raises mid-request. Chrome driver is wrapped in try/finally in `setup`/`login`/`collect`.

---

## Configuration & Secrets

All optional. Resolution order: CLI flags > env vars > `~/.streaming-catalog/config.env` > defaults.

| Var | Default | Purpose |
|-----|---------|---------|
| `STREAMING_CATALOG_DB` | `./data/catalog.db` | DB path override |
| `STREAMING_CATALOG_CHROME_PROFILE` | `./chrome-profile` | Profile dir override |
| `STREAMING_CATALOG_PORT` | `5858` | Search UI port (set interactively by `setup`) |

**Never committed**: `.gitignore` excludes `data/`, `chrome-profile/`, `*.db`, `.env`, build artifacts. The whole "user state" footprint lives in `data/`, `chrome-profile/`, and `.env`, all gitignored — so a `git status` after a full setup+update is clean.

---

## Running / Deployment

Install (pipx, recommended):
```bash
pipx install "streaming-catalog[all] @ git+https://github.com/WowWashington/streaming-catalog.git"
```

Or zero-install via wrapper script:
```bash
git clone https://github.com/WowWashington/streaming-catalog.git
cd streaming-catalog
pip install ".[all]"
./streaming-catalog setup           # macOS/Linux
# streaming-catalog.bat setup       # Windows
```

Lifecycle commands:
```bash
streaming-catalog setup       # one-time: creates DB at ~/.streaming-catalog/data/, opens Chrome with both login tabs, prompts for port
streaming-catalog update      # collect library + sync metadata (~5-10 min for a typical library)
streaming-catalog search      # opens http://127.0.0.1:5858 in browser
streaming-catalog status      # DB stats
streaming-catalog export      # CSV or JSON dump
```

---

## What's Complete

- Cross-platform CLI (macOS / Linux / Windows) with 8 commands
- Selenium-driven collector for Vudu + MA with proven PageDown technique for MA
- Public-API metadata scrapers (apicache.vudu.com + MA JSON-LD per-movie pages)
- SQLite + FTS5 schema with revocation tracking and `first_seen_date`
- Year-tolerant cross-service deduplication
- Flask search UI with pagination, source filters, type/quality filters, sortable columns, poster hover zoom (5× scale-up)
- Cross-service stats breakdown (unique titles · on both · vudu-only · ma-only)
- Per-user config persisted to `~/.streaming-catalog/config.env` (atomic write, 0600)
- Wrapper scripts (`./streaming-catalog`, `streaming-catalog.bat`) for zero-PATH-setup invocation
- Optional Docker setup (search UI only — collector needs host Chrome)
- README with three install paths, troubleshooting, scheduling examples
- Code review pass with critical, important, and nice-to-have tiers all addressed
- Released MIT-licensed at https://github.com/WowWashington/streaming-catalog

---

## What's In Progress

Nothing actively in progress. Project considered v0.1.0 release-ready.

---

## What's NOT Implemented (Future Work)

- **Additional services**: Apple TV, Amazon Video, Plex, Google Play. HomeProjects has a working Google Play scraper that could be ported.
- **Tests**: `tests/` directory exists in pyproject.toml but is empty. Unit tests for `_build_fts_query`, `dedupe_videos`, `_parse_response`, and the MA JSON-LD parser would be high-value.
- **Watched-status tracking**: services don't expose this, but the user could mark it manually in the UI.
- **Rental availability cross-reference**: "what can I rent that I don't own" via JustWatch or similar.
- **GitHub Actions CI**: lint + smoke tests on push.
- **Headless login fallback**: deferred from v0.1 (Chrome profile is always the auth path now).

---

## Git History (recent)

```
9d535ad simplify DB resolution to env var + home default
01e5e5d make 'just clone and run' actually work
9c9e3e4 cleanup: dead code, connection leaks, cross-platform fixes
6ea3085 harden scrapers, browser lifecycle, and search input
e822a78 dedup: tolerate year mismatches and missing years
c6c4cc4 fix critical correctness issues from code review
568241b rewrite README to explain the problem, trade-offs, and intent
5e0c53c interactive setup, port change, poster hover zoom
331633b search UI: pagination, clearer stats, robust login
40b8c66 streamline UX for first-time users
fd9426b initial scaffold
```

---

## Current Status

**Last updated**: 2026-05-18
**State**: Stable — v0.1.0 release-ready, repo is public on GitHub
**Recent changes**: Iteratively addressed all three tiers of code review findings (critical / important / nice-to-have). Final layout is project-local: data, Chrome profile, and `.env` all live inside the project directory you cloned (or wherever you cd before running `setup`), gitignored, so the whole library lives in one folder you can back up as a unit. Added wrapper scripts (`./streaming-catalog`, `streaming-catalog.bat`) to eliminate PATH friction.
**Next steps**:
- Optional: port select improvements back to HomeProjects (year-tolerant dedup, FTS sanitization, pagination, mark_missing_as_removed Python-diff fix, hover-zoom posters, stats breakdown)
- Optional: write unit tests for the parsers and dedup logic
- Optional: announce via the drafted LinkedIn post at `docs/linkedin-post.md`
