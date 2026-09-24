#!/usr/bin/env python3
"""Fetch Wiktionary pages edited after a dump's snapshot, as an overlay.

Dumps come out once a month, so a fix made on the wiki (e.g. adding
``*{{eo}}: [[aj]]`` to io.wiktionary 'aye') otherwise waits weeks to reach the
dictionaries. This stage asks the MediaWiki API which main-namespace pages
changed since the dump's snapshot and stores their current wikitext next to
the dump as ``<dump>.overlay.json``. ``wiktionary_parser.iter_pages`` reads it
automatically: overlay pages replace their dump version, new pages are added,
deleted pages are dropped. Everything still comes from the source wiki and is
reproducible; the overlay only brings the snapshot up to date.

The snapshot time is the newest ``<timestamp>`` inside the dump itself (minus
a day's margin), so it fits whichever dump file is on disk. Wikimedia keeps recentchanges for
90 days — older dumps are refused (download a newer dump instead).

Usage:
  python3 scripts/fetch_wiktionary_overlay.py --lang io [--dump FILE]
"""
from __future__ import annotations

import argparse
import bz2
import json
import logging
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Iterable, List

from utils.parser_base import find_dump_file

USER_AGENT = "apertium-ido-epo-extractor/1.0 (https://github.com/komapc/ido-esperanto-extractor)"
RC_MAX_AGE = timedelta(days=90)
SNAPSHOT_MARGIN = timedelta(days=1)
_TS_RE = re.compile(rb"<timestamp>([0-9T:\-]+Z)</timestamp>")


def overlay_path(dump: Path) -> Path:
    return dump.with_name(dump.name + ".overlay.json")


def dump_snapshot_time(dump: Path) -> str:
    """Newest revision timestamp in the dump (ISO 8601, UTC)."""
    newest = b""
    opener = bz2.open if dump.suffix == ".bz2" else open
    with opener(dump, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 22), b""):
            for ts in _TS_RE.findall(chunk):
                if ts > newest:
                    newest = ts
    if not newest:
        raise SystemExit(f"No <timestamp> found in {dump}")
    return newest.decode()


def _api(lang: str, params: Dict[str, str]) -> dict:
    url = f"https://{lang}.wiktionary.org/w/api.php?" + urllib.parse.urlencode(
        {**params, "format": "json", "formatversion": "2"})
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.load(resp)
        except Exception as e:  # network hiccup / 429: back off and retry
            wait = 2 ** attempt
            logging.warning("API request failed (%s); retrying in %ds", e, wait)
            time.sleep(wait)
    raise SystemExit(f"API unreachable: {url}")


def changed_titles(lang: str, since: str) -> List[str]:
    """Main-namespace titles edited, created or moved-into since `since`."""
    titles: Dict[str, None] = {}
    params = {"action": "query", "list": "recentchanges", "rcnamespace": "0",
              "rcend": since, "rcprop": "title|loginfo", "rclimit": "500",
              "rctype": "edit|new|log"}
    while True:
        data = _api(lang, params)
        for rc in data.get("query", {}).get("recentchanges", []):
            titles.setdefault(rc["title"], None)
            # a move's target is a page too (its source then reads as deleted
            # or as a redirect, which the parser ignores)
            target = (rc.get("logparams") or {}).get("target_title")
            if target and (rc.get("logparams") or {}).get("target_ns", 0) == 0:
                titles.setdefault(target, None)
        cont = data.get("continue")
        if not cont:
            break
        params.update(cont)
        time.sleep(1)
    return list(titles)


def fetch_texts(lang: str, titles: Iterable[str]) -> Dict[str, dict]:
    """{title: {"ns", "text", "timestamp"}} or {"deleted": True} for gone pages."""
    titles = list(titles)
    pages: Dict[str, dict] = {}
    for i in range(0, len(titles), 50):
        params = {"action": "query", "prop": "revisions",
                  "rvprop": "content|timestamp", "rvslots": "main",
                  "titles": "|".join(titles[i:i + 50])}
        while True:
            data = _api(lang, params)
            for p in data.get("query", {}).get("pages", []):
                if p.get("missing"):
                    pages[p["title"]] = {"deleted": True}
                elif p.get("revisions"):
                    rev = p["revisions"][0]
                    pages[p["title"]] = {"ns": str(p.get("ns", 0)),
                                         "text": rev["slots"]["main"].get("content", ""),
                                         "timestamp": rev["timestamp"]}
                # else: content held back by the response size limit —
                # it arrives on the continuation below
            time.sleep(1)
            if "continue" not in data:
                break
            params.update(data["continue"])
    return pages


def main(argv: Iterable[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--lang", required=True, help="Wiktionary language code (io, eo, …)")
    ap.add_argument("--dump", type=Path,
                    help="dump file (default: the one parse_wiktionary_stage1 picks)")
    ap.add_argument("-v", "--verbose", action="count", default=0)
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")

    if args.dump is None:
        base = Path(__file__).resolve().parents[1]
        args.dump = find_dump_file(f"{args.lang}wiktionary-*.xml.bz2", base / "dumps",
                                   [base / "data" / "raw"])
        if args.dump is None:
            raise SystemExit(f"No {args.lang}wiktionary dump found")
    # A dump is written over hours: a page dumped early can be edited before
    # the newest <timestamp> in the file. Start a day earlier; refetching a
    # page that was already current is harmless.
    newest = datetime.strptime(dump_snapshot_time(args.dump), "%Y-%m-%dT%H:%M:%SZ"
                               ).replace(tzinfo=timezone.utc)
    since_dt = newest - SNAPSHOT_MARGIN
    since = since_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    if datetime.now(timezone.utc) - since_dt > RC_MAX_AGE:
        raise SystemExit(f"Dump snapshot {since} is older than recentchanges' 90-day "
                         "window — download a newer dump.")
    logging.info("Dump %s: fetching edits since %s (newest page %s, minus margin)", args.dump.name, since, newest.strftime("%Y-%m-%dT%H:%M:%SZ"))

    titles = changed_titles(args.lang, since)
    logging.info("%d main-namespace pages changed since the snapshot", len(titles))
    pages = fetch_texts(args.lang, titles)
    out = overlay_path(args.dump)
    out.write_text(json.dumps({
        "lang": args.lang,
        "dump": args.dump.name,
        "since": since,
        "fetched": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "pages": pages,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    logging.info("Wrote %s (%d pages, %d deleted)", out, len(pages),
                 sum(1 for p in pages.values() if p.get("deleted")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
