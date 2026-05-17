"""Platform detection and configuration resolution."""
import os
import platform
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
    return int(os.environ.get("STREAMING_CATALOG_PORT", "5858"))


def schema_path() -> Path:
    """Path to the bundled schema.sql file (lives inside the package so it ships in wheels)."""
    return Path(__file__).parent / "schema.sql"
