"""Configuration resolution (env vars, .env file, per-user defaults)."""
import os
from pathlib import Path

from dotenv import load_dotenv


def user_config_dir() -> Path:
    """The directory where StreamingCatalog stores its per-user config."""
    return Path.home() / ".streaming-catalog"


def user_config_file() -> Path:
    """Per-user .env file written by 'streaming-catalog setup'."""
    return user_config_dir() / "config.env"


# Load .env from CWD first (project-level override), then user config (per-user defaults)
load_dotenv()
if user_config_file().exists():
    load_dotenv(user_config_file(), override=False)


def resolve_chrome_profile() -> Path:
    """
    Resolve the Chrome user-data directory for Selenium.

    Uses a DEDICATED profile directory for StreamingCatalog (not the user's
    main Chrome profile). This avoids Chrome 148+ security restrictions that
    block Selenium from attaching to the real profile.

    The user logs in once via 'streaming-catalog login', and sessions persist.
    """
    if env := os.environ.get("STREAMING_CATALOG_CHROME_PROFILE"):
        return Path(env)

    return Path.home() / ".streaming-catalog" / "chrome-profile"


def resolve_db_path() -> Path:
    """
    Resolve the SQLite database path.

    Resolution order:
      1. STREAMING_CATALOG_DB env var (explicit override)
      2. ~/.streaming-catalog/data/catalog.db if it exists (current default)
      3. ./data/catalog.db if it exists (legacy cwd-relative default — kept
         working so existing installs aren't broken by the move)
      4. ~/.streaming-catalog/data/catalog.db (new path, will be created)
    """
    if env := os.environ.get("STREAMING_CATALOG_DB"):
        return Path(env)

    home_default = user_config_dir() / "data" / "catalog.db"
    if home_default.exists():
        return home_default

    legacy_local = Path.cwd() / "data" / "catalog.db"
    if legacy_local.exists():
        return legacy_local

    return home_default


def resolve_data_dir() -> Path:
    """Resolve the data directory (holds DB + ID files)."""
    return resolve_db_path().parent


def resolve_port() -> int:
    """Resolve the search UI port."""
    return int(os.environ.get("STREAMING_CATALOG_PORT", "5858"))


def schema_path() -> Path:
    """Path to the bundled schema.sql file (lives inside the package so it ships in wheels)."""
    return Path(__file__).parent / "schema.sql"
