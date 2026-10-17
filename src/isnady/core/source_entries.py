"""The entries of the classical biographical works, in their own words (BIO2b, 2026-10-18).

Bayram (2026-10-17), on the lives written for isnady: "Nereden alıyorsun bu bilgileri?" The written lives are
summaries; this module lets each of them be read beside the entry of the work it is summarised from, as the
author wrote it. Today: al-Dhahabi's Siyar A'lam al-Nubala' (the Risala edition, in the OpenITI corpus), whose
entries are numbered within each volume ("vol. 2, no. 126" is Abu Hurayra). The work is downloaded once, on request
(about 22 MB), split into its entries and kept in the data folder (sources/<work>.db) — shared by every profile,
never published (like the Taqrib: OpenITI gives no licence, so it stays on this computer).

Which entry belongs to which written life is a hand-checked table (assets/sources/lives.json); nothing is guessed.
"""

from __future__ import annotations

import json
import re
import sqlite3
from functools import lru_cache
from importlib import resources
from pathlib import Path

from isnady.data.paths import data_dir

WORKS = {
    "siyar": {
        "title": {"en": "al-Dhahabi, Siyar A'lam al-Nubala'", "tr": "Zehebî, Siyeru a'lâmi'n-nübelâ",
                  "ar": "الذهبي، سير أعلام النبلاء"},
        "url": "https://raw.githubusercontent.com/OpenITI/0750AH/master/data/0748Dhahabi/0748Dhahabi.SiyarAclamNubala/"
               "0748Dhahabi.SiyarAclamNubala.Shamela0010906-ara1.mARkdown",
        "page": "https://github.com/OpenITI/0750AH/tree/master/data/0748Dhahabi/0748Dhahabi.SiyarAclamNubala",
        "size_mb": 22,
    },
}
_HEAD = re.compile(r"^### \$+ (\d+) -\s*(.*)$", re.M)
_PAGE = re.compile(r"PageV(\d+)P(\d+)")
_MARKUP = re.compile(r"PageV\d+P\d+|ms\d+|^~~|^#+ ?\|*|^# ", re.M)


def _db_path(work: str) -> Path:
    return data_dir() / "sources" / f"{work}.db"


def available(work: str) -> bool:
    path = _db_path(work)
    if not path.exists():
        return False
    try:
        conn = sqlite3.connect(path)
        try:
            return conn.execute("SELECT COUNT(*) FROM entries").fetchone()[0] > 0
        finally:
            conn.close()
    except sqlite3.Error:
        return False


def split(text: str) -> list[tuple[int, int, str, str]]:
    """(volume, number, heading, text) of every entry of an OpenITI file whose entries are "### $ N - heading"."""
    body = text.split("#META#Header#End#", 1)[-1]
    heads = list(_HEAD.finditer(body))
    out = []
    for i, m in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(body)
        chunk = body[m.end():end]
        page = _PAGE.search(body, m.start(), min(len(body), m.start() + 200000))
        volume = int(page.group(1)) if page else 0
        chunk = re.sub(r"\n~~", " ", chunk)                 # a line the corpus wrapped: the same paragraph
        chunk = re.sub(r"\n# ", "\n", chunk)               # a new paragraph: a new line
        clean = _MARKUP.sub("", chunk)
        clean = re.sub(r"[ \t]+", " ", clean)
        clean = re.sub(r"\n\s*\n+", "\n\n", clean).strip()
        heading = re.sub(r"\s+", " ", _MARKUP.sub("", m.group(2))).strip(" *")
        out.append((volume, int(m.group(1)), heading, clean))
    return out


def fetch(work: str, progress=None, location: str | None = None) -> int:
    """Download a work (or read it from a file, location) and keep its entries; returns how many."""
    from isnady.data.fetch import read_bytes

    say = progress or (lambda _m: None)
    info = WORKS[work]
    say(f"Downloading {info['title']['en']} (about {info['size_mb']} MB)")
    raw = read_bytes(location or info["url"], timeout=600)
    say("Reading the entries")
    entries = split(raw.decode("utf-8", "replace"))
    path = _db_path(work)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    if tmp.exists():
        tmp.unlink()
    conn = sqlite3.connect(tmp)
    conn.execute("CREATE TABLE entries (volume INTEGER, number INTEGER, heading TEXT, text TEXT, "
                 "PRIMARY KEY (volume, number))")
    conn.executemany("INSERT OR IGNORE INTO entries VALUES (?, ?, ?, ?)", entries)
    conn.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
    conn.execute("INSERT INTO meta VALUES ('source', ?)", (location or info["url"],))
    conn.commit()
    conn.close()
    tmp.replace(path)
    return len(entries)


def entry(work: str, volume: int, number: int) -> dict | None:
    """{"heading", "text", "volume", "number"} of one entry, or None (not downloaded, or no such entry)."""
    path = _db_path(work)
    if not path.exists():
        return None
    try:
        conn = sqlite3.connect(path)
        try:
            row = conn.execute("SELECT heading, text FROM entries WHERE volume = ? AND number = ?",
                               (volume, number)).fetchone()
        finally:
            conn.close()
    except sqlite3.Error:
        return None
    return {"heading": row[0], "text": row[1], "volume": volume, "number": number} if row else None


@lru_cache(maxsize=1)
def _table() -> dict:
    try:
        path = resources.files("isnady.assets").joinpath("sources", "lives.json")
        return json.loads(path.read_text(encoding="utf-8")).get("works", {})
    except (OSError, ValueError, ModuleNotFoundError):
        return {}


def of_life(life_id: str) -> list[dict]:
    """The entries of the classical works a written life is summarised from: [{"work", "volume", "number"}]."""
    out = []
    for work, lives in _table().items():
        where = lives.get(life_id)
        if where and work in WORKS:
            out.append({"work": work, "volume": where[0], "number": where[1]})
    return out


def title(work: str, lang: str = "en") -> str:
    names = WORKS[work]["title"]
    return names.get(lang) or names["en"]
