#!/usr/bin/env python3
import argparse
import logging
from pathlib import Path
from typing import Any, Dict, Iterable, List, Set, Tuple

from _common import read_json, save_text, configure_logging
import re


def find_conflicts(entries: List[Dict[str, Any]]) -> List[Tuple[str, List[str]]]:
    # Map lemma -> term -> set(short sources)
    by_lemma_terms: Dict[str, Dict[str, Set[str]]] = {}
    EO_ALLOWED_RE = re.compile(r"^[A-Za-zĈĜĤĴŜŬĉĝĥĵŝŭ\-]+$")

    def clean(term: str) -> str:
        t = (term or '').strip()
        if not t:
            return ''
        if any(x in t for x in ['|','{','}','bgcolor']):
            return ''
        t = re.sub(r"\s*Kategorio:[^\s]+.*$", "", t)
        t = re.sub(r"\s+", " ", t).strip()
        if '*' in t:
            return ''
        test = t.replace(' ', '')
        if not EO_ALLOWED_RE.match(test):
            return ''
        return t
    def short(src: str) -> str:
        s = src or ''
        if 'io_wiktionary' in s:
            return 'wikt_io'
        if 'eo_wiktionary' in s:
            return 'wikt_eo'
        if 'wikipedia' in s:
            return 'wiki'
        if 'pivot_en' in s:
            return 'pivot_en'
        if 'pivot_fr' in s:
            return 'pivot_fr'
        if 'langlinks' in s:
            return 'll'
        return s
    for e in entries:
        if (e.get('language') or '') != 'io':
            continue
        lemma = (e.get('lemma') or '').strip()
        if not lemma:
            continue
        tmap: Dict[str, Set[str]] = by_lemma_terms.setdefault(lemma, {})
        for s in e.get('senses', []) or []:
            for tr in s.get('translations', []) or []:
                if tr.get('lang') != 'eo':
                    continue
                term = clean(tr.get('term') or '')
                if not term:
                    continue
                srcs = tr.get('sources') or []
                bucket = tmap.setdefault(term, set())
                for src in srcs:
                    bucket.add(short(str(src)))
    conflicts: List[Tuple[str, List[str]]] = []
    for lemma, tmap in by_lemma_terms.items():
        # Only a conflict if at least two distinct EO terms and from at least two distinct sources
        if len(tmap) <= 1:
            continue
        all_srcs = set()
        for srcs in tmap.values():
            all_srcs.update(srcs)
        if len(all_srcs) <= 1:
            continue
        formatted = [f"{t}{{{','.join(sorted(srcs))}}}" if srcs else t for t, srcs in sorted(tmap.items())]
        conflicts.append((lemma, formatted))
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
    for lemma, terms in conflicts[:10000]:
        a(f'- {lemma}: {", ".join(terms)}')
    save_text(args.out, '\n'.join(lines) + '\n')
    logging.info('Wrote %s', args.out)
    return 0


if __name__ == '__main__':
    import sys
    raise SystemExit(main(sys.argv[1:]))


