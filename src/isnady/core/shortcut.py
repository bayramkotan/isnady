"""Desktop and menu shortcuts for isnady itself (Tools → Create Desktop Shortcut, `iy shortcut`).

The shortcut starts isnady the way it is installed here: the AppImage file, the Windows / macOS application,
or the `isnady-gui` command of a pip / pipx / editable install. Three lessons from VenvStudio, built in from the
start: the icon must ship inside the package (it does: assets/icons/isnady.png, .ico, .icns); a Windows .lnk
needs an .ico of its own or it shows Python's icon; and the Desktop folder is asked of the system (it is
"Masaüstü" on a Turkish Linux, and may be redirected to OneDrive on Windows). Qt-free.
"""

import os
import shutil
import subprocess
import sys
from importlib import resources
from pathlib import Path

APP_ID = "isnady"


def _icon(ext: str) -> Path | None:
    p = resources.files("isnady") / "assets" / "icons" / f"isnady.{ext}"
    return Path(str(p)) if p.is_file() else None


def launch_command() -> tuple[str, list[str], str]:
    """(program, arguments, how) — what a shortcut must run to start isnady as installed here."""
    if os.environ.get("APPIMAGE"):                     # running from the AppImage: the file itself
        return os.environ["APPIMAGE"], [], "the AppImage"
    if getattr(sys, "frozen", False):                  # the Windows / macOS application (PyInstaller)
        if sys.platform == "darwin":
            app = Path(sys.executable).resolve().parents[2]          # …/isnady.app/Contents/MacOS/isnady
            return str(app), [], "the macOS application"
        return sys.executable, [], "the application"
    gui = shutil.which("isnady-gui")
    if gui:
        return gui, [], "the isnady-gui command"
    # last resort: this very Python, without a console window on Windows
    python = sys.executable
    if os.name == "nt":
        windowless = Path(python).with_name("pythonw.exe")
        python = str(windowless) if windowless.exists() else python
    return python, ["-m", "isnady"], "this Python"        # no arguments: python -m isnady opens the window


def desktop_dir() -> Path:
    if os.name == "nt":
        out = subprocess.run(["powershell", "-NoProfile", "-Command", "[Environment]::GetFolderPath('Desktop')"],
                             capture_output=True, text=True)
        if out.returncode == 0 and out.stdout.strip():
            return Path(out.stdout.strip())
        return Path.home() / "Desktop"
    if sys.platform != "darwin":
        if shutil.which("xdg-user-dir"):
            out = subprocess.run(["xdg-user-dir", "DESKTOP"], capture_output=True, text=True)
            if out.returncode == 0 and out.stdout.strip() and Path(out.stdout.strip()) != Path.home():
                return Path(out.stdout.strip())
        # the file xdg-user-dir reads, for systems without the program: XDG_DESKTOP_DIR="$HOME/Masaüstü"
        dirs = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))) / "user-dirs.dirs"
        try:
            for line in dirs.read_text(encoding="utf-8").splitlines():
                if line.startswith("XDG_DESKTOP_DIR="):
                    value = line.split("=", 1)[1].strip().strip('"').replace("$HOME", str(Path.home()))
                    if value and Path(value) != Path.home():
                        return Path(value)
        except OSError:
            pass
    return Path.home() / "Desktop"


def create(desktop: bool = True, menu: bool = True) -> list[tuple[str, Path]]:
    """Create the shortcuts; returns [(what, path)] of what was written. Raises OSError with a plain message."""
    program, args, how = launch_command()
    if sys.platform == "darwin":
        return _macos(program, args, desktop, menu)
    if os.name == "nt":
        return _windows(program, args, desktop, menu)
    return _linux(program, args, how, desktop, menu)


# ------------------------------------------------------------------ Linux
def _linux(program: str, args: list[str], how: str, desktop: bool, menu: bool) -> list[tuple[str, Path]]:
    icon_src = _icon("png")
    icon_dir = Path.home() / ".local/share/icons/hicolor/512x512/apps"
    icon_dir.mkdir(parents=True, exist_ok=True)
    icon = icon_dir / "isnady.png"
    if icon_src:
        shutil.copyfile(icon_src, icon)               # a stable place: the package's own path changes with versions
    exec_line = " ".join(_quote(a) for a in [program, *args])
    entry = (
        "[Desktop Entry]\nType=Application\nName=isnady\n"
        "GenericName=Hadith search and chains of transmission\n"
        "Comment=Search hadith, follow their chains of transmission, read the books\n"
        f"Exec={exec_line}\nIcon={icon}\nTerminal=false\nCategories=Education;Literature;\n"
        "Keywords=hadith;isnad;rijal;Arabic;\nStartupWMClass=isnady\n"
        f"X-isnady-Launches={how}\n")
    made = []
    targets = []
    if menu:
        targets.append(("menu", Path.home() / ".local/share/applications/isnady.desktop"))
    if desktop:
        targets.append(("desktop", desktop_dir() / "isnady.desktop"))
    for what, path in targets:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(entry, encoding="utf-8")
        path.chmod(0o755)                             # desktops refuse to launch a non-executable .desktop file
        if what == "desktop" and shutil.which("gio"):  # GNOME: mark it trusted so it launches on double-click
            subprocess.run(["gio", "set", str(path), "metadata::trusted", "true"], capture_output=True)
        made.append((what, path))
    if menu and shutil.which("update-desktop-database"):
        subprocess.run(["update-desktop-database", str(Path.home() / ".local/share/applications")], capture_output=True)
    return made


def _quote(arg: str) -> str:
    return f'"{arg}"' if any(c in arg for c in ' "\'\\') else arg


# ------------------------------------------------------------------ Windows
def _windows(program: str, args: list[str], desktop: bool, menu: bool) -> list[tuple[str, Path]]:
    icon = _icon("ico")
    targets = []
    if desktop:
        targets.append(("desktop", desktop_dir() / "isnady.lnk"))
    if menu:
        start = Path(os.environ.get("APPDATA", str(Path.home() / "AppData/Roaming"))) / "Microsoft/Windows/Start Menu/Programs"
        targets.append(("menu", start / "isnady.lnk"))
    made = []
    for what, path in targets:
        path.parent.mkdir(parents=True, exist_ok=True)
        ps = (
            "$s = (New-Object -ComObject WScript.Shell).CreateShortcut($env:ISNADY_LNK); "
            "$s.TargetPath = $env:ISNADY_TARGET; $s.Arguments = $env:ISNADY_ARGS; "
            "$s.WorkingDirectory = $env:USERPROFILE; $s.Description = 'isnady - hadith search'; "
            "if ($env:ISNADY_ICON) { $s.IconLocation = $env:ISNADY_ICON + ',0' }; $s.Save()")
        env = dict(os.environ, ISNADY_LNK=str(path), ISNADY_TARGET=program,
                   ISNADY_ARGS=subprocess.list2cmdline(args), ISNADY_ICON=str(icon) if icon else "")
        out = subprocess.run(["powershell", "-NoProfile", "-Command", ps], env=env, capture_output=True, text=True)
        if out.returncode != 0 or not path.exists():
            raise OSError(f"Windows could not write {path}: {out.stderr.strip() or 'no reason given'}")
        made.append((what, path))
    return made


# ------------------------------------------------------------------ macOS
def _macos(program: str, args: list[str], desktop: bool, menu: bool) -> list[tuple[str, Path]]:
    made = []
    if program.endswith(".app"):                      # the application itself: a link to it is enough
        app = Path(program)
    else:                                             # pip install: a small app bundle that runs isnady-gui
        app = Path.home() / "Applications" / "isnady.app"
        macos_dir = app / "Contents" / "MacOS"
        res = app / "Contents" / "Resources"
        macos_dir.mkdir(parents=True, exist_ok=True)
        res.mkdir(parents=True, exist_ok=True)
        launcher = macos_dir / "isnady"
        launcher.write_text("#!/bin/sh\nexec " + " ".join(_quote(a) for a in [program, *args]) + ' "$@"\n')
        launcher.chmod(0o755)
        icns = _icon("icns")
        if icns:
            shutil.copyfile(icns, res / "isnady.icns")
        (app / "Contents" / "Info.plist").write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
            '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n<plist version="1.0"><dict>\n'
            "<key>CFBundleName</key><string>isnady</string>\n<key>CFBundleDisplayName</key><string>isnady</string>\n"
            "<key>CFBundleIdentifier</key><string>com.bayramkotan.isnady.launcher</string>\n"
            "<key>CFBundleExecutable</key><string>isnady</string>\n<key>CFBundleIconFile</key><string>isnady</string>\n"
            "<key>CFBundlePackageType</key><string>APPL</string>\n</dict></plist>\n")
        if menu:
            made.append(("menu", app))
    if desktop:
        link = desktop_dir() / "isnady.app"
        if link.is_symlink() or link.exists():
            if link.is_symlink():
                link.unlink()
        if not link.exists():
            link.symlink_to(app)
        made.append(("desktop", link))
    return made
