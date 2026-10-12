"""The statistics' long computations in a process of their own (PERF2).

Bayram (2026-10-12): the first computation of Statistics on the full database (16 s) made the whole window slow while
it ran. It ran in a thread, but Python runs one thread at a time (the GIL): every click waited for the statistics.
Now a computation that is not already saved runs in a separate Python process (`python -m isnady.core.stats_jobs`);
it writes its results where they are always kept (`<data folder>/derived/*.json`) and the page reads them from
there. Its progress comes line by line. The window stays as fast as without it.

Saved results are read at once, without a process. In the packaged applications (exe, AppImage, macOS app) there
is no Python to start: there the computation runs in the thread, as before.

Qt-free: used by gui/statistics_page.py.
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
from pathlib import Path


class NotSaved(Exception):
    """Raised by a stats module's cached(saved_only=True) when its results are not saved for this data."""


def corpus_and_models(conn, key, progress=None, recompute: bool = False, saved_only: bool = False) -> dict:
    """The analyses of the corpus sections: the descriptive one, the model, the laboratory. Each road on its own
    scale (SH1): road B (the Shia books) on al-Najashi's categories and the four Imami grades of al-Majlisi and
    al-Behbudi — never on Ibn Hajar's ranks or the Sunni grade groups (core.stats_corpus.Road)."""
    from isnady.core import stats_corpus as corpus
    from isnady.core import stats_lab as lab
    from isnady.core import stats_models as models

    return {"corpus": corpus.cached(conn, key, progress, recompute, saved_only=saved_only),
            "models": models.cached(conn, key, progress, recompute, saved_only=saved_only),
            "lab": lab.cached(conn, key, progress, recompute, saved_only=saved_only),
            "road": corpus.tradition_of_scope(conn, key)}


def graders(conn, key, progress=None, recompute: bool = False, saved_only: bool = False) -> dict:
    from isnady.core import stats_graders

    return stats_graders.cached(conn, key, progress, recompute, saved_only=saved_only)


JOBS = {"corpus": corpus_and_models, "graders": graders}
NONE = "-"                       # the key None (every Sunni book) on the command line

_LIVE: set[subprocess.Popen] = set()
_LOCK = threading.Lock()


def can_use_process() -> bool:
    """A separate Python can be started: not in a packaged application (its executable is the app itself)."""
    return not getattr(sys, "frozen", False) and bool(sys.executable)


def _forget_files(value):
    """What was just computed is shown as computed, not as read from the saved file."""
    if isinstance(value, dict):
        if "from_file" in value:
            value["from_file"] = None
        for v in value.values():
            if isinstance(v, dict) and "from_file" in v:
                v["from_file"] = None
    return value


def run(name: str, key, recompute: bool, progress) -> dict:
    """The job's result: saved results at once; otherwise computed in a separate process (in this thread when no
    process can be started). progress(text) is called with each step."""
    from isnady.data import db

    job = JOBS[name]
    conn = db.connect()                      # its own connection: SQLite connections stay in their thread
    try:
        if not recompute:
            try:
                return job(conn, key, progress, False, saved_only=True)
            except NotSaved:
                pass
        if not can_use_process():
            return job(conn, key, progress, recompute)
        _in_process(name, key, recompute, progress)
        try:
            return _forget_files(job(conn, key, progress, False, saved_only=True))
        except NotSaved:
            # the process could not save (a read-only data folder): compute here, as before
            return job(conn, key, progress, recompute)
    finally:
        conn.close()


def _in_process(name: str, key, recompute: bool, progress) -> None:
    import isnady
    from isnady.core.i18n import language
    from isnady.data.paths import data_dir

    env = dict(os.environ)
    # the same isnady as this window (not another copy found first on the path) and the same data folder
    package_root = str(Path(isnady.__file__).resolve().parent.parent)
    env["PYTHONPATH"] = package_root + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    env["ISNADY_DATA_DIR"] = str(data_dir())
    env["PYTHONIOENCODING"] = "utf-8"
    argv = [sys.executable, "-m", "isnady.core.stats_jobs", name, NONE if key is None else str(key),
            "1" if recompute else "0", language()]
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0      # no console window from the window app
    proc = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL,
                            env=env, text=True, encoding="utf-8", errors="replace", creationflags=flags)
    with _LOCK:
        _LIVE.add(proc)
    try:
        err: list[str] = []
        reader = threading.Thread(target=lambda: err.extend(proc.stderr), daemon=True)
        reader.start()
        for line in proc.stdout:
            line = line.rstrip("\n")
            if line and progress:
                progress(line)
        code = proc.wait()
        reader.join(timeout=2)
    finally:
        with _LOCK:
            _LIVE.discard(proc)
    if code != 0:
        tail = "".join(err[-6:]).strip()
        raise RuntimeError(tail.splitlines()[-1] if tail else f"the computation ended with code {code}")


def stop_all() -> None:
    """End every computation still running (isnady is closing)."""
    with _LOCK:
        live = list(_LIVE)
    for proc in live:
        try:
            proc.kill()
            proc.wait(timeout=3)
        except (OSError, subprocess.SubprocessError):
            pass


def _main(argv: list[str]) -> int:
    name, key, recompute, lang = argv[0], argv[1], argv[2] == "1", argv[3] if len(argv) > 3 else "en"
    from isnady.core.i18n import set_language
    from isnady.data import db

    set_language(lang)
    conn = db.connect()
    try:
        JOBS[name](conn, None if key == NONE else key, lambda text: print(text, flush=True), recompute)
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
