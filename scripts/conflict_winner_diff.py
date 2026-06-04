#!/usr/bin/env python3
"""Show how confidence-ranked selection changes bidix winners — WITHOUT a regen.

Conflict *selection* runs over dist/bidix_big.json, which already holds every
candidate + provenance. This diffs the current `eo_terms[0]` (insertion-order)
winner against the deterministic scorer, for every lemma with >1 EO candidate.
It is the validation gate for PIPELINE_AUDIT.md P3: tune/approve the score by the
visible blast radius across all conflicts, not by a ~10-sentence gold set.

Usage:
  python3 scripts/conflict_winner_diff.py                 # baseline scorer
  python3 scripts/conflict_winner_diff.py --table demote-eo --show 40
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from conflict_resolution import (
    SOURCE_RANK_BASELINE, SOURCE_RANK_DEMOTE_EO, pick_best,
)


def _candidates(entry):
    """[(term, [sources]), …] in stored order, deduped by term (sources merged)."""
    order, by_term = [], {}
    for s in entry.get('senses') or []:
        for tr in s.get('translations') or []:
            if tr.get('lang') != 'eo':
                continue
            term = (tr.get('term') or '').strip()
            if not term:
                continue
            srcs = tr.get('sources') or ([tr['source']] if tr.get('source') else [])
            if term not in by_term:
                by_term[term] = set()
                order.append(term)
            by_term[term].update(srcs)
    return [(t, sorted(by_term[t])) for t in order]


def main() -> int:
    here = Path(__file__).resolve().parent.parent
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--bidix', type=Path, default=here / 'dist/bidix_big.json')
    ap.add_argument('--table', choices=['baseline', 'demote-eo'], default='baseline')
    ap.add_argument('--show', type=int, default=25, help='sample N changed winners')
    args = ap.parse_args()

    table = SOURCE_RANK_BASELINE if args.table == 'baseline' else SOURCE_RANK_DEMOTE_EO
    data = json.loads(args.bidix.read_text(encoding='utf-8'))
    entries = data if isinstance(data, list) else data.get('entries', data)

    multi = 0
    changed = []
    for e in entries:
        if not isinstance(e, dict):
            continue
        lm = str(e.get('lemma') or '').strip()
        cands = _candidates(e)
        if len(cands) < 2:
            continue
        multi += 1
        old = cands[0][0]                       # current eo_terms[0] behaviour
        new = pick_best(cands, table)           # deterministic scorer
        if new != old:
            changed.append((lm, old, new, cands))

    print(f"table={args.table}  multi-candidate lemmas={multi}  "
          f"winners changed={len(changed)} ({100*len(changed)/max(multi,1):.1f}%)")
    print("-" * 70)
    for lm, old, new, cands in changed[:args.show]:
        srcmap = {t: s for t, s in cands}
        print(f"{lm:18} {old!r}{srcmap.get(old)}  →  {new!r}{srcmap.get(new)}")
    if len(changed) > args.show:
        print(f"... and {len(changed) - args.show} more")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
