"""Before anything is built or published: one version everywhere, the npm README in step, the CHANGELOG ready.

    python tools/release_check.py v0.1.1 [--notes release-notes.md]

Checks the tag against src/isnady/__init__.py, js/package.json and js/index.js; that js/README.md is what
README.md gives; that CHANGELOG.md has a section for the version. With --notes, writes the GitHub Release
text from that section. Used by .github/workflows/publish.yml; run it locally before tagging.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def fail(message: str) -> None:
    sys.exit(f"release check failed: {message}")


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    version = sys.argv[1].lstrip("v")
    found = {
        "tag": version,
        "src/isnady/__init__.py": re.search(r'__version__ = "([^"]+)"', (ROOT / "src/isnady/__init__.py").read_text()).group(1),
        "js/package.json": json.loads((ROOT / "js/package.json").read_text())["version"],
        "js/index.js": re.search(r'version = "([^"]+)"', (ROOT / "js/index.js").read_text()).group(1),
    }
    differing = {k: v for k, v in found.items() if v != version}
    if differing:
        fail("versions differ: " + ", ".join(f"{k} {v}" for k, v in found.items()))
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for label, pattern in (("README status line", r"Pre-alpha \(([^)]+)\)"), ("PyPI badge", r"badge/PyPI-v([0-9.]+)-"),
                           ("npm badge", r"badge/npm-v([0-9.]+)-")):
        m = re.search(pattern, readme)
        if not m or m.group(1) != version:
            fail(f"{label} says {m.group(1) if m else 'nothing'}, not {version} — run  python tools/bump_version.py {version}")
    print(f"one version everywhere: {version} (code, npm files, README status line and badges)")
    synced = subprocess.run([sys.executable, str(ROOT / "tools/sync_readme.py"), "--check"], capture_output=True, text=True)
    if synced.returncode != 0:
        fail("js/README.md is not in step with README.md — run  python tools/sync_readme.py  and commit")
    print(synced.stdout.strip())
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    m = re.search(rf"^## \[{re.escape(version)}\][^\n]*\n(.*?)(?=^## \[|\Z)", changelog, re.S | re.M)
    if not m or not m.group(1).strip():
        fail(f"CHANGELOG.md has no section '## [{version}]'")
    print(f"CHANGELOG.md has the {version} section")
    if "--notes" in sys.argv:
        out = Path(sys.argv[sys.argv.index("--notes") + 1])
        downloads = f"""
### Download

| System | File |
|---|---|
| Windows 10/11 (64-bit) | `isnady-{version}-windows-portable.exe` — portable: nothing to install, run it from anywhere. Windows may say the publisher is unknown (the app is not signed): *More info → Run anyway* |
| Linux (x86-64) | `isnady-{version}-linux-x86_64.AppImage` — portable: `chmod +x` it and run; needs `libxcb-cursor0` on some systems |
| macOS, Apple silicon | `isnady-{version}-macos-arm64.zip` — unzip, run `isnady.app` |
| macOS, Intel | `isnady-{version}-macos-x86_64.zip` |
| Python | `pip install -U isnady` (or `iy update`) |

All three applications are portable. Put a folder named `isnady-data` beside the file and isnady keeps its databases
and settings there — isnady on a USB stick. The macOS app is not notarized: the first time, right-click it and choose
*Open*. `SHA256SUMS.txt` lists the checksum of every file. The same version is on PyPI and npm.
"""
        out.write_text(m.group(1).strip() + "\n" + downloads, encoding="utf-8")
        print(f"release notes written to {out}")


if __name__ == "__main__":
    main()
