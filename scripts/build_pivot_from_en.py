#!/usr/bin/env python3
import argparse
import logging
from pathlib import Path
from typing import Any, Dict, Iterable, List, Set

from _common import read_json, write_json, configure_logging


def build(ioeo_path: Path, out_path: Path) -> None:
    entries = read_json(ioeo_path)
    out: List[Dict[str, Any]] = []
    added = 0
    for e in entries:
        io_terms: Set[str] = set()
        eo_terms: Set[str] = set()
        for s in e.get('senses', []) or []:
            for tr in s.get('translations', []) or []:
                term = (tr.get('term') or '').strip()
                if not term:
                    continue
                if tr.get('lang') == 'io':
                    io_terms.add(term)
                elif tr.get('lang') == 'eo':
                    eo_terms.add(term)
        if not (io_terms and eo_terms):
            continue
        for io_t in sorted(io_terms):
            for eo_t in sorted(eo_terms):
                item = {
                    'lemma': io_t,
                    'pos': e.get('pos'),
                    'language': 'io',
                    'senses': [{
                        'senseId': None,
                        'gloss': None,
                        'translations': [{ 'lang': 'eo', 'term': eo_t, 'source': 'pivot_en_dump', 'sources': ['pivot_en'] }]
                    }],
                    'provenance': [{'source': 'pivot_en_dump', 'page': e.get('lemma')}],
                }
                out.append(item)
                added += 1
    write_json(out_path, out)
    logging.info('Wrote %s (%d items)', out_path, added)


def main(argv: Iterable[str]) -> int:
    ap = argparse.ArgumentParser(description='Build IO↔EO pairs from English Wiktionary (pages with both IO and EO translations)')
    ap.add_argument('--input', type=Path, default=Path(__file__).resolve().parents[1] / 'work/en_wikt_en_xx.json')
    ap.add_argument('--out', type=Path, default=Path(__file__).resolve().parents[1] / 'work/bilingual_pivot_from_en.json')
    ap.add_argument('-v', '--verbose', action='count', default=0)
    args = ap.parse_args(list(argv))

    configure_logging(args.verbose)
    build(args.input, args.out)
    return 0


if __name__ == '__main__':
    import sys
    raise SystemExit(main(sys.argv[1:]))


