#!/usr/bin/env python3
"""Regression tests for the active-future participle/agent-noun derivation
(-onta/-onto), added to close the MEDIUM defect from the 2026-06-14
morphology review ("kantonta" -> "*kantonta").

Covers two bugs caught while implementing this:

1. data/pardefs.xml must stay well-formed XML. An earlier edit added an XML
   comment containing a literal "--", which is illegal inside an XML comment
   and made the file unparseable. load_pardefs_from_file() used to swallow
   that ParseError silently and fall back to an EMPTY <pardefs/> element, so
   export_apertium.py "succeeded" while quietly producing a .dix with every
   <par n="..."/> reference left dangling -- the failure only surfaced later
   as an opaque `Undefined paradigm` error from `lt-comp` during `make`.
   load_pardefs_from_file() now raises instead of swallowing the error.

2. -onta (active-future participle adjective, e.g. "kantonta") is
   productively generatable by apertium-epo via <vblex><pp2><sg> (verified
   directly against apertium-epo across several verbs), so its bidix
   derivation goes through the real generator like der_ppa/der_ppas/der_pprs.
   -onto (the corresponding future agent NOUN, e.g. "kreonto") is NOT --
   apertium-epo rejects generating any -onto noun form regardless of verb
   stem -- so, unlike der_pres/der_act/der_past (anto/ado/into), der_onto
   gets no bidix entry at all (monodix analysis only, same class of gap as
   der_izar/der_esar/der_aj).
"""

import sys
from pathlib import Path
from xml.etree import ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'scripts'))

from export_apertium import build_bidix, load_pardefs_from_file

_PARDEFS_PATH = Path(__file__).resolve().parent.parent / 'data' / 'pardefs.xml'


def test_pardefs_xml_is_well_formed():
    load_pardefs_from_file(_PARDEFS_PATH)  # raises ET.ParseError if malformed


def test_pardefs_xml_defines_onta_and_onto():
    root = load_pardefs_from_file(_PARDEFS_PATH)
    ar_vblex = next(pd for pd in root.iter('pardef') if pd.get('n') == 'ar__vblex')
    lefts = {e.find('p/l').text for e in ar_vblex.iter('e')}
    assert 'onta' in lefts
    assert 'onto' in lefts


def _kanti_entry():
    return {
        "lemma": "kantar",
        "pos": "vblex",
        "language": "io",
        "morphology": {"paradigm": "ar__vblex"},
        "senses": [{"translations": [{"lang": "eo", "term": "kanti",
                                       "sources": ["io_wiktionary"]}]}],
    }


def test_der_onta_uses_generator_tags_not_literal_suffix():
    result = build_bidix([_kanti_entry()])
    xml_str = ET.tostring(result, encoding='unicode')
    assert 'der_onta' in xml_str
    # Generator route: right side is the EPO LEMMA ("kanti") + pp2, not a
    # literal "kantonta" string (which is what der_ppra/der_pfut do because
    # THEIR tags aren't generatable -- der_onta's pp2 tag is).
    for e in result.iter('e'):
        l = e.find('p/l')
        if l is not None and any(s.get('n') == 'der_onta' for s in l.findall('s')):
            r = e.find('p/r')
            assert r.text == 'kanti'
            assert any(s.get('n') == 'pp2' for s in r.findall('s'))
            break
    else:
        raise AssertionError("no der_onta bidix entry emitted")


def test_der_onto_has_no_bidix_entry():
    # apertium-epo cannot generate -onto for any verb stem, so no bidix <e>
    # should reference it (monodix-only, like der_izar/der_esar/der_aj) -- the
    # sdef declaration itself is unconditional and doesn't count.
    result = build_bidix([_kanti_entry()])
    for e in result.iter('e'):
        for s in e.iter('s'):
            assert s.get('n') != 'der_onto'
