"""Build the isnady desktop application for this system — one script for the three:

    python packaging/build_app.py windows VERSION   → dist-app/isnady-VERSION-windows-portable.exe (one file)
    python packaging/build_app.py linux   VERSION   → dist-app/isnady-VERSION-linux-x86_64.AppImage
    python packaging/build_app.py macos   VERSION   → dist-app/isnady-VERSION-macos-<arch>.zip (isnady.app inside)

All three are PORTABLE (Bayram, 2026-10-06: no setup): nothing is installed, the file runs where it is. A folder
named isnady-data beside it keeps every database and setting there (data.paths.portable_data_dir).
Needs: isnady installed with its AI extra (pip install ".[ai]"), PyInstaller; Linux: network once for appimagetool. Run from the repository root. Used by .github/workflows/publish.yml.
"""

import os
import platform
import shutil
import stat
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PKG = ROOT / "packaging"
OUT = ROOT / "dist-app"
APPIMAGETOOL = "https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage"
# Qt parts isnady never uses: kept out so the application is smaller
EXCLUDE = ["PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick", "PySide6.Qt3DCore",
           "PySide6.Qt3DRender", "PySide6.QtQuick3D", "PySide6.QtMultimedia", "PySide6.QtMultimediaWidgets",
           "PySide6.QtBluetooth", "PySide6.QtNfc", "PySide6.QtPositioning", "PySide6.QtLocation", "PySide6.QtSensors",
           "PySide6.QtSerialPort", "PySide6.QtDesigner", "PySide6.QtPdf", "PySide6.QtPdfWidgets", "PySide6.QtQml",
           "PySide6.QtQuick", "PySide6.QtQuickWidgets", "tkinter", "matplotlib", "IPython", "pytest"]


def run(*args, **kw) -> None:
    print("$", " ".join(str(a) for a in args), flush=True)
    subprocess.run([str(a) for a in args], check=True, **kw)


def pyinstaller(target: str, onefile: bool = False) -> Path:
    icon = PKG / ("isnady.ico" if target == "windows" else "isnady.icns" if target == "macos" else "isnady.png")
    args = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--name", "isnady", "--windowed",
            "--icon", icon, "--collect-data", "isnady", "--collect-submodules", "isnady",
            "--distpath", ROOT / "dist", "--workpath", ROOT / "build" / "pyinstaller", "--specpath", ROOT / "build"]
    if target == "macos":
        args += ["--osx-bundle-identifier", "com.bayramkotan.isnady"]
    if onefile:
        args.append("--onefile")
    for module in EXCLUDE:
        args += ["--exclude-module", module]
    run(*args, PKG / "isnady_app.py")
    if onefile:
        return ROOT / "dist" / ("isnady.exe" if target == "windows" else "isnady")
    return ROOT / "dist" / ("isnady.app" if target == "macos" else "isnady")


def windows(version: str) -> Path:
    """One portable .exe: no installer, no administrator rights; it unpacks itself at each start."""
    exe = pyinstaller("windows", onefile=True)
    target = OUT / f"isnady-{version}-windows-portable.exe"
    shutil.copy2(exe, target)
    return target


def linux(version: str) -> Path:
    folder = pyinstaller("linux")
    appdir = ROOT / "build" / "isnady.AppDir"
    shutil.rmtree(appdir, ignore_errors=True)
    (appdir / "usr").mkdir(parents=True)
    shutil.copytree(folder, appdir / "usr" / "lib" / "isnady")
    shutil.copy(PKG / "isnady.desktop", appdir / "isnady.desktop")
    shutil.copy(PKG / "isnady.png", appdir / "isnady.png")
    icons = appdir / "usr" / "share" / "icons" / "hicolor" / "256x256" / "apps"
    icons.mkdir(parents=True)
    shutil.copy(PKG / "isnady.png", icons / "isnady.png")
    apprun = appdir / "AppRun"
    apprun.write_text('#!/bin/sh\nHERE="$(dirname "$(readlink -f "$0")")"\nexec "$HERE/usr/lib/isnady/isnady" "$@"\n')
    apprun.chmod(apprun.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    tool = ROOT / "build" / "appimagetool"
    if not tool.exists():
        urllib.request.urlretrieve(APPIMAGETOOL, tool)
        tool.chmod(tool.stat().st_mode | stat.S_IEXEC)
    target = OUT / f"isnady-{version}-linux-x86_64.AppImage"
    env = dict(os.environ, ARCH="x86_64", APPIMAGE_EXTRACT_AND_RUN="1")   # no FUSE needed on build machines
    run(tool, "--no-appstream", appdir, target, env=env)
    return target


def macos(version: str) -> Path:
    """isnady.app in a zip: unzip and run, from anywhere (no disk image, nothing to install)."""
    app = pyinstaller("macos")
    arch = "arm64" if platform.machine() == "arm64" else "x86_64"
    target = OUT / f"isnady-{version}-macos-{arch}.zip"
    # ditto keeps the bundle's symlinks and permissions, which a plain zip would break
    run("ditto", "-c", "-k", "--sequesterRsrc", "--keepParent", app, target)
    return target


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] not in ("windows", "linux", "macos"):
        sys.exit(__doc__)
    kind, version = sys.argv[1], sys.argv[2].lstrip("v")
    OUT.mkdir(exist_ok=True)
    made = {"windows": windows, "linux": linux, "macos": macos}[kind](version)
    size = made.stat().st_size / 1e6
    print(f"built {made.name} ({size:.0f} MB)")
