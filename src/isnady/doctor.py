"""Find every isnady installation on this machine and say which one really runs.

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
                        editable = Path(info["url"].replace("file://", "", 1))
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
    try:
        head = path.read_bytes()[:4096] if path.suffix.lower() == ".exe" else path.read_bytes()[:256]
    except OSError:
        return None
    m = re.search(rb"#!\s*([^\r\n\"]+?python[^\r\n\"]*)", head)
    return m.group(1).decode(errors="replace").strip() if m else None


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
                if interp and Path(interp.split()[0]).exists():
                    try:
                        r = subprocess.run([interp.split()[0], "-c", "import isnady; print(isnady.__version__)"],
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


def uninstall_argv(inst: Install) -> list[str]:
    extra = ["--break-system-packages"] if _externally_managed() else []
    if inst.kind == "pipx":
        return ["pipx", "uninstall", PACKAGE]
    if inst.kind == "system":
        # pip removes the FIRST copy it finds, and the user folder comes first: "-s" hides the user folder
        # so the system copy is the one removed
        argv = [sys.executable, "-s", "-m", "pip", "uninstall", "-y", PACKAGE] + extra
        if os.name != "nt" and not os.access(inst.location, os.W_OK):
            return ["sudo"] + argv
        return argv
    return [sys.executable, "-m", "pip", "uninstall", "-y", PACKAGE] + extra


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
    keep = next((i for i in installs if i.kind == "editable"), None) or \
        max(installs, key=lambda i: _vkey(i.version), default=None)
    if len(installs) > 1:
        rep.problems.append(f"{len(installs)} installations of isnady for this Python; only one should exist.")
        for inst in installs:
            if inst is not keep:
                rep.fixes.append(uninstall_argv(inst))
    active = next((i for i in installs if i.active), None)
    if active and keep and active is not keep:
        rep.problems.append(f"Python imports isnady {active.version} from {active.location}, "
                            f"which hides {keep.version} ({keep.kind}).")
    for c in rep.commands:
        if c.first and keep and c.version and c.version != keep.version:
            rep.problems.append(f"The command '{c.path.name}' starts isnady {c.version} ({c.path}), "
                                f"not {keep.version}.")
    if keep and keep.editable_path and not Path(keep.editable_path).exists():
        rep.problems.append(f"The editable installation points to {keep.editable_path}, which no longer exists.")
    if rep.latest and keep and not keep.editable_path and _vkey(rep.latest) > _vkey(keep.version):
        rep.problems.append(f"isnady {rep.latest} is on PyPI; this installation is {keep.version}.")
        rep.fixes.append(install_argv(keep.kind))
    user_bin = Path(site.getuserbase()) / ("Scripts" if os.name == "nt" else "bin")
    if keep and keep.kind in ("user", "editable") and str(user_bin) not in os.environ.get("PATH", ""):
        rep.problems.append(f"{user_bin} is not in PATH, so the isnady commands may not be found.")
    return rep


def install_argv(kind: str = "user") -> list[str]:
    extra = ["--break-system-packages"] if _externally_managed() else []
    if kind == "pipx" and shutil.which("pipx"):
        return ["pipx", "upgrade", PACKAGE]
    return [sys.executable, "-m", "pip", "install", "--user", "-U", PACKAGE] + extra


RESCUE = "python3 -s -m isnady doctor --fix" if os.name != "nt" else "py -s -m isnady doctor --fix"


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
            lines.append("\nTo fix (iy doctor --fix runs these):")
            lines += ["  " + " ".join(f'"{a}"' if " " in a else a for a in f) for f in rep.fixes]
        lines.append(f"\nIf 'iy doctor' itself does not start because an old copy runs instead: {RESCUE}")
    else:
        lines.append("No problems found.")
    return "\n".join(lines)
