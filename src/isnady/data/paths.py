"""Where isnady keeps its data on each platform, and how the user moves it.

The data folder holds the database, settings.json and user_sources.json, so
the choice of folder cannot live inside it: it is kept in a small pointer file
in the platform's configuration folder (location.json). Order of precedence:
  1. the ISNADY_DATA_DIR environment variable (tests, portable use);
  2. the folder chosen by the user (location.json);
  3. the platform default.
"""

import json
import os
import shutil
import sqlite3
import sys
from pathlib import Path

APP_DIR_NAME = "isnady"
DB_FILE_NAME = "isnady.db"
POINTER_FILE = "location.json"


def default_data_dir() -> Path:
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / APP_DIR_NAME
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_DIR_NAME
    xdg = os.environ.get("XDG_DATA_HOME")
    return (Path(xdg) if xdg else Path.home() / ".local" / "share") / APP_DIR_NAME


def config_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Preferences"
    else:
        xdg = os.environ.get("XDG_CONFIG_HOME")
        base = Path(xdg) if xdg else Path.home() / ".config"
    return base / APP_DIR_NAME


def _pointer() -> Path:
    return config_dir() / POINTER_FILE


def chosen_data_dir() -> Path | None:
    try:
        value = json.loads(_pointer().read_text(encoding="utf-8")).get("data_dir")
        return Path(value).expanduser() if value else None
    except (OSError, ValueError, AttributeError):
        return None


def data_dir_source() -> str:
    """Why the data folder is where it is: environment, chosen, or default."""
    if os.environ.get("ISNADY_DATA_DIR"):
        return "environment"
    return "chosen" if chosen_data_dir() else "default"


def data_dir() -> Path:
    override = os.environ.get("ISNADY_DATA_DIR")
    base = Path(override).expanduser() if override else (chosen_data_dir() or default_data_dir())
    base.mkdir(parents=True, exist_ok=True)
    return base


def db_path() -> Path:
    return data_dir() / DB_FILE_NAME


class RelocateError(Exception):
    """The data folder could not be changed; the message is meant for the user."""


def relocate(new: Path | str | None, mode: str = "copy") -> Path:
    """Use another data folder from the next start.

    mode "copy":  copy the current database, settings and user sources there (the old folder is kept);
    mode "as-is": use the folder as it is (an empty folder, or one that already holds isnady data);
    new None:     go back to the platform default.
    """
    if os.environ.get("ISNADY_DATA_DIR"):
        raise RelocateError("The data folder is set by the ISNADY_DATA_DIR environment variable; unset it first.")
    current = data_dir()
    target = Path(new).expanduser().resolve() if new else default_data_dir()
    if target == current.resolve():
        raise RelocateError(f"isnady already uses {target}.")
    target.mkdir(parents=True, exist_ok=True)
    if not os.access(target, os.W_OK):
        raise RelocateError(f"{target} cannot be written to.")
    if mode == "copy":
        if (target / DB_FILE_NAME).exists():
            raise RelocateError(f"{target} already holds an isnady database. Choose 'use as it is', or another folder.")
        source_db = current / DB_FILE_NAME
        if source_db.exists():
            conn = sqlite3.connect(source_db)          # fold the write-ahead log into the file before copying
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            conn.close()
        for item in current.iterdir():
            if item.name.endswith(("-wal", "-shm")) or item.name.startswith("."):
                continue
            destination = target / item.name
            if item.is_dir():
                shutil.copytree(item, destination, dirs_exist_ok=True)
            else:
                shutil.copy2(item, destination)
    elif mode != "as-is":
        raise RelocateError("mode must be copy or as-is")
    pointer = _pointer()
    pointer.parent.mkdir(parents=True, exist_ok=True)
    if new:
        pointer.write_text(json.dumps({"data_dir": str(target)}, ensure_ascii=False, indent=2), encoding="utf-8")
    elif pointer.exists():
        pointer.unlink()
    return target
