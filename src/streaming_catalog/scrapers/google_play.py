"""Google Play Movies metadata scraper.

Fetches per-movie metadata from public Google Play detail pages. The pages
use HTML microdata (itemprop) for structured metadata: name, genre,
description, contentRating, duration, image. Year and runtime are in
visible text as "YYYY • NNN minutes". No authentication required for
metadata — only the ID-list collection step needs a logged-in browser.
"""
from __future__ import annotations

import json
import re
import sqlite3
import time
import logging
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

DETAIL_URL = "https://play.google.com/store/movies/details/{slug}?id={gid}"
REQUEST_DELAY = 0.5

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def _fetch_movie_page(gid: str, slug: str, session: requests.Session) -> Optional[dict]:
    """Fetch the Google Play movie detail page and extract metadata via itemprop."""
    url = DETAIL_URL.format(slug=slug, gid=gid)
    try:
        r = session.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
    except requests.RequestException as e:
        log.warning("Failed to fetch Google Play movie %s: %s", gid, e)
        return None

    soup = BeautifulSoup(r.text, "html.parser")
    return _parse_detail_page(soup, gid, slug)


def _itemprop(soup: BeautifulSoup, prop: str) -> Optional[str]:
    """Extract text from the first element with the given itemprop."""
    el = soup.find(attrs={"itemprop": prop})
    if el is None:
        return None
    if el.get("content"):
        return el["content"]
    return el.get_text(strip=True) or None


def _parse_detail_page(soup: BeautifulSoup, gid: str, slug: str) -> Optional[dict]:
    """Parse metadata from itemprop microdata and visible text."""
    title = _itemprop(soup, "name")
    if not title:
        og = soup.find("meta", property="og:title")
        title = og["content"].replace(" - Movies on Google Play", "") if og else None
    if not title:
        log.warning("No title found for Google Play movie %s", gid)
        return None

    description = _itemprop(soup, "description")
    genre = _itemprop(soup, "genre")
    rating = _itemprop(soup, "contentRating")

    # Duration: itemprop="duration" or parse from visible text
    runtime = None
    duration_str = _itemprop(soup, "duration")
    if duration_str:
        h = re.search(r"(\d+)H", duration_str, re.IGNORECASE)
        m = re.search(r"(\d+)M", duration_str, re.IGNORECASE)
        runtime = (int(h.group(1)) * 60 if h else 0) + (int(m.group(1)) if m else 0)
        if runtime == 0:
            runtime = None

    # Year: parse from visible text "YYYY • NNN minutes"
    year = None
    page_text = soup.get_text()
    year_match = re.search(r"(\d{4})\s*[·•]\s*(\d+)\s*minutes", page_text)
    if year_match:
        year = int(year_match.group(1))
        if runtime is None:
            runtime = int(year_match.group(2))

    # Thumbnail
    image = None
    img_el = soup.find(attrs={"itemprop": "image"})
    if img_el and img_el.get("src"):
        image = img_el["src"]
    if not image:
        og_img = soup.find("meta", property="og:image")
        image = og_img["content"] if og_img else None

    return {
        "title": title,
        "type": "movie",
        "year": year,
        "description": description,
        "genre": genre,
        "rating": rating.upper() if rating else None,
        "runtime_minutes": runtime,
        "director": None,
        "cast": None,
        "quality": None,
        "thumbnail_url": image,
        "gid": gid,
        "slug": slug,
    }


def upsert_video(conn: sqlite3.Connection, row: dict, gid: str) -> int:
    """Insert or update a video record, return its id."""
    cur = conn.cursor()

    cur.execute(
        "SELECT video_id FROM video_sources WHERE source='google_play' AND source_id=?",
        (gid,),
    )
    existing = cur.fetchone()

    if existing:
        video_id = existing[0]
        cur.execute(
            """UPDATE videos SET title=?, type=?, year=?, description=?,
               genre=COALESCE(?, genre), rating=COALESCE(?, rating),
               runtime_minutes=COALESCE(?, runtime_minutes),
               director=COALESCE(?, director), "cast"=COALESCE(?, "cast"),
               thumbnail_url=COALESCE(?, thumbnail_url), updated_at=datetime('now')
               WHERE id=?""",
            (
                row["title"], row["type"], row["year"], row["description"],
                row["genre"], row["rating"], row["runtime_minutes"],
                row["director"], row["cast"], row["thumbnail_url"], video_id,
            ),
        )
    else:
        cur.execute(
            """INSERT INTO videos (title, type, year, description, genre, rating,
               runtime_minutes, director, cast, thumbnail_url)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                row["title"], row["type"], row["year"], row["description"],
                row["genre"], row["rating"], row["runtime_minutes"],
                row["director"], row["cast"], row["thumbnail_url"],
            ),
        )
        video_id = cur.lastrowid

    cur.execute(
        """INSERT INTO video_sources
             (video_id, source, source_id, raw_json,
              first_seen_date, last_seen_date, is_active, removed_date, last_synced)
           VALUES (?, 'google_play', ?, ?,
                   date('now'), date('now'), 1, NULL, datetime('now'))
           ON CONFLICT(source, source_id) DO UPDATE SET
             video_id=excluded.video_id,
             raw_json=excluded.raw_json,
             last_seen_date=date('now'),
             is_active=1,
             removed_date=NULL,
             last_synced=datetime('now')""",
        (video_id, gid, json.dumps(row)),
    )
    return video_id


def mark_missing_as_removed(conn: sqlite3.Connection, seen_ids: set) -> int:
    """
    Mark Google Play sources not present in this run's seen_ids as revoked.

    See vudu.mark_missing_as_removed for the reasoning behind the Python-side
    diff (a SQL last_seen_date filter would miss same-day re-runs).
    """
    cur = conn.cursor()
    cur.execute(
        "SELECT source_id FROM video_sources WHERE source='google_play' AND is_active=1"
    )
    missing = [r[0] for r in cur.fetchall() if r[0] not in seen_ids]
    if not missing:
        return 0
    placeholders = ",".join("?" * len(missing))
    cur.execute(
        f"""UPDATE video_sources
            SET is_active=0, removed_date=date('now')
            WHERE source='google_play' AND source_id IN ({placeholders})""",
        missing,
    )
    conn.commit()
    return len(missing)


def scrape(entries: list[tuple[str, str]], db_path: Path, progress_callback=None) -> dict:
    """Fetch metadata for Google Play movies and store in DB.

    entries: list of (gid, slug) tuples.
    """
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    session = requests.Session()

    stats = {"new": 0, "updated": 0, "failed": 0, "revoked": 0, "total": len(entries)}
    log.info("Google Play: fetching metadata for %d movies", len(entries))
    seen_ids = {gid for gid, _ in entries}

    for i, (gid, slug) in enumerate(entries, 1):
        if progress_callback:
            progress_callback(1)
        elif i % 25 == 0:
            log.info("Google Play: processed %d/%d", i, len(entries))

        try:
            row = _fetch_movie_page(gid, slug, session)
            if not row:
                stats["failed"] += 1
                continue

            with conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT id FROM video_sources WHERE source='google_play' AND source_id=?",
                    (gid,),
                )
                is_new = cur.fetchone() is None
                upsert_video(conn, row, gid)
                if is_new:
                    stats["new"] += 1
                else:
                    stats["updated"] += 1
        except Exception as e:
            log.warning("Google Play: skipping %s due to error: %s", gid, e)
            stats["failed"] += 1

        time.sleep(REQUEST_DELAY)

    stats["revoked"] = mark_missing_as_removed(conn, seen_ids)
    conn.close()
    log.info("Google Play done: %s", stats)
    return stats


def load_ids_from_file(ids_file: Path) -> list[tuple[str, str]]:
    """Load Google Play (gid, slug) tuples from a tab-separated file."""
    if not ids_file.exists():
        raise FileNotFoundError(f"ID file not found: {ids_file}")
    entries = []
    for line in ids_file.read_text().strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        parts = line.split("\t", 1)
        if len(parts) == 2:
            entries.append((parts[0], parts[1]))
    return entries
