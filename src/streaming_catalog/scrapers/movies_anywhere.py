"""Movies Anywhere metadata scraper.

Fetches per-slug metadata from public movie detail pages (JSON-LD structured
data). No authentication required — only the slug list collection step needs
a logged-in browser session.
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

MA_BASE = "https://moviesanywhere.com"
REQUEST_DELAY = 0.5

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def _fetch_movie_page(slug: str, session: requests.Session) -> Optional[dict]:
    """Fetch the MA movie detail page and extract JSON-LD metadata."""
    url = f"{MA_BASE}/movie/{slug}"
    try:
        r = session.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
    except requests.RequestException as e:
        log.warning("Failed to fetch MA movie %s: %s", slug, e)
        return None

    soup = BeautifulSoup(r.text, "html.parser")

    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
            if isinstance(data, dict) and data.get("@type") in ("Movie", "TVSeries", "TVEpisode"):
                return _jsonld_to_row(slug, data)
        except (json.JSONDecodeError, AttributeError):
            continue

    # Fallback: Open Graph meta tags
    def meta(prop):
        tag = soup.find("meta", property=prop) or soup.find("meta", attrs={"name": prop})
        return tag.get("content", "").strip() if tag else None

    title = meta("og:title") or meta("twitter:title")
    description = meta("og:description") or meta("twitter:description")
    image = meta("og:image")

    if not title:
        log.warning("No metadata found for MA slug: %s", slug)
        return None

    return {
        "title": title,
        "type": "movie",
        "year": None,
        "description": description,
        "genre": None,
        "rating": None,
        "runtime_minutes": None,
        "director": None,
        "cast": None,
        "quality": None,
        "thumbnail_url": image,
        "slug": slug,
    }


def _jsonld_to_row(slug: str, data: dict) -> dict:
    """Map a schema.org JSON-LD Movie object to our schema."""
    schema_type = data.get("@type", "Movie")
    if schema_type == "TVSeries":
        video_type = "tv_series"
    elif schema_type == "TVEpisode":
        video_type = "episode"
    else:
        video_type = "movie"

    year = None
    date_published = data.get("datePublished") or data.get("dateCreated") or ""
    if date_published:
        m = re.match(r"(\d{4})", str(date_published))
        if m:
            year = int(m.group(1))

    runtime = None
    duration = data.get("duration") or ""
    if duration:
        h = re.search(r"(\d+)H", duration)
        mins = re.search(r"(\d+)M", duration)
        runtime = (int(h.group(1)) * 60 if h else 0) + (int(mins.group(1)) if mins else 0)
        if runtime == 0:
            runtime = None

    genre = data.get("genre")
    if isinstance(genre, list):
        genre = ", ".join(genre)

    director = data.get("director")
    if isinstance(director, list):
        director = ", ".join(d.get("name", "") for d in director if isinstance(d, dict))
    elif isinstance(director, dict):
        director = director.get("name")

    cast_list = data.get("actor") or []
    if isinstance(cast_list, list):
        cast = json.dumps([a.get("name", "") for a in cast_list if isinstance(a, dict)])
    else:
        cast = None

    rating = None
    content_rating = data.get("contentRating")
    if isinstance(content_rating, str):
        rating = content_rating.upper()
    elif isinstance(content_rating, list) and content_rating:
        rating = str(content_rating[0]).upper()

    image = data.get("image") or data.get("thumbnailUrl")
    if isinstance(image, dict):
        image = image.get("url") or image.get("contentUrl")

    return {
        "title": data.get("name") or "Unknown",
        "type": video_type,
        "year": year,
        "description": data.get("description"),
        "genre": genre,
        "rating": rating,
        "runtime_minutes": runtime,
        "director": director,
        "cast": cast,
        "quality": None,
        "thumbnail_url": image,
        "slug": slug,
    }


def upsert_video(conn: sqlite3.Connection, row: dict, slug: str) -> int:
    """Insert or update a video record, return its id."""
    cur = conn.cursor()

    cur.execute(
        "SELECT video_id FROM video_sources WHERE source='movies_anywhere' AND source_id=?",
        (slug,),
    )
    existing = cur.fetchone()

    if existing:
        video_id = existing[0]
        cur.execute(
            """UPDATE videos SET title=?, type=?, year=?, description=?,
               genre=?, rating=?, runtime_minutes=?, director=?, cast=?,
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
           VALUES (?, 'movies_anywhere', ?, ?,
                   date('now'), date('now'), 1, NULL, datetime('now'))
           ON CONFLICT(source, source_id) DO UPDATE SET
             video_id=excluded.video_id,
             raw_json=excluded.raw_json,
             last_seen_date=date('now'),
             is_active=1,
             removed_date=NULL,
             last_synced=datetime('now')""",
        (video_id, slug, json.dumps(row)),
    )
    return video_id


def mark_missing_as_removed(conn: sqlite3.Connection, seen_slugs: set) -> int:
    """Mark MA sources not seen this run as revoked."""
    cur = conn.cursor()
    cur.execute(
        """SELECT source_id FROM video_sources
           WHERE source='movies_anywhere' AND is_active=1
             AND last_seen_date != date('now')"""
    )
    missing = [r[0] for r in cur.fetchall() if r[0] not in seen_slugs]
    if not missing:
        return 0
    placeholders = ",".join("?" * len(missing))
    cur.execute(
        f"""UPDATE video_sources
            SET is_active=0, removed_date=date('now')
            WHERE source='movies_anywhere' AND source_id IN ({placeholders})""",
        missing,
    )
    conn.commit()
    return len(missing)


def scrape(slugs: list[str], db_path: Path, progress_callback=None) -> dict:
    """Fetch metadata for MA movie slugs and store in DB."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    session = requests.Session()

    stats = {"new": 0, "updated": 0, "failed": 0, "revoked": 0, "total": len(slugs)}
    log.info("Movies Anywhere: fetching metadata for %d slugs", len(slugs))
    seen_slugs = set(slugs)

    for i, slug in enumerate(slugs, 1):
        if progress_callback:
            progress_callback(1)
        elif i % 25 == 0:
            log.info("MA: processed %d/%d", i, len(slugs))

        row = _fetch_movie_page(slug, session)
        if not row:
            stats["failed"] += 1
            continue

        with conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT id FROM video_sources WHERE source='movies_anywhere' AND source_id=?",
                (slug,),
            )
            is_new = cur.fetchone() is None
            upsert_video(conn, row, slug)
            if is_new:
                stats["new"] += 1
            else:
                stats["updated"] += 1

        time.sleep(REQUEST_DELAY)

    stats["revoked"] = mark_missing_as_removed(conn, seen_slugs)
    conn.close()
    log.info("Movies Anywhere done: %s", stats)
    return stats


def load_slugs_from_file(slugs_file: Path) -> list[str]:
    """Load MA slugs from the saved file."""
    if not slugs_file.exists():
        raise FileNotFoundError(f"Slugs file not found: {slugs_file}")
    return [s.strip() for s in slugs_file.read_text().strip().split("\n") if s.strip()]
