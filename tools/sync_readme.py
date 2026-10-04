"""js/README.md (shown on npmjs.com) made from README.md (shown on GitHub and PyPI), so the three never differ.

    python tools/sync_readme.py           write js/README.md
    python tools/sync_readme.py --check   exit 1 if js/README.md is not what README.md gives (release check)
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NPM_NOTE = """> **About this npm package.** `npm install isnady` installs a small JavaScript library that will grow into
> isnady's API for the web (isnady.net); it does **not** install the isnady application. The application is
> installed with Python (`pip install isnady`, or the one-line installers below) or downloaded as a desktop
> app from the [GitHub Releases](https://github.com/bayramkotan/isnady/releases/latest) page. The npm package
> always carries the same version number as the application.
>
> ```js
> import { info, version } from "isnady";
> console.log(version);      // the isnady version, the same as on PyPI and GitHub
> console.log(info());       // { name, version, dataLoaded, homepage }
> ```

"""
MARK = "<!-- generated from README.md by tools/sync_readme.py — edit README.md, not this file -->\n"


def generate() -> str:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    # the note goes after the opening block (title, badges, picture): before the first "## " heading
    at = readme.find("\n## ")
    head, rest = (readme[:at + 1], readme[at + 1:]) if at > 0 else ("", readme)
    return MARK + head + "\n" + NPM_NOTE + rest


if __name__ == "__main__":
    target = ROOT / "js" / "README.md"
    text = generate()
    if "--check" in sys.argv:
        current = target.read_text(encoding="utf-8") if target.exists() else ""
        if current != text:
            sys.exit("js/README.md is not in step with README.md: run  python tools/sync_readme.py")
        print("js/README.md is in step with README.md")
    else:
        target.write_text(text, encoding="utf-8")
        print(f"wrote {target.relative_to(ROOT)} ({len(text):,} characters)")
