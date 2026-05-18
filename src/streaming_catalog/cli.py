"""CLI entry point for streaming-catalog."""
from __future__ import annotations

import logging
import os
import sys
import time
import webbrowser

import click

from streaming_catalog import __version__
from streaming_catalog.config import resolve_db_path, resolve_port


def _ensure_db():
    """Auto-create DB if it doesn't exist."""
    db_path = resolve_db_path()
    if not db_path.exists():
        from streaming_catalog.db import init_db
        init_db()
    return db_path


def _wait_for_browser_close(driver):
    """
    Block until the user closes all Chrome windows.

    Only treats Selenium's "browser is gone" exceptions as a close signal;
    other errors are logged and the loop keeps polling so a transient hiccup
    doesn't end the wait prematurely (which would skip the user's login).
    """
    from selenium.common.exceptions import (
        InvalidSessionIdException,
        NoSuchWindowException,
        WebDriverException,
    )

    while True:
        try:
            handles = driver.window_handles
            if not handles:
                return
        except (InvalidSessionIdException, NoSuchWindowException):
            return
        except WebDriverException as e:
            # Treat a clean "disconnected" as close; log anything else and retry
            msg = str(e).lower()
            if "disconnected" in msg or "no such window" in msg or "not connected" in msg:
                return
            logging.debug("transient driver error while waiting: %s", e)
        time.sleep(1)


def _progress_factory(name, total):
    """Create a click.progressbar wrapper that returns (callback, finish) pair."""
    bar = click.progressbar(length=total, label=f"  {name:18s}", show_eta=True, show_percent=True)
    bar.__enter__()
    def callback(n):
        bar.update(n)
    def finish():
        bar.__exit__(None, None, None)
    return callback, finish


def _ensure_selenium():
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        return webdriver, Options
    except ImportError:
        click.echo("Error: selenium not installed. Run: pip install streaming-catalog[collect]", err=True)
        sys.exit(1)


def _chrome_options():
    from streaming_catalog.config import resolve_chrome_profile
    _, Options = _ensure_selenium()

    profile_dir = resolve_chrome_profile()
    profile_dir.mkdir(parents=True, exist_ok=True)

    opts = Options()
    opts.add_argument(f"--user-data-dir={str(profile_dir)}")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--no-first-run")
    opts.add_argument("--no-default-browser-check")
    return opts, profile_dir


@click.group()
@click.version_option(__version__)
@click.option("--verbose", "-v", is_flag=True, help="Enable debug logging")
@click.option("--db", "db_path", type=click.Path(), envvar="STREAMING_CATALOG_DB",
              help="Override database path")
@click.pass_context
def main(ctx, verbose, db_path):
    """Catalog your Fandango at Home and Movies Anywhere libraries."""
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.WARNING,
        format="%(asctime)s %(message)s",
        datefmt="%H:%M:%S",
    )
    ctx.ensure_object(dict)
    if db_path:
        os.environ["STREAMING_CATALOG_DB"] = db_path


# ─── First-time setup ─────────────────────────────────────────────────────────

@main.command()
def setup():
    """First-time setup: create database and log in to streaming services."""
    import shutil
    from streaming_catalog.config import user_config_file

    webdriver, Options = _ensure_selenium()

    # Step 1: Init DB
    db_path = _ensure_db()
    click.echo(f"Database ready: {db_path}")

    # Step 2: Choose port
    click.echo()
    click.echo("The search UI runs on a local web port. Default: 5858.")
    click.echo("(Pick something else if 5858 is already in use on your machine.)")
    port = click.prompt("Port for search UI", default=resolve_port(), type=int)

    # Persist port to the project-local .env so future runs use it.
    # Atomic write: tmp file + rename, with 0600 perms on POSIX.
    config_file = user_config_file()
    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_lines = []
    if config_file.exists():
        config_lines = [
            l for l in config_file.read_text().splitlines()
            if not l.startswith("STREAMING_CATALOG_PORT=")
        ]
    config_lines.append(f"STREAMING_CATALOG_PORT={port}")
    tmp = config_file.with_suffix(config_file.suffix + ".tmp")
    tmp.write_text("\n".join(config_lines) + "\n")
    if os.name == "posix":
        try:
            tmp.chmod(0o600)
        except OSError:
            pass
    tmp.replace(config_file)
    os.environ["STREAMING_CATALOG_PORT"] = str(port)
    click.echo(f"Saved port to {config_file}")

    # Step 3: Open Chrome for login
    click.echo()
    click.echo("Next: opening Chrome with two tabs to log in.")
    click.echo("  Tab 1: Fandango at Home")
    click.echo("  Tab 2: Movies Anywhere")
    click.echo()

    opts, _ = _chrome_options()
    driver = webdriver.Chrome(options=opts)
    try:
        driver.get("https://athome.fandango.com/content/account/login")
        time.sleep(2)
        driver.execute_script("window.open('https://moviesanywhere.com/login', '_blank');")

        click.echo("Chrome is open. Log in to both services in the browser tabs.")
        click.echo("This terminal will wait until you close Chrome.")
        click.echo()

        _wait_for_browser_close(driver)
    finally:
        try:
            driver.quit()
        except Exception:
            pass

    # Step 4: Tell user exactly what to run next
    cmd_prefix = "streaming-catalog" if shutil.which("streaming-catalog") else "python3 -m streaming_catalog"

    click.echo()
    click.echo("=" * 60)
    click.echo("Setup complete!")
    click.echo("=" * 60)
    click.echo()
    click.echo("Next, run these commands in your shell:")
    click.echo()
    click.echo(f"  1. Collect your library and fetch metadata (~10 min):")
    click.echo(f"     {cmd_prefix} update")
    click.echo()
    click.echo(f"  2. Open the search UI in your browser:")
    click.echo(f"     {cmd_prefix} search")
    click.echo()
    click.echo(f"     (will open at http://127.0.0.1:{port})")
    click.echo()


# ─── Update (collect + sync) ──────────────────────────────────────────────────

@main.command()
@click.option("--service", type=click.Choice(["vudu", "ma", "all"]), default="all",
              help="Which service to update")
@click.option("--timeout", default=120, help="Timeout per service in seconds")
def update(service, timeout):
    """Collect library from Chrome and sync metadata (the main command)."""
    from streaming_catalog.collector import collect_via_selenium
    from streaming_catalog.scrapers.sync import run_sync

    _ensure_db()
    services = ["vudu", "ma"] if service == "all" else [service]

    # Step 1: Collect
    click.echo("Step 1/2: Collecting library from Chrome...")
    click.echo("         (don't touch the Chrome window)")
    try:
        collect_results = collect_via_selenium(services=services, timeout=timeout)
    except RuntimeError as e:
        click.echo(f"\nError: {e}", err=True)
        click.echo("\nTip: Run 'streaming-catalog setup' if this is your first time.", err=True)
        sys.exit(2)

    total_collected = 0
    for svc, data in collect_results.items():
        count = data.get("total", data) if isinstance(data, dict) else data
        click.echo(f"         {svc}: {count} items")
        total_collected += count if isinstance(count, int) else 0

    if total_collected == 0:
        click.echo("\nNo items collected. Your sessions may have expired.")
        click.echo("Run 'streaming-catalog setup' to log in again.")
        sys.exit(1)

    # Step 2: Sync metadata
    click.echo(f"\nStep 2/2: Fetching metadata for {total_collected} items...")

    results = run_sync(services=services, progress_factory=_progress_factory)

    # Summary
    click.echo()
    for svc, stats in results.items():
        if svc in ("dedup_merges", "totals"):
            continue
        if isinstance(stats, dict) and "skipped" not in stats:
            click.echo(
                f"  {svc}: {stats.get('new', 0)} new, "
                f"{stats.get('updated', 0)} updated, "
                f"{stats.get('revoked', 0)} revoked"
            )

    if "totals" in results:
        t = results["totals"]
        click.echo(f"\n  Total unique videos: {t['videos']}")
        if results.get("dedup_merges"):
            click.echo(f"  Cross-service matches: {results['dedup_merges']}")

    click.echo("\nDone! Run 'streaming-catalog search' to browse your library.")


# ─── Search UI ────────────────────────────────────────────────────────────────

@main.command()
@click.option("--port", type=int, help="Port to serve on")
@click.option("--host", default="127.0.0.1", help="Host to bind to")
@click.option("--no-open", is_flag=True, help="Don't auto-open browser")
def search(port, host, no_open):
    """Start the search web UI."""
    try:
        from streaming_catalog.search.app import create_app
    except ImportError:
        click.echo("Error: flask not installed. Run: pip install streaming-catalog[search]", err=True)
        sys.exit(1)

    db_path = _ensure_db()
    port = port or resolve_port()

    app = create_app(db_path)
    url = f"http://{host}:{port}"
    click.echo(f"Search UI: {url}")

    if not no_open:
        # Open the browser after the server is actually listening so we don't
        # race the bind. A short background thread polls and then opens.
        import threading
        import socket

        def _open_when_ready():
            for _ in range(50):  # up to ~5 seconds
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    if s.connect_ex((host, port)) == 0:
                        webbrowser.open(url)
                        return
                time.sleep(0.1)

        threading.Thread(target=_open_when_ready, daemon=True).start()

    try:
        app.run(host=host, port=port, debug=False)
    except OSError as e:
        if "Address already in use" in str(e) or e.errno == 48:
            click.echo(f"\nPort {port} is already in use.", err=True)
            click.echo(f"Try a different port: streaming-catalog search --port 5859", err=True)
            sys.exit(1)
        raise


# ─── Individual commands (advanced) ──────────────────────────────────────────

@main.command()
def login():
    """Open Chrome to log in to streaming services."""
    webdriver, _ = _ensure_selenium()
    opts, _ = _chrome_options()

    click.echo("Opening Chrome — log in to both services, then close the window:")
    click.echo("  1. https://athome.fandango.com")
    click.echo("  2. https://moviesanywhere.com")
    click.echo()

    driver = webdriver.Chrome(options=opts)
    try:
        driver.get("https://athome.fandango.com/content/account/login")
        time.sleep(2)
        driver.execute_script("window.open('https://moviesanywhere.com/login', '_blank');")

        click.echo("Waiting... close Chrome when done.")
        _wait_for_browser_close(driver)
    finally:
        try:
            driver.quit()
        except Exception:
            pass

    click.echo("Sessions saved.")


@main.command()
@click.option("--service", type=click.Choice(["vudu", "ma", "all"]), default="all")
@click.option("--timeout", default=120)
def collect(service, timeout):
    """Collect library IDs from Chrome (without syncing metadata)."""
    from streaming_catalog.collector import collect_via_selenium

    _ensure_db()
    click.echo("Collecting... don't touch the Chrome window.")

    try:
        results = collect_via_selenium(
            services=["vudu", "ma"] if service == "all" else [service],
            timeout=timeout,
        )
    except RuntimeError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(2)

    for svc, data in results.items():
        count = data.get("total", data) if isinstance(data, dict) else data
        click.echo(f"  {svc}: {count} items")


@main.command()
@click.option("--service", type=click.Choice(["vudu", "ma", "all"]), default="all")
def sync(service):
    """Fetch metadata for collected IDs and rebuild search index."""
    from streaming_catalog.scrapers.sync import run_sync

    _ensure_db()
    results = run_sync(
        services=["vudu", "ma"] if service == "all" else [service],
        progress_factory=_progress_factory,
    )

    for svc, stats in results.items():
        if svc in ("dedup_merges", "totals"):
            continue
        if isinstance(stats, dict) and "skipped" in stats:
            click.echo(f"  {svc}: skipped ({stats['skipped']})")
        elif isinstance(stats, dict):
            click.echo(
                f"  {svc}: {stats.get('new', 0)} new, "
                f"{stats.get('updated', 0)} updated, "
                f"{stats.get('revoked', 0)} revoked"
            )

    if "totals" in results:
        click.echo(f"  Total: {results['totals']['videos']} videos")


@main.command()
def status():
    """Show database stats."""
    db_path = resolve_db_path()
    if not db_path.exists():
        click.echo("No database yet. Run 'streaming-catalog setup' to get started.")
        return

    from streaming_catalog.db import get_connection
    conn = get_connection(db_path)
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM videos")
    total = cur.fetchone()[0]

    cur.execute("SELECT source, COUNT(*) FROM video_sources WHERE is_active=1 GROUP BY source")
    active = dict(cur.fetchall())

    cur.execute("SELECT source, COUNT(*) FROM video_sources WHERE is_active=0 GROUP BY source")
    revoked = dict(cur.fetchall())

    cur.execute("SELECT MAX(last_synced) FROM video_sources")
    last_sync = cur.fetchone()[0]

    conn.close()

    click.echo(f"Database: {db_path} ({db_path.stat().st_size / 1024:.0f} KB)")
    click.echo(f"Videos: {total}")
    for src, count in active.items():
        click.echo(f"  {src}: {count}")
    if revoked:
        click.echo(f"Revoked:")
        for src, count in revoked.items():
            click.echo(f"  {src}: {count}")
    click.echo(f"Last sync: {last_sync or 'never'}")


@main.command()
@click.option("--format", "fmt", type=click.Choice(["csv", "json"]), default="json")
@click.option("--output", "-o", type=click.Path(), help="Output file (default: stdout)")
def export(fmt, output):
    """Export library to CSV or JSON."""
    import json as json_mod
    import csv
    import io

    db_path = resolve_db_path()
    if not db_path.exists():
        click.echo("No database yet. Run 'streaming-catalog setup' first.", err=True)
        sys.exit(1)

    from streaming_catalog.db import get_connection
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("""
        SELECT v.title, v.type, v.year, v.genre, v.rating, v.runtime_minutes,
               v.director, v.quality, v.description,
               GROUP_CONCAT(DISTINCT vs.source) as sources
        FROM videos v
        JOIN video_sources vs ON vs.video_id = v.id AND vs.is_active = 1
        GROUP BY v.id
        ORDER BY v.title
    """)
    columns = [d[0] for d in cur.description]
    rows = [dict(zip(columns, row)) for row in cur.fetchall()]
    conn.close()

    if fmt == "json":
        text = json_mod.dumps(rows, indent=2)
    else:
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
        text = buf.getvalue()

    if output:
        from pathlib import Path
        Path(output).write_text(text)
        click.echo(f"Exported {len(rows)} videos to {output}")
    else:
        click.echo(text)
