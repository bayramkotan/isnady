"""After a release: what each place publishes now — PyPI, npm, GitHub (main and the Release page).

    python tools/release_status.py [0.1.4]

Reads the sites themselves (no cache of ours); a page that still shows an older version a few minutes after is
the site's own cache, not the release.
"""

import json
import re
import sys
import urllib.request

REPO = "bayramkotan/isnady"


def get(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "isnady-release-status", "Cache-Control": "no-cache"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def main() -> None:
    want = sys.argv[1].lstrip("v") if len(sys.argv) > 1 else None
    rows = []
    try:
        d = json.loads(get("https://pypi.org/pypi/isnady/json"))
        readme = d["info"]["description"]
        badge = re.search(r"badge/PyPI-v([0-9.]+)-", readme)
        rows.append(("PyPI", d["info"]["version"], f"README badge {badge.group(1) if badge else '(dynamic)'}"))
    except Exception as exc:
        rows.append(("PyPI", "?", str(exc)))
    try:
        d = json.loads(get("https://registry.npmjs.org/isnady"))
        readme = d.get("readme", "")
        badge = re.search(r"badge/npm-v([0-9.]+)-", readme)
        rows.append(("npm", d["dist-tags"]["latest"], f"README badge {badge.group(1) if badge else '(dynamic)'}"))
    except Exception as exc:
        rows.append(("npm", "?", str(exc)))
    try:
        init = get(f"https://raw.githubusercontent.com/{REPO}/main/src/isnady/__init__.py")
        readme = get(f"https://raw.githubusercontent.com/{REPO}/main/README.md")
        v = re.search(r'__version__ = "([^"]+)"', init).group(1)
        badge = re.search(r"badge/PyPI-v([0-9.]+)-", readme)
        rows.append(("GitHub main", v, f"README badge {badge.group(1) if badge else '(dynamic)'}"))
    except Exception as exc:
        rows.append(("GitHub main", "?", str(exc)))
    if want:
        try:
            page = get(f"https://github.com/{REPO}/releases/expanded_assets/v{want}")
            files = sorted(set(re.findall(rf"releases/download/v{re.escape(want)}/([^\"]+)", page)))
            rows.append((f"Release v{want}", want if files else "?", f"{len(files)} files: " + ", ".join(files)))
        except Exception as exc:
            rows.append((f"Release v{want}", "?", str(exc)))
    for place, version, note in rows:
        mark = "" if not want else ("  ✓" if version == want else "  ✗")
        print(f"{place:16} {version:10}{mark}  {note}")


if __name__ == "__main__":
    main()
