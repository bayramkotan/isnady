"""A new version of isnady starts clean, keeping what is the user's own (CFG1, 2026-10-18).

Bayram (2026-10-13): "Versiyon değişikliğinde tüm config dosyalar silip tekrardan taranarak yapılsın VenvStudio'daki
gibi, ama kullanıcı bookmark ve diğer bilgileri, tema font.... gibi silinmesin."

`version.json` in the data folder names the version that last ran. When another version starts (the window or the
command line), what isnady computed and kept for speed is deleted, so nothing an older version worked out is shown by
a newer one: the kept counts and readings (`cache/`) and files an interrupted write left (`*.tmp`).

The saved statistics (`derived/`) are NOT deleted on a new version (Bayram, 2026-10-25: "neden surekli istatistik
kismini hesapliyor … eger cok buyuk bir degisiklik yoksa neden surekli bunu yapiyor?"). Each carries the fingerprint
of what it was computed from — the hadith, the narrators identified in the chains, the verdicts, the grades, the books
switched off — and the METHOD of the analysis (stats_corpus, stats_models, stats_lab, stats_graders): it is computed
again only when one of these changed, a new version or not. A change to an analysis must therefore change its METHOD.

KEPT, always: the database (its schema is upgraded by isnady.data.db), the
settings (theme, fonts, languages, sidebar), the remembered places and the recent searches (state.json), the
bookmarks, the profiles and every profile's own files, the downloaded classical works (sources/) and the data
repositories (repos/). What was deleted is said once, in the window's footer and on the command line.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from isnady import __version__
from isnady.data.paths import data_dir

FILE = "version.json"
CLEARED = ("cache",)                    # folders of computed files, deleted on a new version (derived/: see above)


def _path() -> Path:
    return data_dir() / FILE


def last_version() -> str | None:
    try:
        return json.loads(_path().read_text(encoding="utf-8")).get("version")
    except (OSError, ValueError, AttributeError):
        return None


def check(version: str = __version__) -> dict | None:
    """Run at start. None when this version ran here before (or the data folder is new); otherwise
    {"previous", "version", "files"} after clearing what was computed."""
    folder = data_dir()
    previous = last_version()
    if previous == version:
        return None
    first_time = previous is None and not (folder / "isnady.db").exists()
    files = 0
    if not first_time:
        for name in CLEARED:
            where = folder / name
            if where.is_dir():
                for f in where.glob("*.json"):
                    try:
                        f.unlink()
                        files += 1
                    except OSError:
                        pass
        for f in list(folder.glob("*.tmp")) + list((folder / "cache").glob("*.tmp")):
            try:
                f.unlink()
            except OSError:
                pass
        try:
            from isnady.core import cache

            cache.forget()
        except Exception:
            pass
    try:
        folder.mkdir(parents=True, exist_ok=True)
        _path().write_text(json.dumps({"version": version, "previous": previous,
                                       "since": time.strftime("%Y-%m-%dT%H:%M:%S"), "cleared_files": files},
                                      ensure_ascii=False, indent=1), encoding="utf-8")
    except OSError:
        return None
    if first_time:
        return None
    return {"previous": previous, "version": version, "files": files}


def message(result: dict, tr=lambda s, **k: s.format(**k)) -> str:
    """The one-time note, in the interface language when tr is given."""
    return tr("isnady {version}: what the earlier version computed ({n} files) was cleared and is computed again; "
              "settings, bookmarks and recent searches are kept.", version=result["version"], n=result["files"])
