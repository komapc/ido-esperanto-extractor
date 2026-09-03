#!/usr/bin/env python3
"""Regression tests for _FUNCTION_WORD_OVERRIDES in build_one_big_bidix_json.py.

Each entry here fixes the same class of bug: io_wiktionary's only gloss for
a closed-class contraction word is a multi-word Esperanto phrase (e.g. "de
la"), which the bidix generatability gate in export_apertium.py correctly
rejects (no monodix entry backs that phrase), silently dropping the whole
bidix entry. These asserts guard against that regressing if the table is
ever trimmed without checking the audit numbers first.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'scripts'))

from build_one_big_bidix_json import _FUNCTION_WORD_OVERRIDES


def test_dal_dil_del_contractions_map_to_de():
    for lemma in ('dal', 'dil', 'del'):
        info = _FUNCTION_WORD_OVERRIDES[lemma]
        assert info['pos'] == 'prep_art', f"{lemma!r} should be pos=prep_art"
        assert info['eo'] == 'de', f"{lemma!r} should override to eo='de'"
