#!/usr/bin/env python3
import argparse
import logging
from pathlib import Path
from typing import Any, Dict, Iterable, List, Set, Tuple

from _common import read_json, save_text, configure_logging


def load_entries(path: Path) -> List[Dict[str, Any]]:
    data = read_json(path)
    return data if isinstance(data, list) else data.get('entries', data)


def lemmas_and_paradigms(entries: List[Dict[str, Any]]) -> Tuple[Set[str], Dict[str, Set[str]]]:
    lemmas: Set[str] = set()
    lemma_to_pars: Dict[str, Set[str]] = {}
    for e in entries:
        lemma = str(e.get('lemma') or '').strip()
        if not lemma:
            continue
        lemmas.add(lemma)
        par = None
        morph = e.get('morphology') or {}
        par = morph.get('paradigm') or e.get('pos') or ''
        lemma_to_pars.setdefault(lemma, set()).add(str(par))
    return lemmas, lemma_to_pars


def main(argv: Iterable[str]) -> int:
    ap = argparse.ArgumentParser(description='Lemma-only diff and paradigm differences')
    ap.add_argument('--old-json', type=Path, required=True)
    ap.add_argument('--new-json', type=Path, required=True)
    ap.add_argument('--report-md', type=Path, required=True)
    ap.add_argument('-v', '--verbose', action='count', default=0)
    args = ap.parse_args(list(argv))

    configure_logging(args.verbose)
    old_entries = load_entries(args.old_json)
    new_entries = load_entries(args.new_json)

    old_lemmas, old_pars = lemmas_and_paradigms(old_entries)
    new_lemmas, new_pars = lemmas_and_paradigms(new_entries)

    new_only = sorted(new_lemmas - old_lemmas)
    old_only = sorted(old_lemmas - new_lemmas)

    both = old_lemmas & new_lemmas
    paradigm_diffs: List[Tuple[str, List[str], List[str]]] = []
    for lemma in sorted(both):
        op = sorted(old_pars.get(lemma, set()))
        np = sorted(new_pars.get(lemma, set()))
        if op != np:
            paradigm_diffs.append((lemma, op, np))

    lines: List[str] = []
    lines.append('# Lemma-only Coverage Diff\n')
    lines.append(f'- Old lemmas: {len(old_lemmas)}')
    lines.append(f'- New lemmas: {len(new_lemmas)}')
    lines.append(f'- New-only lemmas: {len(new_only)}')
    lines.append(f'- Old-only lemmas: {len(old_only)}')
    lines.append(f'- Lemmas with paradigm differences: {len(paradigm_diffs)}\n')

    lines.append('## New-only lemmas (present now, missing before)\n')
    for l in new_only[:5000]:
        lines.append(f'- {l}')

    lines.append('\n## Old-only lemmas (present before, missing now)\n')
    for l in old_only[:5000]:
        lines.append(f'- {l}')

    lines.append('\n## Paradigm differences (same lemma, different paradigms)\n')
    for lemma, op, np in paradigm_diffs[:5000]:
        lines.append(f'- {lemma}: old={op} new={np}')

    save_text(args.report_md, '\n'.join(lines) + '\n')
    logging.info('Wrote %s', args.report_md)
    return 0


if __name__ == '__main__':
    import sys
    raise SystemExit(main(sys.argv[1:]))


