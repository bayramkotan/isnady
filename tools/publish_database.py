"""Prepare this computer's isnady data for the isnady-data repository.

    python tools/publish_database.py ~/Github/isnady-data [--data DIR]

  * the database (isnady.db) is copied compactly (VACUUM INTO), without what was imported from your own files
    (User Resources never leave the computer), then zipped: release/isnady-db-<date>.zip — too large for a git
    file (GitHub takes at most 100 MB a file), so it is published as a Release of isnady-data;
  * every saved computation (derived/*.json: statistics, models, laboratory …) is copied into derived/ of the
    repository, so they are kept with the data and never computed again for the same data;
  * database.json describes the zip: date, schema, size, sha256, books, hadith, texts, narrators.

Settings, window state and your list of sources and repositories are personal and are not copied.
"""

import argparse
import hashlib
import json
import shutil
import sqlite3
import sys
import zipfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("repo", help="the isnady-data folder (a git clone)")
    ap.add_argument("--data", help="isnady's data folder (default: the one isnady uses on this computer)")
    a = ap.parse_args()
    sys.path.insert(0, str(ROOT / "src"))
    from isnady.data import db
    from isnady.data.paths import data_dir

    data = Path(a.data).expanduser() if a.data else data_dir()
    repo = Path(a.repo).expanduser()
    source = data / "isnady.db"
    if not source.exists():
        print(f"No database in {data}", file=sys.stderr)
        return 1
    release = repo / "release"
    release.mkdir(parents=True, exist_ok=True)
    stamp = date.today().isoformat()
    copy = release / "isnady.db"
    if copy.exists():
        copy.unlink()

    print(f"Copying {source} …")
    conn = sqlite3.connect(source)
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    conn.execute("VACUUM INTO ?", (str(copy),))
    conn.close()

    conn = sqlite3.connect(copy)
    conn.execute("PRAGMA foreign_keys = ON")
    mine = conn.execute("SELECT key FROM sources WHERE origin = 'user'").fetchall()
    if mine:
        print("Leaving out your own sources: " + ", ".join(k for (k,) in mine))
        conn.execute("DELETE FROM sources WHERE origin = 'user'")
        conn.commit()
        db.cleanup(conn)
        conn.execute("VACUUM")
    one = lambda sql: conn.execute(sql).fetchone()[0]  # noqa: E731
    info = {"date": stamp, "schema": one("PRAGMA user_version"), "books": one("SELECT COUNT(*) FROM collections"),
            "hadith": one("SELECT COUNT(*) FROM hadiths"), "texts": one("SELECT COUNT(*) FROM texts"),
            "narrators": one("SELECT COUNT(*) FROM persons"), "grades": one("SELECT COUNT(*) FROM grades"),
            "sources": [k for (k,) in conn.execute("SELECT key FROM sources ORDER BY key")]}
    conn.close()

    target = release / f"isnady-db-{stamp}.zip"
    print(f"Zipping {copy.stat().st_size / 1e6:,.0f} MB …")
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        z.write(copy, "isnady.db")
    copy.unlink()
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    info.update(file=target.name, size=target.stat().st_size, sha256=digest,
                url=f"https://github.com/bayramkotan/isnady-data/releases/download/db-{stamp}/{target.name}")
    (repo / "database.json").write_text(json.dumps(info, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    derived = data / "derived"
    out = repo / "derived"
    if out.exists():
        shutil.rmtree(out)
    out.mkdir()
    n = 0
    for f in sorted(derived.glob("*.json")) if derived.exists() else []:
        shutil.copy2(f, out / f.name)
        n += 1
    ignore = repo / ".gitignore"
    lines = ignore.read_text(encoding="utf-8").splitlines() if ignore.exists() else []
    if "release/" not in lines:
        ignore.write_text("\n".join(lines + ["release/"]) + "\n", encoding="utf-8")
    print(f"{target} ({target.stat().st_size / 1e6:,.0f} MB, sha256 {digest[:12]}…): {info['books']} books, "
          f"{info['hadith']:,} hadith, {info['texts']:,} texts, {info['narrators']:,} narrators; "
          f"{n} saved computations in derived/")
    print(f"tag db-{stamp}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
