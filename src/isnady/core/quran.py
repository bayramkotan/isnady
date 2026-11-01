"""The Qur'an (Q1, Q1b) and the verses the hadith name (Q2, GEN1-H2).

Where the text comes from: isnady-data first — isnady's own repository keeps the Arabic (Tanzil's text, verbatim) and
a chosen set of translations under the names their readers know them by, listed in the "quran" section of its
catalog. Any other translation, of the 98 languages, is read from fawazahmed0/quran-api (the same author as the
hadith editions; the Unlicense; each edition names its own source: Tanzil, the King Fahd Complex, QuranEnc …), and a
text isnady-data cannot give at the moment is read from there too. Nothing is bundled: it is downloaded on request
into sources/quran.db in the data folder.

Verses named in the hadith: the translations of the hadith mark a verse they quote as "(33:33)", "[43:67]",
"(Al-Qur'an 66:1)" or "(Ahzab 33/51)". These marks are read, each checked against the number of verses of its
sura, and kept as the hadith's verse — what the translation says, not a reading of isnady's own.
"""

import hashlib
import json
import re
import sqlite3
from functools import lru_cache
from pathlib import Path

from isnady.data.paths import data_dir

BASE = "https://raw.githubusercontent.com/fawazahmed0/quran-api/1"
PAGE = "https://github.com/fawazahmed0/quran-api"
OWN_PAGE = "https://github.com/bayramkotan/isnady-data"
OWN, SOURCE = "isnady-data", "fawazahmed0/quran-api"     # where an edition is read from
ARABIC = "ara-quransimple"                # Tanzil's simple script: every Arabic face draws it, search reads it
DEFAULTS = {"tr": ["tur-diyanetisleri"], "en": ["eng-ummmuhammad"], "ar": []}     # kept for older callers
# the translation each language starts with (Q1d): the one its readers know best, kept in isnady-data
DEFAULT_OF = {
    "Turkish": "tur-diyanetisleri", "English": "eng-ummmuhammad", "Urdu": "urd-fatehmuhammadja",
    "Indonesian": "ind-indonesianislam", "Bengali": "ben-muhiuddinkhan", "French": "fra-muhammadhamidul",
    "Russian": "rus-elmirkuliev", "Tamil": "tam-janturstfoundat", "German": "deu-asfbubenheimand",
    "Persian": "fas-hussainansarian", "Spanish": "spa-juliocortes", "Bosnian": "bos-besimkorkut",
    "Albanian": "sqi-sherifahmeti", "Azerbaijani": "aze-vasimmammadaliy", "Uzbek": "uzb-muhammadsodikmu",
    "Kazakh": "kaz-khalifahaltai", "Tatar": "tat-yakubibnnugman", "Malay": "msa-abdullahmuhamma"}


def wanted_languages() -> list[str]:
    """The languages the reader reads (Q1d, Bayram 2026-11-01: an English translation shown to a Turkish
    interface): the interface language first, then the content languages chosen (View → Content), Arabic aside."""
    from isnady.core import i18n, language

    out = [i18n.LANGUAGES.get(language.ui_language(), ("", "English", False))[1]]
    out += language.content_languages()
    return [lang for lang in dict.fromkeys(out) if lang and lang != "Arabic"]


def default_editions() -> list[str]:
    """The translations downloaded with the Arabic: one in each language the reader reads."""
    return [DEFAULT_OF[lang] for lang in wanted_languages() if lang in DEFAULT_OF] or [DEFAULT_OF["English"]]


def missing_languages() -> list[str]:
    """The languages the reader reads that have no translation downloaded yet (and one isnady-data keeps)."""
    have = {e["language"] for e in editions()}
    return [lang for lang in wanted_languages() if lang in DEFAULT_OF and lang not in have]


def shown(saved: str | None) -> list[str]:
    """The translations shown beside the Arabic. saved: the reader's own choice ("quran.editions"; "," = none);
    None (never chosen): those downloaded in the languages the reader reads, the interface language first."""
    have = [e for e in editions() if e["key"] != ARABIC]
    keys = [e["key"] for e in have]
    if saved is not None:
        return [k for k in str(saved).split(",") if k in keys]
    out = []
    for lang in wanted_languages():
        mine = [e["key"] for e in have if e["language"] == lang]
        mine.sort(key=lambda k: k != DEFAULT_OF.get(lang))
        out += mine[:1]
    return out or keys[:1]

# the suras' names in Turkish, as the Diyanet gives them
TR_NAMES = (
    "Fâtiha", "Bakara", "Âl-i İmrân", "Nisâ", "Mâide", "En'âm", "A'râf", "Enfâl", "Tevbe", "Yûnus", "Hûd", "Yûsuf",
    "Ra'd", "İbrâhîm", "Hicr", "Nahl", "İsrâ", "Kehf", "Meryem", "Tâhâ", "Enbiyâ", "Hac", "Mü'minûn", "Nûr", "Furkân",
    "Şuarâ", "Neml", "Kasas", "Ankebût", "Rûm", "Lokmân", "Secde", "Ahzâb", "Sebe'", "Fâtır", "Yâsîn", "Sâffât", "Sâd",
    "Zümer", "Mü'min", "Fussilet", "Şûrâ", "Zuhruf", "Duhân", "Câsiye", "Ahkâf", "Muhammed", "Fetih", "Hucurât", "Kâf",
    "Zâriyât", "Tûr", "Necm", "Kamer", "Rahmân", "Vâkıa", "Hadîd", "Mücâdele", "Haşr", "Mümtehine", "Saf", "Cuma",
    "Münâfikûn", "Teğâbün", "Talâk", "Tahrîm", "Mülk", "Kalem", "Hâkka", "Meâric", "Nûh", "Cin", "Müzzemmil",
    "Müddessir", "Kıyâme", "İnsân", "Mürselât", "Nebe'", "Nâziât", "Abese", "Tekvîr", "İnfitâr", "Mutaffifîn",
    "İnşikâk", "Bürûc", "Târık", "A'lâ", "Gâşiye", "Fecr", "Beled", "Şems", "Leyl", "Duhâ", "İnşirâh", "Tîn", "Alak",
    "Kadr", "Beyyine", "Zilzâl", "Âdiyât", "Kâria", "Tekâsür", "Asr", "Hümeze", "Fîl", "Kureyş", "Mâûn", "Kevser",
    "Kâfirûn", "Nasr", "Tebbet", "İhlâs", "Felak", "Nâs")


def _log():
    from isnady.core import log

    return log.get("quran")


def path() -> Path:
    return data_dir() / "sources" / "quran.db"


def _connect() -> sqlite3.Connection:
    p = path()
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(p)
    conn.execute("CREATE TABLE IF NOT EXISTS suras (n INTEGER PRIMARY KEY, name TEXT, english TEXT, arabic TEXT, "
                 "place TEXT, verses INTEGER)")
    conn.execute("CREATE TABLE IF NOT EXISTS editions (key TEXT PRIMARY KEY, language TEXT, author TEXT, "
                 "direction TEXT, source TEXT, comments TEXT, imported_at TEXT)")
    conn.execute("CREATE TABLE IF NOT EXISTS verses (edition TEXT, sura INTEGER, ayah INTEGER, text TEXT, "
                 "PRIMARY KEY (edition, sura, ayah))")
    if "origin" not in {r[1] for r in conn.execute("PRAGMA table_info(editions)")}:
        conn.execute("ALTER TABLE editions ADD COLUMN origin TEXT")        # Q1b: isnady-data or the source
    return conn


def available() -> bool:
    """The Arabic text is downloaded."""
    if not path().exists():
        return False
    try:
        conn = sqlite3.connect(path())
        n = conn.execute("SELECT COUNT(*) FROM verses WHERE edition = ?", (ARABIC,)).fetchone()[0]
        conn.close()
        return n > 6000
    except sqlite3.Error:
        return False


# ------------------------------------------------------------------ where the text is read from (Q1b)
def own() -> tuple[dict, str] | None:
    """(the "quran" section of isnady-data's catalog, what its locations are relative to), or None when the
    repository chosen and isnady-data have none."""
    from isnady.core import repositories as R

    seen = set()
    for repo in [R.selected(), R.find(R.DEFAULT_ID)]:
        if repo is None or repo.id in seen:
            continue
        seen.add(repo.id)
        try:
            cat, _where = R.catalog(repo)
        except Exception:  # noqa: BLE001 — the source is read instead
            continue
        q = cat.get("quran")
        if isinstance(q, dict) and q.get("editions"):
            return q, R.base_of(repo)
    return None


def _own_editions() -> tuple[dict[str, dict], dict | None, str]:
    found = own()
    if found is None:
        return {}, None, ""
    q, base = found
    from isnady.core.repositories import absolute

    out = {}
    for e in q["editions"]:
        out[e["key"]] = {"language": e.get("language", ""), "author": e.get("author", e["key"]),
                         "direction": e.get("direction", "ltr"), "source": e.get("source", ""),
                         "comments": e.get("comments", ""), "origin": OWN, "size": e.get("size"),
                         "sha256": e.get("sha256"), "url": absolute(base, e["location"])}
    return out, q, base


def _source_editions() -> dict[str, dict]:
    from isnady.data.fetch import read_bytes

    raw = json.loads(read_bytes(f"{BASE}/editions.json", timeout=120))
    return {v["name"]: {**{k: v.get(k, "") for k in ("language", "author", "direction", "source", "comments")},
                        "origin": SOURCE, "url": f"{BASE}/editions/{v['name']}.min.json"}
            for v in raw.values()}


def catalog(progress=None, source: bool = True) -> dict[str, dict]:
    """Every edition there is to download: {key: {language, author, direction, source, comments, origin, url}} —
    isnady-data's first, then (source=True) the rest of fawazahmed0/quran-api's. Raises only when neither is read."""
    say = progress or (lambda _m: None)
    say("Reading the list of translations")
    mine, _q, _base = _own_editions()
    out = dict(mine)
    if source:
        try:
            for key, v in _source_editions().items():
                out.setdefault(key, v)
        except Exception as exc:  # noqa: BLE001
            _log().warning("The list of %s could not be read: %s", SOURCE, exc)
            if not mine:
                raise
    if mine:
        _rename(mine)
    return out


def _rename(mine: dict[str, dict]) -> None:
    """The translations downloaded before keep their text but take the names isnady-data gives them."""
    if not path().exists():
        return
    try:
        conn = _connect()
        conn.executemany("UPDATE editions SET author = ? WHERE key = ? AND author != ?",
                         [(v["author"], k, v["author"]) for k, v in mine.items()])
        changed = conn.total_changes
        conn.commit()
        conn.close()
        if changed:
            _cached.cache_clear()
    except sqlite3.Error:
        pass


def _verses_of(data: dict) -> list[tuple[int, int, str]]:
    if "verses" in data:                                   # isnady-quran/1
        return [(int(s), int(a), t) for s, a, t in data["verses"]]
    return [(v["chapter"], v["verse"], v["text"]) for v in data["quran"]]


def _read(about: dict, key: str) -> tuple[list, str]:
    """The verses of an edition and where they came from: its own address first, the source's after."""
    from isnady.data.fetch import read_bytes

    tries = [(about.get("url") or f"{BASE}/editions/{key}.min.json", about.get("origin", SOURCE), about.get("sha256"))]
    if about.get("origin") == OWN:
        tries.append((f"{BASE}/editions/{key}.min.json", SOURCE, None))
    last = None
    for url, origin, sha in tries:
        try:
            raw = read_bytes(url, timeout=600)
            if sha and hashlib.sha256(raw).hexdigest() != sha:
                raise ValueError(f"{url}: the file is not the one the catalog lists (sha256)")
            rows = _verses_of(json.loads(raw.decode("utf-8-sig")))
            if len(rows) < 6000:
                raise ValueError(f"{url}: {len(rows)} verses")
            return rows, origin
        except Exception as exc:  # noqa: BLE001 — the next place is tried, the last error said
            _log().warning("Qur'an text %s not read from %s: %s", key, url, exc)
            last = exc
    raise last  # type: ignore[misc]


def _suras_rows(q: dict | None, base: str) -> list[tuple]:
    from isnady.data.fetch import read_bytes

    if q and q.get("suras"):
        from isnady.core.repositories import absolute

        try:
            data = json.loads(read_bytes(absolute(base, q["suras"]), timeout=120))
            return [(x["n"], x["name"], x["english"], x["arabic"], x["place"], x["verses"]) for x in data["suras"]]
        except Exception as exc:  # noqa: BLE001
            _log().warning("The suras not read from %s: %s", OWN, exc)
    meta = json.loads(read_bytes(f"{BASE}/info.json", timeout=120))
    return [(c["chapter"], c["name"], c["englishname"], c["arabicname"], c["revelation"], len(c["verses"]))
            for c in meta["chapters"]]


def fetch(editions: list[str] | None = None, progress=None, info: dict | None = None) -> list[str]:
    """Download the Arabic (once) and these editions (keys as "tur-diyanetisleri"); returns the keys kept. A text
    that cannot be read is said (progress, the log) and the others are still downloaded; raises only when none was."""
    from datetime import datetime, timezone

    say = progress or (lambda _m: None)
    conn = _connect()
    try:
        mine, q, base = _own_editions()
        if not conn.execute("SELECT COUNT(*) FROM suras").fetchone()[0]:
            say("Reading the suras")
            conn.executemany("INSERT OR REPLACE INTO suras VALUES (?, ?, ?, ?, ?, ?)", _suras_rows(q, base))
            conn.commit()
        wanted = ([ARABIC] if not available() else []) + [e for e in dict.fromkeys(editions or []) if e != ARABIC]
        info = {**(info or {}), **mine}
        if any(e not in info for e in wanted):
            try:
                info = {**_source_editions(), **info}
            except Exception as exc:  # noqa: BLE001
                _log().warning("The list of %s could not be read: %s", SOURCE, exc)
        kept, failed = [], []
        for key in wanted:
            about = info.get(key)
            if about is None:
                say(f"No translation '{key}'")
                failed.append(f"{key}: not listed")
                continue
            say(f"Downloading {about['language']} — {about['author']}")
            try:
                rows, origin = _read(about, key)
            except Exception as exc:  # noqa: BLE001
                failed.append(f"{about['author']}: {exc}")
                say(f"Not downloaded: {about['author']} ({exc})")
                continue
            conn.execute("DELETE FROM verses WHERE edition = ?", (key,))
            conn.executemany("INSERT OR REPLACE INTO verses VALUES (?, ?, ?, ?)", [(key, s, a, t) for s, a, t in rows])
            conn.execute("INSERT OR REPLACE INTO editions (key, language, author, direction, source, comments, "
                         "imported_at, origin) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                         (key, about["language"], about["author"], about.get("direction") or "ltr",
                          about.get("source") or "", about.get("comments") or "",
                          datetime.now(timezone.utc).isoformat(timespec="seconds"), origin))
            conn.commit()
            kept.append(key)
            _log().info("Qur'an text %s downloaded from %s", key, origin)
        _cached.cache_clear()
        if failed and not kept:
            raise RuntimeError("; ".join(failed))
        return kept
    finally:
        conn.close()


def remove(edition: str) -> bool:
    if edition == ARABIC or not path().exists():
        return False
    conn = _connect()
    n = conn.execute("DELETE FROM verses WHERE edition = ?", (edition,)).rowcount
    conn.execute("DELETE FROM editions WHERE key = ?", (edition,))
    conn.commit()
    conn.close()
    _cached.cache_clear()
    return n > 0


@lru_cache(maxsize=1)
def _cached() -> tuple[list[dict], list[dict]]:
    if not path().exists():
        return [], []
    conn = _connect()
    suras = [{"n": n, "name": name, "english": english, "arabic": arabic, "place": place, "verses": verses,
              "tr": TR_NAMES[n - 1] if 0 < n <= len(TR_NAMES) else name}
             for n, name, english, arabic, place, verses in conn.execute("SELECT * FROM suras ORDER BY n")]
    eds = [{"key": k, "language": lang, "author": author, "direction": d, "source": s, "comments": c,
            "origin": o or SOURCE}
           for k, lang, author, d, s, c, o in conn.execute(
               "SELECT key, language, author, direction, source, comments, origin FROM editions "
               "ORDER BY language, author")]
    conn.close()
    return suras, eds


def suras() -> list[dict]:
    return _cached()[0]


def editions() -> list[dict]:
    """The editions downloaded, the Arabic first."""
    eds = _cached()[1]
    return sorted(eds, key=lambda e: (e["key"] != ARABIC, e["language"], e["author"]))


def sura_name(n: int, lang: str = "en") -> str:
    s = next((x for x in suras() if x["n"] == n), None)
    if s is None:
        return TR_NAMES[n - 1] if lang == "tr" and 0 < n <= 114 else str(n)
    return {"tr": s["tr"], "ar": s["arabic"]}.get(lang) or s["name"]


def verses(sura: int, editions_: list[str] | None = None, start: int = 1, end: int | None = None) -> list[dict]:
    """[{ayah, texts: {edition: text}}] of a sura (or of its verses start..end)."""
    if not path().exists():
        return []
    keys = [ARABIC] + [e for e in (editions_ or []) if e != ARABIC]
    conn = _connect()
    rows = conn.execute(
        f"SELECT ayah, edition, text FROM verses WHERE sura = ? AND ayah BETWEEN ? AND ? AND edition IN "
        f"({','.join('?' * len(keys))}) ORDER BY ayah", (sura, start, end or 999, *keys)).fetchall()
    conn.close()
    out: dict[int, dict] = {}
    for ayah, edition, text in rows:
        out.setdefault(ayah, {"ayah": ayah, "texts": {}})["texts"][edition] = text
    return [out[a] for a in sorted(out)]


def search(text: str, editions_: list[str] | None = None, limit: int = 200) -> list[dict]:
    """Verses holding every word (Arabic without its vowels; Latin letters without case and accents):
    [{sura, ayah, edition, text}] in the order of the mushaf."""
    from isnady.core.narrators import fold_latin
    from isnady.core.normalize import normalize

    words = [w for w in text.split() if w]
    if not words or not path().exists():
        return []
    keys = [ARABIC] + [e for e in (editions_ or [e["key"] for e in editions()]) if e != ARABIC]
    arabic = any("؀" <= ch <= "ۿ" for ch in text)
    conn = _connect()
    rows = conn.execute(f"SELECT sura, ayah, edition, text FROM verses WHERE edition IN ({','.join('?' * len(keys))}) "
                        "ORDER BY sura, ayah", keys).fetchall()
    conn.close()
    out = []
    wanted = [normalize(w) for w in words] if arabic else [fold_latin(w) for w in words]
    for sura, ayah, edition, t in rows:
        if (edition == ARABIC) != arabic:
            continue
        hay = normalize(t) if arabic else fold_latin(t)
        if all(w in hay for w in wanted):
            out.append({"sura": sura, "ayah": ayah, "edition": edition, "text": t})
            if len(out) >= limit:
                break
    return out


# ------------------------------------------------------------------ the verses the hadith name (Q2, GEN1-H2)
VERSES_IN = (7, 286, 200, 176, 120, 165, 206, 75, 129, 109, 123, 111, 43, 52, 99, 128, 111, 110, 98, 135, 112, 78,
             118, 64, 77, 227, 93, 88, 69, 60, 34, 30, 73, 54, 45, 83, 182, 88, 75, 85, 54, 53, 89, 59, 37, 35, 38,
             29, 18, 45, 60, 49, 62, 55, 78, 96, 29, 22, 24, 13, 14, 11, 11, 18, 12, 12, 30, 52, 52, 44, 28, 28, 20,
             56, 40, 31, 50, 40, 46, 42, 29, 19, 36, 25, 22, 17, 19, 26, 30, 20, 15, 21, 11, 8, 8, 19, 5, 8, 8, 11,
             11, 8, 3, 9, 5, 4, 7, 3, 6, 3, 5, 4, 5, 6)       # the verses of each sura (Hafs), to check a mark

_MARK = re.compile(r"[\(\[]\s*(?:(?P<name>[^\d\(\)\[\]\n]{2,30}?)[,]?\s*)?(?P<s>\d{1,3})\s*(?P<sep>[:/])\s*"
                   r"(?P<a>\d{1,3})(?:\s*[-–]\s*(?P<b>\d{1,3}))?\s*[\)\]]")


def marks_in(text: str) -> list[tuple[int, int, int]]:
    """(sura, first verse, last verse) of each verse a translation marks: "(33:33)", "[23:99-100]", "(Ahzab 33/51)".
    A slash counts only after a sura's name (a bare "(1/2)" is a fraction); every number is checked against the sura."""
    out = []
    for m in _MARK.finditer(text or ""):
        s, a = int(m["s"]), int(m["a"])
        b = int(m["b"]) if m["b"] else a
        if m["sep"] == "/" and not (m["name"] and re.search(r"[A-Za-zÀ-ÿĞğİıŞş]{3}", m["name"])):
            continue
        if 1 <= s <= 114 and 1 <= a <= b <= VERSES_IN[s - 1] and b - a < 30:
            out.append((s, a, b))
    return out


def _cites_counted(conn: sqlite3.Connection) -> dict:
    by_hadith: dict[int, list] = {}
    by_verse: dict[str, list] = {}
    for hid, text in conn.execute(
            "SELECT t.hadith_id, t.text FROM texts t JOIN editions e ON e.id = t.edition_id "
            "WHERE e.language IN ('English', 'Turkish') AND (t.text LIKE '%:%' OR t.text LIKE '%/%')"):
        for s, a, b in marks_in(text):
            ref = (s, a, b)
            if ref not in by_hadith.setdefault(hid, []):
                by_hadith[hid].append(ref)
                for v in range(a, b + 1):
                    by_verse.setdefault(f"{s}:{v}", []).append(hid)
    return {"hadith": {str(k): v for k, v in by_hadith.items()}, "verse": by_verse}


def cites(conn: sqlite3.Connection) -> dict:
    """{"hadith": {hadith id: [(sura, from, to)]}, "verse": {"s:a": [hadith ids]}}, counted once per change of the
    database (core.cache) — about a second."""
    from isnady.core import cache

    return cache.kept(conn, "quran-cites", _cites_counted)


def verses_of(conn: sqlite3.Connection, hadith_id: int) -> list[tuple[int, int, int]]:
    return [tuple(x) for x in cites(conn)["hadith"].get(str(hadith_id), [])]


def hadith_of(conn: sqlite3.Connection, sura: int, ayah: int) -> list[int]:
    return list(dict.fromkeys(cites(conn)["verse"].get(f"{sura}:{ayah}", [])))


def counts_by_sura(conn: sqlite3.Connection) -> dict[int, int]:
    """How many hadith name a verse of each sura."""
    out: dict[int, set] = {}
    for key, hids in cites(conn)["verse"].items():
        out.setdefault(int(key.split(":")[0]), set()).update(hids)
    return {s: len(h) for s, h in out.items()}


def label(sura: int, a: int, b: int, lang: str = "en") -> str:
    return f"{sura_name(sura, lang)} {sura}:{a}" + (f"-{b}" if b != a else "")
