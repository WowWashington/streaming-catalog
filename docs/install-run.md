# Install & Run

pipx/wrapper install, lifecycle commands.

> Component detail. Start at `STATE.md` in the project root.

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
