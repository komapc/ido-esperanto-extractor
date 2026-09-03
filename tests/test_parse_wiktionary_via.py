#!/usr/bin/env python3
"""Tests for parse_wiktionary_via.build_english_via_pairs' (lemma, senseId)
keying (Fix A) — io/eo terms from the same English Wiktionary page must only
cross-pair when they came from the same trans-top/trans-bottom sense block,
matching the senseId wiktionary_parser.py now assigns per block.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'scripts'))

from parse_wiktionary_via import build_english_via_pairs


def _entry(lemma, senses):
    return {'lemma': lemma, 'senses': senses}


def test_same_sense_pairs_cross_but_different_senses_do_not(tmp_path):
    # "light" page: block 3 = "to set fire to" (io: nothing), block 5 =
    # "to illuminate" (eo: lumigi), block 57 = "to find by chance" (io: trovar).
    # Real data (both io and eo terms) live in ONE shared file, as
    # parse_wiktionary_en.py's --io-input/--eo-input both point at
    # en_wikt_en_both.json.
    shared = [
        _entry('like', [
            {'senseId': 1, 'translations': [{'lang': 'io', 'term': 'prizar'}]},
            {'senseId': 1, 'translations': [{'lang': 'eo', 'term': 'ŝati'}]},
            {'senseId': 17, 'translations': [{'lang': 'io', 'term': 'quale'}]},
            {'senseId': 17, 'translations': [{'lang': 'eo', 'term': 'kiel'}]},
        ]),
        _entry('light', [
            {'senseId': 57, 'translations': [{'lang': 'io', 'term': 'trovar'}]},
            {'senseId': 5, 'translations': [{'lang': 'eo', 'term': 'lumigi'}]},
        ]),
    ]
    shared_path = tmp_path / 'en_wikt_en_both.json'
    shared_path.write_text(json.dumps(shared))
    out_path = tmp_path / 'bilingual_via_en.json'

    build_english_via_pairs(shared_path, shared_path, out_path)

    results = json.loads(out_path.read_text())
    pairs = {(r['lemma_io'], r['lemma_eo']) for r in results}

    assert ('prizar', 'ŝati') in pairs
    assert ('quale', 'kiel') in pairs
    # trovar (block 57) and lumigi (block 5) are different senses on "light"
    # and must NOT be paired — this is the bug being fixed.
    assert ('trovar', 'lumigi') not in pairs
    # cross-sense combinations on "like" must not appear either.
    assert ('prizar', 'kiel') not in pairs
    assert ('quale', 'ŝati') not in pairs


def test_flat_none_sense_id_never_pairs():
    # A page where the only io senses came from parse_wiktionary's flat,
    # unscoped translations = extract_translations(section, "io") fallback
    # (senseId=None) must never pair with anything, since eo terms always
    # carry a real int senseId from the block-scoped extraction.
    import tempfile
    shared = [
        _entry('word', [
            {'senseId': None, 'translations': [{'lang': 'io', 'term': 'vorto'}]},
            {'senseId': 0, 'translations': [{'lang': 'eo', 'term': 'vorto'}]},
        ]),
    ]
    with tempfile.TemporaryDirectory() as d:
        shared_path = Path(d) / 'en_wikt_en_both.json'
        shared_path.write_text(json.dumps(shared))
        out_path = Path(d) / 'bilingual_via_en.json'
        build_english_via_pairs(shared_path, shared_path, out_path)
        results = json.loads(out_path.read_text())
    assert results == []
