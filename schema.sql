CREATE TABLE IF NOT EXISTS videos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    type TEXT CHECK(type IN ('movie','tv_series','episode')) DEFAULT 'movie',
    year INTEGER,
    description TEXT,
    genre TEXT,
    rating TEXT,
    runtime_minutes INTEGER,
    director TEXT,
    cast TEXT,
    quality TEXT,
    thumbnail_url TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS video_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id INTEGER REFERENCES videos(id) ON DELETE CASCADE,
    source TEXT NOT NULL CHECK(source IN ('vudu','movies_anywhere')),
    source_id TEXT NOT NULL,
    purchased_date TEXT,
    purchase_price REAL,
    quality TEXT,
    raw_json TEXT,
    first_seen_date TEXT DEFAULT (date('now')),
    last_seen_date TEXT DEFAULT (date('now')),
    is_active INTEGER DEFAULT 1,
    removed_date TEXT,
    last_synced TEXT DEFAULT (datetime('now')),
    UNIQUE(source, source_id)
);

CREATE INDEX IF NOT EXISTS idx_video_sources_active ON video_sources(source, is_active);

CREATE VIRTUAL TABLE IF NOT EXISTS videos_fts USING fts5(
    title, description, genre, director, cast,
    content=videos, content_rowid=id
);

CREATE TRIGGER IF NOT EXISTS videos_ai AFTER INSERT ON videos BEGIN
    INSERT INTO videos_fts(rowid, title, description, genre, director, cast)
    VALUES (new.id, new.title, new.description, new.genre, new.director, new.cast);
END;

CREATE TRIGGER IF NOT EXISTS videos_ad AFTER DELETE ON videos BEGIN
    INSERT INTO videos_fts(videos_fts, rowid, title, description, genre, director, cast)
    VALUES ('delete', old.id, old.title, old.description, old.genre, old.director, old.cast);
END;

CREATE TRIGGER IF NOT EXISTS videos_au AFTER UPDATE ON videos BEGIN
    INSERT INTO videos_fts(videos_fts, rowid, title, description, genre, director, cast)
    VALUES ('delete', old.id, old.title, old.description, old.genre, old.director, old.cast);
    INSERT INTO videos_fts(rowid, title, description, genre, director, cast)
    VALUES (new.id, new.title, new.description, new.genre, new.director, new.cast);
END;
