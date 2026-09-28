"""isnady-cli — command-line access to the data layer (no Qt needed).

Examples
  isnady-cli formats
  isnady-cli import fawazahmed0 ./tur-bukhari.json
  isnady-cli import fawazahmed0 https://example.org/editions.json --book bukhari --language tur
  isnady-cli import fawazahmed0 https://example.org/ed.json --user bayram          (password is asked)
  isnady-cli import fawazahmed0 https://example.org/ed.json --token-env MY_TOKEN
  isnady-cli import fawazahmed0 https://example.org/ed.json --api-key-env KEY --api-key-header X-API-Key
  isnady-cli sources
  isnady-cli stats
  isnady-cli remove <source-key>
"""

import argparse
import getpass
import os
import sys

from isnady import APP_NAME, __version__
from isnady.core import search as core_search
from isnady.data import db
from isnady.data.fetch import Auth, ResourceError
from isnady.data.importers import SourceInfo, get_importer, list_importers
from isnady.data.paths import db_path


def _connect():
    try:
        return db.connect(reset_old=True)
    except db.SchemaReset as exc:
        print(f"Note: {exc}", file=sys.stderr)
        return db.connect()


def _secret_from_env(name: str | None) -> str | None:
    if not name:
        return None
    value = os.environ.get(name)
    if value is None:
        raise SystemExit(f"Environment variable {name} is not set.")
    return value


def _auth_from_args(args) -> Auth:
    token = args.token or _secret_from_env(args.token_env)
    api_key = args.api_key or _secret_from_env(args.api_key_env)
    chosen = [bool(args.user), bool(token), bool(api_key)]
    if sum(chosen) > 1:
        raise SystemExit("Use only one of: --user, --token/--token-env, --api-key/--api-key-env.")
    if args.user:
        password = _secret_from_env(args.password_env) if args.password_env else getpass.getpass(f"Password for {args.user}: ")
        return Auth(kind="basic", username=args.user, password=password)
    if token:
        return Auth(kind="bearer", token=token)
    if api_key:
        if args.api_key_param:
            return Auth(kind="apikey", token=api_key, key_name=args.api_key_param, key_in="query")
        return Auth(kind="apikey", token=api_key, key_name=args.api_key_header or "X-API-Key", key_in="header")
    return Auth()


def cmd_formats(_args) -> int:
    for imp in list_importers():
        print(f"{imp.format_id:14} {imp.title}\n{'':14} {imp.description}")
    return 0


def cmd_import(args) -> int:
    try:
        importer = get_importer(args.format)
    except KeyError as exc:
        print(exc.args[0], file=sys.stderr)
        return 2
    source = SourceInfo(
        location=args.location,
        name=args.name,
        license=args.license,
        origin="builtin" if args.builtin else "user",
        tier=args.tier,
        auth=_auth_from_args(args),
    )
    options = {
        "editions": args.edition,
        "books": args.book,
        "languages": args.language,
        "all": args.all,
        "edition_key": args.edition_key,
        "include_plain": args.include_plain,
    }
    conn = _connect()
    try:
        report = importer.run(conn, source, options, progress=lambda m: print(f"  {m}"))
        db.cleanup(conn)
        core_search.ensure_index(conn, progress=lambda m: print(f"  {m}"))
    except ResourceError as exc:
        print(f"Import failed: {exc}", file=sys.stderr)
        return 1
    finally:
        conn.close()
    print(f"Done: source '{report.source_key}' — {len(report.editions)} edition(s), "
          f"{report.texts} texts, {report.new_hadiths} new hadith, {report.grades} new grades")
    if report.skipped_editions:
        print(f"  skipped diacritics-free copies (use --include-plain to keep): {', '.join(report.skipped_editions)}")
    for warning in report.warnings:
        print(f"  warning: {warning}")
    return 0


def cmd_sources(_args) -> int:
    conn = _connect()
    rows = conn.execute(
        """SELECT s.key, s.name, s.format, s.origin, s.tier, s.auth_type, s.license, s.location, s.imported_at,
                  COUNT(e.id) AS editions, COALESCE(SUM(e.text_count), 0) AS texts
           FROM sources s LEFT JOIN editions e ON e.source_id = s.id
           GROUP BY s.id ORDER BY s.origin, s.key"""
    ).fetchall()
    conn.close()
    if not rows:
        print("No sources yet. Add one with: isnady-cli import <format> <file-or-url>")
        return 0
    for r in rows:
        label = "User Resource" if r["origin"] == "user" else "Built-in"
        print(f"[{label}] {r['key']}  —  {r['name']}")
        tier_note = {"A": "redistributable", "B": "redistributable with conditions", "C": "not redistributable"}[r["tier"]]
        print(f"    format {r['format']}, auth {r['auth_type']}, license {r['license'] or 'not stated'}, "
              f"tier {r['tier']} ({tier_note})")
        print(f"    {r['editions']} edition(s), {r['texts']} texts, imported {r['imported_at']}")
        print(f"    last imported from {r['location']}")
    return 0


def cmd_stats(_args) -> int:
    conn = _connect()
    books = conn.execute(
        """SELECT c.id, c.name,
                  (SELECT COUNT(*) FROM hadiths h WHERE h.collection_id = c.id) AS hadiths,
                  (SELECT COUNT(DISTINCT g.hadith_id) FROM grades g JOIN hadiths h ON h.id = g.hadith_id
                   WHERE h.collection_id = c.id) AS graded,
                  (SELECT COUNT(*) FROM grades g JOIN hadiths h ON h.id = g.hadith_id
                   WHERE h.collection_id = c.id) AS grades
           FROM collections c ORDER BY c.name"""
    ).fetchall()
    print(f"Database: {db_path()}")
    for b in books:
        print(f"  {b['name']}: {b['hadiths']} hadith, {b['graded']} graded ({b['grades']} grades)")
        for e in conn.execute(
            "SELECT key, language, text_count FROM editions WHERE collection_id = ? ORDER BY language, key", (b["id"],)
        ):
            print(f"      {e['key']:22} {e['language']:11} {e['text_count']:>6} texts")
    totals = conn.execute(
        "SELECT (SELECT COUNT(*) FROM hadiths), (SELECT COUNT(*) FROM texts), (SELECT COUNT(*) FROM grades),"
        " (SELECT COUNT(*) FROM persons), (SELECT COUNT(*) FROM isnads)"
    ).fetchone()
    conn.close()
    print(f"Total: {totals[0]} hadith, {totals[1]} texts, {totals[2]} grades, "
          f"{totals[3]} persons, {totals[4]} isnads")
    return 0


def cmd_search(args) -> int:
    conn = _connect()
    core_search.ensure_index(conn, progress=lambda m: print(m, file=sys.stderr))
    q = core_search.SearchQuery(
        text=" ".join(args.words), mode=args.mode, whole_words=args.whole_words,
        collections=args.book or [], languages=args.language or [], limit=args.limit, offset=args.offset,
    )
    page = core_search.search(conn, q)
    conn.close()
    print(f"{page.total} hadith found in {page.elapsed_ms} ms"
          f"{'' if page.used_index else ' (no FTS5 index available; slower scan)'}")
    for r in page.results:
        print(f"\n{r.collection_name} #{r.number}")
        if r.grades:
            print("  grades: " + "; ".join(f"{g}: {v}" for g, v in r.grades))
        for t in r.texts:
            if not t.matched and not args.all_texts:
                continue
            marked, last = [], 0
            for a, b in t.spans:
                marked.append(t.text[last:a] + "[" + t.text[a:b] + "]")
                last = b
            marked.append(t.text[last:])
            body = "".join(marked)
            if len(body) > args.width:
                body = body[: args.width] + " ..."
            print(f"  [{t.language}] {body}")
    return 0


def cmd_remove(args) -> int:
    conn = _connect()
    with conn:
        cur = conn.execute("DELETE FROM sources WHERE key = ?", (args.key,))
    db.cleanup(conn)
    conn.close()
    if cur.rowcount == 0:
        print(f"No source with key '{args.key}'. See: isnady-cli sources", file=sys.stderr)
        return 1
    print(f"Removed source '{args.key}' and everything imported from it.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="isnady-cli", description=f"{APP_NAME} {__version__} data tools")
    p.add_argument("--version", action="version", version=f"{APP_NAME} {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("formats", help="list supported data formats").set_defaults(func=cmd_formats)

    imp = sub.add_parser("import", help="import a file or URL")
    imp.add_argument("format", help="data format, see 'isnady-cli formats'")
    imp.add_argument("location", help="local file path or http(s) URL")
    imp.add_argument("--name", help="display name of the source")
    imp.add_argument("--license", help="license of the data, e.g. Unlicense, CC-BY-4.0")
    imp.add_argument("--builtin", action="store_true", help="mark as built-in data instead of a User Resource")
    imp.add_argument("--tier", choices=["A", "B", "C"],
                     help="licence tier: A redistributable, B with conditions, C not (default: from --license, unknown = C)")
    sel = imp.add_argument_group("choosing editions from an index")
    sel.add_argument("--edition", action="append", help="edition name, e.g. tur-bukhari (repeatable)")
    sel.add_argument("--book", action="append", help="book key, e.g. bukhari (repeatable)")
    sel.add_argument("--language", action="append", help="language name or code, e.g. Turkish or tur (repeatable)")
    sel.add_argument("--all", action="store_true", help="import every edition in the index")
    sel.add_argument("--edition-key", help="edition name for a single file whose file name is not the edition name")
    sel.add_argument("--include-plain", action="store_true",
                     help="also import diacritics-free Arabic copies (skipped by default)")
    auth = imp.add_argument_group("authentication (credentials are never stored)")
    auth.add_argument("--user", help="username for HTTP Basic authentication; the password is asked")
    auth.add_argument("--password-env", help="read the Basic password from this environment variable instead")
    auth.add_argument("--token", help="bearer token (visible in shell history — prefer --token-env)")
    auth.add_argument("--token-env", help="read the bearer token from this environment variable")
    auth.add_argument("--api-key", help="API key (visible in shell history — prefer --api-key-env)")
    auth.add_argument("--api-key-env", help="read the API key from this environment variable")
    auth.add_argument("--api-key-header", help="header name for the API key (default X-API-Key)")
    auth.add_argument("--api-key-param", help="send the API key as this query parameter instead of a header")
    imp.set_defaults(func=cmd_import)

    se = sub.add_parser("search", help="search hadith text (same engine as the app)")
    se.add_argument("words", nargs="+", help="words to search; Arabic diacritics and letter forms are ignored")
    se.add_argument("--mode", choices=["all", "any", "phrase"], default="all")
    se.add_argument("--whole-words", action="store_true", help="match whole words only")
    se.add_argument("--book", action="append", help="collection key, e.g. bukhari (repeatable)")
    se.add_argument("--language", action="append", help="language name, e.g. Turkish (repeatable)")
    se.add_argument("--limit", type=int, default=10)
    se.add_argument("--offset", type=int, default=0)
    se.add_argument("--width", type=int, default=300, help="characters of text to show")
    se.add_argument("--all-texts", action="store_true", help="also show texts that did not match")
    se.set_defaults(func=cmd_search)

    sub.add_parser("sources", help="list imported sources").set_defaults(func=cmd_sources)
    sub.add_parser("stats", help="count what the database holds").set_defaults(func=cmd_stats)
    rm = sub.add_parser("remove", help="remove a source and everything imported from it")
    rm.add_argument("key", help="source key, see 'isnady-cli sources'")
    rm.set_defaults(func=cmd_remove)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
