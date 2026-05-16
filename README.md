# StreamingCatalog

Catalog your **Fandango at Home** (Vudu) and **Movies Anywhere** libraries into a searchable SQLite database with full-text search.

## What it does

1. Opens your Chrome browser (where you're already logged in) and scrolls through your library pages to collect what you own
2. Fetches metadata for each title from public APIs (no credentials stored)
3. Stores everything in a local SQLite database with FTS5 full-text search
4. Provides a web UI to search, filter, and browse your collection
5. Detects revoked licenses (titles removed from your library between syncs)

## Requirements

- Python 3.9+
- Google Chrome (or Chromium) installed
- You must be logged in to [Fandango at Home](https://athome.fandango.com) and [Movies Anywhere](https://moviesanywhere.com) in Chrome
- Chrome must remain open and visible during collection (the scroll automation requires a real viewport)

## Quick Start

```bash
# Install
pip install .                    # core only
pip install ".[all]"             # includes search UI + browser collection

# Initialize database
streaming-catalog init

# Collect your library (opens Chrome — don't touch it during this step)
streaming-catalog collect

# Fetch metadata and build search index
streaming-catalog sync

# Browse your collection
streaming-catalog search
# Open http://127.0.0.1:18797
```

## CLI Reference

| Command | Description |
|---------|-------------|
| `streaming-catalog init` | Create database and data directory |
| `streaming-catalog collect` | Open Chrome and harvest library IDs |
| `streaming-catalog sync` | Fetch metadata, deduplicate, rebuild search index |
| `streaming-catalog search` | Start the search web UI |
| `streaming-catalog status` | Show database stats |
| `streaming-catalog export` | Export library to CSV or JSON |

### Global options

- `--db PATH` — Override database path
- `-v, --verbose` — Enable debug logging
- `--version` — Show version

## Configuration

Configuration is resolved in this order: CLI flags > environment variables > `.env` file > platform auto-detection.

Copy `.env.example` to `.env` and customize if needed:

```bash
cp .env.example .env
```

| Variable | Default | Description |
|----------|---------|-------------|
| `STREAMING_CATALOG_CHROME_PROFILE` | Auto-detected per OS | Path to Chrome user-data directory |
| `STREAMING_CATALOG_CHROME_PROFILE_NAME` | `Default` | Chrome profile name |
| `STREAMING_CATALOG_DB` | `./data/catalog.db` | Database file path |
| `STREAMING_CATALOG_PORT` | `18797` | Search UI port |

## Docker (optional)

The search UI can run in Docker for always-on access. The collection step always runs natively (needs your Chrome browser).

```bash
# After running collect + sync locally:
docker compose up -d
# Search UI at http://localhost:18797
```

## How it works

The collection step uses Selenium to drive your logged-in Chrome session:

- **Fandango at Home**: Scrolls a virtualized list container, harvesting content IDs from DOM links
- **Movies Anywhere**: Dispatches synthetic PageDown keyboard events (the only method that triggers MA's IntersectionObserver-based lazy loader) until all items are rendered, then harvests slugs from `<main>`

Metadata is then fetched from public endpoints (no auth required):
- Vudu's `apicache.vudu.com` API (JSON, stripped of a security wrapper)
- Movies Anywhere's per-movie pages (JSON-LD structured data)

Cross-service deduplication merges titles by normalized name + year.

## Scheduling

This tool doesn't include a built-in scheduler. See [docs/scheduling.md](docs/scheduling.md) for examples of running it on a cron/Task Scheduler/launchd schedule.

## Troubleshooting

See [docs/troubleshooting.md](docs/troubleshooting.md) for common issues.

## License

MIT
