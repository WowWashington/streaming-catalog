# Troubleshooting

## "Chrome failed to start"

Chrome can only have one process using a profile at a time.

**If you have Chrome open**: Quit Chrome (Cmd+Q on macOS, or close all windows on Windows/Linux). This applies to your *normal* Chrome too — even though StreamingCatalog uses its own profile, on macOS Chrome can sometimes refuse to launch a second instance.

**If Chrome is closed but you still see this**: A previous run may have crashed and left a lock file. Remove it:

```bash
rm ./chrome-profile/SingletonLock      # from inside the project folder
```

## "Collected 0 items"

Your sessions have expired. Re-run setup to log back in:

```bash
streaming-catalog setup
```

Or just the login step if the database already exists:

```bash
streaming-catalog login
```

## "selenium not installed" or "flask not installed"

You installed the bare package without optional dependencies. Reinstall with all extras:

```bash
pip install ".[all]"
```

## Chrome opens but immediately closes

This usually means ChromeDriver and Chrome versions don't match. Selenium 4.15+ auto-manages ChromeDriver, but if you get version mismatch errors:

```bash
pip install --upgrade selenium
```

## "FTS5 not available"

Your Python build is missing SQLite FTS5 support (rare on 3.9+). Verify:

```bash
python3 -c "import sqlite3; sqlite3.connect(':memory:').execute('CREATE VIRTUAL TABLE t USING fts5(x)')"
```

If this errors, install Python from python.org or use pyenv.

## Collection is slow or finds fewer items than expected

The library pages use lazy-loaded virtual scrolling. Defaults should work, but you can extend the timeout:

```bash
streaming-catalog update --timeout 300
```

Movies Anywhere is particularly finicky — if you suspect items are missing, compare the slug count in `data/ma_slugs.txt` to the "X Movies" header on the MA website. Run the collect step alone:

```bash
streaming-catalog collect --service ma
```

## Rate limiting

Both metadata APIs are public but rate-limited. The scraper uses conservative delays (0.4s for Vudu, 0.5s for MA). If you get HTTP 429 errors during sync, wait an hour and try again.

## Database corrupted

Reset and start over:

```bash
rm data/catalog.db
streaming-catalog setup
streaming-catalog update
```

Your Chrome session in `./chrome-profile/` is preserved, so you won't need to log in again.
