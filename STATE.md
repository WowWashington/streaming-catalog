# StreamingCatalog — Project State

> Resume instruction: "Read STATE.md to understand where we are in the project and what needs to happen next. Do not review the previous chat history."

## Project Overview

**StreamingCatalog** — a distributable, cross-platform tool that catalogs a user's owned movies and TV from **Fandango at Home** (Vudu), **Movies Anywhere**, and **Google Play Movies** into a local SQLite database with full-text search and a Flask web UI.

As of 2026-05-18 this is also the user's **personal** instance — the previous separate HomeProjects project was merged in (Google Play scraper ported, household.db migrated to ./data/catalog.db) and retired to `~/Projects/HomeProjects-archived/`. There is no longer a "private fork" — public improvements and personal usage share the same codebase. Personal customizations stay in gitignored files (`.env`, `data/`, `chrome-profile/`, the launchd plists which live in `~/Library/LaunchAgents/` rather than the repo).

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
│   │   ├── google_play.py          # GP detail-page (itemprop) metadata scraper
│   │   └── sync.py                 # orchestrator + dedup (year-tolerant) + revocation + purge
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

2. **Local-only data, project-local defaults.** All state lives inside the project directory: `./chrome-profile/`, `./data/`, `./.env`. DB path resolution is just two cases: `STREAMING_CATALOG_DB` env var or the cwd-relative default.

3. **Three install paths in the README, ordered by friction**: `pipx install` (recommended global), `git clone + ./streaming-catalog` (zero install via wrapper script), venv (developers).

4. **Public APIs for metadata, browser for ownership lists.** The Vudu apicache and MA per-movie pages return rich metadata without authentication. Only the "what do I own" list requires the logged-in browser session.

5. **MA PageDown trick is required for MA collection.** Movies Anywhere uses an IntersectionObserver-based lazy loader that ignores programmatic `scrollTo()`. Synthetic `KeyboardEvent('keydown', {keyCode: 34})` dispatched repeatedly via `MA_SCROLL_JS`. Chrome window must be visible.

6. **Year-tolerant dedup.** Metadata sources sometimes disagree on release years. The dedup buckets by normalized title (with trailing `(YYYY)` year suffixes stripped), then clusters within each bucket allowing year mismatches of ≤2 years OR a missing year on either side.

7. **Revocation via Python-side diff, not SQL date filter.** `mark_missing_as_removed` compares the live `seen_ids` set against the DB rows in Python, so a same-day re-run still catches newly-revoked items.

8. **`purge_superseded_sources()` prevents ID-change false positives.** After every sync, any `is_active=0` source entry is deleted if the same `(video_id, source)` already has an `is_active=1` entry. This handles the case where a service changes a movie's source_id without removing it from your library — the old ID gets marked inactive by `mark_missing_as_removed`, but the new active entry confirms you still own it. Without this step, ID changes show up as spurious revocations.

9. **"Show revoked" is a filter, not a toggle.** When checked, it filters TO videos that have any `is_active=0` source entry (not just videos with no active sources). Makes it a useful "what was removed" view.

10. **Per-item exception handling in scrape loops.** A single malformed JSON-LD or unexpected actor shape no longer kills the whole sync.

11. **FTS query sanitization.** User input tokenized via `re.findall(r"\w+", q)` then per-token prefix-quoted. Punctuation-only queries sanitize cleanly.

12. **Connection lifecycle.** Search handler wraps the request in try/finally. Chrome driver is wrapped in try/finally in `setup`/`login`/`collect`.

---

## Configuration & Secrets

All optional. Resolution order: CLI flags > env vars > `~/.streaming-catalog/config.env` > defaults.

| Var | Default | Purpose |
|-----|---------|---------|
| `STREAMING_CATALOG_DB` | `./data/catalog.db` | DB path override |
| `STREAMING_CATALOG_CHROME_PROFILE` | `./chrome-profile` | Profile dir override |
| `STREAMING_CATALOG_PORT` | `5858` | Search UI port (set interactively by `setup`) |

**Never committed**: `.gitignore` excludes `data/`, `chrome-profile/`, `*.db`, `.env`, build artifacts.

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
streaming-catalog setup       # one-time: creates DB, opens Chrome with login tabs, prompts for port
streaming-catalog update      # collect library + sync metadata (~5-10 min for a typical library)
streaming-catalog search      # opens http://127.0.0.1:5858 in browser
streaming-catalog status      # DB stats
streaming-catalog export      # CSV or JSON dump
```

---

## What's Complete

- Cross-platform CLI (macOS / Linux / Windows) with 8 commands
- Selenium-driven collector for Vudu + MA + Google Play
- Public-API metadata scrapers (apicache.vudu.com, MA JSON-LD, GP itemprop pages)
- SQLite + FTS5 schema with revocation tracking and `first_seen_date`
- Year-tolerant cross-service deduplication with trailing-year title normalization
- `purge_superseded_sources()` — prevents ID-change events from appearing as revocations
- Flask search UI with pagination, source filters, type/quality filters, sortable columns, poster hover zoom
- "Show revoked" filters TO movies with any revoked source entry (was broken before — showed nothing useful)
- Revoked sources render as faded badges with removal date tooltip; partial-revoke rows get a red left border
- Cross-service stats breakdown (unique titles · on multiple · vudu-only · ma-only · gp-only)
- Per-user config persisted to `~/.streaming-catalog/config.env` (atomic write, 0600)
- Wrapper scripts for zero-PATH-setup invocation
- Optional Docker setup (search UI only)
- README with three install paths, troubleshooting, scheduling examples
- Released MIT-licensed at https://github.com/WowWashington/streaming-catalog
- launchd services: `com.streaming-catalog.{sync,search}` at `~/Library/LaunchAgents/`; weekly sync Sunday 3 AM, search on port 5858

---

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

## Git History (recent)

```
26970ff update STATE.md for HomeProjects merge
ea409cc add Google Play Movies as a third source
41254f2 move data layout back to project-local
8a0b299 update STATE.md with v0.1.0 release-ready snapshot
9d535ad simplify DB resolution to env var + home default
01e5e5d make 'just clone and run' actually work
9c9e3e4 cleanup: dead code, connection leaks, cross-platform fixes
6ea3085 harden scrapers, browser lifecycle, and search input
e822a78 dedup: tolerate year mismatches and missing years
c6c4cc4 fix critical correctness issues from code review
```

---

## Current Status

**Last updated**: 2026-07-22
**State**: Stable — 882 unique videos in local catalog across 3 services
**Recent changes**:
- Fixed "show revoked" UI: now filters TO movies with any revoked source entry, and shows a red left-border on partially-revoked rows with faded source badges
- Fixed false revocation tracking: `purge_superseded_sources()` added to sync pipeline — removes `is_active=0` entries where the same `(video_id, source)` has an active replacement, so ID changes (Google Play changing source IDs) no longer count as revocations
- Fixed dedup: `normalize_title()` now strips trailing `(YYYY)` year suffixes, enabling "Spider-Man (2002)" and "Spider-Man" to merge correctly
- Catalog refreshed: 882 unique titles, 0 genuine revocations
**Next steps**:
- Commit and push the three changed source files
- Optional: write unit tests for parsers and dedup logic
- Optional: announce via `docs/linkedin-post.md`
- Safe to delete `~/Projects/HomeProjects-archived/` when ready
