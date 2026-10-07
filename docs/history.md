# StreamingCatalog — History

Original overview, completed list, git log, status, moved verbatim from STATE.md.

> Component detail. Start at `STATE.md` in the project root.

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
