#!/usr/bin/env python3
"""Shared lexicon cleaning — junk-lemma rejection and EO-candidate dedup.

Consolidates the junk logic that was duplicated across export_vortaro
(`is_junk_lemma`) and build_one_big_bidix_json (`_IDO_LEMMA_RE`), and adds the
case-variant dedup the candidate audit found (3,877 entries carry the same EO
term twice differing only by capitalisation — a capitalised langlink/wikidata
title alongside the lowercase Wiktionary noun, e.g. `['abato', 'Abato']`).

Used by both build_one_big_bidix_json.py (so the monodix benefits too) and
eval_vortaro.py (so measurement sees the same candidates the export emits).
"""
from __future__ import annotations

import re
from typing import List, Sequence, Tuple

Candidate = Tuple[str, List[str]]  # (eo term, sources)

# --------------------------------------------------------------------------- #
# Junk lemma rejection
# --------------------------------------------------------------------------- #
# Ido orthography is plain ASCII a-z; any non-ASCII letter (é, ñ, ç, ł, ı, ý…)
# means a foreign spelling leaked in from a langlink/wikidata title — the real
# Ido form would be ASCII. (The BERT path already applied this to its vocab;
# this generalises it to every source.)
_NON_ASCII_RE = re.compile(r"[^\x00-\x7f]")
# MediaWiki / HTML layout tokens that slipped through as "words".
_MEDIAWIKI_RE = re.compile(
    r"^(thumb|left|right|center|centre|displaytitle|redirect|colspan|rowspan|"
    r"bgcolor|rowcolor|style|px|small|big|border|align|valign|background|font|"
    r"nbsp|sub|sup|br|hr|ref|nowrap|width|height|color)$",
    re.IGNORECASE,
)
_NUMERIC_JUNK_RES = (
    re.compile(r"^-?\d+(\.\d+)?$"),        # pure numbers
    re.compile(r"^\d+[,;:]"),              # corrupted (2000,, 2011,)
    re.compile(r"^[\d.,%\-]+$"),           # percentages / corrupted decimals
    re.compile(r"^\d+(ma|st|nd|rd|th|ĝa|a|esma)$"),  # ordinals (1ma, 6ma…)
    re.compile(r"^\w{0,3}\d{2,}\w{0,3}$"), # codes mostly digits
)


def is_junk_lemma(lemma: str) -> bool:
    """True if the Ido lemma is non-lexical junk and should not enter the dict."""
    if not lemma or not isinstance(lemma, str):
        return True
    lemma = lemma.strip()
    if not lemma:
        return True
    if _NON_ASCII_RE.search(lemma):
        return True
    if _MEDIAWIKI_RE.match(lemma):
        return True
    return any(rx.match(lemma) for rx in _NUMERIC_JUNK_RES)


# --------------------------------------------------------------------------- #
# EO-candidate dedup (case variants), with lemma-driven casing
# --------------------------------------------------------------------------- #
def _prefer_casing(variants: Sequence[str], lemma: str) -> str:
    """Choose the surviving spelling among case-variants of one EO term.

    Driven by the Ido lemma's case (advisor): a lowercase common-noun lemma
    keeps the lowercase gloss; a capitalised proper-noun lemma keeps the capital
    (`Aachen → Akeno`, not `akeno`). Falls back to the first-seen variant.
    """
    lemma_proper = bool(lemma) and lemma[:1].isupper()
    lower = [v for v in variants if not v[:1].isupper()]
    upper = [v for v in variants if v[:1].isupper()]
    if lemma_proper:
        return (upper or lower or list(variants))[0]
    return (lower or upper or list(variants))[0]


def dedupe_eo_candidates(lemma: str, candidates: Sequence[Candidate]) -> List[Candidate]:
    """Merge EO candidates that differ only by letter-case.

    Dedup key is casefold only — NOT diacritic-folded, because ĉ/ĝ/ĥ/ĵ/ŝ/ŭ are
    distinct Esperanto letters. Merged groups keep the lemma-driven casing, the
    union of sources, and the earliest position (preserving insertion order so
    same-rank ties stay deterministic).
    """
    order: List[str] = []                 # group keys in first-seen order
    forms: dict[str, List[str]] = {}      # key -> variant spellings (in order)
    srcs: dict[str, List[str]] = {}       # key -> merged sources (dedup, in order)
    for term, sources in candidates:
        key = term.casefold()
        if key not in forms:
            order.append(key)
            forms[key] = []
            srcs[key] = []
        if term not in forms[key]:
            forms[key].append(term)
        for s in sources:
            if s not in srcs[key]:
                srcs[key].append(s)
    return [(_prefer_casing(forms[k], lemma), srcs[k]) for k in order]


# --------------------------------------------------------------------------- #
# EO-candidate dedup (inflected forms)
# --------------------------------------------------------------------------- #
# Esperanto regular inflection on the same lexeme: plural -j, accusative -n,
# both -jn. wikidata_labels in particular leaks the plural of a noun alongside
# the noun itself (`urbo` + `urboj`).
_EO_INFLECTION_SUFFIXES = ("jn", "j", "n")  # longest first


def fold_inflected_eo_duplicates(candidates: Sequence[Candidate]) -> List[Candidate]:
    """Fold an EO candidate that is the -j/-n/-jn inflection of another candidate
    present in the same entry into that base (e.g. `urbo` + `urboj` -> `urbo`).

    The base must itself be a candidate of the entry, so this never merges two
    distinct lexemes — only a word with its own plural/accusative. The surviving
    spelling is the base form; sources are unioned; order is the first-seen order
    of the resolved (base) terms. Robust to the inflected form preceding the base.
    """
    cands = list(candidates)
    bases = {t.casefold() for t, _ in cands}

    def resolve(term: str) -> str:
        key = term.casefold()
        for suf in _EO_INFLECTION_SUFFIXES:
            if key.endswith(suf):
                stem = key[: -len(suf)]
                # Only nouns (-o) and adjectives (-a) take same-lexeme -j/-n/-jn.
                # Requiring the base to end in o/a excludes directional adverbs
                # (`nenie`/`nenien`, `ree`/`reen`) and pronouns, which are distinct
                # lexemes that merely look like an accusative of one another.
                if stem and stem != key and stem[-1] in "oa" and stem in bases:
                    return stem
        return key

    order: List[str] = []                 # resolved keys, first-seen order
    term_for: dict[str, str] = {}         # resolved key -> surviving spelling (base)
    srcs: dict[str, List[str]] = {}       # resolved key -> merged sources
    for term, sources in cands:
        rkey = resolve(term)
        if rkey not in srcs:
            order.append(rkey)
            srcs[rkey] = []
            term_for[rkey] = term
        if term.casefold() == rkey:       # this IS the base — prefer its spelling
            term_for[rkey] = term
        for s in sources:
            if s not in srcs[rkey]:
                srcs[rkey].append(s)
    return [(term_for[k], srcs[k]) for k in order]
