#!/usr/bin/env python3
"""Extract Ido↔Esperanto pairs from Wikipedia interlanguage links.

Supports two source directions:

  iowiki (default):
    --xml  data/raw/iowiki-latest-pages-articles.xml.bz2
    --langlinks data/raw/iowiki-latest-langlinks.sql.gz
    Reads io.wiki XML for io page titles; extracts 'eo' rows from langlinks.

  eowiki (--source-wiki eo):
    --page-sql data/raw/eowiki-latest-page.sql.gz
    --langlinks data/raw/eowiki-latest-langlinks.sql.gz
    Reads eo.wiki page SQL for eo page titles; extracts 'io' rows from langlinks.

In both cases the output schema is identical: lemma=io_title, lang='io',
translation lang='eo', source tag = 'wikipedia_langlinks'.

Filters:
  - Drop pairs where either title contains digits (asteroid designations etc.)
  - Drop pairs where titles contain parentheses or dots (template artifacts)
  - Require length >= 3 and start-with-letter on both sides
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def extract_pages_from_xml(xml_path: Path) -> dict[int, str]:
    """page_id -> title for namespace-0 pages from a Wikipedia XML dump."""
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


def extract_pages_from_sql(sql_path: Path) -> dict[int, str]:
    """page_id -> title for namespace-0 pages from a Wikipedia page.sql dump.

    The page table schema is:
      (page_id, page_namespace, page_title, ...)
    We capture rows where page_namespace=0.
    """
    pages: dict[int, str] = {}
    proc = subprocess.Popen(['zcat', str(sql_path)], stdout=subprocess.PIPE)
    # Match: (int, 0, 'title', ...) — namespace field is the second value
    pat = re.compile(rb"\((\d+),0,'((?:[^'\\]|\\.)*)(?:','[^)]*\)|\|)")
    assert proc.stdout is not None
    for line in proc.stdout:
        if b'INSERT INTO' not in line:
            continue
        # Use a broader pattern: capture (page_id, namespace, title)
        for m in re.finditer(rb"\((\d+),(\d+),'((?:[^'\\]|\\.)*)'", line):
            pid = int(m.group(1))
            ns = int(m.group(2))
            if ns != 0:
                continue
            title = (
                m.group(3)
                .decode('utf-8', errors='ignore')
                .replace("\\'", "'")
                .replace('\\"', '"')
                .replace('\\\\', '\\')
                .replace('_', ' ')
            )
            pages[pid] = title
    proc.wait()
    return pages


def extract_langlinks(sql_path: Path, target_lang: str) -> dict[int, str]:
    """page_id -> target_title for pages with a langlink to target_lang."""
    out: dict[int, str] = {}
    lang_bytes = target_lang.encode()
    proc = subprocess.Popen(['zcat', str(sql_path)], stdout=subprocess.PIPE)
    pat = re.compile(
        rb"\((\d+),'" + re.escape(lang_bytes) + rb"','((?:[^'\\]|\\.)*)'\)"
    )
    assert proc.stdout is not None
    for line in proc.stdout:
        if lang_bytes not in line:
            continue
        for m in pat.finditer(line):
            pid = int(m.group(1))
            title = (
                m.group(2)
                .decode('utf-8', errors='ignore')
                .replace("\\'", "'")
                .replace('\\"', '"')
                .replace('\\\\', '\\')
                .replace('_', ' ')
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


def build_pairs(
    page_titles: dict[int, str],
    langlink_titles: dict[int, str],
    page_lang: str,
    link_lang: str,
    source_tag: str,
) -> list[dict]:
    """Join + filter into entries suitable for build_one_big_bidix_json.

    page_titles: {page_id: title} for the source wiki
    langlink_titles: {page_id: title} for the target language
    page_lang / link_lang: 'io' or 'eo' — which side is which
    Output always has lemma=io_title, translation lang=eo.
    """
    pairs: list[dict] = []
    for pid, link_title in langlink_titles.items():
        page_title = page_titles.get(pid)
        if not page_title:
            continue
        if page_lang == 'io':
            io_title, eo_title = page_title, link_title
        else:
            eo_title, io_title = page_title, link_title
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
                    'source': source_tag,
                }],
            }],
            'provenance': [{
                'source': source_tag,
                'page': io_title,
            }],
        })
    return pairs


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    base = Path(__file__).resolve().parents[1]

    ap.add_argument(
        '--source-wiki', choices=['io', 'eo'], default='io',
        help="Which Wikipedia to use as the page source (default: io)"
    )
    ap.add_argument('--xml', type=Path,
                    default=base / 'data/raw/iowiki-latest-pages-articles.xml.bz2',
                    help="io.wiki XML dump (used when --source-wiki=io)")
    ap.add_argument('--page-sql', type=Path,
                    default=base / 'data/raw/eowiki-latest-page.sql.gz',
                    help="eo.wiki page.sql dump (used when --source-wiki=eo)")
    ap.add_argument('--langlinks', type=Path,
                    help="langlinks SQL dump (default: auto-selected by source-wiki)")
    ap.add_argument('--out', type=Path,
                    help="Output path (default: auto-selected by source-wiki)")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

    if args.source_wiki == 'io':
        langlinks_path = args.langlinks or base / 'data/raw/iowiki-latest-langlinks.sql.gz'
        out_path = args.out or base / 'work/io_eo_langlinks.json'
        target_lang = 'eo'
        source_tag = 'wikipedia_langlinks'

        logger.info('Extracting io.wiki page_id → title from %s', args.xml)
        page_titles = extract_pages_from_xml(args.xml)
        logger.info('  %d io pages', len(page_titles))
    else:
        langlinks_path = args.langlinks or base / 'data/raw/eowiki-latest-langlinks.sql.gz'
        out_path = args.out or base / 'work/eo_io_langlinks.json'
        target_lang = 'io'
        source_tag = 'eowiki_langlinks'

        logger.info('Extracting eo.wiki page_id → title from %s', args.page_sql)
        page_titles = extract_pages_from_sql(args.page_sql)
        logger.info('  %d eo pages', len(page_titles))

    logger.info('Extracting %s→%s langlinks from %s', args.source_wiki, target_lang, langlinks_path)
    link_titles = extract_langlinks(langlinks_path, target_lang)
    logger.info('  %d %s→%s links', len(link_titles), args.source_wiki, target_lang)

    logger.info('Building filtered pairs...')
    pairs = build_pairs(page_titles, link_titles, args.source_wiki, target_lang, source_tag)
    logger.info('  %d clean (io_title, eo_title) pairs', len(pairs))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(pairs, f, ensure_ascii=False, indent=None)
    logger.info('Wrote %s', out_path)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
