"""Vudu / Fandango at Home metadata scraper.

Fetches per-ID metadata from the public apicache.vudu.com API. No authentication
required — the API returns public content data for any valid content ID.
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

log = logging.getLogger(__name__)

APICACHE = (
    "https://apicache.vudu.com/api2/_type/contentSearch/contentEncoding/gzip/"
    "contentId/{id}/count/1/followup/promoTags/followup/uxPromoTags/"
    "format/application*2Fjson"
)
BATCH_SIZE = 10
REQUEST_DELAY = 0.4

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}


def _parse_response(text: str) -> Optional[dict]:
    """
    Strip the /*-secure-{...}*/ wrapper Vudu apicache returns and parse JSON.

    Uses explicit prefix/suffix removal (not rstrip, which would eat any
    trailing run of `*` or `/` characters) and tolerates surrounding
    whitespace.
    """
    clean = text.strip()
    if clean.startswith("/*-secure-"):
        clean = clean[len("/*-secure-"):]
    if clean.endswith("*/"):
        clean = clean[:-2]
    try:
        return json.loads(clean)
    except json.JSONDecodeError as e:
        log.warning("JSON parse error: %s", e)
        return None


def _first(val) -> Optional[str]:
    """Extract first element from Vudu's array-wrapped values."""
    if isinstance(val, list) and val:
        return val[0]
    return val if val is not None else None


def _fetch_content(content_id: str, session: requests.Session) -> Optional[dict]:
    """Fetch metadata for one content ID from apicache."""
    url = APICACHE.format(id=content_id)
    try:
        r = session.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        data = _parse_response(r.text)
        if not data or not data.get("content"):
            return None
        return data["content"][0]
    except requests.RequestException as e:
        log.warning("Failed to fetch content %s: %s", content_id, e)
        return None


def _content_to_row(c: dict, tv_ids: set) -> dict:
    """Map a Vudu content object to our videos table schema."""
    raw_type = _first(c.get("type")) or "program"
    content_id = _first(c.get("contentId")) or ""
    if raw_type in ("series", "season"):
        video_type = "tv_series"
    elif raw_type == "episode":
        video_type = "episode"
    elif content_id in tv_ids:
        video_type = "tv_series"
    else:
        video_type = "movie"

    release_time = _first(c.get("releaseTime")) or ""
    year = None
    if release_time:
        m = re.match(r"(\d{4})", release_time)
        if m:
            year = int(m.group(1))

    length_s = _first(c.get("lengthSeconds"))
    runtime = int(length_s) // 60 if length_s else None

    mpaa = _first(c.get("mpaaRating")) or ""
    if not mpaa:
        rating_obj = c.get("contentRating", [{}])
        r0 = rating_obj[0] if isinstance(rating_obj, list) else rating_obj
        mpaa = _first(r0.get("ratingValue")) or ""

    studio_obj = c.get("studio") or c.get("distributionStudio") or [{}]
    studio = ""
    if isinstance(studio_obj, list) and studio_obj:
        studio = _first(studio_obj[0].get("name")) or ""

    quality_map = {"uhd": "4K UHD", "hdx": "HD", "hd": "HD", "sd": "SD"}
    raw_quality = _first(c.get("bestStreamableVideoQuality")) or ""
    quality = quality_map.get(raw_quality.lower(), raw_quality.upper() or None)

    return {
        "title": _first(c.get("title")) or "Unknown",
        "type": video_type,
        "year": year,
        "description": _first(c.get("description")),
        "genre": None,
        "rating": mpaa.upper() or None,
        "runtime_minutes": runtime,
        "director": None,
        "cast": None,
        "quality": quality,
        "thumbnail_url": _first(c.get("posterUrl")),
        "source_id": _first(c.get("contentId")),
    }


def upsert_video(conn: sqlite3.Connection, row: dict, source_id: str) -> int:
    """Insert or update a video record, return its id."""
    cur = conn.cursor()

    cur.execute(
        "SELECT video_id FROM video_sources WHERE source='vudu' AND source_id=?",
        (source_id,),
    )
    existing = cur.fetchone()

    if existing:
        video_id = existing[0]
        cur.execute(
            """UPDATE videos SET title=?, type=?, year=?, description=?,
               genre=?, rating=?, runtime_minutes=?, director=?, cast=?,
               quality=?, thumbnail_url=?, updated_at=datetime('now')
               WHERE id=?""",
            (
                row["title"], row["type"], row["year"], row["description"],
                row["genre"], row["rating"], row["runtime_minutes"],
                row["director"], row["cast"], row["quality"],
                row["thumbnail_url"], video_id,
            ),
        )
    else:
        cur.execute(
            """INSERT INTO videos (title, type, year, description, genre, rating,
               runtime_minutes, director, cast, quality, thumbnail_url)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                row["title"], row["type"], row["year"], row["description"],
                row["genre"], row["rating"], row["runtime_minutes"],
                row["director"], row["cast"], row["quality"],
                row["thumbnail_url"],
            ),
        )
        video_id = cur.lastrowid

    cur.execute(
        """INSERT INTO video_sources
             (video_id, source, source_id, quality, raw_json,
              first_seen_date, last_seen_date, is_active, removed_date, last_synced)
           VALUES (?, 'vudu', ?, ?, ?,
                   date('now'), date('now'), 1, NULL, datetime('now'))
           ON CONFLICT(source, source_id) DO UPDATE SET
             video_id=excluded.video_id,
             quality=excluded.quality,
             raw_json=excluded.raw_json,
             last_seen_date=date('now'),
             is_active=1,
             removed_date=NULL,
             last_synced=datetime('now')""",
        (video_id, source_id, row["quality"], json.dumps(row)),
    )
    return video_id


def mark_missing_as_removed(conn: sqlite3.Connection, seen_ids: set) -> int:
    """
    Mark Vudu sources not present in this run's seen_ids as revoked.

    seen_ids is the authoritative "what we saw today" set, so we compute the
    diff in Python rather than relying on last_seen_date — a same-day re-run
    of this sync would otherwise miss newly-revoked items because their
    last_seen_date was already bumped by the previous run.
    """
    cur = conn.cursor()
    cur.execute(
        "SELECT source_id FROM video_sources WHERE source='vudu' AND is_active=1"
    )
    missing = [r[0] for r in cur.fetchall() if r[0] not in seen_ids]
    if not missing:
        return 0
    placeholders = ",".join("?" * len(missing))
    cur.execute(
        f"""UPDATE video_sources
            SET is_active=0, removed_date=date('now')
            WHERE source='vudu' AND source_id IN ({placeholders})""",
        missing,
    )
    conn.commit()
    return len(missing)


def scrape(content_ids: list[str], db_path: Path, tv_ids_file: Path | None = None,
           progress_callback=None) -> dict:
    """Fetch metadata for given content IDs and store in DB."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    session = requests.Session()

    tv_ids: set = set()
    if tv_ids_file and tv_ids_file.exists():
        raw = tv_ids_file.read_text().strip().replace("\n", ",")
        tv_ids = {x for x in raw.split(",") if x}

    stats = {"new": 0, "updated": 0, "failed": 0, "revoked": 0, "total": len(content_ids)}
    log.info("Vudu: fetching metadata for %d content IDs", len(content_ids))
    seen_ids = set(content_ids)

    for i, cid in enumerate(content_ids, 1):
        if progress_callback:
            progress_callback(1)
        elif i % 50 == 0:
            log.info("Vudu: processed %d/%d", i, len(content_ids))

        try:
            content = _fetch_content(cid, session)
            if not content:
                stats["failed"] += 1
                continue

            row = _content_to_row(content, tv_ids)

            with conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT id FROM video_sources WHERE source='vudu' AND source_id=?",
                    (cid,),
                )
                is_new = cur.fetchone() is None
                upsert_video(conn, row, cid)
                if is_new:
                    stats["new"] += 1
                else:
                    stats["updated"] += 1
        except Exception as e:
            log.warning("Vudu: skipping %s due to error: %s", cid, e)
            stats["failed"] += 1

        time.sleep(REQUEST_DELAY)

    stats["revoked"] = mark_missing_as_removed(conn, seen_ids)
    conn.close()
    log.info("Vudu done: %s", stats)
    return stats


def load_ids_from_file(ids_file: Path) -> list[str]:
    """Load content IDs from the saved file."""
    if not ids_file.exists():
        raise FileNotFoundError(f"ID file not found: {ids_file}")
    return [i.strip() for i in ids_file.read_text().strip().split(",") if i.strip()]
