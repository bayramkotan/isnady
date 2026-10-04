"""Sources isnady knows about, and sources the user adds.

BUILT-IN entries are defined here: the hadith collections of the open
fawazahmed0/hadith-api (one entry per book, the languages chosen at import)
and Ibn Hajar's Taqrib al-Tahdhib from OpenITI. They are imported from the
network with one click (or `iy catalog import ID`).

USER entries (User Resources) are kept in user_sources.json in the data
folder: a title, a format, a file or URL, a licence and the KIND of
authentication. Credentials are never stored; they are asked for at import.
"""

import json
import re
import sqlite3
import uuid
from dataclasses import asdict, dataclass, field

from isnady.core.imports import ImportRequest, remove_source, run_import, run_many
from isnady.data import db
from isnady.data.fetch import Auth
from isnady.data.paths import data_dir

FAWAZ_INDEX = "https://cdn.jsdelivr.net/gh/fawazahmed0/hadith-api@1/editions.json"
FAWAZ_SOURCE = "fawazahmed0/hadith-api"
FAWAZ_KEY = "fawazahmed0-hadith-api"
NAJASHI_URL = ("https://raw.githubusercontent.com/OpenITI/0450AH/master/data/0450Najashi/0450Najashi.Rijal/"
               "0450Najashi.Rijal.Shia002931-ara1.mARkdown")
TAQRIB_URL = ("https://raw.githubusercontent.com/OpenITI/0875AH/master/data/0852IbnHajarCasqalani/"
              "0852IbnHajarCasqalani.TaqribTahdhib/0852IbnHajarCasqalani.TaqribTahdhib.JK000121-ara1.completed")
TAQRIB_SOURCE = "Ibn Hajar, Taqrib al-Tahdhib (OpenITI)"

LANGUAGE_NAMES = {"ara": "Arabic", "tur": "Turkish", "eng": "English", "urd": "Urdu", "ind": "Indonesian",
                  "ben": "Bengali", "fra": "French", "rus": "Russian", "tam": "Tamil"}
# book key -> (title, languages offered by the source) as published in its editions.json
FAWAZ_BOOKS = {
    "bukhari": ("Sahih al-Bukhari", "ara tur eng urd ind ben fra rus tam"),
    "muslim": ("Sahih Muslim", "ara tur eng urd ind ben fra rus tam"),
    "abudawud": ("Sunan Abi Dawud", "ara tur eng urd ind ben fra rus"),
    "tirmidhi": ("Jami' al-Tirmidhi", "ara tur eng urd ind ben"),
    "nasai": ("Sunan al-Nasa'i", "ara tur eng urd ind ben fra"),
    "ibnmajah": ("Sunan Ibn Majah", "ara tur eng urd ind ben fra"),
    "malik": ("Muwatta Malik", "ara tur eng urd ind ben fra"),
    "nawawi": ("Forty Hadith of al-Nawawi", "ara tur eng ben fra"),
    "qudsi": ("Forty Hadith Qudsi", "ara eng fra"),
    "dehlawi": ("Forty Hadith of Shah Waliullah Dehlawi", "ara eng fra"),
}
DEFAULT_LANGUAGES = ["ara", "tur", "eng"]


@dataclass
class Entry:
    id: str
    title: str
    kind: str                       # hadith | rijal
    format_id: str
    location: str
    description: str
    license: str | None
    source_name: str
    source_key: str
    book: str | None = None
    languages: list[str] = field(default_factory=list)       # offered
    builtin: bool = True
    auth_kind: str = "none"
    key_name: str | None = None
    key_in: str = "header"


def builtin_entries() -> list[Entry]:
    out = []
    for book, (title, langs) in FAWAZ_BOOKS.items():
        codes = langs.split()
        out.append(Entry(
            id=f"fawaz-{book}", title=title, kind="hadith", format_id="fawazahmed0", location=FAWAZ_INDEX,
            description=f"From fawazahmed0/hadith-api: Arabic text and translations ({', '.join(LANGUAGE_NAMES[c] for c in codes)}); "
                        "grades by scholar where the source gives them.",
            license="Unlicense", source_name=FAWAZ_SOURCE, source_key=FAWAZ_KEY, book=book, languages=codes))
    out.append(Entry(
        id="taqrib", title="Taqrib al-Tahdhib — Ibn Hajar al-'Asqalani", kind="rijal", format_id="taqrib",
        location=TAQRIB_URL,
        description="8,824 narrators of the six books with Ibn Hajar's verdict, rank, tabaqa, death year and book "
                    "marks; identifies the narrators in every chain. From the OpenITI corpus (licence not stated "
                    "there, so kept on this computer only).",
        license=None, source_name=TAQRIB_SOURCE, source_key="openiti-taqrib"))
    out.append(Entry(
        id="najashi", title="Rijal al-Najashi — al-Najashi (Shia)", kind="rijal", format_id="najashi",
        location=NAJASHI_URL,
        description="1,266 authors and narrators with al-Najashi's words, read on the Shia scale (thiqa, praised, "
                    "muwaththaq, weak; creed: Imami, Waqifi, Fathi, Zaydi …); readable in Books. From the OpenITI "
                    "corpus (licence not stated there, so kept on this computer only).",
        license=None, source_name="al-Najashi, Rijal (OpenITI)", source_key="openiti-najashi"))
    return out


# ------------------------------------------------------------------ user entries
def _user_file():
    return data_dir() / "user_sources.json"


def user_entries() -> list[Entry]:
    try:
        rows = json.loads(_user_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    out = []
    for r in rows if isinstance(rows, list) else []:
        try:
            out.append(Entry(**{**r, "builtin": False}))
        except TypeError:
            continue
    return out


def _save_user(entries: list[Entry]) -> None:
    rows = [{k: v for k, v in asdict(e).items() if k != "builtin"} for e in entries]
    path = _user_file()
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def add_user_entry(title: str, format_id: str, location: str, license: str | None = None,
                   auth_kind: str = "none", key_name: str | None = None, key_in: str = "header",
                   book: str | None = None) -> Entry:
    from isnady.data.importers.base import get_importer, slugify

    get_importer(format_id)                      # raises KeyError for an unknown format
    if not title.strip() or not location.strip():
        raise ValueError("A user source needs a title and a file or URL.")
    if auth_kind not in ("none", "basic", "bearer", "apikey"):
        raise ValueError("Authentication must be none, basic, bearer or apikey.")
    entry = Entry(id=f"user-{uuid.uuid4().hex[:8]}", title=title.strip(), kind="hadith", format_id=format_id,
                  location=location.strip(), description="Added by you.", license=(license or None),
                  source_name=title.strip(), source_key=slugify(title.strip()), book=book, builtin=False,
                  auth_kind=auth_kind, key_name=key_name, key_in=key_in)
    entries = user_entries()
    entries.append(entry)
    _save_user(entries)
    return entry


def delete_user_entry(entry_id: str) -> bool:
    entries = user_entries()
    kept = [e for e in entries if e.id != entry_id]
    _save_user(kept)
    return len(kept) != len(entries)


def all_entries() -> list[Entry]:
    return builtin_entries() + user_entries()


def find(entry_id: str) -> Entry | None:
    return next((e for e in all_entries() if e.id == entry_id), None)


# ------------------------------------------------------------------ status and actions
def status(conn: sqlite3.Connection, entry: Entry) -> dict:
    """What of this entry is in the database now."""
    src = conn.execute("SELECT id, imported_at, tier FROM sources WHERE key = ?", (entry.source_key,)).fetchone()
    if src is None:
        return {"imported": False, "languages": [], "when": None, "count": 0}
    if entry.book:
        langs = [r[0] for r in conn.execute(
            """SELECT DISTINCT e.language FROM editions e JOIN collections c ON c.id = e.collection_id
               WHERE e.source_id = ? AND c.key = ? ORDER BY e.language""", (src["id"], entry.book))]
        count = conn.execute(
            "SELECT COUNT(*) FROM hadiths h JOIN collections c ON c.id = h.collection_id WHERE c.key = ?",
            (entry.book,)).fetchone()[0]
        return {"imported": bool(langs), "languages": langs, "when": src["imported_at"], "count": count,
                "tier": src["tier"]}
    if entry.kind == "rijal":
        count = conn.execute("SELECT COUNT(*) FROM persons WHERE source_id = ?", (src["id"],)).fetchone()[0]
    else:
        count = conn.execute("SELECT COALESCE(SUM(text_count), 0) FROM editions WHERE source_id = ?",
                             (src["id"],)).fetchone()[0]
    return {"imported": True, "languages": [], "when": src["imported_at"], "count": count, "tier": src["tier"]}


def request_for(entry: Entry, languages: list[str] | None = None, auth: Auth | None = None) -> ImportRequest:
    options = {}
    if entry.book and entry.builtin:
        chosen = [c for c in (languages or DEFAULT_LANGUAGES) if c in entry.languages] or ["ara"]
        options = {"books": [entry.book], "languages": chosen}
    elif entry.book:
        options = {"books": [entry.book], "languages": list(languages or [])}
    return ImportRequest(format_id=entry.format_id, location=entry.location, name=entry.source_name,
                         license=entry.license, origin="builtin" if entry.builtin else "user",
                         auth=auth or Auth(), options=options)


def import_all(conn: sqlite3.Connection, languages: dict[str, list[str]] | list[str] | None = None, progress=None):
    """Every built-in source: hadith collections first, then the rijal works that identify their narrators.

    languages: one list for every book, or {entry id: [codes]}; missing = the defaults.
    """
    entries = sorted(builtin_entries(), key=lambda e: e.kind != "hadith")
    requests = []
    for e in entries:
        langs = languages.get(e.id) if isinstance(languages, dict) else languages
        requests.append((e.title, request_for(e, langs)))
    return run_many(conn, requests, progress)


def import_entry(conn: sqlite3.Connection, entry: Entry, languages: list[str] | None = None,
                 auth: Auth | None = None, progress=None):
    # a user's own file: its language comes from the file itself, never from our defaults (request_for)
    return run_import(conn, request_for(entry, languages, auth), progress)


def remove_entry(conn: sqlite3.Connection, entry: Entry) -> bool:
    """Remove what this entry imported (for one book of a shared source: that book only)."""
    src = conn.execute("SELECT id FROM sources WHERE key = ?", (entry.source_key,)).fetchone()
    if src is None:
        return False
    if entry.book:
        with conn:
            removed = conn.execute(
                """DELETE FROM editions WHERE source_id = ? AND collection_id IN
                   (SELECT id FROM collections WHERE key = ?)""", (src["id"], entry.book)).rowcount
            conn.execute("DELETE FROM grades WHERE source_id = ? AND hadith_id IN (SELECT h.id FROM hadiths h "
                         "JOIN collections c ON c.id = h.collection_id WHERE c.key = ?)", (src["id"], entry.book))
            conn.execute("DELETE FROM isnads WHERE source_id = ? AND hadith_id IN (SELECT h.id FROM hadiths h "
                         "JOIN collections c ON c.id = h.collection_id WHERE c.key = ?)", (src["id"], entry.book))
            if not conn.execute("SELECT 1 FROM editions WHERE source_id = ?", (src["id"],)).fetchone():
                conn.execute("DELETE FROM sources WHERE id = ?", (src["id"],))
        db.cleanup(conn)
        return bool(removed)
    return remove_source(conn, entry.source_key)


def language_label(code: str) -> str:
    return LANGUAGE_NAMES.get(code, code)


def code_for(language_name_or_code: str) -> str:
    v = language_name_or_code.strip().lower()
    return next((c for c, n in LANGUAGE_NAMES.items() if n.lower() == v), v if re.fullmatch(r"[a-z]{3}", v) else v)
