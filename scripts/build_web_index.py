#!/usr/bin/env python3
import argparse
import json
import logging
from pathlib import Path
from typing import Any, Dict, Iterable, List

from _common import read_json, ensure_dir, configure_logging


def build_index(bidix_path: Path, out_path: Path) -> None:
    data = read_json(bidix_path)
    records: List[Dict[str, Any]] = []
    for e in data:
        if (e.get('language') or '') != 'io':
            continue
        lemma = (e.get('lemma') or '').strip()
        if not lemma:
            continue
        pos = e.get('pos') or None
        # Collect EO translations (unique)
        terms: List[str] = []
        seen = set()
        for s in e.get('senses', []) or []:
            for tr in s.get('translations', []) or []:
                if tr.get('lang') != 'eo':
                    continue
                term = (tr.get('term') or '').strip()
                if not term:
                    continue
                # Add short sources if present
                srcs = []
                for sname in tr.get('sources') or []:
                    sname = str(sname)
                    if 'io_wiktionary' in sname:
                        srcs.append('wikt_io')
                    elif 'eo_wiktionary' in sname:
                        srcs.append('wikt_eo')
                    elif 'wikipedia' in sname:
                        srcs.append('wiki')
                    elif 'pivot_en' in sname:
                        srcs.append('pivot_en')
                    elif 'pivot_fr' in sname:
                        srcs.append('pivot_fr')
                    elif 'langlinks' in sname:
                        srcs.append('ll')
                label = term
                if srcs:
                    label = f"{term}{{{','.join(sorted(set(srcs)))}}}"
                if label in seen:
                    continue
                seen.add(label)
                terms.append(label)
        records.append({'l': lemma, 'p': pos, 't': terms})

    ensure_dir(out_path.parent)
    out_path.write_text(json.dumps(records, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
    logging.info('Wrote %s (%d records)', out_path, len(records))


def main(argv: Iterable[str]) -> int:
    ap = argparse.ArgumentParser(description='Build compact web index JSON from BIG BIDIX')
    ap.add_argument('--input', type=Path, default=Path(__file__).resolve().parents[1] / 'dist/bidix_big.json')
    ap.add_argument('--out', type=Path, default=Path(__file__).resolve().parents[1] / 'docs/data/index.json')
    ap.add_argument('-v', '--verbose', action='count', default=0)
    args = ap.parse_args(list(argv))

    configure_logging(args.verbose)
    build_index(args.input, args.out)
    return 0


if __name__ == '__main__':
    import sys
    raise SystemExit(main(sys.argv[1:]))


