"""Configuration resolution (env vars, .env file).

Default layout is project-local: everything StreamingCatalog needs (DB,
collected ID files, Chrome profile, port config) lives in subdirectories
of the current working directory. The expected workflow is:

  cd /path/to/streaming-catalog
  streaming-catalog setup     # creates ./chrome-profile/, ./data/, .env
  streaming-catalog update
  streaming-catalog search

Power users who want a different layout can override every path via env
vars (see resolve_* functions below).
"""
import os
from pathlib import Path

from dotenv import load_dotenv


def project_root() -> Path:
    """The directory the user is currently working in. All project-local
    paths (data/, chrome-profile/, .env) are anchored here."""
    return Path.cwd()


def user_config_file() -> Path:
    """Per-project .env file written by `streaming-catalog setup`."""
    return project_root() / ".env"


def user_config_dir() -> Path:
    """Per-project config directory (same as project_root, but kept as a
    separate name so callers stay explicit about intent)."""
    return project_root()


# Load .env from CWD so project-local config takes effect.
load_dotenv(user_config_file(), override=False)


def resolve_chrome_profile() -> Path:
    """
    Resolve the Chrome user-data directory for Selenium.

    Project-local default: ./chrome-profile/ next to where you ran the
    command. Uses a DEDICATED profile (not your main Chrome) to avoid
    Chrome 148+ restrictions that block Selenium from attaching to a
    profile that's also in use by your everyday browser.
    """
    if env := os.environ.get("STREAMING_CATALOG_CHROME_PROFILE"):
        return Path(env)
    return project_root() / "chrome-profile"


def resolve_db_path() -> Path:
    """
    Resolve the SQLite database path.

    Resolution order:
      1. STREAMING_CATALOG_DB env var (explicit override)
      2. ./data/catalog.db relative to the current working directory
    """
    if env := os.environ.get("STREAMING_CATALOG_DB"):
        return Path(env)
    return project_root() / "data" / "catalog.db"


def resolve_data_dir() -> Path:
    """Resolve the data directory (holds DB + ID files)."""
    return resolve_db_path().parent


def resolve_port() -> int:
    """Resolve the search UI port."""
    return int(os.environ.get("STREAMING_CATALOG_PORT", "5858"))


def schema_path() -> Path:
    """Path to the bundled schema.sql file (lives inside the package so it ships in wheels)."""
    return Path(__file__).parent / "schema.sql"
