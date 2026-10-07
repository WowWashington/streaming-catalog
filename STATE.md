# StreamingCatalog — STATE

**State**: Stable — 882 unique titles across Fandango at Home (Vudu), Movies Anywhere and Google Play; revocation and dedup fixes committed (`5ab2f6b`)
**Updated**: 2026-10-06 · **Path**: `~/Projects/StreamingCatalog/` · **Repo**: github.com/WowWashington/streaming-catalog (public, MIT, main)
**Stack**: Python 3.9+ (Click CLI, Flask, Selenium, BeautifulSoup), SQLite FTS5 `data/catalog.db`

> Load this file first; open a `docs/` file only when the task needs it. Keep this file ~4 KB:
> add detail and dated notes to the matching component doc, not here.

## What it is
A distributable, cross-platform catalog of the movies and TV a user owns across streaming stores, with a local search UI.
It's also Peter's personal instance, after absorbing #22 HomeProjects on 2026-05-18.

## Components
| Component | Doc |
|---|---|
| Intent, files, architecture, decisions, config/secrets | `docs/architecture.md` |
| Install + lifecycle commands | `docs/install-run.md` |
| Scheduling, Chrome setup, troubleshooting | `docs/scheduling.md`, `docs/setup-chrome.md`, `docs/troubleshooting.md` |
| Backlog · history | `docs/backlog.md`, `docs/history.md` |

## Run
- `streaming-catalog update | search | status | export`. Search UI on :5858.
- LaunchAgents: `com.streaming-catalog.search` (always on), `com.streaming-catalog.sync` (weekly)

## Hard rules
Public repo: never commit `data/`, cookies or account IDs.

## Now / next
1. Optional: unit tests for the parsers and dedup logic. Optional: announce via `docs/linkedin-post.md`.
2. `~/Projects/HomeProjects-archived/` is safe to delete when Peter is ready.

## Related
Successor of #22 HomeProjects. Featured in #20 PromotePeter.
