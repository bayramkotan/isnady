"""User settings — Qt-free, shared by the window and the command line.

Stored as JSON in the isnady data folder (settings.json; another profile's in profiles/<id>/, core.profiles). Every key has a
default; a stored value of "" or a missing key means "use the default".

Keys
  view.theme                       system | light | dark
  view.text_scale                  0.8 - 1.6, reading text size multiplier (Ctrl+ / Ctrl-)
  view.sidebar                     the order of the sidebar sections, comma-separated ("" = isnady's order)
  log.level                        info | debug: how much logs/isnady.log says (core.log)
  view.language_order              the order of the texts' languages after Arabic, comma-separated ("" = A to Z)
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
import time
from pathlib import Path

from isnady.core.i18n import N_
from isnady.data.paths import data_dir

SETTINGS_FILE = "settings.json"

# script -> (label, sample text, default family, default size, default line height %)
SCRIPTS = {
    "arabic": (N_("Arabic script (Arabic, Urdu, Persian)"), "إِنَّمَا الأَعْمَالُ بِالنِّيَّاتِ", "Amiri", 20.0, 125),
    "latin": (N_("Latin script (Turkish, English, French, Indonesian)"), "Ameller niyetlere göredir", "Amiri", 12.5, 115),
    "cyrillic": (N_("Cyrillic script (Russian)"), "Поистине, дела оцениваются по намерениям", "", 12.5, 120),
    "bengali": (N_("Bengali script"), "কর্মসমূহ নিয়তের উপর নির্ভরশীল", "", 13.0, 130),
    "tamil": (N_("Tamil script"), "செயல்கள் எண்ணங்களைப் பொறுத்தே", "", 13.0, 130),
}
SCRIPT_OF_LANGUAGE = {
    "arabic": "arabic", "urdu": "arabic", "persian": "arabic", "farsi": "arabic",
    "russian": "cyrillic", "bengali": "bengali", "tamil": "tamil",
}

# theme colour tokens a user may override, with a label for the Preferences window
COLOR_TOKENS = {
    "window": N_("Window background"),
    "surface": N_("Cards and fields"),
    "border": N_("Borders"),
    "ink": N_("Main text"),
    "muted": N_("Secondary text"),
    "lapis": N_("Accent (buttons, links, numbers)"),
    "gold": N_("Gold accent (terms, lines)"),
    "gilt": N_("Matched words"),
    "sidebar": N_("Sidebar"),
    "sidebar_ink": N_("Sidebar text"),
}

_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")

# the sidebar's sections in isnady's own order (Bayram, 2026-10-11: Books second, Learn last); the user may reorder
# them (Preferences → Sidebar, or iy config set view.sidebar books,search,…)
SIDEBAR = ("search", "books", "narrators", "chains", "scholars", "companions", "genealogy", "statistics", "bookmarks",
           "learn")


def sidebar_order() -> list[str]:
    """The sections in the order chosen: the saved ones first, any section not named after them in isnady's order."""
    saved = [k for k in str(get("view.sidebar") or "").split(",") if k in SIDEBAR]
    seen = []
    for k in saved:
        if k not in seen:
            seen.append(k)
    return seen + [k for k in SIDEBAR if k not in seen]


def defaults() -> dict:
    d = {"view.theme": "system", "view.text_scale": 1.0, "ui.family": "", "ui.size": 0.0,
         "view.ui_language": "en",            # the interface language (I1) and how names and terms are read (L1)
         "view.content_languages": "",        # the hadith texts shown, by language, comma-separated; empty: all
         "view.language_order": "",           # the languages after Arabic, in the order chosen; empty: A to Z
         "sources.repository": "",            # the data repository chosen (core.repositories); empty: isnady's own
         "books.disabled": "",                # collections switched off (core.books), comma-separated keys
         "view.other_languages": "fold",      # texts in languages not chosen: "fold" behind an arrow, or "omit"
         "view.sidebar": "",                  # the order of the sidebar (SIDEBAR); empty: isnady's
         "log.level": "info"}                 # how much the log says (core.log): info, or debug for more
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
    """settings.json of the profile in use (core.profiles, PRF1): the data folder itself for the first profile."""
    from isnady.core import profiles

    return profiles.folder() / SETTINGS_FILE


def forget() -> None:
    """Read the settings and the remembered state from disk again (another profile was chosen)."""
    _recent.clear()
    _read_cache.clear()
    _state_recent.clear()


_read_cache: dict = {}
# the settings as last read and when: a page asks for settings hundreds of times while it draws; on Windows every
# look at the file costs (antivirus), so for a second the last reading is used (writes here update it at once)
_recent: list = []


def _read() -> dict:
    """The settings file, read again only when it changed (its size, time or file): drawing a page asks for
    a setting over a thousand times (UI5-P). A copy is returned, so a caller may change it."""
    now = time.monotonic()
    if _recent and now - _recent[0] < 1.0:           # looked at less than a second ago: no disk access at all
        return dict(_recent[1])
    path = settings_path()
    try:
        st = path.stat()
        stamp = (st.st_mtime_ns, st.st_size, st.st_ino)
        hit = _read_cache.get(path)
        if hit is not None and hit[0] == stamp:
            _recent[:] = [now, hit[1]]
            return dict(hit[1])
        data = json.loads(path.read_text(encoding="utf-8"))
        data = data if isinstance(data, dict) else {}
        _read_cache[path] = (stamp, data)
        _recent[:] = [now, data]
        return dict(data)
    except (OSError, ValueError):
        _recent[:] = [now, {}]
        return {}


def _write(data: dict) -> None:
    path = settings_path()
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)
    _recent[:] = [time.monotonic(), dict(data)]      # the next read sees this at once


def validate(key: str, value):
    """Return the value converted to its stored type, or raise ConfigError."""
    if key not in DEFAULTS:
        raise ConfigError(f"Unknown setting '{key}'. See: iy config list")
    if value in ("", None):
        return ""
    default = DEFAULTS[key]
    if key == "view.theme":
        allowed = ("system", "sky", "starry", "garden", "light", "dark", "paper", "slate", "emerald", "midnight", "contrast")   # every theme of gui.theme.THEMES (UI-FRESH added sky, starry, garden)
        if value not in allowed:
            raise ConfigError("view.theme must be one of: " + ", ".join(allowed))
        return value
    if key == "view.ui_language":
        from isnady.core.i18n import LANGUAGES

        if value not in LANGUAGES:
            raise ConfigError("view.ui_language must be one of: " + ", ".join(LANGUAGES))
        return value
    if key == "books.disabled":
        return ",".join(sorted({p.strip() for p in str(value).split(",") if p.strip()}))
    if key == "view.other_languages":
        if value not in ("fold", "omit"):
            raise ConfigError("view.other_languages must be fold or omit")
        return value
    if key == "sources.repository":
        return re.sub(r"[^a-z0-9._-]", "", str(value).strip().lower())
    if key == "view.sidebar":
        keys = [k.strip() for k in str(value).split(",") if k.strip()]
        wrong = [k for k in keys if k not in SIDEBAR]
        if wrong:
            raise ConfigError("view.sidebar takes these sections: " + ", ".join(SIDEBAR))
        order = list(dict.fromkeys(keys)) + [k for k in SIDEBAR if k not in keys]
        return "" if order == list(SIDEBAR) else ",".join(order)
    if key == "view.content_languages":
        return ",".join(part.strip() for part in str(value).split(",") if part.strip())
    if key == "log.level":
        value = str(value).strip().lower()
        if value not in ("info", "debug"):
            raise ConfigError("log.level is info or debug")
        return value
    if key == "view.language_order":           # Arabic always comes first: it is not in the list
        parts = [part.strip() for part in str(value).split(",") if part.strip() and part.strip() != "Arabic"]
        return ",".join(dict.fromkeys(parts))
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


# ------------------------------------------------------------------ state (not settings)
# Where the reader was, which languages it showed: remembered between runs, never validated, never listed by
# `iy config` — so settings.json stays a clean list of the user's choices.
STATE_FILE = "state.json"


def _state_path() -> Path:
    return settings_path().with_name(STATE_FILE)


_state_recent: list = []     # (when, contents): state.json read at most once a second (see _recent)


def state_get(key: str, default=None):
    now = time.monotonic()
    if not (_state_recent and now - _state_recent[0] < 1.0):
        try:
            data = json.loads(_state_path().read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
        _state_recent[:] = [now, data if isinstance(data, dict) else {}]
    return _state_recent[1].get(key, default)


def state_forget(prefix: str) -> None:
    """Forget every remembered value whose key begins with prefix (each book's own languages, when the content
    languages are chosen anew for all)."""
    path = _state_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    kept = {k: v for k, v in data.items() if not k.startswith(prefix)}
    _state_recent.clear()
    if kept != data:
        try:
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(kept, ensure_ascii=False, indent=1), encoding="utf-8")
            tmp.replace(path)
        except OSError:
            pass


def state_set(key: str, value) -> None:
    path = _state_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    data[key] = value
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(path)
    except OSError:
        pass                      # remembering a position must never stop reading
    _state_recent[:] = [time.monotonic(), data]
