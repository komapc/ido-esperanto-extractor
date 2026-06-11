#!/usr/bin/env python3
"""Deterministic, confidence-ranked selection of the winning io→eo translation.

Replaces the old `eo_terms[0]` (insertion-order) pick, which made the chosen
translation depend on merge order — so a re-parse could flip `di→de` to
`di→antaŭ`. The key here is a pure function of (ido lemma, candidate term, its
sources), so the same `bidix_big.json` always yields the same winner.

Ranking (lower = better):
  1. source reliability  (curated override > direct Wiktionary > pivots/labels > BERT)
  2. insertion order     (the candidate's position in bidix_big — preserves the
                          existing de-facto source-priority ordering for same-rank
                          ties, so this change only overrides genuine rank inversions)

A winner-diff (scripts/conflict_winner_diff.py) showed that richer signals
(cognate proximity, corroboration count) cause large, harmful churn — cognate
prefers close-but-wrong glosses (abandonar: postlasi→apostati) and corroboration
lets capitalized langlink titles beat lowercase Wiktionary nouns (abato→Abato).
So the score deliberately stays minimal: source rank, then original order.

See PIPELINE_AUDIT.md P3. The `eo_wiktionary` rank is the gated "(b)" lever: it
reverse-maps some closed-class forms wrongly (`omna→ĉia`, `ta→tio`); demoting it
below the pivots fixes those — vet the change with scripts/conflict_winner_diff.py.
"""
from __future__ import annotations

from typing import Dict, Iterable, Sequence, Tuple

# (a) determinism-preserving ranks: io/eo Wiktionary share the top Wiktionary tier,
# matching the existing _entry_quality policy — only the *order-dependence* is removed.
SOURCE_RANK_BASELINE: Dict[str, int] = {
    'function_word_override': 0,
    'function_words_seed': 0,
    # Structured closed-class tables (parse_closed_class.py): pronoun comparison
    # table + correlative grid. Authoritative for its small lemma set, so it
    # shares the top tier. Its *qualified* twin ('closed_class_tables_qualified',
    # cells the source page itself footnotes as theoretical, e.g. tu→ci¹) is
    # deliberately NOT listed → default rank, never outranks live extractions.
    'closed_class_tables': 0,
    'io_wiktionary': 1,
    'eo_wiktionary': 1,
    'fr_wiktionary_meaning': 1,
    'fr_wiktionary_via': 2,
    'en_wiktionary_via': 2,
    'wikidata_labels': 2,
    'wikipedia_langlinks': 2,
    'eowiki_langlinks': 2,
    'morphological_expansion': 2,
    'bert_embeddings': 4,
}

# (b) correctness re-ranking: eo_wiktionary demoted below the pivots so the
# correct pivot forms (omna→ĉiu, ta→tiu) win. Gate on the winner-diff before use.
SOURCE_RANK_DEMOTE_EO = {**SOURCE_RANK_BASELINE, 'eo_wiktionary': 3}

_DEFAULT_RANK = 2


def source_rank(sources: Iterable[str], table: Dict[str, int] = SOURCE_RANK_BASELINE) -> int:
    return min((table.get(s, _DEFAULT_RANK) for s in sources), default=_DEFAULT_RANK)


def confidence_key(term: str, sources: Sequence[str], index: int,
                   table: Dict[str, int] = SOURCE_RANK_BASELINE) -> Tuple[int, int]:
    """Sort key for a candidate; the minimum across candidates is the winner.

    `index` is the candidate's original position in the entry (insertion order),
    which is a total order, so the key is deterministic and ties fall back to the
    pre-existing ordering rather than to an arbitrary alphabetical pick.
    """
    return (source_rank(sources, table), index)


def pick_best(candidates: Sequence[Tuple[str, Sequence[str]]],
              table: Dict[str, int] = SOURCE_RANK_BASELINE) -> str:
    """candidates: [(term, [sources]), …] in insertion order → winning term."""
    best_i = min(range(len(candidates)),
                 key=lambda i: confidence_key(candidates[i][0], candidates[i][1], i, table))
    return candidates[best_i][0]


# --------------------------------------------------------------------------- #
# Vortaro display ranking — richer than the MT winner (pick_best stays minimal).
#
# The vortaro shows every candidate, so a confidently-wrong #1 only mis-orders a
# list a human reads — but ordering is the whole point, so it is still vetted by
# the misses (false-friend set), not just by precision@1 (eval_vortaro.py).
#
# Built incrementally so each signal's contribution is measurable:
#   source reliability  (dominant) — the SOURCE_RANK tiers above
#   corroboration       — how many distinct sources independently agree
#   cognate proximity   — Ido↔Esperanto are highly cognate, so the candidate
#                         closest to the lemma is usually the right primary gloss
#                         (`aceptar`→akcepti, not the paraphrase ricevi). Capped so
#                         it breaks ties / nudges adjacent ranks but never overrides
#                         a strong reliability gap (guards false friends).
# --------------------------------------------------------------------------- #
from difflib import SequenceMatcher  # noqa: E402

_CORROBORATION_CAP = 4
_COGNATE_WEIGHT = 6.0


def cognate_proximity(lemma: str, term: str) -> float:
    """0..1 string similarity of the Ido lemma and an Esperanto candidate."""
    if not lemma or not term:
        return 0.0
    return SequenceMatcher(None, lemma.casefold(), term.casefold()).ratio()


def confidence_score(term: str, sources: Sequence[str], lemma: str = "", *,
                     use_corroboration: bool = True, use_cognate: bool = True,
                     table: Dict[str, int] = SOURCE_RANK_BASELINE) -> float:
    """Vortaro ranking score (higher = better). Pure function of the candidate.

    Source reliability dominates (rank gap weighted ×10); corroboration and
    cognate proximity are secondary tie-breakers. Toggle the latter two to
    measure each signal's marginal contribution.
    """
    score = -10.0 * source_rank(sources, table)
    if use_corroboration:
        score += min(len(set(sources)), _CORROBORATION_CAP)
    if use_cognate and lemma:
        score += _COGNATE_WEIGHT * cognate_proximity(lemma, term)
    return score
