#!/usr/bin/env python3
import argparse
import logging
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from _common import read_json, write_json, configure_logging
import re


def build_big_bidix(entries_paths: List[Path]) -> List[Dict[str, Any]]:
    # Load and merge all input files
    entries = []
    for path in entries_paths:
        if path.exists():
            logging.info("Loading %s", path)
            entries.extend(read_json(path))
        else:
            logging.warning("File not found: %s (skipping)", path)
    # Map: (lemma, pos) -> { 'lemma':.., 'pos':.., 'language':'io', 'morphology':.., 'translations': term -> set(sources), 'provenance': set(sources) }
    by_key: Dict[Tuple[str, str], Dict[str, Any]] = {}

    def sources_from_prov(prov_list: Any) -> List[str]:
        out: List[str] = []
        for p in prov_list or []:
            if isinstance(p, dict):
                s = str(p.get('source') or '')
                if s:
                    out.append(s)
        return out

    EO_ALLOWED_RE = re.compile(r"^[A-Za-zĈĜĤĴŜŬĉĝĥĵŝŭ\-]+$")

    def clean_term(term: str) -> str:
        t = (term or '').strip()
        if not t:
            return ''
        # Drop table/template artifacts and categories
        if any(x in t for x in ['|', '{', '}', 'bgcolor']):
            return ''
        t = re.sub(r"\s*Kategorio:[^\s]+.*$", "", t)
        t = re.sub(r"\s+", " ", t).strip()
        # Drop bullet/star artifacts
        if '*' in t:
            return ''
        # Enforce Esperanto orthography (letters + hyphen); remove spaces for test
        test = t.replace(' ', '')
        if not EO_ALLOWED_RE.match(test):
            return ''
        return t

    for e in entries:
        if (e.get('language') or '') != 'io':
            continue
        lemma = (e.get('lemma') or '').strip()
        pos = (e.get('pos') or '').strip()
        if not lemma:
            continue
        key = (lemma.lower(), pos.lower())
        rec = by_key.get(key)
        if rec is None:
            rec = {
                'lemma': lemma,
                'pos': pos or None,
                'language': 'io',
                'morphology': (e.get('morphology') or {}),
                '_eo_terms': {},  # term -> set(sources)
                '_all_sources': set(),
            }
            by_key[key] = rec
        # Accumulate sources
        for s in sources_from_prov(e.get('provenance')):
            rec['_all_sources'].add(s)
        # Collect only EO translations, aggregate per term sources
        for s in e.get('senses', []) or []:
            for tr in s.get('translations', []) or []:
                lang = tr.get('lang')
                raw = (tr.get('term') or '')
                term = clean_term(raw)
                if lang != 'eo' or not term:
                    continue
                src = str(tr.get('source') or '')
                cur = rec['_eo_terms'].setdefault(term, set())
                if src:
                    cur.add(src)

    # Materialize final structure: senses with EO-only translations; keep multi-provenance per translation
    out: List[Dict[str, Any]] = []
    for (_lm, _pos), rec in sorted(by_key.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        translations: List[Dict[str, Any]] = []
        for term, srcs in sorted(rec['_eo_terms'].items(), key=lambda kv: kv[0]):
            translations.append({
                'lang': 'eo',
                'term': term,
                # keep all sources; do not include confidence
                'sources': sorted(srcs),
            })
        senses = []
        if translations:
            senses.append({'senseId': None, 'gloss': None, 'translations': translations})
        out.append({
            'lemma': rec['lemma'],
            'pos': rec['pos'],
            'language': 'io',
            'senses': senses,
            'morphology': rec.get('morphology') or {},
            # retain union of sources at entry level as provenance summary
            'provenance': [{'source': s} for s in sorted(rec['_all_sources'])],
        })
    return out


def main(argv: Iterable[str]) -> int:
    ap = argparse.ArgumentParser(description='Build ONE BIG BIDIX JSON (EO-only translations, multi-provenance, no confidence)')
    ap.add_argument('--input', type=Path, action='append', help='Input JSON file(s) to merge (can be specified multiple times)')
    ap.add_argument('--out', type=Path, default=Path(__file__).resolve().parents[1] / 'dist/bidix_big.json')
    ap.add_argument('-v', '--verbose', action='count', default=0)
    args = ap.parse_args(list(argv))

    configure_logging(args.verbose)
    
    # Default inputs if none specified
    base_path = Path(__file__).resolve().parents[1]
    inputs = args.input if args.input else [
        base_path / 'work/bilingual_with_morph.json',
        base_path / 'work/fr_wikt_meanings.json',
    ]
    
    big = build_big_bidix(inputs)
    write_json(args.out, big)
    logging.info('Wrote %s (%d entries)', args.out, len(big))
    return 0


if __name__ == '__main__':
    import sys
    raise SystemExit(main(sys.argv[1:]))


