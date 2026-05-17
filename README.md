# StreamingCatalog

Catalog your **Fandango at Home** (Vudu) and **Movies Anywhere** libraries into a searchable SQLite database with full-text search.

## What it does

1. Logs into your accounts in a managed Chrome session (one-time)
2. Scrolls your library pages to collect what you own
3. Fetches metadata for each title from public APIs
4. Stores everything in a local SQLite database with full-text search
5. Serves a web UI to search, filter, and browse your collection

No credentials are stored — the tool uses a dedicated Chrome profile that you log into once.

## Requirements

- Python 3.9+
- Google Chrome installed

## Quick Start

```bash
# Install
pip install ".[all]"

# First-time setup (creates database + opens Chrome for login)
streaming-catalog setup

# Collect your library and fetch metadata
streaming-catalog update

# Browse your library (auto-opens in your browser)
streaming-catalog search
```

That's it. Three commands.

## Commands

| Command | What it does |
|---------|-------------|
| `setup` | First-time setup — creates DB and opens Chrome for you to log in |
| `update` | Main command — collects library + fetches metadata (run weekly) |
| `search` | Opens the search UI in your browser |
| `status` | Database stats |
| `export` | Export library to CSV or JSON |

### Advanced commands

| Command | What it does |
|---------|-------------|
| `login` | Re-log in if your session expires |
| `collect` | Just harvest library IDs (without metadata) |
| `sync` | Just fetch metadata for already-collected IDs |

### Global options

- `--db PATH` — Override database path
- `-v, --verbose` — Show debug logging
- `--version` — Show version

## Configuration

Copy `.env.example` to `.env` to customize. All settings are optional.

| Variable | Default | Description |
|----------|---------|-------------|
| `STREAMING_CATALOG_CHROME_PROFILE` | `~/.streaming-catalog/chrome-profile` | Where to store the dedicated Chrome profile |
| `STREAMING_CATALOG_DB` | `./data/catalog.db` | Database file path |
| `STREAMING_CATALOG_PORT` | `18797` | Search UI port |

## Docker (optional, search UI only)

The search UI can run in Docker for always-on access. The collection step always runs natively (needs Chrome).

```bash
# After running setup + update locally:
docker compose up -d
# Search UI at http://localhost:18797
```

## How it works

**Login session**: The tool uses a dedicated Chrome profile at `~/.streaming-catalog/chrome-profile`. You log in once via `streaming-catalog setup`, and the session persists across runs. This avoids Chrome's security restrictions on automating your main browser profile.

**Library collection**: Selenium drives Chrome through your library pages:
- **Fandango at Home**: Scrolls a virtualized list, harvesting content IDs from links
- **Movies Anywhere**: Dispatches PageDown keys to trigger MA's lazy loader (the only method that works), then harvests slugs

**Metadata**: Fetched from public endpoints, no auth needed:
- Vudu's `apicache.vudu.com` API
- Movies Anywhere's per-movie JSON-LD pages

**Cross-service dedup**: Titles you own on both services are merged into a single video record with both source links.

## Scheduling

This tool doesn't include a built-in scheduler. See [docs/scheduling.md](docs/scheduling.md) for cron/Task Scheduler/launchd examples.

## Troubleshooting

See [docs/troubleshooting.md](docs/troubleshooting.md).

## License

MIT
