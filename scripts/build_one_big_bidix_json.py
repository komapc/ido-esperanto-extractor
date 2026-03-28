#!/usr/bin/env python3
import argparse
import logging
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from _common import read_json, write_json, configure_logging
from infer_morphology import infer_paradigm as _infer_paradigm
import re


# Normalize verbose Wiktionary POS names to short Apertium tags so that all
# entries in bidix_big.json carry a consistent POS regardless of source.
_SHORT_POS: Dict[str, str] = {
    "noun": "n", "adjective": "adj", "adverb": "adv", "verb": "vblex",
    "preposition": "pr", "conjunction": "cnjcoo",
    "subordinating conjunction": "cnjsub", "determiner": "det", "pronoun": "prn",
    "interjection": "ij", "numeral": "num",
}


# Translations for function words that have no usable Wiktionary entry.
# These are kept minimal — one canonical Esperanto equivalent per word.
_FUNCTION_WORD_OVERRIDES: Dict[str, Dict[str, str]] = {
    'e':   {'pos': 'cnjcoo',    'eo': 'kaj'},   # and
    'ed':  {'pos': 'cnjcoo',    'eo': 'kaj'},   # and (before vowels)
    'o':   {'pos': 'cnjcoo',    'eo': 'aŭ'},    # or
    'od':  {'pos': 'cnjcoo',    'eo': 'aŭ'},    # or (before vowels)
    'a':   {'pos': 'pr',        'eo': 'al'},     # to (direction)
    'al':  {'pos': 'pr',        'eo': 'al'},     # towards/to
    'kon': {'pos': 'pr',        'eo': 'kun'},    # with
    'multa': {'pos': 'det',     'eo': 'multa'},  # many/much
    'dal': {'pos': 'prep_art',  'eo': 'de'},     # da + la = from the (contraction)
}


def build_big_bidix(entries_paths: List[Path]) -> List[Dict[str, Any]]:
    # Load and merge all input files
    entries = []
    for path in entries_paths:
        if path.exists():
            logging.info("Loading %s", path)
            data = read_json(path)
            if isinstance(data, dict):
                entries.extend(data.get('entries', []))
            else:
                entries.extend(data)
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

    def clean_terms(raw: str):
        """Split on commas/semicolons, clean each part, yield valid terms."""
        for part in re.split(r'[,;]', raw or ''):
            t = clean_term(part)
            if t:
                yield t

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
        # Reject likely definitions (3+ words are descriptions, not translations)
        if t.count(' ') >= 2:
            return ''
        return t

    for e in entries:
        # Allow entries without a language field (source_io_wiktionary.json format)
        lang_field = e.get('language')
        if lang_field is not None and lang_field != 'io':
            continue
        lemma = (e.get('lemma') or '').strip()
        pos = _SHORT_POS.get((e.get('pos') or '').strip(), (e.get('pos') or '').strip())
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
                if tr.get('lang') != 'eo':
                    continue
                src = str(tr.get('source') or '')
                for term in clean_terms(tr.get('term') or ''):
                    cur = rec['_eo_terms'].setdefault(term, set())
                    if src:
                        cur.add(src)
        # Also collect top-level translations (source_io_wiktionary.json format)
        for tr in e.get('translations', []) or []:
            if tr.get('lang') != 'eo':
                continue
            src = str(tr.get('source') or '')
            for term in clean_terms(tr.get('term') or ''):
                cur = rec['_eo_terms'].setdefault(term, set())
                if src:
                    cur.add(src)

    # Inject function-word overrides for words absent from all sources.
    for lemma_lc, info in _FUNCTION_WORD_OVERRIDES.items():
        key = (lemma_lc, info['pos'])
        # prep_art uses its own paradigm name; other function words use __<pos>
        par = info['pos'] if info['pos'] == 'prep_art' else '__' + info['pos']
        if key not in by_key:
            by_key[key] = {
                'lemma': lemma_lc,
                'pos': info['pos'],
                'language': 'io',
                'morphology': {'paradigm': par, 'features': {}},
                '_eo_terms': {info['eo']: {'function_word_override'}},
                '_all_sources': {'function_word_override'},
            }
        elif not by_key[key]['_eo_terms']:
            # Entry exists (from whitelist) but has no translation — inject it
            by_key[key]['_eo_terms'][info['eo']] = {'function_word_override'}

    # Infer paradigm for entries with empty morphology (e.g. fr_wikt entries
    # that bypass prepare_vocabulary.py).  Uses the same function-word-aware
    # heuristic as infer_morphology.py so export_apertium.py needs no fallback.
    _POS_TO_PAR: Dict[str, str] = {
        'n': 'o__n', 'adj': 'a__adj', 'adv': 'e__adv', 'vblex': 'ar__vblex',
        'pr': '__pr', 'det': '__det', 'prn': '__prn',
        'cnjcoo': '__cnjcoo', 'cnjsub': '__cnjsub', 'ij': 'o__n', 'num': 'num',
    }
    for rec in by_key.values():
        if not (rec.get('morphology') or {}).get('paradigm'):
            par = _infer_paradigm(rec)
            if not par:
                # infer_morphology expects verbose POS; fall back to short-form map
                par = _POS_TO_PAR.get(str(rec.get('pos') or ''))
            if par:
                rec['morphology'] = {'paradigm': par, 'features': {}}

    # Materialize final structure: senses with EO-only translations; keep multi-provenance per translation
    out: List[Dict[str, Any]] = []
    for (_lm, _pos), rec in sorted(by_key.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        translations: List[Dict[str, Any]] = []
        for term, srcs in rec['_eo_terms'].items():
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
        # prepare_vocabulary.py output: normalized + morphology-inferred + filtered
        # (replaces the old bilingual_with_morph.json + source_io_wiktionary.json pair)
        base_path / 'work/final_vocabulary.json',
        base_path / 'work/fr_wikt_meanings.json',
    ]
    
    big = build_big_bidix(inputs)
    write_json(args.out, big)
    logging.info('Wrote %s (%d entries)', args.out, len(big))
    return 0


if __name__ == '__main__':
    import sys
    raise SystemExit(main(sys.argv[1:]))


