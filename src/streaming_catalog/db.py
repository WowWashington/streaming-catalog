"""Database connection and schema management."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from streaming_catalog.config import resolve_db_path, schema_path


def get_connection(db_path: Path | None = None) -> sqlite3.Connection:
    """Open a connection with foreign keys enabled."""
    path = db_path or resolve_db_path()
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Path | None = None) -> Path:
    """Create the database and apply schema. Returns the DB path."""
    path = db_path or resolve_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    sql = schema_path().read_text()
    conn = sqlite3.connect(path)
    conn.executescript(sql)
    conn.close()
    return path


def rebuild_fts(conn: sqlite3.Connection) -> None:
    """Rebuild the FTS5 index."""
    conn.execute("INSERT INTO videos_fts(videos_fts) VALUES('rebuild')")
    conn.commit()
