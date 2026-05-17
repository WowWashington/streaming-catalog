"""Platform detection and configuration resolution."""
import os
import platform
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


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


def resolve_profile_name() -> str:
    """Chrome profile directory name (e.g. 'Default', 'Profile 1')."""
    return os.environ.get("STREAMING_CATALOG_CHROME_PROFILE_NAME", "Default")


def resolve_db_path() -> Path:
    """Resolve the SQLite database path."""
    if env := os.environ.get("STREAMING_CATALOG_DB"):
        return Path(env)
    return Path.cwd() / "data" / "catalog.db"


def resolve_data_dir() -> Path:
    """Resolve the data directory (holds DB + ID files)."""
    return resolve_db_path().parent


def resolve_port() -> int:
    """Resolve the search UI port."""
    return int(os.environ.get("STREAMING_CATALOG_PORT", "18797"))


def schema_path() -> Path:
    """Path to the bundled schema.sql file."""
    return Path(__file__).parent.parent.parent / "schema.sql"
