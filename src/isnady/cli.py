"""The isnady command line (no Qt needed).

Every name runs it: `isnady ARGS`, `iy ARGS`, `isnady-cli ARGS`.

Examples
  iy search niyet
  iy search النيات --book bukhari
  iy chain bukhari 1
  iy isnads
  iy import fawazahmed0 ./tur-bukhari.json
  iy import fawazahmed0 https://example.org/editions.json --book bukhari --language tur
  iy import fawazahmed0 https://example.org/ed.json --user bayram          (password is asked)
  iy import fawazahmed0 https://example.org/ed.json --token-env MY_TOKEN
  iy config list --prefix text.arabic
  iy config set text.arabic.size 22
  iy config set colors.dark.gilt "#5A4A1E"
  iy config reset text.arabic
  iy sources
  iy stats
  iy remove <source-key>
  iy -V
"""

import argparse
import os.path
import getpass
import os
import sys

from isnady import APP_NAME, __version__
from isnady.core import isnad as core_isnad
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


def cmd_config(args) -> int:
    from isnady import config

    try:
        if args.action == "list":
            for key, value, default in config.all_values():
                if args.prefix and not key.startswith(args.prefix):
                    continue
                mark = "" if value == default else "   (changed)"
                shown = value if value != "" else "(default)"
                print(f"{key:32} {shown}{mark}")
            print(f"\nSaved in {config.settings_path()}")
        elif args.action == "get":
            if not args.key:
                raise config.ConfigError("Give the setting: iy config get text.arabic.size")
            config.validate(args.key, "")
            print(config.get(args.key))
        elif args.action == "set":
            if not args.key or args.value is None:
                raise config.ConfigError("Give the setting and the value: iy config set text.arabic.size 22")
            config.set(args.key, args.value)
            print(f"{args.key} = {config.get(args.key)}")
        elif args.action == "reset":
            removed = config.reset(args.key or "")
            print(f"Reset {removed} setting{'s' if removed != 1 else ''} to the default"
                  + (f" under {args.key}" if args.key else ""))
    except config.ConfigError as exc:
        print(exc, file=sys.stderr)
        return 2
    return 0


def cmd_version(_args) -> int:
    print(f"{APP_NAME} {__version__}")
    return 0


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
        core_isnad.ensure_isnads(conn, progress=lambda m: print(f"  {m}"))
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
        print("No sources yet. Add one with: iy import <format> <file-or-url>")
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


def cmd_isnads(args) -> int:
    conn = _connect()
    stats = core_isnad.ensure_isnads(conn, progress=print, rebuild=args.rebuild)
    if stats["parsed"] or stats["raw_only"]:
        print(f"Read {stats['parsed'] + stats['raw_only']} chains now.")
    print(f"Parser: {core_isnad.PARSER_ID}")
    for b in core_isnad.book_stats(conn):
        print(f"  {b['name']}: {b['chains']} chains, {b['split']} split into narrators "
              f"({100 * b['split'] / b['chains']:.1f}%), {b['marfu']} reach the Prophet, {b['links']} links")
        for problem, count in b["problems"]:
            print(f"    {count:6}  not split: {problem}")
    conn.close()
    return 0


def cmd_chain(args) -> int:
    conn = _connect()
    core_isnad.ensure_isnads(conn)
    row = conn.execute(
        """SELECT h.id, c.name FROM hadiths h JOIN collections c ON c.id = h.collection_id
           WHERE c.key = ? AND h.number = ?""", (args.book, args.number)
    ).fetchone()
    if row is None:
        print(f"No hadith {args.number} in '{args.book}'. See: iy stats", file=sys.stderr)
        conn.close()
        return 1
    chains = core_isnad.chain(conn, row["id"])
    conn.close()
    print(f"{row['name']} {args.number}")
    if not chains:
        print("  no chain stored (no Arabic text for this hadith)")
    for ch in chains:
        if ch["problem"]:
            print(f"  not split: {ch['problem']}")
        for link in ch["links"]:
            arabic, meaning, _why = core_isnad.term_label(link["transmission"])
            print(f"  {link['position']:>2}. {arabic} ({meaning})  {link['raw_name']}")
        if ch["links"]:
            print("      -> the Prophet" if ch["reaches_prophet"] else "      (chain stops here)")
        if args.raw and ch["raw"]:
            print(f"  raw: {ch['raw']}")
    return 0


def cmd_remove(args) -> int:
    conn = _connect()
    with conn:
        cur = conn.execute("DELETE FROM sources WHERE key = ?", (args.key,))
    db.cleanup(conn)
    conn.close()
    if cur.rowcount == 0:
        print(f"No source with key '{args.key}'. See: iy sources", file=sys.stderr)
        return 1
    print(f"Removed source '{args.key}' and everything imported from it.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    prog = os.path.splitext(os.path.basename(sys.argv[0]))[0] or "isnady"
    if prog in ("__main__", "main", "cli", "python", "python3"):
        prog = "isnady"
    p = argparse.ArgumentParser(
        prog=prog,
        description=f"{APP_NAME} {__version__}. Run it without arguments to open the window.",
    )
    p.add_argument("-v", "-V", "--version", "--v", "--V", action="version",
                   version=f"{APP_NAME} {__version__}", help="show the version")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("version", help="show the version").set_defaults(func=cmd_version)
    cfg = sub.add_parser("config", help="appearance and other settings (the same as Edit → Preferences)")
    cfg.add_argument("action", choices=["list", "get", "set", "reset"])
    cfg.add_argument("key", nargs="?", help="e.g. text.arabic.size, colors.dark.gilt, ui.family")
    cfg.add_argument("value", nargs="?", help="value for set; an empty string restores the default")
    cfg.add_argument("--prefix", default="", help="list only keys starting with this, e.g. text.arabic")
    cfg.set_defaults(func=cmd_config)
    sub.add_parser("formats", help="list supported data formats").set_defaults(func=cmd_formats)

    imp = sub.add_parser("import", help="import a file or URL")
    imp.add_argument("format", help="data format, see 'iy formats'")
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

    isn = sub.add_parser("isnads", help="read the chains of transmission from the Arabic texts and report")
    isn.add_argument("--rebuild", action="store_true", help="read every chain again")
    isn.set_defaults(func=cmd_isnads)
    ch = sub.add_parser("chain", help="show the chain of one hadith")
    ch.add_argument("book", help="collection key, e.g. bukhari")
    ch.add_argument("number", help="hadith number, e.g. 1")
    ch.add_argument("--raw", action="store_true", help="also print the chain as written")
    ch.set_defaults(func=cmd_chain)

    sub.add_parser("sources", help="list imported sources").set_defaults(func=cmd_sources)
    sub.add_parser("stats", help="count what the database holds").set_defaults(func=cmd_stats)
    rm = sub.add_parser("remove", help="remove a source and everything imported from it")
    rm.add_argument("key", help="source key, see 'iy sources'")
    rm.set_defaults(func=cmd_remove)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
