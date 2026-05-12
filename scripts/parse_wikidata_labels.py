#!/usr/bin/env python3
"""Extract Ido↔Esperanto pairs from Wikidata item labels and aliases.

Queries the Wikidata SPARQL endpoint for items that carry labels in both
Ido ('io') and Esperanto ('eo'), then fetches per-item aliases via the
Wikidata REST API so that alternate forms are included as extra translations.

Output: work/io_eo_wikidata.json — unified format (same schema as other
        sources; source tag 'wikidata_labels').

Usage:
    python3 scripts/parse_wikidata_labels.py [-v] [--dry-run] [--out PATH]
    python3 scripts/parse_wikidata_labels.py --no-aliases   # skip alias fetch
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Iterator

sys.path.insert(0, str(Path(__file__).parent))
from _common import configure_logging, write_json

logger = logging.getLogger(__name__)

SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"
ENTITY_API = "https://www.wikidata.org/wiki/Special:EntityData/{qid}.json"
USER_AGENT = "ApertiumIoEoBot/1.0 (https://github.com/apertium; komapc@gmail.com)"
PAGE_SIZE = 5_000
MAX_RETRIES = 6
BASE_DELAY = 5.0   # seconds; doubles on each 429

SOURCE_TAG = "wikidata_labels"

# Valid Ido lemma: only Latin letters and hyphens, length ≥ 2
_LEMMA_RE = re.compile(r"^[a-zA-ZĈĉĜĝĤĥĴĵŜŝŬŭÀ-ÿ][a-zA-ZĈĉĜĝĤĥĴĵŜŝŬŭÀ-ÿ\-]{1,}$")
# Multi-word: contains space → usually a phrase, not a lemma
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
    """Accept single words or hyphenated compounds (eo allows multi-word senses)."""
    if not s or len(s) < 2:
        return False
    return True


def _sparql_request(query: str) -> list[dict]:
    """Execute a SPARQL query against the Wikidata endpoint; return bindings."""
    url = SPARQL_ENDPOINT + "?" + urllib.parse.urlencode(
        {"query": query, "format": "json"}
    )
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "application/sparql-results+json",
    })
    delay = BASE_DELAY
    for attempt in range(MAX_RETRIES):
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read())
                return data["results"]["bindings"]
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503):
                logger.warning("WDQS %d; sleeping %.0fs (attempt %d/%d)",
                               e.code, delay, attempt + 1, MAX_RETRIES)
                time.sleep(delay)
                delay = min(delay * 2, 120)
            else:
                raise
        except Exception as e:
            logger.warning("SPARQL request failed (%s); sleeping %.0fs", e, delay)
            time.sleep(delay)
            delay = min(delay * 2, 120)
    raise RuntimeError(f"SPARQL query failed after {MAX_RETRIES} attempts")


def iter_io_items(page_size: int = PAGE_SIZE) -> Iterator[tuple[str, str]]:
    """Yield (qid, io_label) for Wikidata items linked from io.wikipedia.

    Uses schema:isPartOf <https://io.wikipedia.org/> as a selective index
    (bounded set of ~70k items) instead of scanning all rdfs:label triples,
    which triggers WDQS 429 rate-limiting. eo label is fetched per-item via
    the entity API (fetch_entity).
    """
    offset = 0
    total = 0
    while True:
        query = f"""
SELECT DISTINCT ?item ?ioLabel WHERE {{
  ?article schema:about ?item ;
           schema:isPartOf <https://io.wikipedia.org/> .
  ?item rdfs:label ?ioLabel . FILTER(LANG(?ioLabel) = "io")
}}
ORDER BY ?item
LIMIT {page_size}
OFFSET {offset}
"""
        logger.info("SPARQL page offset=%d …", offset)
        rows = _sparql_request(query)
        if not rows:
            break
        for row in rows:
            qid = row["item"]["value"].rsplit("/", 1)[-1]
            io_label = row["ioLabel"]["value"].strip()
            yield qid, io_label
        total += len(rows)
        logger.info("  → %d rows this page (%d total so far)", len(rows), total)
        if len(rows) < page_size:
            break
        offset += page_size
        time.sleep(1.0)  # be polite between pages


def fetch_entity(qid: str) -> tuple[str | None, list[str], list[str]]:
    """Return (eo_label, io_aliases, eo_aliases) via the entity API.

    eo_label is None when the item has no Esperanto label.
    """
    url = ENTITY_API.format(qid=qid)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    delay = BASE_DELAY
    for attempt in range(MAX_RETRIES):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read())
            item = data["entities"].get(qid, {})
            eo_lbl = item.get("labels", {}).get("eo", {}).get("value", "").strip() or None
            aliases = item.get("aliases", {})
            io_al = [a["value"].strip() for a in aliases.get("io", [])]
            eo_al = [a["value"].strip() for a in aliases.get("eo", [])]
            return eo_lbl, io_al, eo_al
        except urllib.error.HTTPError as e:
            if e.code in (429, 503):
                logger.debug("Entity API %d for %s; sleeping %.0fs", e.code, qid, delay)
                time.sleep(delay)
                delay = min(delay * 2, 60)
            else:
                logger.debug("Entity API error %d for %s", e.code, qid)
                return None, [], []
        except Exception as e:
            logger.debug("Entity API failed for %s: %s", qid, e)
            return None, [], []
    return None, [], []


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
    ap = argparse.ArgumentParser(description="Extract IO↔EO pairs from Wikidata labels")
    ap.add_argument("--out", type=Path,
                    default=Path(__file__).resolve().parents[1] / "work/io_eo_wikidata.json")
    ap.add_argument("--no-aliases", action="store_true",
                    help="Skip alias API calls (faster but misses alternate forms)")
    ap.add_argument("--dry-run", action="store_true",
                    help="Fetch one SPARQL page and stop without writing output")
    ap.add_argument("-v", "--verbose", action="count", default=0)
    args = ap.parse_args(argv)
    configure_logging(args.verbose)

    entries: list[dict] = []
    # Track by io lemma to merge multiple eo terms for the same Ido word
    by_io: dict[str, dict] = {}   # io_lemma -> entry dict

    logger.info("Querying Wikidata SPARQL for items with io labels …")
    seen_qids: set[str] = set()
    pages = 0

    try:
        for qid, io_label in iter_io_items():
            pages += 1
            if args.dry_run and pages > PAGE_SIZE:
                logger.info("--dry-run: stopping after first page")
                break

            if not _is_valid_io_lemma(io_label):
                continue

            # Always call entity API: get eo label + aliases in one request.
            # --no-aliases suppresses alias processing but we still need the
            # eo label, so the API call happens regardless.
            eo_label, io_al, eo_al = fetch_entity(qid)
            if args.no_aliases:
                io_al, eo_al = [], []

            if not eo_label or not _is_valid_eo_term(eo_label):
                continue

            seen_qids.add(qid)
            io_key = io_label.lower()

            # Collect eo terms: primary label first
            eo_terms: list[str] = [eo_label]
            for t in eo_al:
                if _is_valid_eo_term(t) and t not in eo_terms:
                    eo_terms.append(t)

            for io_alias in io_al:
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

    except RuntimeError as e:
        logger.warning("SPARQL unavailable after retries: %s", e)
        logger.warning("Writing partial output (%d entries collected so far)", len(by_io))

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
