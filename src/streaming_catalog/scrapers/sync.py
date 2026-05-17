"""Sync orchestrator: runs scrapers, deduplicates, rebuilds FTS index."""
from __future__ import annotations
import logging
import re
import sqlite3
from pathlib import Path

from streaming_catalog.config import resolve_db_path, resolve_data_dir
from streaming_catalog.db import get_connection, rebuild_fts
from streaming_catalog.scrapers import vudu, movies_anywhere

log = logging.getLogger(__name__)


def normalize_title(title: str) -> str:
    """Lowercase, strip articles + punctuation for dedup matching."""
    t = title.lower().strip()
    t = re.sub(r"^(the|a|an)\s+", "", t)
    t = re.sub(r"[^a-z0-9]+", "", t)
    return t


YEAR_TOLERANCE = 2  # merge records whose years differ by this much or less


def _years_compatible(a, b) -> bool:
    """
    Years are compatible (likely the same film) if both are missing, both
    are present and within YEAR_TOLERANCE, or one is missing and the other
    is present (no contradiction).
    """
    if a is None and b is None:
        return True
    if a is None or b is None:
        return True
    return abs(a - b) <= YEAR_TOLERANCE


def dedupe_videos(conn: sqlite3.Connection) -> int:
    """
    Merge video records that likely refer to the same film.

    Strategy: bucket records by normalized title, then within each bucket
    do pairwise year-compatibility checks. This handles three real cases:
      - Same title + same year (most common)
      - Same title + slightly different years (metadata sources disagree —
        Google sometimes returns the wrong year, e.g. Clockwork Orange)
      - Same title + one source missing the year (no contradiction)

    Records with different years that are more than YEAR_TOLERANCE apart
    are kept separate, since two different films can share a title
    (e.g. "Awakening" 1990 vs "Awakening" 2011).

    For each cluster: keep lowest video.id, repoint video_sources, delete dupes.
    """
    cur = conn.cursor()
    cur.execute("SELECT id, title, year FROM videos")
    rows = cur.fetchall()

    # Bucket by normalized title (years compared per-cluster below)
    by_title: dict[str, list[tuple[int, int | None]]] = {}
    for vid, title, year in rows:
        norm = normalize_title(title or "")
        if not norm:
            continue
        by_title.setdefault(norm, []).append((vid, year))

    merges = 0
    for norm, entries in by_title.items():
        if len(entries) < 2:
            continue
        # Build clusters by year-compatibility within this title bucket
        clusters: list[list[tuple[int, int | None]]] = []
        for entry in entries:
            placed = False
            for cluster in clusters:
                if any(_years_compatible(entry[1], existing[1]) for existing in cluster):
                    cluster.append(entry)
                    placed = True
                    break
            if not placed:
                clusters.append([entry])

        for cluster in clusters:
            if len(cluster) < 2:
                continue
            ids = [vid for vid, _ in cluster]
            keeper = min(ids)
            dupes = [i for i in ids if i != keeper]
            placeholders = ",".join("?" * len(dupes))
            cur.execute(
                f"UPDATE video_sources SET video_id=? WHERE video_id IN ({placeholders})",
                (keeper, *dupes),
            )
            cur.execute(f"DELETE FROM videos WHERE id IN ({placeholders})", dupes)
            merges += len(dupes)

    conn.commit()
    return merges


def run_sync(services: list[str] | None = None, progress_factory=None) -> dict:
    """
    Run the full sync pipeline.

    progress_factory: optional callable that takes (service_name, total) and
    returns (progress_callback, finish_callback). Used for CLI progress bars.
    """
    if services is None:
        services = ["vudu", "ma"]

    db_path = resolve_db_path()
    data_dir = resolve_data_dir()
    results = {}

    if "vudu" in services:
        ids_file = data_dir / "vudu_ids.txt"
        tv_ids_file = data_dir / "vudu_tv_ids.txt"
        try:
            content_ids = vudu.load_ids_from_file(ids_file)
            cb, finish = (progress_factory("Vudu", len(content_ids))
                          if progress_factory else (None, lambda: None))
            results["vudu"] = vudu.scrape(content_ids, db_path, tv_ids_file, progress_callback=cb)
            finish()
        except FileNotFoundError as e:
            log.warning("Skipping Vudu: %s", e)
            results["vudu"] = {"skipped": str(e)}

    if "ma" in services:
        slugs_file = data_dir / "ma_slugs.txt"
        try:
            slugs = movies_anywhere.load_slugs_from_file(slugs_file)
            cb, finish = (progress_factory("Movies Anywhere", len(slugs))
                          if progress_factory else (None, lambda: None))
            results["movies_anywhere"] = movies_anywhere.scrape(slugs, db_path, progress_callback=cb)
            finish()
        except FileNotFoundError as e:
            log.warning("Skipping Movies Anywhere: %s", e)
            results["movies_anywhere"] = {"skipped": str(e)}

    conn = get_connection(db_path)
    merges = dedupe_videos(conn)
    rebuild_fts(conn)

    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM videos")
    total_videos = cur.fetchone()[0]
    cur.execute("SELECT source, COUNT(*) FROM video_sources WHERE is_active=1 GROUP BY source")
    active = dict(cur.fetchall())
    cur.execute("SELECT source, COUNT(*) FROM video_sources WHERE is_active=0 GROUP BY source")
    revoked = dict(cur.fetchall())
    conn.close()

    results["dedup_merges"] = merges
    results["totals"] = {"videos": total_videos, "active": active, "revoked": revoked}
    log.info("Sync done: %s", results)
    return results
