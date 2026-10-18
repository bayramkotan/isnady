"""Help → Check for Updates (UPD4, 2026-10-18): isnady from PyPI and from npm, whichever are installed.

Bayram (2026-10-11): "Help altında güncellemeleri sorgulasın → hem npmjs hem pypi!!! Hangisi yüklü ise sorsun. İkisi
yüklü ise ikisini yüklemek için sorsun!!!!" The Python package is the program (updated by isnady.doctor, every copy
where it is installed: system, user, venv, pipx, clone); the npm package is the JavaScript library of the same version
(`npm install -g isnady`). What is new comes from the CHANGELOG on GitHub, the sections after the installed version.
Nothing is updated without the user's yes; `iy update --check` only looks.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import urllib.request

from isnady import __version__

PACKAGE = "isnady"
NPM_LATEST = f"https://registry.npmjs.org/{PACKAGE}/latest"
CHANGELOG = "https://raw.githubusercontent.com/bayramkotan/isnady/main/CHANGELOG.md"


def vkey(v: str | None) -> tuple:
    return tuple(int(x) for x in re.findall(r"\d+", v or "")[:4])


def _npm() -> str | None:
    return shutil.which("npm") or shutil.which("npm.cmd")


def _run(argv: list[str], timeout: float = 25) -> str:
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    try:
        r = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=timeout, stdin=subprocess.DEVNULL, creationflags=flags)
        return r.stdout
    except (OSError, subprocess.SubprocessError):
        return ""


def npm_installed() -> str | None:
    """The version of isnady installed globally with npm, or None (npm missing, or isnady not installed by it)."""
    npm = _npm()
    if not npm:
        return None
    out = _run([npm, "ls", "-g", PACKAGE, "--json", "--depth=0"])
    try:
        return json.loads(out or "{}").get("dependencies", {}).get(PACKAGE, {}).get("version")
    except ValueError:
        return None


def latest_npm(timeout: float = 5.0) -> str | None:
    try:
        with urllib.request.urlopen(NPM_LATEST, timeout=timeout) as r:
            return json.load(r).get("version")
    except Exception:          # offline, blocked: said as "could not be reached"
        return None


def whats_new(since: str, timeout: float = 5.0, limit: int = 6) -> list[tuple[str, str]]:
    """[(version, the CHANGELOG's text)] of the versions after `since`, newest first; [] when not reachable."""
    try:
        with urllib.request.urlopen(CHANGELOG, timeout=timeout) as r:
            text = r.read().decode("utf-8", "replace")
    except Exception:
        return []
    out = []
    for m in re.finditer(r"^## \[(\d+\.\d+\.\d+)\][^\n]*\n(.*?)(?=^## \[|\Z)", text, re.M | re.S):
        if vkey(m.group(1)) > vkey(since):
            body = re.sub(r"\n[ \t]+", " ", m.group(2).strip())      # a wrapped line joins its item
            body = body.replace("**", "").replace("`", "")
            out.append((m.group(1), body))
    return out[:limit]


def check() -> dict:
    """{"pypi": {"installed", "latest", "behind"}, "npm": {...}, "news": [(version, text)]} — a channel whose
    "installed" is None is not installed here (npm), and a "latest" of None could not be reached."""
    from isnady import doctor

    pypi_latest = doctor.latest_on_pypi()
    npm_have = npm_installed()
    npm_latest = latest_npm() if npm_have else None
    news = whats_new(__version__) if pypi_latest and vkey(pypi_latest) > vkey(__version__) else []
    return {
        "pypi": {"installed": __version__, "latest": pypi_latest,
                 "behind": bool(pypi_latest and vkey(pypi_latest) > vkey(__version__))},
        "npm": {"installed": npm_have, "latest": npm_latest,
                "behind": bool(npm_have and npm_latest and vkey(npm_latest) > vkey(npm_have))},
        "news": news,
    }


def npm_update_argv() -> list[str]:
    """`npm install -g isnady@latest`, as administrator where npm's global folder is not the user's own."""
    from isnady import doctor

    npm = _npm() or "npm"
    argv = [npm, "install", "-g", f"{PACKAGE}@latest"]
    if os.name == "nt":
        return argv                            # npm's global folder on Windows is the user's (%APPDATA%\npm)
    prefix = _run([npm, "prefix", "-g"]).strip()
    if prefix and not os.access(os.path.join(prefix, "lib"), os.W_OK):
        return doctor._as_admin(argv)
    return argv


def plan(pypi: bool = True, npm: bool = True) -> list[list[str]]:
    """The commands that bring the chosen channels up to date (the PyPI one: every copy, doctor's plan)."""
    from isnady import doctor

    out: list = []
    if pypi:
        out += doctor.diagnose(check_pypi=True).fixes
    if npm and npm_installed():
        out.append(npm_update_argv())
    return out
