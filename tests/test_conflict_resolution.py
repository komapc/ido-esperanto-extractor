#!/usr/bin/env python3
"""Tests for scripts/conflict_resolution.pick_best, including the `valid`
generatability gate (Fix B): a candidate the target monodix cannot generate
must not win, even when it has the best source rank.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'scripts'))

from conflict_resolution import pick_best


def test_no_valid_set_keeps_old_behaviour():
    cands = [('altetaksi', ['io_wiktionary']), ('ŝati', ['en_wiktionary_via'])]
    assert pick_best(cands) == 'altetaksi'  # rank 1 beats rank 2, as before


def test_valid_set_filters_out_top_ranked_ungeneratable_candidate():
    cands = [('altetaksi', ['io_wiktionary']), ('ŝati', ['en_wiktionary_via'])]
    assert pick_best(cands, valid={'ŝati'}) == 'ŝati'


def test_valid_set_is_case_insensitive():
    cands = [('Trovis', ['bert_embeddings']), ('trovi', ['io_wiktionary'])]
    assert pick_best(cands, valid={'trovi'}) == 'trovi'


def test_all_candidates_invalid_returns_none():
    cands = [('trovis', ['bert_embeddings']), ('troveblas', ['bert_embeddings'])]
    assert pick_best(cands, valid={'trovi'}) is None


def test_valid_set_does_not_override_rank_among_generatable_candidates():
    cands = [('malkovri', ['fr_wiktionary_via']), ('trovi', ['io_wiktionary'])]
    assert pick_best(cands, valid={'malkovri', 'trovi'}) == 'trovi'
