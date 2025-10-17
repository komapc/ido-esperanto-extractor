#!/usr/bin/env python3
import argparse
import logging
from pathlib import Path
from typing import Any, Dict, Iterable, List

from _common import read_json, write_json, configure_logging


def merge_function_words(entries_path: Path, function_words_path: Path, out_path: Path) -> None:
    entries = read_json(entries_path)
    if not isinstance(entries, list):
        raise ValueError("Expected list of entries in entries_path")
    fws = read_json(function_words_path)
    by_lemma = {str(e.get('lemma') or ''): e for e in entries}
    for fw in fws:
        lemma = str(fw.get('lemma') or '')
        pos = str(fw.get('pos') or '')
        if not lemma or not pos:
            continue
        if lemma in by_lemma:
            # If exists, ensure morphology/pos is consistent
            existing = by_lemma[lemma]
            existing['pos'] = pos
            existing['morphology'] = {'paradigm': pos if pos in {'cnjcoo','cnjsub','pr','det','prn'} else None, 'features': {}}
            continue
        by_lemma[lemma] = {
            'id': f'io:{lemma}:{pos}',
            'lemma': lemma,
            'pos': pos,
            'language': 'io',
            'senses': [],
            'morphology': { 'paradigm': pos if pos in {'cnjcoo','cnjsub','pr','det','prn'} else None, 'features': {} },
            'provenance': [ { 'source': 'whitelist' } ],
        }
    merged = list(by_lemma.values())
    merged.sort(key=lambda x: (str(x.get('lemma','')), str(x.get('pos',''))))
    write_json(out_path, merged)
    logging.info('Merged function words. Wrote %s (%d entries)', out_path, len(merged))


def main(argv: Iterable[str]) -> int:
    ap = argparse.ArgumentParser(description='Final preparation: merge function words whitelist')
    ap.add_argument('--input', type=Path, default=Path(__file__).resolve().parents[1] / 'work/final_vocabulary.json')
    ap.add_argument('--function-words', type=Path, default=Path(__file__).resolve().parents[1] / 'data/function_words_io.json')
    ap.add_argument('--out', type=Path, default=Path(__file__).resolve().parents[1] / 'work/final_vocabulary.json')
    ap.add_argument('-v', '--verbose', action='count', default=0)
    args = ap.parse_args(list(argv))

    configure_logging(args.verbose)
    merge_function_words(args.input, args.function_words, args.out)
    return 0


if __name__ == '__main__':
    import sys
    raise SystemExit(main(sys.argv[1:]))


