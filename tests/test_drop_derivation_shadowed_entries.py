#!/usr/bin/env python3
"""Regression tests for _drop_derivation_shadowed_entries.

Covers the envidioza/envidiozo case: io_wiktionary has a translationless
page for "envidioza" (adj), but "envidi" (the o__n-paradigm root "envidio")
already has a working EO translation, and o__n's pardef bakes in a der_oz
reading for free (envidi+oza -> envidioza, translating to "envia"). The
dead atomic "envidioza" entry must be dropped so lt-proc's ambiguous
analysis resolves to the working derivational reading instead of an
untranslated one (@envidioz).

Regression covered: the translated-root set must be built from
bidix_entries (bidix_big.json), not mono_entries (entries + extra) --
final_vocabulary.json's own copy of a root lemma frequently carries empty
`senses` even when the bidix-format twin of the same lemma has a real
translation, which silently defeated the filter for exactly this case.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'scripts'))

from export_apertium import (
    _drop_derivation_shadowed_entries,
    _DERIVATION_SHADOW_SUFFIXES,
)


def _root(lemma, paradigm, translated):
    e = {"lemma": lemma, "pos": None, "morphology": {"paradigm": paradigm}, "senses": []}
    if translated:
        e["senses"] = [{"translations": [{"lang": "eo", "term": lemma[:-1] + "o-eo"}]}]
    return e


def _dead(lemma, paradigm):
    return {"lemma": lemma, "pos": None, "morphology": {"paradigm": paradigm}, "senses": []}


def test_shadowed_entry_dropped_when_root_translation_only_in_bidix_entries():
    # final_vocabulary.json shape: the root's own copy has NO translation.
    mono_entries = [
        _root("envidio", "o__n", translated=False),
        _dead("envidioza", "a__adj"),
    ]
    # bidix_big.json shape: the same root DOES carry the real translation.
    bidix_entries = [
        {"lemma": "envidio", "pos": "n", "morphology": {"paradigm": "o__n"},
         "senses": [{"translations": [{"lang": "eo", "term": "envio"}]}]},
    ]

    result = _drop_derivation_shadowed_entries(mono_entries, bidix_entries)
    lemmas = {e["lemma"] for e in result}

    assert "envidio" in lemmas
    assert "envidioza" not in lemmas, (
        "envidioza should be dropped: its root 'envidi' (o__n) has a real "
        "translation on the bidix-format entry, and der_oz already covers "
        "this exact surface form")


def test_unrelated_word_with_matching_suffix_is_kept():
    # "aro" coincidentally ends a word whose root has no translation at all --
    # must not be dropped (no working derivational reading exists to fall back on).
    mono_entries = [
        _root("figo", "o__n", translated=False),
        _dead("figaro", "o__n"),
    ]
    bidix_entries = [
        {"lemma": "figo", "pos": "n", "morphology": {"paradigm": "o__n"}, "senses": []},
    ]

    result = _drop_derivation_shadowed_entries(mono_entries, bidix_entries)
    lemmas = {e["lemma"] for e in result}
    assert "figaro" in lemmas


def test_pos_mismatch_is_not_shadowed():
    # "aro" suffix implies a noun derivation; a word ending in "aro" that is
    # itself analysed as e.g. an adjective must not be treated as a shadow.
    mono_entries = [
        _root("mondo", "o__n", translated=True),
        {"lemma": "mondaro", "pos": "adj", "morphology": {"paradigm": "a__adj"}, "senses": []},
    ]
    bidix_entries = [
        {"lemma": "mondo", "pos": "n", "morphology": {"paradigm": "o__n"},
         "senses": [{"translations": [{"lang": "eo", "term": "mondo"}]}]},
    ]

    result = _drop_derivation_shadowed_entries(mono_entries, bidix_entries)
    lemmas = {e["lemma"] for e in result}
    assert "mondaro" in lemmas


def test_entries_with_real_translations_are_never_dropped():
    mono_entries = [
        _root("envidio", "o__n", translated=False),
        _root("envidioza", "a__adj", translated=True),
    ]
    bidix_entries = [
        {"lemma": "envidio", "pos": "n", "morphology": {"paradigm": "o__n"},
         "senses": [{"translations": [{"lang": "eo", "term": "envio"}]}]},
    ]

    result = _drop_derivation_shadowed_entries(mono_entries, bidix_entries)
    lemmas = {e["lemma"] for e in result}
    assert "envidioza" in lemmas


def test_all_ar_vblex_participle_suffixes_are_covered():
    # Every adjective/adverb/noun suffix ar__vblex's pardef bakes in for a
    # verb derivation must have a shadow-guard entry -- a gap here is exactly
    # how the "konstruktita" bug (below) went unnoticed: der_ppas ("ita")
    # existed and worked in build_bidix long before anyone added it here.
    for suffix in ('anto', 'ado', 'into', 'onto', 'anta', 'inta', 'ita',
                   'ata', 'ota', 'onta', 'ante', 'inte', 'onte', 'ate',
                   'ite', 'ote'):
        assert suffix in _DERIVATION_SHADOW_SUFFIXES, (
            f"-{suffix} is a real ar__vblex derivation suffix with no "
            "shadow-guard entry -- a translationless lexicalized entry "
            "with this ending can silently shadow the productive reading")


def test_leaked_inflected_translation_does_not_block_shadow_drop():
    # bert_embeddings/morphological_expansion can leak an INFLECTED surface
    # form (e.g. "konstruita", the participle) as the gloss for an atomic
    # "konstruktita" entry -- a translation string IS present, so the old
    # _has_eo_translation check alone kept the entry, but "konstruita" is
    # not an independent generatable EO lemma (only reachable via the verb
    # "konstrui"'s own <pp> generation route), so it never got a live bidix
    # entry either. eo_generatable must cause this dead entry to be dropped
    # in favor of the productive der_ppas reading, same as an empty gloss
    # would.
    mono_entries = [
        _root("konstruktar", "ar__vblex", translated=False),
        {"lemma": "konstruktita", "pos": "adj", "morphology": {"paradigm": "a__adj"},
         "senses": [{"translations": [{"lang": "eo", "term": "konstruita"}]}]},
    ]
    bidix_entries = [
        {"lemma": "konstruktar", "pos": "vblex", "morphology": {"paradigm": "ar__vblex"},
         "senses": [{"translations": [{"lang": "eo", "term": "konstrui"}]}]},
    ]
    # "konstruita" (inflected participle) is NOT in the generatable set;
    # "konstrui" (the base verb lemma) is.
    eo_generatable = {"konstrui"}

    result = _drop_derivation_shadowed_entries(mono_entries, bidix_entries, eo_generatable)
    lemmas = {e["lemma"] for e in result}
    assert "konstruktita" not in lemmas, (
        "a translation string that fails the generatability gate must not "
        "protect a dead entry from the shadow-guard")


def test_generatable_translation_still_protects_entry():
    # Sanity check for the same helper: a real, independently generatable
    # translation must still be kept even when it happens to share a suffix
    # with a derivation pattern.
    mono_entries = [
        _root("kreskar", "ar__vblex", translated=False),
        {"lemma": "vinita", "pos": "adj", "morphology": {"paradigm": "a__adj"},
         "senses": [{"translations": [{"lang": "eo", "term": "vinita"}]}]},
    ]
    bidix_entries = [
        {"lemma": "kreskar", "pos": "vblex", "morphology": {"paradigm": "ar__vblex"},
         "senses": [{"translations": [{"lang": "eo", "term": "kreski"}]}]},
    ]
    eo_generatable = {"kreski", "vinita"}

    result = _drop_derivation_shadowed_entries(mono_entries, bidix_entries, eo_generatable)
    lemmas = {e["lemma"] for e in result}
    assert "vinita" in lemmas
