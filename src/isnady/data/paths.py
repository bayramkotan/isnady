"""Where isnady keeps its data on each platform.

Override with the ISNADY_DATA_DIR environment variable.
"""

import os
import sys
from pathlib import Path

APP_DIR_NAME = "isnady"
DB_FILE_NAME = "isnady.db"


def data_dir() -> Path:
    override = os.environ.get("ISNADY_DATA_DIR")
    if override:
        base = Path(override).expanduser()
    elif sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / APP_DIR_NAME
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support" / APP_DIR_NAME
    else:
        xdg = os.environ.get("XDG_DATA_HOME")
        base = (Path(xdg) if xdg else Path.home() / ".local" / "share") / APP_DIR_NAME
    base.mkdir(parents=True, exist_ok=True)
    return base


def db_path() -> Path:
    return data_dir() / DB_FILE_NAME
