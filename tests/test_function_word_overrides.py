#!/usr/bin/env python3
"""Regression tests for the prep+article contraction handling.

dal/dil/del (da/di/de + la) used to be listed by hand in
_FUNCTION_WORD_OVERRIDES with a fabricated "eo" value. That was wrong for
two different reasons and both are retired now:

  * dil/del: io_wiktionary genuinely glosses these "de la" — a correct
    translation, just in the wrong (two-word) shape for the bidix <r> slot.
    export_apertium._reduce_prep_art_contraction() now unwraps any prep_art
    candidate's "X la" gloss to "X" mechanically (real source data, just
    reshaped), and the pre-existing .t1x "prep-art contraction expansion"
    rule (fires generically on any prep_art entry) reattaches "la" at
    generation time.
  * dal: has ZERO source data anywhere in work/*.json — the old override
    was fabricated, not a pipeline-gap fix. It is intentionally left
    unanalyzable (*dal) until real source coverage exists.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'scripts'))

from build_one_big_bidix_json import _FUNCTION_WORD_OVERRIDES
from export_apertium import _reduce_prep_art_contraction


def test_dal_dil_del_are_not_hardcoded_overrides():
    for lemma in ('dal', 'dil', 'del'):
        assert lemma not in _FUNCTION_WORD_OVERRIDES, (
            f"{lemma!r} should come from real source data / the general "
            "prep_art contraction mechanism, not a hardcoded override")


def test_reduce_prep_art_contraction_unwraps_x_la():
    assert _reduce_prep_art_contraction("de la") == "de"
    assert _reduce_prep_art_contraction("da la") == "da"


def test_reduce_prep_art_contraction_leaves_other_phrases_alone():
    # Only the exact "X la" shape is a contraction unwrap; anything else
    # (single word, or a genuine multi-word idiom) passes through untouched.
    assert _reduce_prep_art_contraction("de") == "de"
    assert _reduce_prep_art_contraction("tie ĉi") == "tie ĉi"
