# StreamingCatalog

A local, searchable catalog of the movies and TV you own on **Fandango at Home** (Vudu) and **Movies Anywhere**.

## Why this exists

Neither Fandango at Home nor Movies Anywhere gives you a real way to *search* what you own. You can scroll a virtualized grid and squint at posters, but if you want to ask "do I own *Blade Runner*?" or "show me everything I own from 1997," you're out of luck.

This tool builds a searchable inventory of your library — locally, in a SQLite database you control — by collecting the data the services already show you in the browser.

## How it works (and the trade-offs)

The services don't expose a clean public API for "list everything I own," so the tool has to drive a real Chrome window to scroll through your library pages and harvest item IDs. Once it has the IDs, metadata for each title is fetched from public endpoints (no authentication needed for that part).

A few things to know upfront:

- **You have to be logged in.** The collector reuses a dedicated Chrome profile that you log into once via `streaming-catalog setup`. Your login lives in that local Chrome profile — nothing is sent anywhere or stored outside your machine.
- **The Chrome window needs to be visible during collection.** Both services use lazy-loading UIs that won't render items unless a real browser viewport is scrolling them. The Movies Anywhere page specifically requires synthetic PageDown keypresses to advance — that's the only way to reliably load all your titles. So during collection (a couple of minutes), Chrome is on screen doing its thing.
- **Cross-service titles try to merge but sometimes show as duplicates.** When you own the same movie on both services it gets merged into one row. But the services sometimes name things differently (re-releases, bundles, alternate cuts, a stray colon, the year being off), so a small number of titles may still appear twice. That's a limitation of matching by name + year — fixable by hand if it bothers you.

## What you get

- A local SQLite database of everything you own across both services
- A web UI with full-text search, filters by service / quality / type, sortable columns, and posters that zoom on hover
- **"First seen" dates** — refresh later and you'll see when new purchases first showed up
- **Revoked view** — if a title disappears from your library (which has happened on streaming stores before), it's marked as revoked rather than silently deleted, so you have a record of what you lost and when
- Export to CSV or JSON if you want to do something else with the data

## Quick Start

```bash
git clone https://github.com/WowWashington/streaming-catalog.git
cd streaming-catalog

# Recommended: use a virtual environment
python3 -m venv .venv
source .venv/bin/activate            # macOS/Linux
# .venv\Scripts\activate              # Windows PowerShell

pip install ".[all]"

streaming-catalog setup     # creates DB + opens Chrome for one-time login
streaming-catalog update    # collects library + fetches metadata
streaming-catalog search    # opens the web UI in your browser
```

To refresh later (e.g. weekly), just run `streaming-catalog update` again. New purchases get new "first seen" dates; anything that disappears moves to the revoked view.

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

## Privacy

- **All data is stored locally**, in a SQLite file in `./data/catalog.db`
- **Your login lives in a Chrome profile** at `~/.streaming-catalog/chrome-profile` — same encryption as your normal Chrome
- **No credentials are stored** anywhere by this tool itself
- **Nothing is uploaded** to any third party

## Scope and contributions

This is intentionally a small, focused tool: catalog what you own on Vudu/Fandango at Home and Movies Anywhere, search it locally. It's a framework that could be extended in lots of useful directions — other services (Apple, Amazon, Google Play), other content types (books, games), richer metadata, watched-status tracking, recommendation cross-references with rental availability, etc.

Pull requests, forks, and outright reuses are welcome. If you build something nice on top of this I'd love a credit, but you do you.

## Requirements

- Python 3.9+
- Google Chrome installed
- An account on Fandango at Home and/or Movies Anywhere (with stuff in it, presumably)

## License

MIT — see [LICENSE](LICENSE). Use it, fork it, sell it, build something better on top of it. Attribution to me is appreciated but not required.
