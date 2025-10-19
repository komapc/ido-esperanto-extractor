#!/usr/bin/env python3
import argparse
import logging
from pathlib import Path
from typing import Any, Dict, Iterable, List, Set, Tuple

from _common import read_json, save_text, configure_logging


def find_conflicts(entries: List[Dict[str, Any]]) -> List[Tuple[str, str, List[str]]]:
    # Map lemma -> set of EO terms
    eo_by_lemma: Dict[str, Set[str]] = {}
    for e in entries:
        if (e.get('language') or '') != 'io':
            continue
        lemma = (e.get('lemma') or '').strip()
        if not lemma:
            continue
        terms: Set[str] = eo_by_lemma.setdefault(lemma, set())
        for s in e.get('senses', []) or []:
            for tr in s.get('translations', []) or []:
                if tr.get('lang') == 'eo':
                    term = (tr.get('term') or '').strip()
                    if term:
                        terms.add(term)
    conflicts: List[Tuple[str, str, List[str]]] = []
    for lemma, terms in eo_by_lemma.items():
        if len(terms) > 1:
            conflicts.append((lemma, 'eo', sorted(terms)))
    conflicts.sort(key=lambda x: x[0])
    return conflicts


def main(argv: Iterable[str]) -> int:
    ap = argparse.ArgumentParser(description='Report IO lemmas with multiple distinct EO translations')
    ap.add_argument('--input', type=Path, default=Path(__file__).resolve().parents[1] / 'dist/bidix_big.json')
    ap.add_argument('--out', type=Path, default=Path(__file__).resolve().parents[1] / 'reports/bidix_conflicts.md')
    ap.add_argument('-v', '--verbose', action='count', default=0)
    args = ap.parse_args(list(argv))

    configure_logging(args.verbose)
    entries = read_json(args.input) if args.input.exists() else []
    conflicts = find_conflicts(entries)
    lines: List[str] = []
    a = lines.append
    a('# IO→EO Conflicts (multiple EO terms per IO lemma)')
    a(f'- Total conflicts: {len(conflicts)}\n')
    for lemma, lang, terms in conflicts[:10000]:
        a(f'- {lemma}: {", ".join(terms)}')
    save_text(args.out, '\n'.join(lines) + '\n')
    logging.info('Wrote %s', args.out)
    return 0


if __name__ == '__main__':
    import sys
    raise SystemExit(main(sys.argv[1:]))


