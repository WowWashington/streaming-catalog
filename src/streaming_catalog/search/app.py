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


def create_app(db_path: Path | None = None) -> Flask:
    """Flask app factory."""
    if db_path is None:
        from streaming_catalog.config import resolve_db_path
        db_path = resolve_db_path()

    app = Flask(__name__, template_folder=str(Path(__file__).parent / "templates"))

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

        conn = db()
        cur = conn.cursor()

        cur.execute("SELECT COUNT(*) FROM videos")
        total = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM video_sources WHERE is_active=1")
        active = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM video_sources WHERE is_active=0")
        revoked = cur.fetchone()[0]
        cur.execute(
            """SELECT COUNT(*) FROM (
                 SELECT video_id FROM video_sources WHERE is_active=1
                 GROUP BY video_id HAVING COUNT(DISTINCT source) > 1)"""
        )
        both = cur.fetchone()[0]
        stats = {"total": total, "active": active, "revoked": revoked, "both": both}

        where_clauses, params = [], []

        if q:
            fts_q = " ".join(f'"{w}"*' for w in q.split() if w)
            sql_base = """SELECT v.* FROM videos_fts ft
                          JOIN videos v ON ft.rowid = v.id
                          WHERE videos_fts MATCH ?"""
            params.append(fts_q)
        else:
            sql_base = "SELECT * FROM videos v WHERE 1=1"

        if quality_filter:
            where_clauses.append("v.quality = ?")
            params.append(quality_filter)

        if type_filter:
            where_clauses.append("v.type = ?")
            params.append(type_filter)

        extra = (" AND " + " AND ".join(where_clauses)) if where_clauses else ""
        order_by = SORT_OPTIONS[sort]
        sql = sql_base + extra + f" ORDER BY {order_by} LIMIT 300"

        cur.execute(sql, params)
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

            src_names = {s["source"] for s in srcs}
            if source == "vudu" and src_names != {"vudu"}:
                continue
            if source == "movies_anywhere" and src_names != {"movies_anywhere"}:
                continue
            if source == "both" and src_names != {"vudu", "movies_anywhere"}:
                continue

            if not show_revoked and v["all_revoked"]:
                continue

            videos.append(v)

        conn.close()

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
            p = {**base_params, "sort": new_sort}
            return "&".join(f"{k}={v}" for k, v in p.items())

        def sort_arrow(col):
            if sort == f"{col}_asc":
                return Markup(' <span class="sort-arrow">&#9650;</span>')
            if sort == f"{col}_desc":
                return Markup(' <span class="sort-arrow">&#9660;</span>')
            return Markup("")

        return render_template(
            "index.html",
            videos=videos, q=q, source_filter=source, quality=quality_filter,
            type_filter=type_filter, show_revoked=show_revoked, stats=stats,
            sort=sort, sort_qs=sort_qs, sort_arrow=sort_arrow,
        )

    return app
