# StreamingCatalog

A local, searchable catalog of the movies and TV you own on **Fandango at Home** (Vudu) and **Movies Anywhere**.

## Why this exists

Neither Fandango at Home nor Movies Anywhere gives you a real way to *search* what you own. You can scroll a virtualized grid and squint at posters, but if you want to ask "do I own *Blade Runner*?" or "show me everything I own from 1997," you're out of luck.

This tool builds a searchable inventory of your library — locally, in a SQLite database you control — by collecting the data the services already show you in the browser.

## How it works (and the trade-offs)

The services don't expose a clean public API for "list everything I own," so the tool has to drive a real Chrome window to scroll through your library pages and harvest item IDs. Once it has the IDs, metadata for each title is fetched from public endpoints (no authentication needed for that part).

A few things to know upfront:

- **You have to be logged in.** The collector uses a dedicated Chrome profile that you log into once via `streaming-catalog setup`. Your login lives in that local Chrome profile — nothing is sent anywhere or stored outside your machine.
- **The Chrome window needs to be visible during collection.** Both services use lazy-loading UIs that won't render items unless a real browser viewport is scrolling them. The Movies Anywhere page specifically requires synthetic PageDown keypresses to advance — that's the only way to reliably load all your titles. So during collection (a couple of minutes), Chrome is on screen doing its thing.
- **Cross-service titles try to merge but sometimes show as duplicates.** When you own the same movie on both services it gets merged into one row. The merger is tolerant of year mismatches (Google sometimes returns the wrong year by a year or two) and missing years, but a small number of titles may still appear twice — that's a limitation of matching on metadata alone.

## What you get

- A local SQLite database of everything you own across both services
- A web UI with full-text search, filters by service / quality / type, sortable columns, pagination, and posters that zoom on hover
- **"First seen" dates** — refresh later and you'll see when new purchases first showed up
- **Revoked view** — if a title disappears from your library (which has happened on streaming stores before), it's marked as revoked rather than silently deleted, so you have a record of what you lost and when
- Export to CSV or JSON if you want to do something else with the data

## Quick Start

```bash
# Clone the repo
git clone https://github.com/WowWashington/streaming-catalog.git
cd streaming-catalog

# Install dependencies (optionally inside a venv first)
pip install ".[all]"

# Run the three lifecycle commands — all from inside the streaming-catalog/ folder
./streaming-catalog setup     # one-time: creates DB + opens Chrome for login
./streaming-catalog update    # collects library + fetches metadata
./streaming-catalog search    # opens the web UI in your browser
```

On Windows use `streaming-catalog.bat` in place of `./streaming-catalog`.

The wrapper script in the repo root means you never need to fight with PATH or activate a venv to run commands — just `./streaming-catalog <command>` from inside the project directory.

### Where everything lives

Everything StreamingCatalog needs is bundled inside the project directory you cloned:

```
streaming-catalog/
├── chrome-profile/          # your dedicated Chrome session (gitignored)
├── data/                    # SQLite DB + collected ID files (gitignored)
├── .env                     # your port preference (gitignored)
└── ... (the code)
```

If you want a different layout (multiple catalogs, shared DB elsewhere, etc.) every path can be overridden via env vars — see [Configuration](#configuration) below.

To refresh later (e.g. weekly), just `cd` into the folder and run `./streaming-catalog update` again.

### Alternative installs

If you'd rather have `streaming-catalog` as a system-wide command instead of `./streaming-catalog`, you can install with **pipx**:

```bash
pipx install "streaming-catalog[all] @ git+https://github.com/WowWashington/streaming-catalog.git"
```

The catch: pipx installs the *command* globally, but the *data* still goes in whatever directory you're in when you run `streaming-catalog setup`. So pick a folder to hold your catalog and `cd` there before running setup. Treat that folder like a git working tree — everything for one library lives in it.

## Commands

| Command | What it does |
|---------|-------------|
| `setup` | One-time setup — creates DB and opens Chrome for login |
| `update` | Main command — collects library + fetches metadata |
| `search` | Opens the search UI in your browser |
| `status` | Database stats |
| `export` | Export to CSV or JSON |
| `login` | Re-log in if your session expires |
| `collect` | Just harvest library IDs (no metadata) |
| `sync` | Just fetch metadata for already-collected IDs |

## Configuration

All paths and the search port can be overridden via environment variables (or via the `.env` file that `setup` writes in your project directory).

| Variable | Default | Purpose |
|----------|---------|---------|
| `STREAMING_CATALOG_DB` | `./data/catalog.db` | SQLite database path |
| `STREAMING_CATALOG_CHROME_PROFILE` | `./chrome-profile` | Chrome user-data dir |
| `STREAMING_CATALOG_PORT` | `5858` | Search UI port (set interactively by `setup`) |

A typical project layout after `setup` + `update`:

```
streaming-catalog/
├── chrome-profile/          # Your dedicated Chrome session (gitignored)
├── data/
│   ├── catalog.db           # SQLite database with FTS search
│   ├── vudu_ids.txt         # Last-collected Vudu content IDs
│   ├── vudu_tv_ids.txt      # Last-collected Vudu TV section IDs
│   └── ma_slugs.txt         # Last-collected Movies Anywhere slugs
├── .env                     # Port preference saved by `setup`
└── ... (the code)
```

Want to back up your library? Just back up the whole folder.

## Privacy

- **All data is stored locally** inside your project folder
- **Your login lives in a Chrome profile** at `./chrome-profile/` next to the code — same encryption as your normal Chrome
- **No credentials are stored** anywhere by this tool itself
- **Nothing is uploaded** to any third party

## Remote access without exposing your machine

If you want to reach the search UI from your phone or another computer without opening any ports on your router, install [Tailscale](https://tailscale.com) on the host and on whatever device you want to use. Every device in your tailnet can reach the search UI as if it were on the LAN, while the host stays bound to localhost as far as the public internet is concerned.

## Scope and contributions

This is intentionally a small, focused tool. It's a framework that could be extended in lots of useful directions — other services (Apple, Amazon, Google Play), other content types (books, games), richer metadata, watched-status tracking, rental-availability cross-references, etc.

Pull requests, forks, and outright reuses are welcome. If you build something nice on top of this I'd love a credit, but you do you.

## Requirements

- Python 3.9+
- Google Chrome installed
- An account on Fandango at Home and/or Movies Anywhere (with stuff in it, presumably)

## License

MIT — see [LICENSE](LICENSE). Use it, fork it, sell it, build something better on top of it. Attribution to me is appreciated but not required.
