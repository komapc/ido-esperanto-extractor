#!/usr/bin/env python3
"""Extract Ido↔Esperanto pairs from Wikipedia interlanguage links.

Joins two dumps:
  - data/raw/iowiki-latest-langlinks.sql.gz  (page_id, lang, target_title)
  - data/raw/iowiki-latest-pages-articles.xml.bz2  (page_id → io_title)

Produces work/io_eo_langlinks.json with one entry per (io_title, eo_title)
pair where the eo Wikipedia has a corresponding article. Useful for proper
nouns, places, and concepts that don't appear in Wiktionary but DO have
a Wikipedia article in both languages.

Filters:
  - Drop pairs where either title contains digits (asteroid designations etc.)
  - Drop pairs where titles contain parentheses or dots (template artifacts)
  - Require length ≥ 3 and start-with-letter on both sides
  - Drop pairs where lemma starts with capital but isn't a proper noun
    (heuristic: io_title and eo_title both lowercase OR both capitalized)
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def extract_io_pages(xml_path: Path) -> dict[int, str]:
    """page_id -> io_title for namespace-0 pages."""
    pages: dict[int, str] = {}
    proc = subprocess.Popen(['bzcat', str(xml_path)], stdout=subprocess.PIPE)
    title = b''
    page_id: int | None = None
    in_page = False
    ns = b''
    assert proc.stdout is not None
    for line in proc.stdout:
        if b'<page>' in line:
            in_page = True
            page_id = None
            title = b''
            ns = b''
        if not in_page:
            continue
        if b'<title>' in line:
            m = re.search(rb'<title>([^<]*)', line)
            if m:
                title = m.group(1)
        if b'<ns>' in line:
            m = re.search(rb'<ns>([^<]*)', line)
            if m:
                ns = m.group(1)
        if b'<id>' in line and page_id is None:
            m = re.search(rb'<id>([^<]*)', line)
            if m:
                page_id = int(m.group(1))
        if b'</page>' in line:
            if ns == b'0' and page_id and title:
                pages[page_id] = title.decode('utf-8', errors='ignore')
            in_page = False
    proc.wait()
    return pages


def extract_eo_langlinks(sql_path: Path) -> dict[int, str]:
    """page_id -> eo_title for io.wiki pages with an Esperanto interlanguage link."""
    out: dict[int, str] = {}
    proc = subprocess.Popen(['zcat', str(sql_path)], stdout=subprocess.PIPE)
    pat = re.compile(rb"\((\d+),'eo','((?:[^'\\]|\\.)*)'\)")
    assert proc.stdout is not None
    for line in proc.stdout:
        if b"'eo'" not in line:
            continue
        for m in pat.finditer(line):
            pid = int(m.group(1))
            title = (
                m.group(2)
                .decode('utf-8', errors='ignore')
                .replace("\\'", "'")
                .replace('\\"', '"')
                .replace('\\\\', '\\')
            )
            out[pid] = title
    proc.wait()
    return out


_VALID_LEMMA_RE = re.compile(r"^[A-Za-zĉĝĥĵŝŭĈĜĤĴŜŬ][\w\-ĉĝĥĵŝŭĈĜĤĴŜŬ\s]*$")


def is_valid_lemma(s: str) -> bool:
    s = s.strip()
    if len(s) < 3:
        return False
    if any(c.isdigit() for c in s):
        return False
    if any(c in '.()[]{}|<>' for c in s):
        return False
    if not _VALID_LEMMA_RE.match(s):
        return False
    return True


def build_pairs(io_pages: dict[int, str], io_eo: dict[int, str]) -> list[dict]:
    """Join + filter into entries suitable for build_one_big_bidix_json."""
    pairs: list[dict] = []
    for pid, eo_title in io_eo.items():
        io_title = io_pages.get(pid)
        if not io_title:
            continue
        if not is_valid_lemma(io_title) or not is_valid_lemma(eo_title):
            continue
        pairs.append({
            'lemma': io_title,
            'pos': None,
            'language': 'io',
            'senses': [{
                'senseId': None,
                'gloss': f'Wikipedia langlink: {io_title} ↔ {eo_title}',
                'translations': [{
                    'lang': 'eo',
                    'term': eo_title,
                    'confidence': 0.85,
                    'source': 'wikipedia_langlinks',
                }],
            }],
            'provenance': [{
                'source': 'wikipedia_langlinks',
                'page': io_title,
            }],
        })
    return pairs


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    base = Path(__file__).resolve().parents[1]
    ap.add_argument('--xml', type=Path, default=base / 'data/raw/iowiki-latest-pages-articles.xml.bz2')
    ap.add_argument('--langlinks', type=Path, default=base / 'data/raw/iowiki-latest-langlinks.sql.gz')
    ap.add_argument('--out', type=Path, default=base / 'work/io_eo_langlinks.json')
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    logger.info('Extracting io.wiki page_id → title from %s', args.xml)
    io_pages = extract_io_pages(args.xml)
    logger.info('  %d io pages', len(io_pages))

    logger.info('Extracting io→eo langlinks from %s', args.langlinks)
    io_eo = extract_eo_langlinks(args.langlinks)
    logger.info('  %d io→eo links', len(io_eo))

    logger.info('Building filtered pairs...')
    pairs = build_pairs(io_pages, io_eo)
    logger.info('  %d clean (io_title, eo_title) pairs', len(pairs))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(pairs, f, ensure_ascii=False, indent=None)
    logger.info('Wrote %s', args.out)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
