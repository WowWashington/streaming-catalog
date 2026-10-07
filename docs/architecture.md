# Architecture

Intent, file structure, architecture and key decisions, configuration and secrets.

> Component detail. Start at `STATE.md` in the project root.

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
