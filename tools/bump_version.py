"""One command for a new version (REL2): every place that carries the version number, together.

    python tools/bump_version.py 0.1.4

Writes the version into src/isnady/__init__.py, js/package.json and js/index.js; the README's status line and its
PyPI and npm badges (the version is IN the badge address, so no cache — GitHub's or npm's — can show an old one);
turns CHANGELOG.md's "## [Unreleased]" into "## [0.1.4] — today"; and makes js/README.md again from README.md.
Then: python tools/release_check.py v0.1.4. Cross-platform: replaces the sed / WriteAllText of earlier releases.
"""

import datetime
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def sub(path: str, pattern: str, repl: str, required: bool = True) -> bool:
    f = ROOT / path
    text = f.read_text(encoding="utf-8")
    new, n = re.subn(pattern, repl, text)
    if n == 0 and required:
        sys.exit(f"bump failed: '{pattern}' not found in {path}")
    if new != text:
        f.write_text(new, encoding="utf-8", newline="\n")
    return n > 0


def main() -> None:
    if len(sys.argv) != 2 or not re.fullmatch(r"\d+\.\d+\.\d+", sys.argv[1].lstrip("v")):
        sys.exit(__doc__)
    v = sys.argv[1].lstrip("v")
    old = re.search(r'__version__ = "([^"]+)"', (ROOT / "src/isnady/__init__.py").read_text(encoding="utf-8")).group(1)
    sub("src/isnady/__init__.py", r'__version__ = "[^"]+"', f'__version__ = "{v}"')
    pkg = ROOT / "js/package.json"
    data = json.loads(pkg.read_text(encoding="utf-8"))
    data["version"] = v
    pkg.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    sub("js/index.js", r'export const version = "[^"]+";', f'export const version = "{v}";')
    sub("README.md", r"> \*\*Pre-alpha \([^)]+\)\.\*\*", f"> **Pre-alpha ({v}).**")
    sub("README.md", r"badge/PyPI-v[0-9.]+-", f"badge/PyPI-v{v}-")
    sub("README.md", r"badge/npm-v[0-9.]+-", f"badge/npm-v{v}-")
    today = datetime.date.today().isoformat()
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    if f"## [{v}]" in changelog:
        note = f"CHANGELOG already has [{v}]"
    elif sub("CHANGELOG.md", r"## \[Unreleased\]", f"## [{v}] — {today}", required=False):
        note = f"CHANGELOG: [Unreleased] → [{v}] — {today}"
    else:
        sys.exit("bump failed: CHANGELOG.md has neither '## [Unreleased]' nor a section for this version")
    subprocess.run([sys.executable, str(ROOT / "tools/sync_readme.py")], check=True)
    print(f"{old} → {v}: __init__.py, js/package.json, js/index.js, README status line and badges; {note}; js/README.md")


if __name__ == "__main__":
    main()
