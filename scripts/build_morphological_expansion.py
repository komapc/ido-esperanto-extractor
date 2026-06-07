#!/usr/bin/env python3
"""Generate io↔eo translation pairs by morphological expansion of known bidix pairs.

Ido and Esperanto share an almost identical derivational suffix system. Given a
known pair (e.g. facar→fari), we can reliably derive:

  io_root+ado  → eo_root+ado   (verbal noun:      facado→farado)
  io_root+anto → eo_root+anto  (present agent:    facanto→faranto)
  io_root+ita  → eo_root+ita   (past passive adj: facita→farita)
  io_root+anta → eo_root+anta  (present act. adj: facanta→faranta)
  io_root+ante → eo_root+ante  (present act. adv: facante→farante)
  ...

The same logic applies to noun→adjective/adverb/quality-noun pairs:
  io_noun_root+a   → eo_noun_root+a    (hundo→hundo  ⟹  hunda→hunda)
  io_noun_root+eso → eo_noun_root+eco  (hundo→hundo  ⟹  hundeso→hundeco)

And to adjective→adverb/quality-noun/person pairs:
  io_adj_root+e    → eo_adj_root+e     (bela→bela  ⟹  bele→bele)
  io_adj_root+eso  → eo_adj_root+eco   (bela→bela  ⟹  beleso→beleco)

Generated forms are validated against io.wiki's word frequency list (only forms
that actually appear in Ido texts are kept).

Output: work/io_eo_morphological.json — unified source format.

Usage:
    python3 scripts/build_morphological_expansion.py [-v] [--out PATH]
    python3 scripts/build_morphological_expansion.py --dry-run
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from pathlib import Path
from typing import Iterator

sys.path.insert(0, str(Path(__file__).parent))
from _common import configure_logging, write_json

logger = logging.getLogger(__name__)

SOURCE_TAG = "morphological_expansion"

# Derivational suffixes shared between Ido and Esperanto.
# (io_suffix, eo_suffix, pos_tag)
# All Ido verb classes (-ar/-ir/-or) map to Eo infinitive (-i).
VERB_DERIVATIONS: list[tuple[str, str, str]] = [
    ("ado",   "ado",   "n"),    # nominalization: act of V-ing
    ("anto",  "anto",  "n"),    # present active agent (noun)
    ("into",  "into",  "n"),    # past active agent (noun)
    ("onto",  "onto",  "n"),    # future active agent (noun)
    ("anta",  "anta",  "adj"),  # present active participle (adj)
    ("inta",  "inta",  "adj"),  # past active participle (adj)
    ("onta",  "onta",  "adj"),  # future active participle (adj)
    ("ante",  "ante",  "adv"),  # present active participle (adv)
    ("inte",  "inte",  "adv"),  # past active participle (adv)
    ("onte",  "onte",  "adv"),  # future active participle (adv)
    ("ata",   "ata",   "adj"),  # present passive participle (adj)
    ("ita",   "ita",   "adj"),  # past passive participle (adj)
    ("ota",   "ota",   "adj"),  # future passive participle (adj)
    ("ate",   "ate",   "adv"),  # present passive participle (adv)
    ("ite",   "ite",   "adv"),  # past passive participle (adv)
    ("ote",   "ote",   "adv"),  # future passive participle (adv)
    ("ema",   "ema",   "adj"),  # prone-to adjective
    ("emo",   "emo",   "n"),    # tendency/disposition noun: studemo→studemo
    ("inda",  "inda",  "adj"),  # worthy-of adjective
    ("ilo",   "ilo",   "n"),    # instrument/tool
    ("ejo",   "ejo",   "n"),    # place for
    ("isto",  "isto",  "n"),    # professional agent
]

# Derivations from noun roots.
NOUN_DERIVATIONS: list[tuple[str, str, str]] = [
    ("a",    "a",    "adj"),   # adjective form
    ("e",    "e",    "adv"),   # adverb form
    ("aro",  "aro",  "n"),     # collection / group
    ("ejo",  "ejo",  "n"),     # place for
    ("emo",  "emo",  "n"),     # tendency/passion: muzikemo→muzikemo
    ("eso",  "eco",  "n"),     # quality noun: hundeso→hundeco
    ("ino",  "ino",  "n"),     # feminine form
    ("isto", "isto", "n"),     # professional
    ("ismo", "ismo", "n"),     # ideology / -ism
    ("ulo",  "ulo",  "n"),     # person characterised by
    ("eto",  "eto",  "n"),     # diminutive
    ("ego",  "ego",  "n"),     # augmentative
]

# Derivations from adjective roots (IO adj ends in -a, root = stem without -a).
ADJ_DERIVATIONS: list[tuple[str, str, str]] = [
    ("eso",  "eco",  "n"),    # quality noun: beleso→beleco, rapideso→rapideco
    ("e",    "e",    "adv"),  # adverb: bele→bele, grande→grande
    ("ulo",  "ulo",  "n"),    # person with quality: bonulo→bonulo
    ("ino",  "ino",  "n"),    # female person with quality: belino→belino
]

_IO_VERB_RE = re.compile(r"^(.{2,}?)(ar|ir|or)$")
_EO_VERB_RE = re.compile(r"^(.{2,})i$")
_IO_NOUN_RE = re.compile(r"^(.{2,})o$")
_EO_NOUN_RE = re.compile(r"^(.{2,})o$")
_IO_ADJ_RE  = re.compile(r"^(.{2,})a$")
_EO_ADJ_RE  = re.compile(r"^(.{2,})a$")

# Suffixes that indicate a root is already a derived/participial form — skip those
# to avoid chaining derivations (e.g. studanta→root studant→studanteso would be wrong).
_DERIVED_ROOT_RE = re.compile(r"(ar|ir|or|as|is|os|us|ez|ant|int|ont|at|it|ot|em|ind)$")


def _io_verb_root(word: str) -> str | None:
    m = _IO_VERB_RE.match(word)
    return m.group(1).lower() if m else None


def _eo_verb_root(word: str) -> str | None:
    m = _EO_VERB_RE.match(word)
    return m.group(1).lower() if m else None


def _io_noun_root(word: str) -> str | None:
    m = _IO_NOUN_RE.match(word)
    r = m.group(1).lower() if m else None
    if r and _DERIVED_ROOT_RE.search(r):
        return None
    return r


def _eo_noun_root(word: str) -> str | None:
    m = _EO_NOUN_RE.match(word)
    r = m.group(1).lower() if m else None
    if r and _DERIVED_ROOT_RE.search(r):
        return None
    return r


def _io_adj_root(word: str) -> str | None:
    m = _IO_ADJ_RE.match(word)
    r = m.group(1).lower() if m else None
    if r and _DERIVED_ROOT_RE.search(r):
        return None
    return r


def _eo_adj_root(word: str) -> str | None:
    m = _EO_ADJ_RE.match(word)
    r = m.group(1).lower() if m else None
    if r and _DERIVED_ROOT_RE.search(r):
        return None
    return r


def load_wiki_vocab(path: Path) -> set[str]:
    """Return lowercase token set from io_wiki_frequency.json."""
    data = json.loads(path.read_text())
    return {item["token"].lower() for item in data["items"]}


def _is_common_word(word: str) -> bool:
    """Return True if word is a common (non-proper) lemma."""
    return bool(word) and word[0].islower()


def iter_verb_pairs(bidix: list[dict]) -> Iterator[tuple[str, str, str, str]]:
    """Yield (io_verb, eo_verb, io_root, eo_root) for all verb pairs in bidix."""
    for entry in bidix:
        lm = entry["lemma"]
        if not _is_common_word(lm):
            continue
        io_root = _io_verb_root(lm)
        if not io_root:
            continue
        senses = entry.get("senses") or []
        for sense in senses:
            for tr in sense.get("translations") or []:
                eo = tr.get("term", "")
                if not _is_common_word(eo):
                    continue
                eo_root = _eo_verb_root(eo)
                if eo_root:
                    yield lm, eo, io_root, eo_root


def iter_noun_pairs(bidix: list[dict]) -> Iterator[tuple[str, str, str, str]]:
    """Yield (io_noun, eo_noun, io_root, eo_root) for noun pairs in bidix."""
    for entry in bidix:
        lm = entry["lemma"]
        if not _is_common_word(lm):
            continue
        io_root = _io_noun_root(lm)
        if not io_root:
            continue
        senses = entry.get("senses") or []
        for sense in senses:
            for tr in sense.get("translations") or []:
                eo = tr.get("term", "")
                if not _is_common_word(eo):
                    continue
                eo_root = _eo_noun_root(eo)
                if eo_root:
                    yield lm, eo, io_root, eo_root


def iter_adj_pairs(bidix: list[dict]) -> Iterator[tuple[str, str, str, str]]:
    """Yield (io_adj, eo_adj, io_root, eo_root) for adjective pairs in bidix."""
    for entry in bidix:
        lm = entry["lemma"]
        if not _is_common_word(lm):
            continue
        io_root = _io_adj_root(lm)
        if not io_root:
            continue
        senses = entry.get("senses") or []
        for sense in senses:
            for tr in sense.get("translations") or []:
                eo = tr.get("term", "")
                if not _is_common_word(eo):
                    continue
                eo_root = _eo_adj_root(eo)
                if eo_root:
                    yield lm, eo, io_root, eo_root


def build_entry(io_lemma: str, eo_term: str, pos: str, source_pair: str) -> dict:
    return {
        "lemma": io_lemma,
        "pos": pos,
        "language": "io",
        "senses": [{
            "senseId": None,
            "gloss": f"morphological derivation of {source_pair}",
            "translations": [{
                "lang": "eo",
                "term": eo_term,
                "confidence": 0.95,
                "source": SOURCE_TAG,
            }],
        }],
        "provenance": [{"source": SOURCE_TAG, "page": source_pair}],
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    base = Path(__file__).resolve().parents[1]
    ap.add_argument("--bidix",     type=Path, default=base / "work/final_vocabulary.json")
    ap.add_argument("--wiki-freq", type=Path, default=base / "work/io_wiki_frequency.json")
    ap.add_argument("--out",       type=Path, default=base / "work/io_eo_morphological.json")
    ap.add_argument("--dry-run",   action="store_true")
    ap.add_argument("-v", "--verbose", action="count", default=0)
    args = ap.parse_args(argv)
    configure_logging(args.verbose)

    logger.info("Loading bidix: %s", args.bidix)
    bidix = json.loads(args.bidix.read_text())
    # Skip a derived form only if it ALREADY HAS an EO translation — not merely
    # because the lemma exists. Many derivable forms (bakilo, opakeso, peskisto)
    # are present as zero-EO monodix lemmas; attaching their morphological EO
    # gloss is exactly the recall win. The wiki_vocab gate below still applies.
    def _has_eo(e: dict) -> bool:
        return any(
            tr.get("lang") == "eo" and tr.get("term")
            for s in (e.get("senses") or [])
            for tr in (s.get("translations") or [])
        )
    lemmas_with_eo = {e["lemma"].lower() for e in bidix if _has_eo(e)}
    logger.info("  %d bidix entries (%d with an EO translation)", len(bidix), len(lemmas_with_eo))

    logger.info("Loading io.wiki vocabulary: %s", args.wiki_freq)
    wiki_vocab = load_wiki_vocab(args.wiki_freq)
    logger.info("  %d wiki tokens", len(wiki_vocab))

    # Accumulate: io_lemma -> {eo_term -> source_pair}
    # (multiple source pairs may yield the same derived pair — keep first)
    by_io: dict[str, dict[str, tuple[str, str]]] = {}  # io_lm -> {eo_term: (pos, source_pair)}

    # --- Verb derivations ---
    verb_kept = verb_skipped_dup = verb_skipped_vocab = 0
    seen_verb_pairs: set[tuple[str, str, str]] = set()  # (io_root, eo_root, suffix)

    for io_v, eo_v, io_r, eo_r in iter_verb_pairs(bidix):
        for io_suf, eo_suf, pos in VERB_DERIVATIONS:
            key = (io_r, eo_r, io_suf)
            if key in seen_verb_pairs:
                continue
            seen_verb_pairs.add(key)

            io_d = io_r + io_suf
            eo_d = eo_r + eo_suf
            if io_d in lemmas_with_eo:
                verb_skipped_dup += 1
                continue
            if io_d not in wiki_vocab:
                verb_skipped_vocab += 1
                continue
            src = f"{io_v}→{eo_v}"
            if io_d not in by_io:
                by_io[io_d] = {}
            if eo_d not in by_io[io_d]:
                by_io[io_d][eo_d] = (pos, src)
                verb_kept += 1

    logger.info("Verb derivations: %d new, %d already in bidix, %d not in wiki",
                verb_kept, verb_skipped_dup, verb_skipped_vocab)

    # --- Noun derivations ---
    noun_kept = noun_skipped_dup = noun_skipped_vocab = 0
    seen_noun_pairs: set[tuple[str, str, str]] = set()

    for io_n, eo_n, io_r, eo_r in iter_noun_pairs(bidix):
        for io_suf, eo_suf, pos in NOUN_DERIVATIONS:
            key = (io_r, eo_r, io_suf)
            if key in seen_noun_pairs:
                continue
            seen_noun_pairs.add(key)

            io_d = io_r + io_suf
            eo_d = eo_r + eo_suf
            if io_d in lemmas_with_eo:
                noun_skipped_dup += 1
                continue
            if io_d not in wiki_vocab:
                noun_skipped_vocab += 1
                continue
            src = f"{io_n}→{eo_n}"
            if io_d not in by_io:
                by_io[io_d] = {}
            if eo_d not in by_io[io_d]:
                by_io[io_d][eo_d] = (pos, src)
                noun_kept += 1

    logger.info("Noun derivations: %d new, %d already in bidix, %d not in wiki",
                noun_kept, noun_skipped_dup, noun_skipped_vocab)

    # --- Adjective derivations ---
    adj_kept = adj_skipped_dup = adj_skipped_vocab = 0
    seen_adj_pairs: set[tuple[str, str, str]] = set()

    for io_a, eo_a, io_r, eo_r in iter_adj_pairs(bidix):
        for io_suf, eo_suf, pos in ADJ_DERIVATIONS:
            key = (io_r, eo_r, io_suf)
            if key in seen_adj_pairs:
                continue
            seen_adj_pairs.add(key)

            io_d = io_r + io_suf
            eo_d = eo_r + eo_suf
            if io_d in lemmas_with_eo:
                adj_skipped_dup += 1
                continue
            if io_d not in wiki_vocab:
                adj_skipped_vocab += 1
                continue
            src = f"{io_a}→{eo_a}"
            if io_d not in by_io:
                by_io[io_d] = {}
            if eo_d not in by_io[io_d]:
                by_io[io_d][eo_d] = (pos, src)
                adj_kept += 1

    logger.info("Adj derivations: %d new, %d already in bidix, %d not in wiki",
                adj_kept, adj_skipped_dup, adj_skipped_vocab)

    # Build output entries: merge multiple eo translations for same io lemma
    out: list[dict] = []
    for io_d, eo_map in sorted(by_io.items()):
        # group by (pos, source_pair) — use most common pos/source
        pos, src = next(iter(eo_map.values()))
        translations = [
            {"lang": "eo", "term": eo_t, "confidence": 0.95, "source": SOURCE_TAG}
            for eo_t, (_, _) in eo_map.items()
        ]
        out.append({
            "lemma": io_d,
            "pos": pos,
            "language": "io",
            "senses": [{
                "senseId": None,
                "gloss": f"morphological derivation of {src}",
                "translations": translations,
            }],
            "provenance": [{"source": SOURCE_TAG, "page": src}],
        })

    total = verb_kept + noun_kept + adj_kept
    logger.info("Total new entries: %d (verb: %d, noun: %d, adj: %d)", total, verb_kept, noun_kept, adj_kept)

    if args.dry_run:
        logger.info("--dry-run: first 20 entries:")
        for e in out[:20]:
            trs = [t["term"] for t in e["senses"][0]["translations"]]
            logger.info("  %-22s → %s  [from: %s]",
                        e["lemma"], trs, e["senses"][0]["gloss"].replace("morphological derivation of ", ""))
        return 0

    args.out.parent.mkdir(parents=True, exist_ok=True)
    write_json(args.out, out)
    logger.info("Wrote %s (%d entries)", args.out, len(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
