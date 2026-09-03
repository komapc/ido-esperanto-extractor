#!/usr/bin/env python3
"""Tests for wiktionary_parser.split_translation_blocks /
extract_translations_with_blocks — the sense-scoping fix (Fix A) for the
English Wiktionary via-pivot. Without this, every io/eo term found anywhere
on an English Wiktionary page was cross-paired regardless of which
{{trans-top|gloss}}...{{trans-bottom}} sense block it came from (e.g. "light"
paired the "to find by chance" io term with the "to illuminate" eo term,
giving trovar -> lumigi).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'scripts'))

from wiktionary_parser import split_translation_blocks, extract_translations_with_blocks


def test_two_blocks_split_by_gloss():
    section = (
        "{{trans-top|to observe}}\n"
        "* Esperanto: {{t|eo|vidi}}\n"
        "{{trans-bottom}}\n"
        "{{trans-top|to have an idea}}\n"
        "* Esperanto: {{t|eo|imagi}}\n"
        "{{trans-bottom}}\n"
    )
    blocks = split_translation_blocks(section)
    glosses = [g for g, _ in blocks if g is not None]
    assert glosses == ['to observe', 'to have an idea']
    by_gloss = {g: text for g, text in blocks if g is not None}
    assert 'vidi' in by_gloss['to observe']
    assert 'imagi' in by_gloss['to have an idea']


def test_leftover_text_outside_blocks_becomes_its_own_chunk():
    section = (
        "intro text\n"
        "{{trans-top|sense one}}\n"
        "* Esperanto: {{t|eo|unu}}\n"
        "{{trans-bottom}}\n"
        "trailing text\n"
    )
    blocks = split_translation_blocks(section)
    assert blocks[0] == (None, "intro text\n")
    assert blocks[1][0] == 'sense one'
    assert blocks[2] == (None, "\ntrailing text\n")


def test_malformed_missing_trans_bottom_falls_into_leftover():
    section = (
        "{{trans-top|sense one}}\n"
        "* Esperanto: {{t|eo|unu}}\n"
        # no {{trans-bottom}} — page is malformed/truncated
    )
    blocks = split_translation_blocks(section)
    # No block matched (the regex requires a closing trans-bottom), so the
    # whole section is one leftover chunk rather than crashing or hanging.
    assert len(blocks) == 1
    assert blocks[0][0] is None
    assert 'unu' in blocks[0][1]


def test_trans_mid_does_not_split_a_block():
    section = (
        "{{trans-top|to enjoy}}\n"
        "* French: {{t|fr|aimer}}\n"
        "{{trans-mid}}\n"
        "* Esperanto: {{t|eo|ŝati}}\n"
        "{{trans-bottom}}\n"
    )
    blocks = split_translation_blocks(section)
    assert blocks[0][0] == 'to enjoy'
    assert 'ŝati' in blocks[0][1]
    assert 'aimer' in blocks[0][1]


def test_extract_translations_with_blocks_scopes_terms_to_their_sense():
    section = (
        "{{trans-top|to find by chance}}\n"
        "* Ido: {{t|io|trovar}}\n"
        "{{trans-bottom}}\n"
        "{{trans-top|to illuminate}}\n"
        "* Esperanto: {{t|eo|lumigi}}\n"
        "{{trans-bottom}}\n"
    )
    io_pairs = extract_translations_with_blocks(section, 'io')
    eo_pairs = extract_translations_with_blocks(section, 'eo')
    io_indices = {idx for idx, _ in io_pairs}
    eo_indices = {idx for idx, _ in eo_pairs}
    # "trovar" and "lumigi" come from different blocks, so their indices
    # must not overlap — a same-index match is what the pairer requires.
    assert io_indices.isdisjoint(eo_indices)
    assert ['trovar'] in [syns for _, syns in io_pairs]
    assert ['lumigi'] in [syns for _, syns in eo_pairs]


def test_extract_translations_with_blocks_pairs_same_sense():
    section = (
        "{{trans-top|to enjoy}}\n"
        "* Ido: {{t|io|prizar}}\n"
        "* Esperanto: {{t|eo|ŝati}}\n"
        "{{trans-bottom}}\n"
    )
    io_pairs = extract_translations_with_blocks(section, 'io')
    eo_pairs = extract_translations_with_blocks(section, 'eo')
    assert io_pairs[0][0] == eo_pairs[0][0]  # same block index
