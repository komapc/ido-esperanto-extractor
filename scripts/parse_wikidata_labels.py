#!/usr/bin/env python3
"""Extract Ido↔Esperanto pairs from Wikidata item labels and aliases.

Dump-based approach — no SPARQL required:
  1. Parse iowiki-latest-page_props.sql.gz  → {page_id: QID}
  2. Parse iowiki-latest-pages-articles.xml.bz2 → {page_id: io_page_title}
  3. Batch-fetch labels+aliases via Wikidata wbgetentities API (50 QIDs/call)
  4. Keep items that have both Ido and Esperanto labels in Wikidata

Output: work/io_eo_wikidata.json — unified format (same schema as other
        sources; source tag 'wikidata_labels').

Usage:
    python3 scripts/parse_wikidata_labels.py [-v] [--dry-run] [--out PATH]
    python3 scripts/parse_wikidata_labels.py --no-aliases
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import configure_logging, write_json

logger = logging.getLogger(__name__)

ENTITY_API = "https://www.wikidata.org/w/api.php"
USER_AGENT = "ApertiumIoEoBot/1.0 (https://github.com/apertium; komapc@gmail.com)"
BATCH_SIZE = 50
MAX_RETRIES = 6
BASE_DELAY = 5.0
INTER_BATCH_DELAY = 0.5  # seconds between batches (polite)

SOURCE_TAG = "wikidata_labels"

_LEMMA_RE = re.compile(r"^[a-zA-ZĈĉĜĝĤĥĴĵŜŝŬŭÀ-ÿ][a-zA-ZĈĉĜĝĤĥĴĵŜŝŬŭÀ-ÿ\-]{1,}$")
_MULTIWORD_RE = re.compile(r"\s")


def _is_valid_io_lemma(s: str) -> bool:
    if not s or len(s) < 2:
        return False
    if _MULTIWORD_RE.search(s):
        return False
    if not _LEMMA_RE.match(s):
        return False
    return True


def _is_valid_eo_term(s: str) -> bool:
    if not s or len(s) < 2:
        return False
    return True


def extract_page_props(sql_path: Path) -> dict[int, str]:
    """Return {page_id: QID} for all io.wiki pages with a wikibase_item prop."""
    qids: dict[int, str] = {}
    proc = subprocess.Popen(["zcat", str(sql_path)], stdout=subprocess.PIPE)
    pat = re.compile(rb"\((\d+),'wikibase_item','(Q\d+)'")
    assert proc.stdout is not None
    for line in proc.stdout:
        if b"wikibase_item" not in line:
            continue
        for m in pat.finditer(line):
            qids[int(m.group(1))] = m.group(2).decode("ascii")
    proc.wait()
    logger.info("  page_props: %d QID mappings", len(qids))
    return qids


def extract_pages_from_xml(xml_path: Path) -> dict[int, str]:
    """Return {page_id: title} for namespace-0 pages from io.wiki XML dump."""
    pages: dict[int, str] = {}
    proc = subprocess.Popen(["bzcat", str(xml_path)], stdout=subprocess.PIPE)
    title = b""
    page_id: int | None = None
    in_page = False
    ns = b""
    assert proc.stdout is not None
    for line in proc.stdout:
        if b"<page>" in line:
            in_page = True
            page_id = None
            title = b""
            ns = b""
        if not in_page:
            continue
        if b"<title>" in line:
            m = re.search(rb"<title>([^<]*)", line)
            if m:
                title = m.group(1)
        if b"<ns>" in line:
            m = re.search(rb"<ns>([^<]*)", line)
            if m:
                ns = m.group(1)
        if b"<id>" in line and page_id is None:
            m = re.search(rb"<id>([^<]*)", line)
            if m:
                page_id = int(m.group(1))
        if b"</page>" in line:
            if ns == b"0" and page_id and title:
                pages[page_id] = title.decode("utf-8", errors="ignore")
            in_page = False
    proc.wait()
    logger.info("  xml: %d io.wiki pages", len(pages))
    return pages


def fetch_entities_batch(qids: list[str]) -> dict[str, dict]:
    """Fetch labels+aliases for up to 50 QIDs via wbgetentities.

    Returns {qid: {"io_label": str|None, "io_aliases": [...], "eo_label": str|None, "eo_aliases": [...]}}
    """
    params = urllib.parse.urlencode({
        "action": "wbgetentities",
        "ids": "|".join(qids),
        "languages": "io|eo",
        "props": "labels|aliases",
        "format": "json",
    })
    url = ENTITY_API + "?" + params
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    delay = BASE_DELAY
    for attempt in range(MAX_RETRIES):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read())
            result: dict[str, dict] = {}
            for qid, entity in data.get("entities", {}).items():
                labels = entity.get("labels", {})
                aliases = entity.get("aliases", {})
                result[qid] = {
                    "io_label": labels.get("io", {}).get("value", "").strip() or None,
                    "io_aliases": [a["value"].strip() for a in aliases.get("io", [])],
                    "eo_label": labels.get("eo", {}).get("value", "").strip() or None,
                    "eo_aliases": [a["value"].strip() for a in aliases.get("eo", [])],
                }
            return result
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503):
                logger.warning("API %d; sleeping %.0fs (attempt %d/%d)",
                               e.code, delay, attempt + 1, MAX_RETRIES)
                time.sleep(delay)
                delay = min(delay * 2, 120)
            else:
                raise
        except Exception as e:
            logger.warning("API request failed (%s); sleeping %.0fs", e, delay)
            time.sleep(delay)
            delay = min(delay * 2, 120)
    raise RuntimeError(f"wbgetentities failed after {MAX_RETRIES} attempts")


def build_entry(io_lemma: str, eo_terms: list[str], qid: str) -> dict:
    return {
        "lemma": io_lemma,
        "pos": None,
        "language": "io",
        "senses": [
            {
                "senseId": None,
                "gloss": f"Wikidata {qid}: {io_lemma} ↔ {eo_terms[0]}",
                "translations": [
                    {"lang": "eo", "term": t, "confidence": 0.9, "source": SOURCE_TAG}
                    for t in eo_terms
                ],
            }
        ],
        "provenance": [{"source": SOURCE_TAG, "page": qid}],
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Extract IO↔EO pairs from Wikidata labels (dump-based)")
    base = Path(__file__).resolve().parents[1]
    ap.add_argument("--page-props", type=Path,
                    default=base / "data/raw/iowiki-latest-page_props.sql.gz")
    ap.add_argument("--xml", type=Path,
                    default=base / "data/raw/iowiki-latest-pages-articles.xml.bz2")
    ap.add_argument("--out", type=Path,
                    default=base / "work/io_eo_wikidata.json")
    ap.add_argument("--no-aliases", action="store_true",
                    help="Skip alias processing (faster, misses alternate forms)")
    ap.add_argument("--dry-run", action="store_true",
                    help="Process first batch only, do not write output")
    ap.add_argument("-v", "--verbose", action="count", default=0)
    args = ap.parse_args(argv)
    configure_logging(args.verbose)

    if not args.page_props.exists():
        logger.error("Missing %s — run download_dumps.sh first", args.page_props)
        return 1
    if not args.xml.exists():
        logger.error("Missing %s — run download_dumps.sh first", args.xml)
        return 1

    logger.info("Parsing page_props dump: %s", args.page_props)
    page_qids = extract_page_props(args.page_props)

    logger.info("Parsing io.wiki XML dump: %s", args.xml)
    page_titles = extract_pages_from_xml(args.xml)

    # Build {qid: io_page_title} — page title is our fallback lemma
    qid_to_title: dict[str, str] = {}
    for pid, qid in page_qids.items():
        title = page_titles.get(pid)
        if title:
            qid_to_title[qid] = title
    logger.info("  %d QIDs with io.wiki titles", len(qid_to_title))

    all_qids = list(qid_to_title.keys())
    by_io: dict[str, dict] = {}
    seen_qids: set[str] = set()
    batches_done = 0

    logger.info("Fetching labels+aliases via wbgetentities (%d QIDs, batch=%d)…",
                len(all_qids), BATCH_SIZE)

    for i in range(0, len(all_qids), BATCH_SIZE):
        batch = all_qids[i: i + BATCH_SIZE]
        try:
            entities = fetch_entities_batch(batch)
        except RuntimeError as e:
            logger.warning("Batch %d failed: %s — stopping early", i // BATCH_SIZE, e)
            break

        for qid in batch:
            info = entities.get(qid, {})
            io_page_title = qid_to_title[qid]

            # Prefer Wikidata io label; fall back to Wikipedia page title
            io_label = info.get("io_label") or io_page_title
            eo_label = info.get("eo_label")
            io_aliases = info.get("io_aliases", []) if not args.no_aliases else []
            eo_aliases = info.get("eo_aliases", []) if not args.no_aliases else []

            if not eo_label or not _is_valid_eo_term(eo_label):
                continue
            if not _is_valid_io_lemma(io_label):
                continue

            seen_qids.add(qid)
            eo_terms: list[str] = [eo_label]
            for t in eo_aliases:
                if _is_valid_eo_term(t) and t not in eo_terms:
                    eo_terms.append(t)

            io_key = io_label.lower()
            if io_key not in by_io:
                by_io[io_key] = build_entry(io_label, eo_terms, qid)
            else:
                existing = {
                    tr["term"]
                    for s in by_io[io_key]["senses"]
                    for tr in s["translations"]
                }
                for t in eo_terms:
                    if t not in existing:
                        by_io[io_key]["senses"][0]["translations"].append(
                            {"lang": "eo", "term": t, "confidence": 0.9, "source": SOURCE_TAG}
                        )

            for io_alias in io_aliases:
                if not _is_valid_io_lemma(io_alias):
                    continue
                ak = io_alias.lower()
                if ak not in by_io:
                    by_io[ak] = build_entry(io_alias, eo_terms, qid)
                else:
                    existing = {
                        tr["term"]
                        for s in by_io[ak]["senses"]
                        for tr in s["translations"]
                    }
                    for t in eo_terms:
                        if t not in existing:
                            by_io[ak]["senses"][0]["translations"].append(
                                {"lang": "eo", "term": t, "confidence": 0.9, "source": SOURCE_TAG}
                            )

        batches_done += 1
        if batches_done % 50 == 0:
            logger.info("  %d/%d QIDs processed, %d entries so far",
                        i + len(batch), len(all_qids), len(by_io))

        if args.dry_run:
            logger.info("--dry-run: stopping after first batch")
            break

        time.sleep(INTER_BATCH_DELAY)

    entries = list(by_io.values())
    logger.info("Total: %d distinct Ido lemmas, %d Wikidata items",
                len(entries), len(seen_qids))

    if args.dry_run:
        logger.info("--dry-run: first 5 entries:")
        for e in entries[:5]:
            tr = [t["term"] for s in e["senses"] for t in s["translations"]]
            logger.info("  %s → %s", e["lemma"], tr)
        return 0

    args.out.parent.mkdir(parents=True, exist_ok=True)
    write_json(args.out, entries)
    logger.info("Wrote %s (%d entries)", args.out, len(entries))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
