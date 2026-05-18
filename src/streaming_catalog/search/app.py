"""Flask search UI for the video library."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from flask import Flask, request, render_template
from markupsafe import Markup


SORT_OPTIONS = {
    "title_asc": "v.title ASC",
    "title_desc": "v.title DESC",
    "year_desc": "v.year DESC, v.title ASC",
    "year_asc": "v.year ASC, v.title ASC",
    "added_desc": "v.created_at DESC, v.title ASC",
    "added_asc": "v.created_at ASC, v.title ASC",
}
DEFAULT_SORT = "year_desc"
PAGE_SIZE = 100


def _build_fts_query(q: str) -> str:
    """
    Build a safe FTS5 MATCH query from raw user input.

    FTS5 treats `"` as a phrase delimiter and various other characters as
    operators, so a query like `foo"bar` or `.` will raise a sqlite3
    OperationalError. Tokenize the input by extracting runs of word
    characters (matches how FTS5's default tokenizer indexes the text),
    then wrap each token in double quotes with a prefix-match suffix.
    If nothing is left, return empty so the caller falls back to
    "no search filter".
    """
    if not q:
        return ""
    import re
    tokens = re.findall(r"\w+", q, flags=re.UNICODE)
    return " ".join(f'"{t}"*' for t in tokens)


def create_app(db_path: Path | None = None) -> Flask:
    """Flask app factory."""
    if db_path is None:
        from streaming_catalog.config import resolve_db_path
        db_path = resolve_db_path()

    app = Flask(__name__, template_folder=str(Path(__file__).parent / "templates"))
    app.config["TEMPLATES_AUTO_RELOAD"] = True

    def db():
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn

    @app.route("/")
    def index():
        q = (request.args.get("q") or "").strip()
        source = request.args.get("source", "")
        quality_filter = request.args.get("quality", "")
        type_filter = request.args.get("type", "")
        show_revoked = bool(request.args.get("show_revoked"))
        sort = request.args.get("sort", DEFAULT_SORT)
        if sort not in SORT_OPTIONS:
            sort = DEFAULT_SORT
        try:
            page = max(1, int(request.args.get("page", "1")))
        except ValueError:
            page = 1

        conn = db()
        try:
            return _render(conn, q, source, quality_filter, type_filter,
                           show_revoked, sort, page)
        finally:
            conn.close()

    def _render(conn, q, source, quality_filter, type_filter,
                show_revoked, sort, page):
        cur = conn.cursor()

        cur.execute("SELECT COUNT(*) FROM videos")
        total = cur.fetchone()[0]
        cur.execute(
            """SELECT GROUP_CONCAT(DISTINCT source) AS srcs
               FROM video_sources WHERE is_active=1
               GROUP BY video_id"""
        )
        # Per-service exclusive counts plus multi-source counts. Tracks any
        # combination of {vudu, movies_anywhere, google_play}.
        vudu_only = ma_only = gp_only = 0
        on_multiple = 0  # owned on 2+ services
        for (srcs,) in cur.fetchall():
            parts = set(srcs.split(",")) if srcs else set()
            if len(parts) >= 2:
                on_multiple += 1
            elif "vudu" in parts:
                vudu_only += 1
            elif "movies_anywhere" in parts:
                ma_only += 1
            elif "google_play" in parts:
                gp_only += 1

        cur.execute("SELECT COUNT(*) FROM video_sources WHERE is_active=0")
        revoked = cur.fetchone()[0]

        stats = {
            "total": total,
            "on_multiple": on_multiple,
            "vudu_only": vudu_only,
            "ma_only": ma_only,
            "gp_only": gp_only,
            "revoked": revoked,
        }

        where_clauses, params = [], []

        fts_q = _build_fts_query(q)
        if fts_q:
            sql_base = """FROM videos_fts ft
                          JOIN videos v ON ft.rowid = v.id
                          WHERE videos_fts MATCH ?"""
            params.append(fts_q)
        else:
            sql_base = "FROM videos v WHERE 1=1"

        if quality_filter:
            where_clauses.append("v.quality = ?")
            params.append(quality_filter)

        if type_filter:
            where_clauses.append("v.type = ?")
            params.append(type_filter)

        # Source filter — pushed into SQL via subquery on video_sources.
        # "*_only" filters surface titles exclusive to one service; "multi"
        # surfaces titles owned on 2+ services.
        _only = {
            "vudu": "vudu",
            "movies_anywhere": "movies_anywhere",
            "google_play": "google_play",
        }
        if source in _only:
            where_clauses.append(
                "v.id IN (SELECT video_id FROM video_sources WHERE is_active=1 "
                "GROUP BY video_id HAVING COUNT(DISTINCT source) = 1 "
                f"AND MAX(source) = '{_only[source]}')"
            )
        elif source == "multi":
            where_clauses.append(
                "v.id IN (SELECT video_id FROM video_sources WHERE is_active=1 "
                "GROUP BY video_id HAVING COUNT(DISTINCT source) >= 2)"
            )

        # Revoked filter — hide videos with no active sources unless requested
        if not show_revoked:
            where_clauses.append(
                "v.id IN (SELECT video_id FROM video_sources WHERE is_active=1)"
            )

        extra = (" AND " + " AND ".join(where_clauses)) if where_clauses else ""
        order_by = SORT_OPTIONS[sort]

        # Count for pagination
        count_sql = "SELECT COUNT(*) " + sql_base + extra
        cur.execute(count_sql, params)
        result_count = cur.fetchone()[0]

        # Page bounds
        total_pages = max(1, (result_count + PAGE_SIZE - 1) // PAGE_SIZE)
        page = min(page, total_pages)
        offset = (page - 1) * PAGE_SIZE

        # Fetch the current page
        page_sql = (
            "SELECT v.* " + sql_base + extra +
            f" ORDER BY {order_by} LIMIT ? OFFSET ?"
        )
        cur.execute(page_sql, [*params, PAGE_SIZE, offset])
        rows = [dict(r) for r in cur.fetchall()]

        videos = []
        for v in rows:
            cur.execute(
                """SELECT source, source_id, is_active, removed_date, first_seen_date
                   FROM video_sources WHERE video_id=? ORDER BY source""",
                (v["id"],),
            )
            srcs = [dict(s) for s in cur.fetchall()]
            v["sources"] = srcs
            v["all_revoked"] = bool(srcs) and all(s["is_active"] == 0 for s in srcs)
            v["first_seen"] = min(
                (s["first_seen_date"] for s in srcs if s["first_seen_date"]), default=None
            )
            videos.append(v)

        # Pagination info
        showing_from = offset + 1 if videos else 0
        showing_to = offset + len(videos)
        pagination = {
            "page": page,
            "total_pages": total_pages,
            "result_count": result_count,
            "showing_from": showing_from,
            "showing_to": showing_to,
            "has_prev": page > 1,
            "has_next": page < total_pages,
        }

        base_params = {}
        if q:
            base_params["q"] = q
        if source:
            base_params["source"] = source
        if quality_filter:
            base_params["quality"] = quality_filter
        if type_filter:
            base_params["type"] = type_filter
        if show_revoked:
            base_params["show_revoked"] = "1"

        def sort_qs(col):
            col_asc = f"{col}_asc"
            col_desc = f"{col}_desc"
            if sort == col_asc:
                new_sort = col_desc
            elif sort == col_desc:
                new_sort = col_asc
            else:
                new_sort = col_desc if col == "year" else col_asc
            # Reset to page 1 on sort change
            p = {**base_params, "sort": new_sort}
            return "&".join(f"{k}={v}" for k, v in p.items())

        def sort_arrow(col):
            if sort == f"{col}_asc":
                return Markup(' <span class="sort-arrow">&#9650;</span>')
            if sort == f"{col}_desc":
                return Markup(' <span class="sort-arrow">&#9660;</span>')
            return Markup("")

        def page_qs(target_page):
            p = {**base_params, "sort": sort, "page": target_page}
            return "&".join(f"{k}={v}" for k, v in p.items())

        return render_template(
            "index.html",
            videos=videos, q=q, source_filter=source, quality=quality_filter,
            type_filter=type_filter, show_revoked=show_revoked, stats=stats,
            sort=sort, sort_qs=sort_qs, sort_arrow=sort_arrow,
            pagination=pagination, page_qs=page_qs,
        )

    return app
