"""CLI entry point for streaming-catalog."""
import logging
import sys

import click

from streaming_catalog import __version__
from streaming_catalog.config import resolve_db_path, resolve_data_dir, resolve_port


@click.group()
@click.version_option(__version__)
@click.option("--verbose", "-v", is_flag=True, help="Enable debug logging")
@click.option("--db", "db_path", type=click.Path(), envvar="STREAMING_CATALOG_DB",
              help="Override database path")
@click.pass_context
def main(ctx, verbose, db_path):
    """Catalog your Fandango at Home and Movies Anywhere libraries."""
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    ctx.ensure_object(dict)
    if db_path:
        import os
        os.environ["STREAMING_CATALOG_DB"] = db_path


@main.command()
def init():
    """Create the database and data directory."""
    from streaming_catalog.db import init_db
    from streaming_catalog.config import resolve_chrome_profile

    db_path = resolve_db_path()
    if db_path.exists():
        click.echo(f"Database already exists: {db_path}")
        return

    path = init_db()
    click.echo(f"Created database: {path}")

    try:
        chrome = resolve_chrome_profile()
        if chrome.exists():
            click.echo(f"Chrome profile found: {chrome}")
        else:
            click.echo(f"Warning: Chrome profile not found at {chrome}")
            click.echo("Set STREAMING_CATALOG_CHROME_PROFILE if Chrome is installed elsewhere.")
    except RuntimeError as e:
        click.echo(f"Warning: {e}")

    click.echo("\nNext steps:")
    click.echo("  1. Log in to athome.fandango.com and moviesanywhere.com in Chrome")
    click.echo("  2. Run: streaming-catalog collect")
    click.echo("  3. Run: streaming-catalog sync")


@main.command()
@click.option("--service", type=click.Choice(["vudu", "ma", "all"]), default="all",
              help="Which service to collect from")
@click.option("--timeout", default=120, help="Timeout per service in seconds")
def collect(service, timeout):
    """Open Chrome and harvest library IDs (requires logged-in Chrome)."""
    from streaming_catalog.collector import collect_via_selenium

    click.echo("Opening Chrome to collect library data...")
    click.echo("Do not interact with the Chrome window until collection is complete.")

    try:
        results = collect_via_selenium(
            services=["vudu", "ma"] if service == "all" else [service],
            timeout=timeout,
        )
    except RuntimeError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(2)

    for svc, data in results.items():
        if isinstance(data, dict):
            click.echo(f"  {svc}: {data.get('total', data)} items")
        else:
            click.echo(f"  {svc}: {data} items")

    total = sum(
        v.get("total", v) if isinstance(v, dict) else v
        for v in results.values()
    )
    if total == 0:
        click.echo("\nWarning: collected 0 items. Your Chrome session may have expired.")
        click.echo("Log in to the services in Chrome and try again.")
        sys.exit(1)

    click.echo("\nCollection complete. Run 'streaming-catalog sync' to fetch metadata.")


@main.command()
@click.option("--collect-first", "do_collect", is_flag=True,
              help="Run collection before sync")
@click.option("--service", type=click.Choice(["vudu", "ma", "all"]), default="all",
              help="Which service to sync")
def sync(do_collect, service):
    """Fetch metadata for collected IDs, deduplicate, rebuild search index."""
    from streaming_catalog.scrapers.sync import run_sync

    if do_collect:
        from streaming_catalog.collector import collect_via_selenium
        click.echo("Collecting library data first...")
        collect_via_selenium(
            services=["vudu", "ma"] if service == "all" else [service],
        )

    results = run_sync(services=["vudu", "ma"] if service == "all" else [service])

    for svc, stats in results.items():
        if svc in ("dedup_merges", "totals"):
            continue
        if isinstance(stats, dict) and "skipped" in stats:
            click.echo(f"  {svc}: skipped ({stats['skipped']})")
        elif isinstance(stats, dict):
            click.echo(
                f"  {svc}: {stats.get('new', 0)} new, "
                f"{stats.get('updated', 0)} updated, "
                f"{stats.get('failed', 0)} failed, "
                f"{stats.get('revoked', 0)} revoked"
            )

    if "dedup_merges" in results:
        click.echo(f"  Dedup merges: {results['dedup_merges']}")
    if "totals" in results:
        t = results["totals"]
        click.echo(f"  Total unique videos: {t['videos']}")


@main.command()
@click.option("--port", type=int, help="Port to serve on")
@click.option("--host", default="127.0.0.1", help="Host to bind to")
def search(port, host):
    """Start the search web UI."""
    try:
        from streaming_catalog.search.app import create_app
    except ImportError:
        click.echo("Error: flask not installed. Run: pip install streaming-catalog[search]", err=True)
        sys.exit(1)

    port = port or resolve_port()
    db_path = resolve_db_path()
    if not db_path.exists():
        click.echo(f"Database not found: {db_path}", err=True)
        click.echo("Run 'streaming-catalog init' first.", err=True)
        sys.exit(1)

    app = create_app(db_path)
    click.echo(f"Search UI: http://{host}:{port}")
    app.run(host=host, port=port, debug=False)


@main.command()
def status():
    """Show database stats."""
    db_path = resolve_db_path()
    if not db_path.exists():
        click.echo(f"No database found at {db_path}")
        click.echo("Run 'streaming-catalog init' to create one.")
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
    click.echo(f"Total unique videos: {total}")
    click.echo(f"Active sources:")
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
        click.echo("No database found. Run 'streaming-catalog init' first.", err=True)
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
