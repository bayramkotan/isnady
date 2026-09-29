"""User settings — Qt-free, shared by the window and the command line.

Stored as JSON in the isnady data folder (settings.json). Every key has a
default; a stored value of "" or a missing key means "use the default".

Keys
  view.theme                       system | light | dark
  view.text_scale                  0.8 - 1.6, reading text size multiplier (Ctrl+ / Ctrl-)
  ui.family, ui.size               interface font ("" = system font)
  text.<script>.family             reading font for one script
  text.<script>.size               point size
  text.<script>.color              #RRGGBB, "" = theme ink
  text.<script>.line_height        percent
  colors.<light|dark>.<token>      #RRGGBB overrides of the theme colours

Scripts are chosen by the language of a text (SCRIPT_OF_LANGUAGE); adding a
script is adding an entry to SCRIPTS.
"""

import json
import re
from pathlib import Path

from isnady.data.paths import data_dir

SETTINGS_FILE = "settings.json"

# script -> (label, sample text, default family, default size, default line height %)
SCRIPTS = {
    "arabic": ("Arabic script (Arabic, Urdu, Persian)", "إِنَّمَا الأَعْمَالُ بِالنِّيَّاتِ", "Amiri", 20.0, 125),
    "latin": ("Latin script (Turkish, English, French, Indonesian)", "Ameller niyetlere göredir", "Amiri", 12.5, 115),
    "cyrillic": ("Cyrillic script (Russian)", "Поистине, дела оцениваются по намерениям", "", 12.5, 120),
    "bengali": ("Bengali script", "কর্মসমূহ নিয়তের উপর নির্ভরশীল", "", 13.0, 130),
    "tamil": ("Tamil script", "செயல்கள் எண்ணங்களைப் பொறுத்தே", "", 13.0, 130),
}
SCRIPT_OF_LANGUAGE = {
    "arabic": "arabic", "urdu": "arabic", "persian": "arabic", "farsi": "arabic",
    "russian": "cyrillic", "bengali": "bengali", "tamil": "tamil",
}

# theme colour tokens a user may override, with a label for the Preferences window
COLOR_TOKENS = {
    "window": "Window background",
    "surface": "Cards and fields",
    "border": "Borders",
    "ink": "Main text",
    "muted": "Secondary text",
    "lapis": "Accent (buttons, links, numbers)",
    "gold": "Gold accent (terms, lines)",
    "gilt": "Matched words",
    "sidebar": "Sidebar",
    "sidebar_ink": "Sidebar text",
}

_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


def defaults() -> dict:
    d = {"view.theme": "system", "view.text_scale": 1.0, "ui.family": "", "ui.size": 0.0}
    for script, (_label, _sample, family, size, line) in SCRIPTS.items():
        d[f"text.{script}.family"] = family
        d[f"text.{script}.size"] = size
        d[f"text.{script}.color"] = ""
        d[f"text.{script}.line_height"] = line
    for mode in ("light", "dark"):
        for token in COLOR_TOKENS:
            d[f"colors.{mode}.{token}"] = ""
    return d


DEFAULTS = defaults()


class ConfigError(ValueError):
    """A value that cannot be stored; the message is meant for the user."""


def settings_path() -> Path:
    return data_dir() / SETTINGS_FILE


def _read() -> dict:
    try:
        data = json.loads(settings_path().read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _write(data: dict) -> None:
    path = settings_path()
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def validate(key: str, value):
    """Return the value converted to its stored type, or raise ConfigError."""
    if key not in DEFAULTS:
        raise ConfigError(f"Unknown setting '{key}'. See: iy config list")
    if value in ("", None):
        return ""
    default = DEFAULTS[key]
    if key == "view.theme":
        if value not in ("system", "light", "dark"):
            raise ConfigError("view.theme must be system, light or dark")
        return value
    if key.endswith(".color") or key.startswith("colors."):
        if not _HEX.match(str(value)):
            raise ConfigError(f"{key} must be a colour like #1D4777 (or empty for the default)")
        return str(value).upper()
    if key.endswith(".family"):
        return str(value).strip()
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ConfigError(f"{key} must be a number") from None
    ranges = {"view.text_scale": (0.8, 1.6), "ui.size": (6, 24)}
    if key.endswith(".size"):
        low, high = ranges.get(key, (6, 48))
    elif key.endswith(".line_height"):
        low, high = (80, 250)
    else:
        low, high = ranges.get(key, (float("-inf"), float("inf")))
    if not low <= number <= high:
        raise ConfigError(f"{key} must be between {low:g} and {high:g}")
    return int(number) if isinstance(default, int) and not isinstance(default, bool) else number


def get(key: str):
    stored = _read().get(key, "")
    return DEFAULTS[key] if stored in ("", None) else stored


def set(key: str, value) -> None:  # noqa: A001 (mirrors the command name)
    data = _read()
    value = validate(key, value)
    if value == "" or value == DEFAULTS[key]:
        data.pop(key, None)
    else:
        data[key] = value
    _write(data)


def reset(prefix: str = "") -> int:
    """Forget stored values under prefix ("" = everything). Returns how many were removed."""
    data = _read()
    keys = [k for k in data if k == prefix or k.startswith(prefix.rstrip(".") + ".")] if prefix else list(data)
    for k in keys:
        data.pop(k, None)
    _write(data)
    return len(keys)


def all_values() -> list[tuple[str, object, object]]:
    """(key, effective value, default) for every setting."""
    stored = _read()
    return [(k, stored.get(k, d) if stored.get(k, "") != "" else d, d) for k, d in DEFAULTS.items()]


def script_for_language(language: str | None, direction: str | None = None) -> str:
    script = SCRIPT_OF_LANGUAGE.get((language or "").strip().lower())
    if script:
        return script
    return "arabic" if direction == "rtl" else "latin"
