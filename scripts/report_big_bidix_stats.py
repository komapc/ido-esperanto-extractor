#!/usr/bin/env python3
import argparse
import logging
from pathlib import Path
from typing import Any, Dict, Iterable, List

from _common import read_json, save_text, configure_logging


def short_source(src: str) -> str:
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


def compute_stats(path: Path) -> Dict[str, Any]:
    data = read_json(path)
    total = len(data)
    per_source: Dict[str, int] = {}
    with_tr_src: Dict[str, int] = {}
    tr_counts: Dict[str, int] = {}
    # Count by entry-level provenance sources
    for e in data:
        prov = e.get('provenance') or []
        seen = set()
        for p in prov:
            if isinstance(p, dict):
                ss = short_source(str(p.get('source') or ''))
                if not ss:
                    continue
                seen.add(ss)
        for ss in seen:
            per_source[ss] = per_source.get(ss, 0) + 1
    # Translation-level sources presence (EO-only)
    for e in data:
        for s in e.get('senses', []) or []:
            for tr in s.get('translations', []) or []:
                if tr.get('lang') != 'eo':
                    continue
                present_in_entry: set[str] = set()
                for sname in tr.get('sources') or []:
                    ss = short_source(str(sname))
                    if not ss:
                        continue
                    tr_counts[ss] = tr_counts.get(ss, 0) + 1
                    present_in_entry.add(ss)
                for ss in present_in_entry:
                    with_tr_src[ss] = with_tr_src.get(ss, 0) + 1
    return {
        'total': total,
        'per_source': dict(sorted(per_source.items())),
        'entries_with_translation_sources': dict(sorted(with_tr_src.items())),
        'translation_pairs_by_source': dict(sorted(tr_counts.items())),
    }


def render_md(stats: Dict[str, Any]) -> str:
    lines: List[str] = []
    a = lines.append
    a('# BIG BIDIX Statistics')
    a(f'- Total entries: {stats["total"]}')
    a('\n## Entries per source (entry-level provenance)')
    for k, v in stats['per_source'].items():
        a(f'- {k}: {v}')
    a('\n## Entries with any translation-level source (EO)')
    for k, v in stats.get('entries_with_translation_sources', {}).items():
        a(f'- {k}: {v}')
    a('\n## EO translation pairs by source (counts)')
    for k, v in stats.get('translation_pairs_by_source', {}).items():
        a(f'- {k}: {v}')
    a('')
    return '\n'.join(lines)


def main(argv: Iterable[str]) -> int:
    ap = argparse.ArgumentParser(description='Report statistics for ONE BIG BIDIX JSON')
    ap.add_argument('--input', type=Path, default=Path(__file__).resolve().parents[1] / 'dist/bidix_big.json')
    ap.add_argument('--out', type=Path, default=Path(__file__).resolve().parents[1] / 'reports/big_bidix_stats.md')
    ap.add_argument('-v', '--verbose', action='count', default=0)
    args = ap.parse_args(list(argv))

    configure_logging(args.verbose)
    stats = compute_stats(args.input)
    save_text(args.out, render_md(stats) + '\n')
    logging.info('Wrote %s', args.out)
    return 0


if __name__ == '__main__':
    import sys
    raise SystemExit(main(sys.argv[1:]))


