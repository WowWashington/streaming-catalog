# Troubleshooting

## "Collected 0 items"

Your Chrome session has expired. Fix:
1. Open Chrome manually
2. Navigate to `https://athome.fandango.com` and log in
3. Navigate to `https://moviesanywhere.com` and log in
4. Close Chrome
5. Run `streaming-catalog collect` again

## "selenium not installed"

Install the collect extra:
```bash
pip install streaming-catalog[collect]
```

## "flask not installed"

Install the search extra:
```bash
pip install streaming-catalog[search]
```

## "Chrome not found" or WebDriver errors

- Ensure Chrome/Chromium is installed
- Selenium 4.15+ auto-manages ChromeDriver — if you get driver errors, try updating selenium: `pip install --upgrade selenium`
- If Chrome is installed in a non-standard location, set `STREAMING_CATALOG_CHROME_PROFILE`

## "FTS5 not available"

Your Python was built without FTS5 support. This is rare on Python 3.9+ but can happen on some Linux distros:
```bash
python3 -c "import sqlite3; conn = sqlite3.connect(':memory:'); conn.execute('CREATE VIRTUAL TABLE t USING fts5(x)')"
```

If this errors, install a Python build with FTS5 (e.g., from python.org or pyenv).

## Collection is slow or incomplete

- Fandango at Home: ~60-90 seconds for a large library (700+ titles)
- Movies Anywhere: ~30-60 seconds (PageDown scrolling)
- If the count seems low, the virtual scroll may not have finished. Try increasing timeout: `streaming-catalog collect --timeout 180`

## Movies Anywhere shows fewer items than expected

MA's lazy loader can be flaky. The collector stops when the page height is stable for 3 consecutive iterations. If you suspect it stopped early:
1. Run `streaming-catalog collect --service ma` again
2. Compare the slug count in `data/ma_slugs.txt` to the "X Movies" header on the MA website

## Rate limiting

Both metadata APIs are public but rate-limited. The scraper uses conservative delays (0.4s for Vudu, 0.5s for MA). If you get HTTP 429 errors, increase delays by setting verbose mode to see which requests fail, then wait and retry.

## Database is corrupted

Delete `data/catalog.db` and re-run:
```bash
streaming-catalog init
streaming-catalog sync --collect-first
```

Your ID files (`data/vudu_ids.txt`, `data/ma_slugs.txt`) are preserved, so you don't need to recollect unless they're also missing.
