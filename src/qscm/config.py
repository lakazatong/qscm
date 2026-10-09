import os
from pathlib import Path


def _get_user_cache_dir() -> Path:
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA")
        if base:
            return Path(base)

        return Path.home() / "AppData" / "Local"

    base = os.environ.get("XDG_CACHE_HOME")
    if base:
        return Path(base)

    return Path.home() / ".cache"


PACKAGE_ROOT = Path(".").parent
SRC_DIR = PACKAGE_ROOT.parent
REPO_ROOT = SRC_DIR.parent

USER_CACHE_DIR = _get_user_cache_dir()
CACHE_DIR = USER_CACHE_DIR / "qscm"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
