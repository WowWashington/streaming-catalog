# StreamingCatalog — Cross-Platform Streaming Library Cataloger

> Owner: Peter Sheppard
> Started: 2026-05-16
> Status: Active — v0.1.0 scaffold complete, CLI functional, ready for first real sync test.

## Purpose

Distributable version of the HomeProjects video library tool. Lets any user on
Windows, macOS, or Linux catalog their **Fandango at Home** (Vudu) and **Movies
Anywhere** libraries into a searchable SQLite database. Designed for GitHub
distribution — no macOS-specific dependencies.

Derived from `~/Projects/HomeProjects` with all platform-specific coupling removed
(launchd, Keychain, hardcoded paths).

---

## Architecture

```
streaming-catalog/
├── pyproject.toml              # PEP 621 packaging, click entry point
├── schema.sql                  # SQLite schema (videos + video_sources + FTS5)
├── Dockerfile / docker-compose.yml  # Optional: containerized search UI
├── src/streaming_catalog/
│   ├── cli.py                  # Click CLI: init, collect, sync, search, status, export
│   ├── config.py               # Platform detection, .env loading, Chrome path resolution
│   ├── db.py                   # Connection helper, schema bootstrap
│   ├── collector.py            # Selenium + Chrome profile → harvest IDs/slugs
│   ├── scrapers/
│   │   ├── vudu.py             # Public apicache API scraper
│   │   ├── movies_anywhere.py  # Public JSON-LD page scraper
│   │   └── sync.py             # Orchestrator + dedup + revocation
│   └── search/
│       ├── app.py              # Flask app factory
│       └── templates/index.html
├── docs/                       # Setup guides, scheduling, troubleshooting
└── examples/                   # cron, launchd, Task Scheduler configs
```

---

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Database | Plain SQLite | Zero-dependency, cross-platform, built into Python |
| Docker | Optional (search UI only) | Collector needs host Chrome; Docker adds friction |
| Auth | Chrome profile (logged-in) | No credentials stored. User logs in via browser. |
| PageDown trick | Shipped | Only working method for MA's IntersectionObserver loader |
| Headless mode | Not supported | Both Vudu virtual scroll and MA lazy load need visible viewport |
| Scheduling | Not bundled | Users bring their own cron/Task Scheduler/launchd |
| CLI framework | Click | Mature, auto-generates help, composable |

---

## How to run

```bash
pip install ".[all]"              # Full install
streaming-catalog init            # Create data/ + catalog.db
streaming-catalog collect         # Harvest IDs from logged-in Chrome
streaming-catalog sync            # Fetch metadata, dedup, build FTS
streaming-catalog search          # Web UI on :18797
streaming-catalog status          # DB stats
streaming-catalog export --format json -o library.json
```

---

## Relationship to HomeProjects

This project is a **fork for distribution**. HomeProjects remains the personal
instance with its own cron, Keychain wiring, and portal integration.

| Aspect | HomeProjects | StreamingCatalog |
|--------|-------------|-----------------|
| Secrets | macOS Keychain | None (Chrome profile) |
| Scheduling | launchd plists | User's choice (docs/examples) |
| DB name | household.db | catalog.db |
| Chrome path | Hardcoded macOS | Auto-detect per OS |
| Target user | Peter only | Any GitHub user |

---

## Open work

1. **Tests** — unit tests for parsers (vudu, MA), config platform detection, dedup logic
2. **GitHub Actions** — lint + test CI workflow
3. **First real sync test** — run collect + sync with live Chrome session to validate end-to-end
4. **GitHub repo** — push to GitHub, add badges to README
