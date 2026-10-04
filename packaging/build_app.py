"""Build the isnady desktop application for this system — one script for the three:

    python packaging/build_app.py windows VERSION   → dist-app/isnady-VERSION-windows-setup.exe (Inno Setup)
    python packaging/build_app.py linux   VERSION   → dist-app/isnady-VERSION-linux-x86_64.AppImage
    python packaging/build_app.py macos   VERSION   → dist-app/isnady-VERSION-macos-<arch>.dmg (the .app inside)

Needs: isnady installed with its AI extra (pip install ".[ai]"), PyInstaller; Windows: Inno Setup (iscc);
Linux: network once for appimagetool. Run from the repository root. Used by .github/workflows/publish.yml.
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


def pyinstaller(target: str) -> Path:
    icon = PKG / ("isnady.ico" if target == "windows" else "isnady.icns" if target == "macos" else "isnady.png")
    args = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--name", "isnady", "--windowed",
            "--icon", icon, "--collect-data", "isnady", "--collect-submodules", "isnady",
            "--distpath", ROOT / "dist", "--workpath", ROOT / "build" / "pyinstaller", "--specpath", ROOT / "build"]
    if target == "macos":
        args += ["--osx-bundle-identifier", "com.bayramkotan.isnady"]
    for module in EXCLUDE:
        args += ["--exclude-module", module]
    run(*args, PKG / "isnady_app.py")
    return ROOT / "dist" / ("isnady.app" if target == "macos" else "isnady")


def windows(version: str) -> Path:
    folder = pyinstaller("windows")
    iscc = shutil.which("iscc") or r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
    run(iscc, f"/DMyAppVersion={version}", f"/DSourceDir={folder}", f"/DOutputDir={OUT}", PKG / "isnady.iss")
    return OUT / f"isnady-{version}-windows-setup.exe"


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
    app = pyinstaller("macos")
    arch = "arm64" if platform.machine() == "arm64" else "x86_64"
    stage = ROOT / "build" / "dmg"
    shutil.rmtree(stage, ignore_errors=True)
    stage.mkdir(parents=True)
    run("ditto", app, stage / "isnady.app")
    (stage / "Applications").symlink_to("/Applications")
    target = OUT / f"isnady-{version}-macos-{arch}.dmg"
    run("hdiutil", "create", "-volname", f"isnady {version}", "-srcfolder", stage, "-ov", "-format", "UDZO", target)
    return target


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] not in ("windows", "linux", "macos"):
        sys.exit(__doc__)
    kind, version = sys.argv[1], sys.argv[2].lstrip("v")
    OUT.mkdir(exist_ok=True)
    made = {"windows": windows, "linux": linux, "macos": macos}[kind](version)
    size = made.stat().st_size / 1e6
    print(f"built {made.name} ({size:.0f} MB)")
