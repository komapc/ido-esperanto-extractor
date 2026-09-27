#!/usr/bin/env python3
"""
Tests for export_apertium.py to ensure it handles both old and new JSON formats.

Bug fixes tested:
1. Export script crashes when entries don't have 'language' field (new format)
2. Export script doesn't recognize 'eo_translations' field (new format)
3. Export script produces empty .dix files with new standardized JSON
"""

import sys
import json
import tempfile
from pathlib import Path
from xml.etree import ElementTree as ET

# Add parent directory to path to import the module
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'scripts'))

from export_apertium import build_monodix, build_bidix, _load_eo_generatable_lemmas, _EO_PRPERS_FEATS


def test_new_format_entries_without_language_field():
    """Test that entries without 'language' field are processed (new format)."""
    entries = [
        {"lemma": "hundo", "pos": "n"},
        {"lemma": "bela", "pos": "adj"},
    ]
    
    result = build_monodix(entries)
    assert result is not None
    
    # Check that XML contains entries
    xml_str = ET.tostring(result, encoding='unicode')
    assert 'hundo' in xml_str
    assert 'bela' in xml_str
    

def test_old_format_entries_with_language_field():
    """Test that entries with 'language' field are still processed (old format)."""
    entries = [
        {"lemma": "hundo", "pos": "n", "language": "io"},
        {"lemma": "kato", "pos": "n", "language": "eo"},  # Should be skipped
    ]
    
    result = build_monodix(entries)
    xml_str = ET.tostring(result, encoding='unicode')
    
    assert 'hundo' in xml_str
    assert 'kato' not in xml_str  # Non-io entries should be filtered


def test_new_format_eo_translations_field():
    """Test that new format 'eo_translations' field is recognized."""
    entries = [
        {
            "lemma": "hundo",
            "pos": "n",
            "eo_translations": ["hundo", "hundego"]
        }
    ]
    
    result = build_bidix(entries)
    xml_str = ET.tostring(result, encoding='unicode')
    
    assert 'hundo' in xml_str
    # Should have at least one eo translation
    assert '<r>' in xml_str


def test_old_format_senses_translations():
    """Test that old format with senses/translations still works."""
    entries = [
        {
            "lemma": "hundo",
            "pos": "n",
            "language": "io",
            "senses": [
                {
                    "translations": [
                        {"lang": "eo", "term": "hundo"}
                    ]
                }
            ]
        }
    ]
    
    result = build_bidix(entries)
    xml_str = ET.tostring(result, encoding='unicode')
    
    assert 'hundo' in xml_str
    assert '<r>' in xml_str


def test_mixed_format_entries():
    """Test that both old and new formats can be processed together."""
    entries = [
        # New format
        {"lemma": "hundo", "eo_translations": ["hundo"]},
        # Old format
        {
            "lemma": "kato",
            "language": "io",
            "senses": [{"translations": [{"lang": "eo", "term": "kato"}]}]
        }
    ]
    
    result = build_bidix(entries)
    xml_str = ET.tostring(result, encoding='unicode')
    
    assert 'hundo' in xml_str
    assert 'kato' in xml_str


def test_entries_with_null_lemma_are_skipped():
    """Test that entries with null or missing lemma are skipped."""
    entries = [
        {"lemma": None, "pos": "noun", "eo_translations": ["test"]},
        {"pos": "noun", "eo_translations": ["test2"]},  # No lemma field
        {"lemma": "validword", "pos": "noun", "eo_translations": ["birdo"]},
    ]

    result = build_bidix(entries)
    xml_str = ET.tostring(result, encoding='unicode')

    assert 'validword' in xml_str
    # Invalid entries should not cause crash


def test_entries_without_translations_are_skipped():
    """Test that entries without EO translations are skipped in bidix."""
    entries = [
        {"lemma": "notr", "eo_translations": []},  # Empty
        {"lemma": "hundo", "eo_translations": ["hundo"]},  # Valid
        {"lemma": "test"},  # No translations field
    ]
    
    result = build_bidix(entries)
    xml_str = ET.tostring(result, encoding='unicode')
    
    assert 'hundo' in xml_str
    # Entries without translations should be skipped
    assert xml_str.count('<e>') >= 1  # At least one valid entry


def test_large_entry_set():
    """Test that export handles large number of entries (regression for production data)."""
    # Simulate production-scale data: 14,481 entries
    # eo_translations must be a real, generatable EO lemma (the bidix
    # generatability gate filters out synthetic per-index terms like "vorto0").
    entries = [
        {"lemma": f"word{i}", "pos": "noun", "eo_translations": ["vorto"]}
        for i in range(14481)
    ]
    
    result = build_bidix(entries)
    assert result is not None
    
    xml_str = ET.tostring(result, encoding='unicode')
    # Should have created entries
    assert xml_str.count('<e>') >= 14480


def test_monodix_with_morphology():
    """Test monodix generation with morphology information."""
    entries = [
        {
            "lemma": "hundo",
            "pos": "n",
            "morphology": {"paradigm": "o__n"}
        }
    ]
    
    result = build_monodix(entries)
    xml_str = ET.tostring(result, encoding='unicode')
    
    assert 'hundo' in xml_str
    assert 'o__n' in xml_str


def test_dict_with_entries_key():
    """Test that dict format with 'entries' key is handled (standardized format)."""
    # This tests the wrapper function's handling, but we can test the core functions
    entries_data = {
        "metadata": {"source": "test"},
        "entries": [
            {"lemma": "hundo", "eo_translations": ["hundo"]}
        ]
    }
    
    # In actual usage, the export_apertium function extracts the entries
    # Here we test that the entries themselves are handled correctly
    result = build_bidix(entries_data["entries"])
    xml_str = ET.tostring(result, encoding='unicode')
    
    assert 'hundo' in xml_str


def test_generatable_lemmas_include_closed_class_personal_pronouns():
    """Regression: apertium-epo analyses/generates mi/ni/ci/vi/li/ŝi/ĝi/ili via
    the `prpers` paradigm, not individual <e lm="..."> monodix entries, so a
    naive lm= scan wrongly treats them as ungeneratable and drops the ido->epo
    li<prn> -> ili<prn> bidix entry (caught by comparing a fresh export against
    the previously-deployed dictionary, which still had it)."""
    valid = _load_eo_generatable_lemmas()
    if valid is None:
        return  # sibling apertium-epo checkout unavailable in this environment
    for pronoun in _EO_PRPERS_FEATS:
        assert pronoun in valid, f"{pronoun!r} missing from the generatability gate"


def test_generatable_lemmas_include_genuine_multiword_phrases():
    """Regression: a multi-word candidate backed by its own <e lm="tie ĉi">
    monodix entry (with a real <b/> between components) IS generatable and
    must not be excluded just because it contains a space — that would drop
    hik<adv> -> "tie ĉi" (Ido's single-word "hike" vs Esperanto's two-word
    "tie ĉi") and leave it untranslated (@hik)."""
    valid = _load_eo_generatable_lemmas()
    if valid is None:
        return
    assert 'tie ĉi' in valid


def test_pronoun_bidix_entry_survives_the_generatability_gate():
    entries = [
        {"lemma": "li", "pos": "prn",
         "morphology": {"paradigm": "li__prn"},
         "eo_translations": ["ili"]},
    ]
    result = build_bidix(entries)
    xml_str = ET.tostring(result, encoding='unicode')
    assert '<l>li<s n="prn" /></l><r>ili<s n="prn" /></r>' in xml_str


def test_generatable_lemmas_include_correlative_plural_and_case_forms():
    """Regression: apertium-epo's correlative words (kiu/tiu/...) are irregular
    closed-class entries — each inflected surface form (kiuj, kiujn, kiun, kioj,
    kion, ...) is spelled out directly as its own <e><p><l>SURFACE</l>...</p></e>
    pair with no shared lm= to scan. A pure lm= scan only ever finds the bare
    singular "kiu"/"kio", so the plural/accusative forms looked ungeneratable,
    dropping the ido->epo qui<prn> -> kiuj<prn> bidix entry entirely even
    though the closed_class_tables source already has the correct mapping."""
    valid = _load_eo_generatable_lemmas()
    if valid is None:
        return
    for form in ('kiuj', 'kiujn', 'kiun', 'kioj', 'kion'):
        assert form in valid, f"{form!r} missing from the generatability gate"


if __name__ == "__main__":
    print("Running export_apertium tests...")
    
    tests = [
        ("New format without language field", test_new_format_entries_without_language_field),
        ("Old format with language field", test_old_format_entries_with_language_field),
        ("New format eo_translations field", test_new_format_eo_translations_field),
        ("Old format senses/translations", test_old_format_senses_translations),
        ("Mixed format entries", test_mixed_format_entries),
        ("Null lemma handling", test_entries_with_null_lemma_are_skipped),
        ("Empty translations handling", test_entries_without_translations_are_skipped),
        ("Large entry set (14,481)", test_large_entry_set),
        ("Monodix with morphology", test_monodix_with_morphology),
        ("Dict with entries key", test_dict_with_entries_key),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        try:
            test_func()
            print(f"✅ PASS: {name}")
            passed += 1
        except AssertionError as e:
            print(f"❌ FAIL: {name}")
            print(f"   Error: {e}")
            failed += 1
        except Exception as e:
            print(f"❌ ERROR: {name}")
            print(f"   Error: {e}")
            failed += 1
    
    print(f"\n{'='*60}")
    print(f"Results: {passed} passed, {failed} failed")
    print(f"{'='*60}")
    
    sys.exit(0 if failed == 0 else 1)



def test_resolve_eo_side_closed_class():
    """Closed-class <r> sides take apertium-epo's generatable reading; open-class
    words and suppletive paradigm lemmas (prpers) keep the default."""
    from export_apertium import resolve_eo_side
    readings = {
        'ĉu': [('ĉu', ['cnjadv']), ('ĉu', ['adv', 'itg'])],
        'kion': [('kio', ['prn', 'itg', 'sg', 'acc'])],
        'tio': [('tio', ['prn', 'tn', 'sg', 'nom'])],
        'ol': [('ol', ['cnjsub'])],
        'hundo': [('hundo', ['n', 'sg', 'nom'])],
        'kaj': [('kaj', ['cnjcoo'])],
        'li': [('prpers', ['prn', 'subj', 'p3', 'm', 'sg'])],
    }
    assert resolve_eo_side('ĉu', 'adj', readings) == ('ĉu', ['adv', 'itg'])
    assert resolve_eo_side('ĉu', 'cnjcoo', readings) == ('ĉu', ['cnjadv'])
    assert resolve_eo_side('kion', 'prn', readings) == ('kio', ['prn', 'itg', 'sg', 'acc'])
    assert resolve_eo_side('tio', 'prn', readings) == ('tio', ['prn', 'tn', 'sg', 'nom'])
    assert resolve_eo_side('ol', 'adv', readings) == ('ol', ['cnjsub'])
    assert resolve_eo_side('hundo', 'n', readings) is None      # open class, same POS
    assert resolve_eo_side('kaj', 'cnjcoo', readings) is None   # already exact
    assert resolve_eo_side('li', 'prn', readings) is None       # prpers: bridged by t1x
    assert resolve_eo_side('nekonata', 'adj', readings) is None
    assert resolve_eo_side('tio', 'prn', {}) is None            # analyser unavailable


def test_pos_valid_prefers_a_winner_with_the_entrys_pos():
    from export_apertium import pos_valid
    readings = {"endormiĝi": [("endormiĝi", ["vbntr", "inf"])],
                "ekdormi": [("ekdormi", ["vblex", "inf"]), ("ekdormi", ["vbntr", "inf"])]}
    cands = [("endormiĝi", ["en_wiktionary_via"]), ("ekdormi", ["en_wiktionary_via"])]
    gen = {"endormiĝi", "ekdormi"}
    assert pos_valid(cands, "vblex", gen, readings) == {"ekdormi"}
    # no candidate has the POS: fall back to plain generatability, drop nothing
    assert pos_valid(cands[:1], "vblex", gen, readings) == {"endormiĝi"}
    # closed-class tags are the EO-side resolver's business, not this filter's
    assert pos_valid(cands, "prn", gen, readings) == gen


def test_pos_valid_drops_a_lowercase_name():
    """maria<adj> passed the casefolded lemma gate on Maria<np>'s account."""
    from export_apertium import pos_valid
    readings = {"Maria": [("Maria", ["np", "ant", "f", "sg", "nom"])],
                "Francio": [("Francio", ["np", "loc", "sg", "nom"])]}
    gen = {"maria", "francio"}
    assert pos_valid([("maria", ["bert_embeddings"])], "adj", gen, readings) == set()
    assert pos_valid([("Francio", ["wikipedia_langlinks"])], "np", gen, readings) == {"francio"}


def test_proper_noun_record_becomes_np():
    from export_apertium import np_lemmas, _record_paradigm, _resolve_np
    def rec(lm, par, *eo):
        return {"lemma": lm, "morphology": {"paradigm": par},
                "senses": [{"translations": [{"lang": "eo", "term": t} for t in eo]}]}
    readings = {"Francio": [("Francio", ["np", "loc", "sg", "nom"])],
                "Usono": [("Usono", ["np", "loc", "sg", "nom"])],
                "Anglo": [("Anglo", ["n", "m", "sg", "nom"])],
                "Judoj": [("judo", ["n", "pl", "nom"])],
                "arabo": [("arabo", ["n", "m", "sg", "nom"])]}
    recs = [rec("Francia", "o__n", "Francio"), rec("Francia", "o__n"),   # untranslated twin
            rec("Usa", "a__adj", "Usono", "Unuiĝintaj Ŝtatoj"),
            rec("Angliana", "a__adj", "Anglo"),        # demonym, not a name
            rec("Judi", "o__n", "Judoj"),              # plural surface, not a name
            rec("Arabi", "o__n", "arabo"),             # common noun, not a name
            rec("Germano", "o__n", "Germano"),         # inflecting -o noun
            rec("Ca", "a__adj", "Francio")]            # chemical symbol
    nps = np_lemmas(recs, readings)
    assert nps == {"Francia", "Usa"}
    assert _record_paradigm(recs[1], nps) == "np__np"
    assert _record_paradigm(recs[3], nps) == "a__adj"
    rs = [("Maria", ["np", "ant", "m", "sg"]), ("Maria", ["np", "ant", "f", "sg", "nom"])]
    assert _resolve_np(rs, "Maria") == ("Maria", ["np", "ant", "f"])
    assert _resolve_np([("Japano", ["n", "m", "sg", "nom"])], "Japano") == ("Japano", ["n", "m"])


def test_lowercase_name_lemmas():
    from export_apertium import _lowercase_name_lemmas
    readings = {"Maria": [("Maria", ["np", "ant", "f", "sg", "nom"])],
                "alia": [("alia", ["adj", "sg", "nom"])]}
    rec = lambda lm, *eo: {"lemma": lm, "senses": [{"translations": [
        {"lang": "eo", "term": t} for t in eo]}]}
    assert _lowercase_name_lemmas([rec("maria", "maria"), rec("altra", "alia"),
                                   rec("altra", "maria")], readings) == {"maria"}


def test_intransitive_participles_get_epo_to_ido_twins():
    """apertium-epo tags an intransitive verb's -anta as <vbntr><ppres> and its
    -inta as <vbntr><pp> (on transitive verbs those tags mean -ata/-ita), so
    venanta / venintajn found no bidix row and came out @ in epo->ido. They get
    RL-only rows to the active Ido participles; a transitive verb gets none."""
    from export_apertium import _load_eo_verb_class_lemmas
    vbntr = _load_eo_verb_class_lemmas("vbntr")
    if not vbntr:
        return  # sibling apertium-epo checkout unavailable in this environment
    assert 'veni' in vbntr and 'vidi' not in vbntr
    entries = [
        {"lemma": "venar", "pos": "vblex",
         "morphology": {"paradigm": "ar__vblex"}, "eo_translations": ["veni"]},
        {"lemma": "vidar", "pos": "vblex",
         "morphology": {"paradigm": "ar__vblex"}, "eo_translations": ["vidi"]},
    ]
    xml_str = ET.tostring(build_bidix(entries), encoding='unicode')
    for der, ptag in (('der_ppra', 'ppres'), ('der_ppa', 'pp')):
        assert (f'<e r="RL"><p><l>ven<s n="vblex" /><s n="{der}" /><s n="adj" /></l>'
                f'<r>veni<s n="vbntr" /><s n="{ptag}" /></r></p></e>') in xml_str
    assert '<r>vidi<s n="vbntr" />' not in xml_str


def _rows(xml_str, r_text):
    """The <e> elements of a bidix whose right side is exactly `r_text`."""
    return [e for e in ET.fromstring(xml_str).iter('e')
            if e.find('p/r') is not None and e.find('p/r').text == r_text]


def _adv(lemma, eo, sources):
    return {"lemma": lemma, "pos": "adv", "morphology": {"paradigm": "e__adv"},
            "senses": [{"translations": [{"lang": "eo", "term": eo, "sources": sources}]}]}


def test_epo_to_ido_winner_is_the_best_attested_entry():
    """ibe and tie both translate to tie<adv>; lt-proc -b would pick either in
    epo->ido. The BERT-only one becomes ido->epo only."""
    entries = [_adv("ibe", "tie", ["closed_class_tables", "io_wiktionary"]),
               _adv("tie", "tie", ["bert_embeddings"])]
    mono = build_monodix(entries)
    rows = _rows(ET.tostring(build_bidix(entries, mono), encoding='unicode'), 'tie')
    assert {e.find('p/l').text: e.get('r') for e in rows} == {'ib': None, 'ti': 'LR'}


def test_epo_to_ido_ties_are_left_alone():
    entries = [_adv("forsane", "eble", ["io_wiktionary"]),
               _adv("eventuale", "eble", ["io_wiktionary"])]
    mono = build_monodix(entries)
    rows = _rows(ET.tostring(build_bidix(entries, mono), encoding='unicode'), 'eble')
    assert len(rows) == 2 and all(e.get('r') is None for e in rows)


def test_epo_to_ido_entry_missing_from_the_monodix_loses():
    """A bidix-only record (no monodix entry) can't generate in epo->ido, so
    it must not win over a live one however well it is attested."""
    live = _adv("komence", "komence", ["bert_embeddings"])
    dead = _adv("inicale", "komence", ["io_wiktionary"])
    mono = build_monodix([live])
    rows = _rows(ET.tostring(build_bidix([live, dead], mono), encoding='unicode'), 'komence')
    assert {e.find('p/l').text: e.get('r') for e in rows} == {'komenc': None, 'inical': 'LR'}


def _rec(lemma, par, pos, eo, sources):
    return {"lemma": lemma, "pos": pos, "morphology": {"paradigm": par},
            "senses": [{"translations": [{"lang": "eo", "term": eo, "sources": sources}]}]}


def test_epo_to_ido_live_entry_beats_generated_derivation():
    """uno -> unuo generates un<n><der_ala> -> unua; the sourced unesma -> unua
    must win epo->ido over that guess."""
    entries = [_rec("uno", "o__n", "n", "unuo", ["io_wiktionary"]),
               _rec("unesma", "a__adj", "adj", "unua", ["io_wiktionary"])]
    mono = build_monodix(entries)
    rows = _rows(ET.tostring(build_bidix(entries, mono), encoding='unicode'), 'unua')
    by = {tuple(s.get('n') for s in e.find('p/l')): e.get('r') for e in rows}
    assert by[('adj',)] is None
    assert by[('n', 'der_ala', 'adj')] == 'LR' and by[('n', 'der_oz', 'adj')] == 'LR'


def test_epo_to_ido_dead_and_generated_are_not_ordered():
    """valoroza (absent from the monodix) and valoro's generated -ala/-oza
    rows all map to valora: no live sourced entry, so nothing is restricted."""
    noun = _rec("valoro", "o__n", "n", "valoro", ["io_wiktionary"])
    dead = _rec("valoroza", "a__adj", "adj", "valora", ["io_wiktionary"])
    mono = build_monodix([noun])
    rows = _rows(ET.tostring(build_bidix([noun, dead], mono), encoding='unicode'), 'valora')
    assert len(rows) == 3 and all(e.get('r') is None for e in rows)


def test_ido_determiner_adjective_gets_epo_determiner_rows():
    """neniu is analysed as neniu<det><ind><sp> before a noun, a reading the
    generator doesn't round-trip, so resolution keeps the pronoun for
    ido->epo; epo->ido gets RL rows from the determiner readings to nula."""
    from export_apertium import _load_all_eo_readings, _load_eo_generatable_lemmas
    if not _load_all_eo_readings(_load_eo_generatable_lemmas()):
        return  # sibling apertium-epo build unavailable in this environment
    entries = [_rec("nula", "a__adj", "adj", "neniu", ["closed_class_tables"])]
    xml_str = ET.tostring(build_bidix(entries, build_monodix(entries)), encoding='unicode')
    assert ('<e r="RL"><p><l>nul<s n="adj" /></l>'
            '<r>neniu<s n="det" /><s n="ind" /><s n="sp" /></r></p></e>') in xml_str
    assert '<r>neniu<s n="prn" />' in xml_str
