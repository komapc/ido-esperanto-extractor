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

from export_apertium import _drop_derivation_shadowed_entries


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
