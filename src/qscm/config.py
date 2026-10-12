import os
from pathlib import Path


def _user_cache_root() -> Path:
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA")
        return Path(base) if base else Path.home() / "AppData" / "Local"

    base = os.environ.get("XDG_CACHE_HOME")
    return Path(base) if base else Path.home() / ".cache"


APP_TITLE = "QSCM Graph Browser"
DASH_HOST = "127.0.0.1"
DASH_PORT = 8050
CACHE_DIR = _user_cache_root() / "qscm"
ASSETS_DIR = Path(__file__) / "assets"


def ensure_cache_dir(cache_dir=CACHE_DIR) -> Path:
    """Create the cache directory on demand (not as an import side effect)."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir
