#!/usr/bin/env python3
"""Tests for scripts/lexicon_filters.fold_inflected_eo_duplicates.

Folds an EO candidate that is the -j/-n/-jn inflection of another candidate of
the SAME entry into that base (e.g. wikidata's `urboj` alongside `urbo`). The
guard is that only nouns (-o) and adjectives (-a) take a same-lexeme inflection,
so directional adverbs (`nenie`/`nenien`) and pronouns must NOT fold.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'scripts'))

from lexicon_filters import fold_inflected_eo_duplicates as fold


def _terms(cands):
    return [t for t, _ in cands]


def test_plural_folds_into_singular_and_merges_sources():
    out = fold([('urbo', ['io_wiktionary']),
                ('civito', ['en_via']),
                ('urboj', ['wikidata_labels'])])
    assert _terms(out) == ['urbo', 'civito']
    # the dropped plural's source is preserved on the surviving base
    srcs = dict(out)['urbo']
    assert 'io_wiktionary' in srcs and 'wikidata_labels' in srcs


def test_accusative_and_plural_accusative_fold():
    assert _terms(fold([('urbo', ['a']), ('urbon', ['b'])])) == ['urbo']
    assert _terms(fold([('urbo', ['a']), ('urbojn', ['b'])])) == ['urbo']
    assert _terms(fold([('urbo', ['a']), ('urbon', ['b']),
                        ('urbojn', ['c'])])) == ['urbo']


def test_adjective_inflection_folds():
    assert _terms(fold([('bona', ['a']), ('bonaj', ['b'])])) == ['bona']
    assert _terms(fold([('bona', ['a']), ('bonan', ['b'])])) == ['bona']


def test_inflected_form_before_base_still_folds():
    out = fold([('urboj', ['wikidata_labels']), ('urbo', ['io_wiktionary'])])
    assert _terms(out) == ['urbo']  # base spelling survives regardless of order


def test_directional_adverb_does_not_fold():
    # nenien (to-nowhere) is a distinct lexeme, not the accusative of nenie.
    assert _terms(fold([('nenie', ['a']), ('nenien', ['b'])])) == ['nenie', 'nenien']
    assert _terms(fold([('ree', ['a']), ('reen', ['b'])])) == ['ree', 'reen']


def test_distinct_lexemes_without_base_are_kept():
    # belaj must survive when its base `bela` is not a candidate of the entry.
    assert _terms(fold([('bona', ['a']), ('bonaj', ['b']),
                        ('belaj', ['c'])])) == ['bona', 'belaj']
    # unrelated words are untouched.
    assert _terms(fold([('pano', ['a']), ('akvo', ['b'])])) == ['pano', 'akvo']


def test_noop_returns_equivalent_list():
    cands = [('hundo', ['a']), ('kato', ['b'])]
    assert _terms(fold(cands)) == ['hundo', 'kato']
