"""The recent searches (S4, 2026-10-18): the last 20 searches, newest first, kept with the profile.

Bayram (2026-10-13): "Son aramalar (10–20) ve 'Son aramaları temizle'". They are part of the profile's state
(state.json, beside where the reader was), so every profile has its own, a new version of isnady keeps them, and
`iy search --recent` / `iy search --clear-recent` show and clear the same list as the Search page.
"""

from __future__ import annotations

from isnady import config

KEY = "search.recent"
LIMIT = 20
KINDS = ("hadith", "narrators", "scholars")


def items() -> list[dict]:
    """[{"text", "kind"}], the newest first."""
    raw = config.state_get(KEY, []) or []
    out = []
    for r in raw if isinstance(raw, list) else []:
        if isinstance(r, dict) and str(r.get("text", "")).strip():
            out.append({"text": str(r["text"]).strip(), "kind": r.get("kind") if r.get("kind") in KINDS else "hadith"})
    return out[:LIMIT]


def add(text: str, kind: str = "hadith") -> None:
    """Remember a search; the same words searched again move to the top instead of being kept twice."""
    text = " ".join((text or "").split())
    if not text:
        return
    kind = kind if kind in KINDS else "hadith"
    kept = [r for r in items() if not (r["text"].casefold() == text.casefold() and r["kind"] == kind)]
    config.state_set(KEY, ([{"text": text, "kind": kind}] + kept)[:LIMIT])


def remove(text: str, kind: str | None = None) -> None:
    config.state_set(KEY, [r for r in items() if not (r["text"] == text and (kind is None or r["kind"] == kind))])


def clear() -> int:
    """Forget every recent search; returns how many there were."""
    n = len(items())
    config.state_set(KEY, [])
    return n
