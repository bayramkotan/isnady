"""Find every isnady installation on this machine and keep every one of them up to date, IN PLACE.

Rule (Bayram, 2026-09-30): isnady may be installed anywhere — for all users (as administrator), for one
user, in any virtual environment, with pipx, or editable from a clone. Nothing is ever removed or moved;
updating updates each copy where it is (with sudo or the Windows administrator prompt when needed).
Once every copy is the same version it no longer matters which one starts first.


Why: a copy installed earlier in the user folder (~/.local) is found BEFORE a newer
one in the system folder, both by Python and by the shell (~/.local/bin comes first
in PATH). The newer version then never starts, silently (seen on CachyOS, 2026-09-30:
0.0.1 in ~/.local shadowed 0.0.6 in /usr). Qt-free; used by `iy doctor` and by
Help → Check Installation.
"""

import json
import os
import re
import shutil
import site
import subprocess
import sys
import sysconfig
from dataclasses import dataclass, field
from importlib import metadata
from pathlib import Path

PACKAGE = "isnady"
COMMANDS = ("isnady", "iy", "isnady-gui", "isnady-cli")


@dataclass
class Install:
    version: str
    location: Path                 # the site-packages folder
    kind: str                      # user | system | venv | pipx | editable
    installer: str                 # pip | pipx | uv | ...
    editable_path: Path | None = None
    active: bool = False           # what `import isnady` gives in this interpreter


@dataclass
class Command:
    path: Path
    interpreter: str | None
    version: str | None            # what this command would run
    first: bool = False            # the one the shell starts


@dataclass
class Report:
    python: str
    running_version: str
    running_file: str
    installs: list[Install] = field(default_factory=list)
    commands: list[Command] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    fixes: list[list[str]] = field(default_factory=list)      # argv lists; sudo ones start with "sudo"
    latest: str | None = None


def _vkey(v: str) -> tuple:
    return tuple(int(x) for x in re.findall(r"\d+", v)[:4]) or (0,)


def _externally_managed() -> bool:
    try:
        return (Path(sysconfig.get_path("stdlib")) / "EXTERNALLY-MANAGED").exists()
    except (KeyError, TypeError):
        return False


def _site_dirs() -> list[Path]:
    dirs = []
    for d in list(sys.path) + list(getattr(site, "getsitepackages", lambda: [])()) + [site.getusersitepackages()]:
        p = Path(d) if d else None
        if p and p.is_dir() and p not in dirs:
            dirs.append(p)
    return dirs


def path_from_file_url(url: str) -> Path:
    """file:///home/x/isnady -> /home/x/isnady ; file:///C:/Github/isnady -> C:/Github/isnady (not /C:/...)."""
    from urllib.parse import unquote, urlparse

    path = unquote(urlparse(url).path)
    if re.match(r"^/[A-Za-z]:[/\\]", path):
        path = path[1:]
    return Path(path)


def find_installs() -> list[Install]:
    user_site = Path(site.getusersitepackages())
    found, seen = [], set()
    for d in _site_dirs():
        for dist in metadata.distributions(path=[str(d)]):
            if (dist.metadata["Name"] or "").lower() != PACKAGE:
                continue
            key = (str(d), dist.version)
            if key in seen:
                continue
            seen.add(key)
            installer = (dist.read_text("INSTALLER") or "pip").strip()
            editable = None
            direct = dist.read_text("direct_url.json")
            if direct:
                try:
                    info = json.loads(direct)
                    if info.get("dir_info", {}).get("editable"):
                        editable = path_from_file_url(info["url"])
                except (ValueError, KeyError):
                    pass
            if editable:
                kind = "editable"
            elif "pipx" in str(d) or installer == "pipx":
                kind = "pipx"
            elif d == user_site or str(d).startswith(str(user_site)):
                kind = "user"
            elif sys.prefix != sys.base_prefix and str(d).startswith(sys.prefix):
                kind = "venv"
            else:
                kind = "system"
            found.append(Install(dist.version, d, kind, installer, editable))
    try:
        import isnady

        running = Path(isnady.__file__).resolve()
        for inst in found:
            base = (inst.editable_path / "src") if inst.editable_path else inst.location
            if str(running).startswith(str(base.resolve())):
                inst.active = True
    except ImportError:
        pass
    return found


def _interpreter_of(path: Path) -> str | None:
    """The Python a command starts. Scripts begin with "#!python"; pip's Windows .exe launchers carry the
    same line near their END, often quoted ("#!"C:\\Program Files\\Python314\\python.exe"")."""
    try:
        data = path.read_bytes() if path.suffix.lower() == ".exe" else path.read_bytes()[:512]
    except OSError:
        return None
    found = None
    for m in re.finditer(rb'#!\s*"?([^"\r\n]*?python[\w.]*?)"?[ \t]*\r?\n', data):
        found = m.group(1)          # the last one is the launcher's own
    return found.decode(errors="replace").strip() if found else None


def find_commands() -> list[Command]:
    out, seen = [], set()
    names = [c + ext for c in COMMANDS for ext in ((".exe", "") if os.name == "nt" else ("",))]
    for folder in os.environ.get("PATH", "").split(os.pathsep):
        for name in names:
            p = Path(folder) / name
            try:
                real = p.resolve()
            except OSError:
                continue
            if p.is_file() and real not in seen:
                seen.add(real)
                interp = _interpreter_of(p)
                version = None
                exe = interp if interp and Path(interp).exists() else (interp.split()[0] if interp else None)
                if exe and Path(exe).exists():
                    try:
                        r = subprocess.run([exe, "-c", "import isnady; print(isnady.__version__)"],
                                           capture_output=True, text=True, timeout=15)
                        version = r.stdout.strip() or None
                    except (OSError, subprocess.SubprocessError):
                        pass
                out.append(Command(p, interp, version))
    firsts = {}
    for c in out:
        base = c.path.stem if os.name == "nt" else c.path.name
        if base not in firsts:
            firsts[base] = c
            c.first = True
    return out


def latest_on_pypi(timeout: float = 5.0) -> str | None:
    import urllib.request

    try:
        with urllib.request.urlopen(f"https://pypi.org/pypi/{PACKAGE}/json", timeout=timeout) as r:
            return json.load(r)["info"]["version"]
    except Exception:  # offline, blocked, …: the rest of the report still stands
        return None


def user_scripts_dir() -> Path:
    """Where a user install puts its commands: ~/.local/bin, or %APPDATA%\\Python\\Python3XX\\Scripts."""
    try:
        return Path(sysconfig.get_path("scripts", f"{os.name}_user"))
    except KeyError:
        return Path(site.getuserbase()) / ("Scripts" if os.name == "nt" else "bin")


def _writable(folder: Path) -> bool:
    """os.access ignores Windows permissions (Program Files reports writable); really try."""
    import tempfile

    try:
        with tempfile.TemporaryFile(dir=folder):
            return True
    except OSError:
        return False


def needs_admin(inst: Install) -> bool:
    return inst.kind == "system" and not _writable(inst.location)


def _as_admin(argv: list[str]) -> list[str]:
    if os.name == "nt":
        # Windows has no sudo: PowerShell opens the administrator prompt and waits for the result
        args = ", ".join(f"'{a}'" for a in argv[1:])
        return ["powershell", "-NoProfile", "-Command",
                f"Start-Process -FilePath '{argv[0]}' -ArgumentList {args} -Verb RunAs -Wait"]
    return ["sudo"] + argv


def upgrade_argv(inst: Install) -> list[str]:
    """Update this copy where it is installed."""
    extra = ["--break-system-packages"] if _externally_managed() else []
    if inst.kind == "editable" and inst.editable_path:
        return ["git", "-C", str(inst.editable_path), "pull", "--ff-only"]
    if inst.kind == "pipx":
        return ["pipx", "upgrade", PACKAGE]
    if inst.kind == "user":
        return [sys.executable, "-m", "pip", "install", "--user", "-U", PACKAGE] + extra
    if inst.kind == "venv":
        return [sys.executable, "-m", "pip", "install", "-U", PACKAGE]
    # system: "-s" so pip looks at the system copy, not the user folder in front of it
    argv = [sys.executable, "-s", "-m", "pip", "install", "-U", PACKAGE] + extra
    return _as_admin(argv) if needs_admin(inst) else argv


def diagnose(check_pypi: bool = True) -> Report:
    try:
        import isnady

        running_version, running_file = isnady.__version__, isnady.__file__
    except ImportError:
        running_version, running_file = "", ""
    rep = Report(python=sys.executable, running_version=running_version, running_file=running_file,
                 installs=find_installs(), commands=find_commands())
    rep.latest = latest_on_pypi() if check_pypi else None

    installs = rep.installs
    released = [i for i in installs if i.kind != "editable"]
    newest = max([i.version for i in installs] + ([rep.latest] if rep.latest else []), key=_vkey, default=None)
    versions = sorted({i.version for i in installs}, key=_vkey)
    if len(versions) > 1:
        rep.problems.append("isnady is installed in more than one place with different versions ("
                            + ", ".join(f"{i.version} {i.kind}" for i in installs) + "); updating brings every copy "
                            "to the same version, where it is.")
    for c in rep.commands:
        if c.first and c.version and newest and _vkey(c.version) < _vkey(newest):
            rep.problems.append(f"The command '{c.path.name}' starts isnady {c.version} ({c.path}).")
    for inst in installs:
        if inst.kind == "editable" and inst.editable_path and not Path(inst.editable_path).exists():
            rep.problems.append(f"The editable installation points to {inst.editable_path}, which no longer exists.")
    if rep.latest and any(_vkey(i.version) < _vkey(rep.latest) for i in released):
        rep.problems.append(f"isnady {rep.latest} is on PyPI.")
    # the plan: every copy that is behind is updated in place (editable clones: git pull)
    for inst in installs:
        behind = newest and _vkey(inst.version) < _vkey(newest)
        if behind or (inst.kind == "editable" and rep.latest):
            rep.fixes.append(upgrade_argv(inst))
    # commands from ANOTHER Python (another virtual environment) that start an older copy
    for c in rep.commands:
        exe = c.interpreter
        if c.version and newest and _vkey(c.version) < _vkey(newest) and exe and Path(exe).exists() \
                and Path(exe).resolve() != Path(sys.executable).resolve():
            argv = [exe, "-m", "pip", "install", "-U", PACKAGE]
            if argv not in rep.fixes:
                rep.fixes.append(argv)
    user_bin = user_scripts_dir()
    if any(i.kind in ("user", "editable") for i in installs) and str(user_bin) not in os.environ.get("PATH", "") \
            and not rep.commands:
        rep.problems.append(f"{user_bin} is not in PATH, so the isnady commands may not be found.")
    return rep


def install_argv(kind: str = "user") -> list[str]:
    extra = ["--break-system-packages"] if _externally_managed() else []
    if kind == "pipx" and shutil.which("pipx"):
        return ["pipx", "upgrade", PACKAGE]
    return [sys.executable, "-m", "pip", "install", "--user", "-U", PACKAGE] + extra


RESCUE = "python3 -s -m isnady update" if os.name != "nt" else "py -s -m isnady update"


def as_text(rep: Report) -> str:
    lines = [f"isnady {rep.running_version or '(not importable)'} running from {rep.running_file}",
             f"Python: {rep.python}"]
    if rep.latest:
        lines.append(f"Latest on PyPI: {rep.latest}")
    lines.append("\nInstallations:")
    for i in rep.installs or []:
        mark = "  <- imported" if i.active else ""
        where = f"{i.editable_path} (editable)" if i.editable_path else str(i.location)
        lines.append(f"  {i.version:10} {i.kind:9} {where}{mark}")
    if not rep.installs:
        lines.append("  none found")
    lines.append("\nCommands on PATH (the first of each name is the one that starts):")
    for c in rep.commands:
        lines.append(f"  {'*' if c.first else ' '} {c.path}  -> {c.version or '?'}")
    lines.append("")
    if rep.problems:
        lines.append("Problems:")
        lines += [f"  - {p}" for p in rep.problems]
        if rep.fixes:
            lines.append("\nTo update every copy where it is (iy update runs these):")
            lines += ["  " + " ".join(f'"{a}"' if " " in a else a for a in f) for f in rep.fixes]
        lines.append(f"\nIf 'iy update' itself does not start because an old copy runs instead: {RESCUE}")
    else:
        lines.append("No problems found.")
    return "\n".join(lines)
