"""Find every isnady installation on this machine and keep every one of them up to date, IN PLACE.

Rule (Bayram, 2026-09-30): isnady may be installed anywhere — for all users (as administrator), for one
user, in any virtual environment, with pipx, or editable from a clone. Nothing is ever removed or moved;
updating updates each copy where it is (with sudo or the Windows administrator prompt when needed).
Once every copy is the same version it no longer matters which one starts first.

The one thing removed is not a copy: an old version's record (isnady-X.dist-info) that pip left behind in the same
folder as the new one (seen on Windows, 2026-10-12: 0.2.4 and 0.2.5 side by side in Program Files). The code in that
folder is the new version's; the old record only makes pip and this report read the wrong version ("pip show"
said 0.2.4), and updating again does not remove it. Only that record folder is deleted, never the code.


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

from isnady.core.i18n import N_, t

PACKAGE = "isnady"
COMMANDS = ("isnady", "iy", "isnady-gui", "isnady-cli")
KINDS = (N_("user"), N_("system"), N_("venv"), N_("pipx"), N_("editable"))   # shown in the report, translated


class Step(list):
    """One update command: the list is what the report shows (and what can be pasted in a terminal); `run` is what
    is really started — for the Windows administrator prompt, the same command that also brings pip's output and
    exit code back (the prompt's own window closes and takes them with it)."""

    def __init__(self, shown, run=None) -> None:
        super().__init__(shown)
        self.run = list(run) if run is not None else list(shown)


@dataclass
class Install:
    version: str
    location: Path                 # the site-packages folder
    kind: str                      # user | system | venv | pipx | editable
    installer: str                 # pip | pipx | uv | ...
    editable_path: Path | None = None
    active: bool = False           # what `import isnady` gives in this interpreter


@dataclass
class Leftover:
    version: str
    record: Path                   # the isnady-X.dist-info folder pip left behind
    location: Path                 # the site-packages folder, which holds the code of another version


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
    leftovers: list["Leftover"] = field(default_factory=list)
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


def _version_in(init: Path) -> str | None:
    """The __version__ written in an isnady/__init__.py."""
    try:
        text = Path(init).read_text(encoding="utf-8")
    except OSError:
        return None
    m = re.search(r"""__version__\s*=\s*["']([^"']+)["']""", text)
    return m.group(1) if m else None


def _source_version(clone: Path) -> str | None:
    """The version written in a clone's source (src/isnady/__init__.py), which is what an editable copy runs."""
    return _version_in(Path(clone) / "src" / PACKAGE / "__init__.py")


def _record_path(dist) -> Path | None:
    p = getattr(dist, "_path", None)
    return Path(p) if p else None


def find_installs(leftovers: list[Leftover] | None = None) -> list[Install]:
    """Every isnady installation. An old record pip left beside a newer one in the same folder is not an
    installation: it goes to `leftovers` (when a list is given) and not into the result."""
    user_site = Path(site.getusersitepackages())
    found, seen = [], set()
    for d in _site_dirs():
        dists = [x for x in metadata.distributions(path=[str(d)]) if (x.metadata["Name"] or "").lower() == PACKAGE]
        plain = [x for x in dists if not _editable_of(x)]
        if len(plain) > 1:
            # several records, one code: the code's own __version__ says which record is true
            code = _version_in(d / PACKAGE / "__init__.py")
            versions = [x.version for x in plain]
            real = code if code in versions else max(versions, key=_vkey)
            kept_one = False
            for x in plain:
                if x.version == real and not kept_one:
                    kept_one = True
                    continue
                record = _record_path(x)
                if leftovers is not None and record is not None:
                    leftovers.append(Leftover(x.version, record, d))
                dists.remove(x)
        for dist in dists:
            key = (str(d), dist.version)
            if key in seen:
                continue
            seen.add(key)
            installer = (dist.read_text("INSTALLER") or "pip").strip()
            editable = _editable_of(dist)
            if editable:
                kind = "editable"
                # pip's record keeps the version of the day it was installed; a clone moves on with git pull
                version = _source_version(editable) or dist.version
            elif "pipx" in str(d) or installer == "pipx":
                kind = "pipx"
            elif d == user_site or str(d).startswith(str(user_site)):
                kind = "user"
            elif sys.prefix != sys.base_prefix and str(d).startswith(sys.prefix):
                kind = "venv"
            else:
                kind = "system"
            found.append(Install(version if editable else dist.version, d, kind, installer, editable))
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


def _editable_of(dist) -> Path | None:
    direct = dist.read_text("direct_url.json")
    if direct:
        try:
            info = json.loads(direct)
            if info.get("dir_info", {}).get("editable"):
                return path_from_file_url(info["url"])
        except (ValueError, KeyError):
            pass
    return None


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


def _ps_args(args: list[str]) -> str:
    # Start-Process joins the arguments with spaces: one with a space in it is put in double quotes
    return ", ".join("'" + (f'"{a}"' if " " in a else a).replace("'", "''") + "'" for a in args)


# run by the elevated Python: the command (its own Python + the arguments), its output into a file the caller reads
_LOGGED = ("import subprocess,sys;f=open(sys.argv[1],'w',encoding='utf-8');"
           "r=subprocess.run([sys.executable]+sys.argv[2:],stdout=f,stderr=subprocess.STDOUT);f.close();"
           "sys.exit(r.returncode)")


def _as_admin(argv: list[str]) -> list[str]:
    if os.name == "nt":
        # Windows has no sudo: PowerShell opens the administrator prompt and waits for the result. Shown: the plain
        # command. Run: the same, with pip's output written to a file and printed here, and its exit code returned
        # (2026-10-12: the prompt's window closed with pip's "already up to date" in it, and the report said nothing)
        shown = ["powershell", "-NoProfile", "-Command",
                 f"Start-Process -FilePath '{argv[0]}' -ArgumentList {_ps_args(argv[1:])} -Verb RunAs -Wait"]
        import tempfile

        log = os.path.join(tempfile.gettempdir(), f"isnady-admin-{os.getpid()}.log")
        lit = log.replace("'", "''")
        script = (f"$log = '{lit}'; Remove-Item -LiteralPath $log -ErrorAction SilentlyContinue; "
                  f"$p = Start-Process -FilePath '{argv[0]}' -ArgumentList {_ps_args(['-c', _LOGGED, log] + argv[1:])} "
                  f"-Verb RunAs -Wait -PassThru; "
                  f"if (Test-Path -LiteralPath $log) {{ Get-Content -LiteralPath $log -Encoding UTF8; "
                  f"Remove-Item -LiteralPath $log -ErrorAction SilentlyContinue }}; exit $p.ExitCode")
        return Step(shown, ["powershell", "-NoProfile", "-Command", script])
    return ["sudo"] + argv


def remove_record_argv(left: Leftover) -> list[str]:
    """Delete a leftover record folder (only that folder), as administrator when its folder needs it."""
    argv = [sys.executable, "-c", "import shutil,sys;shutil.rmtree(sys.argv[1])", str(left.record)]
    return argv if _writable(left.location) else _as_admin(argv)


def _pip_spec(latest: str | None) -> list[str]:
    """What pip is asked for: always without its cached copy of PyPI's list of versions — pip keeps that list for
    10 minutes, and right after a release it still said "already up to date" (2026-10-12, 0.2.6 published at 15:50,
    updated at 15:51). With the version PyPI reported: "isnady>=X" (never a step back)."""
    return ["--no-cache-dir", f"{PACKAGE}>={latest}" if latest else PACKAGE]


def upgrade_argv(inst: Install, latest: str | None = None) -> list[str]:
    """Update this copy where it is installed."""
    extra = ["--break-system-packages"] if _externally_managed() else []
    spec = _pip_spec(latest)
    if inst.kind == "editable" and inst.editable_path:
        return ["git", "-C", str(inst.editable_path), "pull", "--ff-only"]
    if inst.kind == "pipx":
        return ["pipx", "upgrade", "--pip-args=--no-cache-dir", PACKAGE]
    if inst.kind == "user":
        return [sys.executable, "-m", "pip", "install", "--user", "-U", *spec] + extra
    if inst.kind == "venv":
        return [sys.executable, "-m", "pip", "install", "-U", *spec]
    # system: "-s" so pip looks at the system copy, not the user folder in front of it
    argv = [sys.executable, "-s", "-m", "pip", "install", "-U", *spec] + extra
    return _as_admin(argv) if needs_admin(inst) else argv


def _same_python(a: str, b: str) -> bool:
    """pythonw.exe (the window launchers' Python) and python.exe beside it are one installation: updating it twice
    ran pip a second time without administrator rights, silently (2026-10-12)."""
    def norm(p: str) -> Path:
        path = Path(p).resolve()
        return path.with_name(path.name.lower().replace("pythonw", "python"))
    try:
        return norm(a) == norm(b)
    except OSError:
        return a == b


def lag_note(rep: Report) -> str | None:
    """After updating, a copy still behind PyPI: say why that can be and what to do."""
    released = [i for i in rep.installs if i.kind != "editable"]
    if rep.latest and any(_vkey(i.version) < _vkey(rep.latest) for i in released):
        return t("isnady {latest} is on PyPI, but this computer still has {have}. Right after a release PyPI's list "
                 "of versions can lag a few minutes behind; pip's output above says what it found. Run the update "
                 "again in a few minutes.", latest=rep.latest,
                 have=", ".join(sorted({i.version for i in released}, key=_vkey)))
    return None


def diagnose(check_pypi: bool = True) -> Report:
    try:
        import isnady

        running_version, running_file = isnady.__version__, isnady.__file__
    except ImportError:
        running_version, running_file = "", ""
    leftovers: list[Leftover] = []
    rep = Report(python=sys.executable, running_version=running_version, running_file=running_file,
                 installs=find_installs(leftovers), leftovers=leftovers, commands=find_commands())
    rep.latest = latest_on_pypi() if check_pypi else None

    installs = rep.installs
    # first: old records pip left beside a newer version (removing them is the whole fix, updating does not)
    for left in rep.leftovers:
        rep.problems.append(t("pip left the record of isnady {version} in {folder} beside the installed version; "
                              "pip reads that old record (\"pip show\" gives {version}) and updating does not remove "
                              "it. Only that record folder is deleted, not the program.",
                              version=left.version, folder=left.location))
        rep.fixes.append(remove_record_argv(left))
    released = [i for i in installs if i.kind != "editable"]
    newest = max([i.version for i in installs] + ([rep.latest] if rep.latest else []), key=_vkey, default=None)
    versions = sorted({i.version for i in installs}, key=_vkey)
    if len(versions) > 1:
        rep.problems.append(t("isnady is installed in more than one place with different versions ({copies}); updating "
                              "brings every copy to the same version, where it is.",
                              copies=", ".join(f"{i.version} {t(i.kind)}" for i in installs)))
    for c in rep.commands:
        if c.first and c.version and newest and _vkey(c.version) < _vkey(newest):
            rep.problems.append(t("The command '{name}' starts isnady {version} ({path}).", name=c.path.name,
                                  version=c.version, path=c.path))
    for inst in installs:
        if inst.kind == "editable" and inst.editable_path and not Path(inst.editable_path).exists():
            rep.problems.append(t("The editable installation points to {path}, which no longer exists.",
                                  path=inst.editable_path))
    if rep.latest and any(_vkey(i.version) < _vkey(rep.latest) for i in released):
        rep.problems.append(t("isnady {latest} is on PyPI.", latest=rep.latest))
    # the plan: every copy that is behind is updated in place (editable clones: git pull)
    for inst in installs:
        behind = newest and _vkey(inst.version) < _vkey(newest)
        if behind or (inst.kind == "editable" and rep.latest):
            rep.fixes.append(upgrade_argv(inst, rep.latest))
    # commands from ANOTHER Python (another virtual environment) that start an older copy
    for c in rep.commands:
        exe = c.interpreter
        if c.version and newest and _vkey(c.version) < _vkey(newest) and exe and Path(exe).exists() \
                and not _same_python(exe, sys.executable):
            argv = [exe, "-m", "pip", "install", "-U", *_pip_spec(rep.latest)]
            if argv not in rep.fixes:
                rep.fixes.append(argv)
    user_bin = user_scripts_dir()
    if any(i.kind in ("user", "editable") for i in installs) and str(user_bin) not in os.environ.get("PATH", "") \
            and not rep.commands:
        rep.problems.append(t("{folder} is not in PATH, so the isnady commands may not be found.", folder=user_bin))
    return rep


def install_argv(kind: str = "user") -> list[str]:
    extra = ["--break-system-packages"] if _externally_managed() else []
    if kind == "pipx" and shutil.which("pipx"):
        return ["pipx", "upgrade", PACKAGE]
    return [sys.executable, "-m", "pip", "install", "--user", "-U", PACKAGE] + extra


RESCUE = "python3 -s -m isnady update" if os.name != "nt" else "py -s -m isnady update"


def as_text(rep: Report) -> str:
    lines = [t("isnady {version} running from {file}", version=rep.running_version or t("(not importable)"),
               file=rep.running_file),
             t("Python: {python}", python=rep.python)]
    if rep.latest:
        lines.append(t("Latest on PyPI: {latest}", latest=rep.latest))
    lines.append("\n" + t("Installations:"))
    for i in rep.installs or []:
        mark = "  <- " + t("imported") if i.active else ""
        where = f"{i.editable_path} ({t('editable')})" if i.editable_path else str(i.location)
        lines.append(f"  {i.version:10} {t(i.kind):9} {where}{mark}")
    for left in rep.leftovers:
        lines.append(f"  {left.version:10} {t('left over'):9} {left.record}")
    if not rep.installs:
        lines.append("  " + t("none found"))
    lines.append("\n" + t("Commands on PATH (the first of each name is the one that starts):"))
    for c in rep.commands:
        lines.append(f"  {'*' if c.first else ' '} {c.path}  -> {c.version or '?'}")
    lines.append("")
    if rep.problems:
        lines.append(t("Problems:"))
        lines += [f"  - {p}" for p in rep.problems]
        if rep.fixes:
            lines.append("\n" + t("To update every copy where it is (iy update runs these):"))
            # quoted when a shell would split or redirect it (a space; "isnady>=0.2.6")
            lines += ["  " + " ".join(f'"{a}"' if any(c in a for c in ' <>|&') else a for a in f) for f in rep.fixes]
        lines.append("\n" + t("If 'iy update' itself does not start because an old copy runs instead: {rescue}",
                              rescue=RESCUE))
    else:
        lines.append(t("No problems found."))
    return "\n".join(lines)


# ---------------------------------------------------------------- running the plan from the window
def for_window(argv: list[str]) -> list[str] | None:
    """The same command for a window with no terminal: sudo cannot ask for the password there, so the system's
    graphical prompt (pkexec) asks instead; None when there is none (then the command is run in a terminal).
    Windows' administrator prompt already is a window."""
    if argv[0] != "sudo":
        return argv
    if shutil.which("pkexec"):
        return ["pkexec"] + argv[1:]
    return None


def run_plan(plan: list[list[str]], say, window: bool = False) -> list[tuple[list[str], int]]:
    """Run every update command, one after the other, passing each line of their output to say(line).
    Returns (command, exit code) for each; a command that could not be run has code -1."""
    results = []
    for argv in plan:
        actual = getattr(argv, "run", argv)
        run = for_window(actual) if window else actual
        if run is None:
            say(t("Needs administrator rights and no graphical prompt was found; run in a terminal:") + "\n  "
                + " ".join(argv))
            results.append((argv, -1))
            continue
        say("$ " + " ".join(argv if run is actual else run))
        try:
            flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0     # no console flashing up
            proc = subprocess.Popen(run, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                    encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL, creationflags=flags)
            for line in proc.stdout:
                say(line.rstrip())
            code = proc.wait()
            if code != 0:
                say(t("The command ended with code {code}.", code=code))
        except OSError as exc:
            say(str(exc))
            code = -1
        results.append((argv, code))
    return results
