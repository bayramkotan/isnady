"""Where the roads of a tahwil meet, when the text does not name the place (ISN-TAH, 2026-10-25).

A tahwil ("ح") says the roads become one: "حدثنا مسدد، حدثنا يحيى، ح وحدثنا محمد بن المثنى، حدثنا خالد، عن هشام بن
أبي عبد الله، عن قتادة …" — Yahya's road goes on with the rest of the second, but the text does not say from whom Yahya
heard it. A muhaddith knows it from the narrators: Yahya al-Qattan narrates from Hisham al-Dastuwa'i. isnady does the
same, and only that (Bayram: "Hadis ilmi cercevesinde yap"): the road that stops is joined to the other road at the
first narrator of it who is ATTESTED as the teacher of the stopped road's last narrator — in at least two other hadith of
the imported books, whose chains are read whole. Nothing attested, nothing joined: the road stays as it is written.

Each joining is written down (table isnad_meetings: which road, from which link on, the narrators and how many
other hadith attest them), so the chain page can say why the roads meet there, and so it can be undone and done again
whenever the narrators are identified anew.
"""

from __future__ import annotations

import sqlite3
from collections import defaultdict

MIN_ATTESTED = 3          # other hadith in which the teacher–student pair is written in a chain read whole


def _table(conn: sqlite3.Connection) -> None:
    conn.execute("""CREATE TABLE IF NOT EXISTS isnad_meetings (
                        isnad_id INTEGER PRIMARY KEY, hadith_id INTEGER NOT NULL, ordinal INTEGER NOT NULL,
                        first_position INTEGER NOT NULL, first_name TEXT NOT NULL, student_id INTEGER,
                        teacher_id INTEGER, attested INTEGER NOT NULL, reaches_before INTEGER NOT NULL,
                        ends_before TEXT)""")


def undo(conn: sqlite3.Connection) -> int:
    """Take back every joining made before (the narrators are about to be identified again)."""
    _table(conn)
    undone = 0
    for isnad_id, hid, ordinal, first, name, reaches, ends in conn.execute(
            "SELECT isnad_id, hadith_id, ordinal, first_position, first_name, reaches_before, ends_before "
            "FROM isnad_meetings").fetchall():
        row = conn.execute("SELECT hadith_id, ordinal FROM isnads WHERE id = ?", (isnad_id,)).fetchone()
        link = conn.execute("SELECT raw_name FROM isnad_links WHERE isnad_id = ? AND position = ?",
                            (isnad_id, first)).fetchone()
        if row is None or tuple(row) != (hid, ordinal) or link is None or link[0] != name:
            continue                            # the chain was read again since: nothing of ours is in it
        conn.execute("DELETE FROM isnad_links WHERE isnad_id = ? AND position >= ?", (isnad_id, first))
        conn.execute("UPDATE isnads SET reaches_prophet = ?, ends_with = ? WHERE id = ?", (reaches, ends, isnad_id))
        undone += 1
    conn.execute("DELETE FROM isnad_meetings")
    return undone


def _attested(conn: sqlite3.Connection) -> tuple[dict, dict]:
    """(student, teacher) → the hadith in whose whole chains the pair stands next to each other."""
    pairs: dict = defaultdict(set)
    rows = conn.execute(
        """SELECT i.hadith_id, l.isnad_id, l.position, l.person_id FROM isnad_links l JOIN isnads i ON i.id = l.isnad_id
           WHERE i.problem IS NULL ORDER BY l.isnad_id, l.position""")
    last = (None, None, None)
    for hid, isnad_id, _pos, pid in rows:
        if last[0] == isnad_id and last[1] is not None and pid is not None and last[1] != pid:
            pairs[(last[1], pid)].add(hid)
        last = (isnad_id, pid, hid)
    return pairs, {}


def _named_meetings(norm: str) -> list[tuple[int, str]]:
    """The narrators the text itself names as a meeting, with where: "كلهم عن الأعمش", "جميعا عن هشام", "كل هؤلاء عن
    أبي الزبير", "كلاهما عن شعبة"."""
    import re

    return [(m.start(), m.group(1)) for m in re.finditer(
        r"(?<!\w)(?:كلهم|جميعا|كل هولاء|كل هؤلاء|كلاهما|ثلاثتهم|اربعتهم)\s*،?\s*"
        r"(?:عن|قالوا حدثنا|قالا حدثنا|حدثنا|اخبرنا)\s+([^،,.:]{2,40})", norm)]


def join(conn: sqlite3.Connection) -> dict:
    """Join each stopped road of a tahwil to the road it meets. Returns counts.

    The meeting is the narrator of the other road who is attested — in other hadith of the imported books, in chains
    read whole — as the teacher of the stopped road's last narrator, and never the other way round, nor of a later
    generation, nor dead too long before him to have taught him. Where the text names meetings after the road
    ("كلهم عن الزهري"), those named and attested come first; among several, the one the narrators attest most."""
    from isnady.core.isnad import BORROWED, _is_companion, _shared, Link, normalize_name

    _table(conn)
    pairs, _ = _attested(conn)
    tabaqa = dict(conn.execute("SELECT id, tabaqa FROM persons WHERE tabaqa IS NOT NULL"))
    died = dict(conn.execute("SELECT id, death_year_ah FROM persons WHERE death_year_ah IS NOT NULL"))
    by_hadith: dict = defaultdict(list)
    borrowed: dict = defaultdict(list)
    for isnad_id, hid, ordinal, reaches, ends, problem in conn.execute(
            "SELECT id, hadith_id, ordinal, reaches_prophet, ends_with, problem FROM isnads "
            "WHERE derived_by IS NOT NULL ORDER BY hadith_id, ordinal"):
        if problem is None:
            by_hadith[hid].append((isnad_id, ordinal, reaches, ends))
        elif problem == BORROWED and ordinal > 1:
            borrowed[hid].append(isnad_id)
    joined = looked = 0

    def fits(student: int, teacher: int, seen: int) -> bool:
        back = len(pairs.get((teacher, student), set()))
        if back >= seen:
            return False                        # attested the other way round as often: not his teacher
        if tabaqa.get(teacher) and tabaqa.get(student) and tabaqa[teacher] > tabaqa[student]:
            return False                        # a teacher of a later generation than his student cannot be
        if died.get(teacher) and died.get(student) and not -40 <= died[student] - died[teacher] <= 100:
            return False                        # too far apart in time to have met (or the student dying far before)
        return True

    for hid, roads in by_hadith.items():
        if len(roads) < 2:
            continue
        links = {r[0]: conn.execute("SELECT position, raw_name, transmission, person_id, match_confidence, candidates "
                                    "FROM isnad_links WHERE isnad_id = ? ORDER BY position", (r[0],)).fetchall()
                 for r in roads}
        firsts = {(conn.execute("SELECT raw_name FROM isnad_links WHERE isnad_id = ? AND position = 1", (b,)).fetchone()
                   or [None])[0] for b in borrowed.get(hid, [])}
        norm = None
        for isnad_id, ordinal, reaches, ends in roads:
            mine = links[isnad_id]
            if reaches or ends or not mine:
                continue
            last = mine[-1]
            if _is_companion(Link(1, "", last[1])) or last[3] is None:
                continue
            if mine[0][1] in firsts:
                continue                            # "… بهذا الإسناد": the book's own pointer goes on (drawn beside it)
            looked += 1
            if norm is None:
                row = conn.execute("SELECT t.text FROM texts t JOIN editions e ON e.id = t.edition_id "
                                   "WHERE t.hadith_id = ? AND e.language = 'Arabic'", (hid,)).fetchone()
                norm = normalize_name(row[0] if row else "")[:3000]
            at = norm.find(normalize_name(last[1])[:20]) if last[1] else -1
            named = [n for pos, n in _named_meetings(norm) if pos > at >= 0]
            best = None                             # (said, attested, other road, j, teacher, reaches, ends)
            for other_id, _o, o_reaches, o_ends in roads:
                theirs = links[other_id]
                if other_id == isnad_id or not (o_reaches or o_ends):
                    continue
                for j in range(1, len(theirs)):
                    teacher = theirs[j][3]
                    if teacher is None or teacher == last[3]:
                        continue
                    seen = len(pairs.get((last[3], teacher), set()) - {hid})
                    said = any(_shared(theirs[j][1], n) for n in named)
                    if seen < (1 if said else MIN_ATTESTED) or not fits(last[3], teacher, seen):
                        continue
                    key = (said, seen)
                    if best is None or key > best[:2]:
                        best = (said, seen, other_id, j, teacher, o_reaches, o_ends)
            if best is None:
                continue
            said, seen, other_id, j, teacher, o_reaches, o_ends = best
            tail = links[other_id][j:]
            first = len(mine) + 1
            conn.executemany(
                "INSERT INTO isnad_links (isnad_id, position, raw_name, transmission, person_id, match_confidence, "
                "candidates) VALUES (?, ?, ?, ?, ?, ?, ?)",
                [(isnad_id, first + k, r[1], r[2], r[3], r[4], r[5]) for k, r in enumerate(tail)])
            conn.execute("UPDATE isnads SET reaches_prophet = ?, ends_with = ? WHERE id = ?", (o_reaches, o_ends, isnad_id))
            conn.execute("INSERT OR REPLACE INTO isnad_meetings (isnad_id, hadith_id, ordinal, first_position, first_name, "
                         "student_id, teacher_id, attested, reaches_before, ends_before) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                         (isnad_id, hid, ordinal, first, tail[0][1], last[3], teacher, -seen if said else seen,
                          reaches, ends))
            links[isnad_id] = mine + [(first + k,) + tuple(r[1:]) for k, r in enumerate(tail)]
            joined += 1
    return {"looked": looked, "joined": joined}


def meeting(conn: sqlite3.Connection, isnad_id: int) -> dict | None:
    """Why a road goes on as another does, for the chain page: from which link, and how the narrators attest it."""
    try:
        row = conn.execute("SELECT first_position, student_id, teacher_id, attested FROM isnad_meetings "
                           "WHERE isnad_id = ?", (isnad_id,)).fetchone()
    except sqlite3.OperationalError:
        return None
    if row is None:
        return None
    return {"first_position": row[0], "student_id": row[1], "teacher_id": row[2], "attested": abs(row[3]),
            "said": row[3] < 0}
