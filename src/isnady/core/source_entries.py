"""The entries of the classical biographical works, in their own words (BIO2b, 2026-10-18).

Bayram (2026-10-17), on the lives written for isnady: "Nereden alıyorsun bu bilgileri?" The written lives are
summaries; this module lets each of them be read beside the entry of the work it is summarised from, as the
author wrote it. Today: al-Dhahabi's Siyar A'lam al-Nubala' (the Risala edition, in the OpenITI corpus), whose
entries are numbered within each volume ("vol. 2, no. 126" is Abu Hurayra); and al-Dhahabi's Tadhkirat al-Huffaz
(HFZ1), numbered through the whole work. The work is downloaded once, on request (about 22 MB) — from isnady-data,
which keeps both (LIB1), else from the OpenITI corpus — split into its entries and kept in the data folder
(sources/<work>.db), shared by every profile. Imported in Data sources, the same work is also a book to read in Books
(data.importers.openiti_work), and its entries are kept here at the same time.

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
    # al-Dhahabi's Tadhkirat al-Huffaz (HFZ1): 1,176 huffaz in 21 generations, numbered through the whole work
    "tadhkira": {
        "title": {"en": "al-Dhahabi, Tadhkirat al-Huffaz", "tr": "Zehebî, Tezkiretü'l-huffâz",
                  "ar": "الذهبي، تذكرة الحفاظ"},
        "url": "https://raw.githubusercontent.com/OpenITI/0750AH/master/data/0748Dhahabi/0748Dhahabi.TadhkiratHuffaz/"
               "0748Dhahabi.TadhkiratHuffaz.JK000532-ara1.mARkdown",
        "page": "https://github.com/OpenITI/0750AH/tree/master/data/0748Dhahabi/0748Dhahabi.TadhkiratHuffaz",
        "size_mb": 3,
        "numbered": "whole",          # one numbering for the whole work: every entry is kept as volume 0
    },
}
_HEAD = re.compile(r"^### \$+ (\d+)\s*-?\s*(.*)$", re.M)          # "### $ 126 - heading" (Siyar), "### $ 16 ع heading"
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


def split(text: str, whole: bool = False) -> list[tuple[int, int, str, str]]:
    """(volume, number, heading, text) of every entry of an OpenITI file whose entries are "### $ N - heading";
    whole: the work numbers its entries through all its volumes (every entry is volume 0)."""
    body = text.split("#META#Header#End#", 1)[-1]
    heads = list(_HEAD.finditer(body))
    out = []
    for i, m in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(body)
        chunk = body[m.end():end]
        page = _PAGE.search(body, m.start(), min(len(body), m.start() + 200000))
        volume = 0 if whole else (int(page.group(1)) if page else 0)
        chunk = re.sub(r"\n~~", " ", chunk)                 # a line the corpus wrapped: the same paragraph
        chunk = re.sub(r"\n# ", "\n", chunk)               # a new paragraph: a new line
        clean = _MARKUP.sub("", chunk)
        clean = re.sub(r"[ \t]+", " ", clean)
        clean = re.sub(r"\n\s*\n+", "\n\n", clean).strip()
        heading = re.sub(r"\s+", " ", _MARKUP.sub("", m.group(2))).strip(" *")
        out.append((volume, int(m.group(1)), heading, clean))
    return out


def _own_location(work: str) -> str | None:
    """Where isnady-data keeps this work (its catalog's library), or None."""
    try:
        from isnady.core import repositories as R

        for repo in (R.selected(), R.find(R.DEFAULT_ID)):
            if repo is None:
                continue
            cat, _where = R.catalog(repo)
            for item in cat.get("library", []):
                if item.get("entries") == work and item.get("location"):
                    return R.absolute(R.base_of(repo), item["location"])
    except Exception:  # noqa: BLE001 — the corpus is read instead
        return None
    return None


def fetch(work: str, progress=None, location: str | None = None) -> int:
    """Download a work (or read it from a file, location) and keep its entries; returns how many. From isnady-data
    first (LIB1), from the OpenITI corpus when isnady-data cannot give it."""
    from isnady.data.fetch import read_bytes

    say = progress or (lambda _m: None)
    info = WORKS[work]
    say(f"Downloading {info['title']['en']} (about {info['size_mb']} MB)")
    places = [location] if location else [p for p in (_own_location(work), info["url"]) if p]
    raw, last = None, None
    for place in places:
        try:
            raw = read_bytes(place, timeout=600)
            location = place
            break
        except Exception as exc:  # noqa: BLE001
            last = exc
    if raw is None:
        raise last  # type: ignore[misc]
    return store(work, raw.decode("utf-8", "replace"), location, say)


def store(work: str, text: str, location: str, progress=None) -> int:
    """Keep the entries of a work's text (already read); returns how many."""
    say = progress or (lambda _m: None)
    info = WORKS[work]
    say("Reading the entries")
    entries = split(text, whole=info.get("numbered") == "whole")
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
    conn.execute("INSERT INTO meta VALUES ('source', ?)", (location,))
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
