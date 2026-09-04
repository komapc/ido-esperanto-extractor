#!/usr/bin/env python3
"""Regression tests for the participial-adverb (gerund) derivations
-ante/-inte/-onte/-ate/-ite/-ote, found while auditing ar__vblex's
participle coverage after fixing -onta/-onto (see test_der_onta_onto.py).

Esperanto/Ido both have a full 2x3x2 participle system: 6 adjective forms
(anta/inta/onta active, ata/ita/ota passive -- pardefs.xml already covers
all 6) and 6 corresponding ADVERB/gerund forms (ante/inte/onte active,
ate/ite/ote passive) that pardefs.xml had none of. Coverage that existed
before this fix was pure accident: whatever specific -ante/-inte words
happened to have their own io_wiktionary page (e.g. "kantante") were
harvested as ordinary e__adv vocabulary entries, with no productive rule
behind them -- so "kantonte"/"kurate" etc. (no lucky Wiktionary page) were
simply unanalyzable.

Like der_onta, apertium-epo's generator only supports the ACTIVE forms
generically (<ger> for -ante, <gerpast> for -inte, verified across several
verb stems); -onte/-ate/-ite/-ote are rejected for every verb stem tested,
so those four get monodix analysis only, no bidix pair.
"""

import sys
from pathlib import Path
from xml.etree import ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'scripts'))

from export_apertium import build_bidix, load_pardefs_from_file, _drop_derivation_shadowed_entries

_PARDEFS_PATH = Path(__file__).resolve().parent.parent / 'data' / 'pardefs.xml'


def test_pardefs_xml_defines_all_six_gerund_suffixes():
    root = load_pardefs_from_file(_PARDEFS_PATH)
    ar_vblex = next(pd for pd in root.iter('pardef') if pd.get('n') == 'ar__vblex')
    lefts = {e.find('p/l').text for e in ar_vblex.iter('e')}
    for suffix in ('ante', 'inte', 'onte', 'ate', 'ite', 'ote'):
        assert suffix in lefts, f"pardefs.xml ar__vblex is missing -{suffix}"


def _kanti_entry():
    return {
        "lemma": "kantar",
        "pos": "vblex",
        "language": "io",
        "morphology": {"paradigm": "ar__vblex"},
        "senses": [{"translations": [{"lang": "eo", "term": "kanti",
                                       "sources": ["io_wiktionary"]}]}],
    }


def _find_der_entry(dictionary, der_tag):
    for e in dictionary.iter('e'):
        l = e.find('p/l')
        if l is not None and any(s.get('n') == der_tag for s in l.findall('s')):
            return e
    return None


def test_der_ante_and_der_inte_use_generator_tags():
    result = build_bidix([_kanti_entry()])
    for der_tag, epo_ptag in [('der_ante', 'ger'), ('der_inte', 'gerpast')]:
        e = _find_der_entry(result, der_tag)
        assert e is not None, f"no bidix entry for {der_tag}"
        r = e.find('p/r')
        assert r.text == 'kanti'
        assert any(s.get('n') == epo_ptag for s in r.findall('s'))


def test_no_bidix_entry_for_ungeneratable_gerunds():
    # apertium-epo cannot generate -onte/-ate/-ite/-ote for any verb stem.
    result = build_bidix([_kanti_entry()])
    for der_tag in ('der_onte', 'der_ate', 'der_ite', 'der_ote'):
        assert _find_der_entry(result, der_tag) is None, (
            f"{der_tag} should have no bidix entry (ungeneratable)")


def test_dead_lexicalized_gerund_is_shadowed_when_root_is_translated():
    # A translationless "kantante" entry harvested as its own e__adv
    # vocabulary item (as io_wiktionary genuinely does for some words) must
    # be dropped once the verb root "kantar" has a real translation -- the
    # new productive der_ante derivation already covers this exact surface
    # form.
    root = {"lemma": "kantar", "pos": "vblex", "morphology": {"paradigm": "ar__vblex"}, "senses": []}
    bidix_root = {"lemma": "kantar", "pos": "vblex", "morphology": {"paradigm": "ar__vblex"},
                  "senses": [{"translations": [{"lang": "eo", "term": "kanti"}]}]}
    dead = {"lemma": "kantante", "pos": None,
            "morphology": {"paradigm": "e__adv"}, "senses": []}
    result = _drop_derivation_shadowed_entries([root, dead], [bidix_root])
    lemmas = {e["lemma"] for e in result}
    assert "kantante" not in lemmas
