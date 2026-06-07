#!/usr/bin/env python3
"""Vortaro quality metric — the living signal for dictionary *generation*.

Two numbers, committed to reports/vortaro_quality.md, that gate every change to
the vocabulary (cleaning, ranking, recall). Mirrors how eval_translation.py is
the signal for the translator.

  precision@1 (ranking)
      Over entries that have BOTH an io_wiktionary-sourced EO term (human-curated
      reference) AND at least one candidate attested by some *other* source, hold
      out io_wiktionary, rank the remaining candidates, and check whether the
      top-1 matches the reference. This measures whether the merged non-Wiktionary
      sources, once ranked, agree with the human gloss — a held-out signal that is
      NOT circular (the reference is excluded from the ranking inputs) and is
      common-word-heavy rather than proper-noun-heavy (unlike held-out langlinks).

  recall (coverage)
      Fraction of the top-N io.wiki tokens (frequency-weighted) whose *lemma*
      (via the monodix FST) has any EO translation in the bidix. Extends
      frequency_coverage.md from raw-token to lemma level.

The ranker is pluggable (--ranker): `insertion` reproduces today's export order
(the baseline); `confidence` uses conflict_resolution.confidence_score once Step 2
lands. Swapping the ranker and re-running is how a ranking change is judged.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Callable, Dict, List, Sequence, Set, Tuple

from _common import read_json
from lexicon_filters import dedupe_eo_candidates, is_junk_lemma

TOKEN_RE = re.compile(r"\^(?P<surface>[^/^$]*)/(?P<analyses>[^$]*)\$")
HAS_LETTER_RE = re.compile(r"[^\W\d_]", re.UNICODE)

IO_WIKT = "io_wiktionary"

Candidate = Tuple[str, List[str]]  # (eo term, sources)
Ranker = Callable[[str, List[Candidate]], List[Candidate]]  # (lemma, cands) -> ranked


# --------------------------------------------------------------------------- #
# Candidate extraction
# --------------------------------------------------------------------------- #
def eo_candidates(entry: dict) -> List[Candidate]:
    """All distinct EO terms for an entry, in insertion order, with their sources."""
    out: List[Candidate] = []
    seen: Set[str] = set()
    for sense in entry.get("senses", []):
        for tr in sense.get("translations", []):
            if tr.get("lang") != "eo":
                continue
            term = tr.get("term")
            if not term or term in seen:
                continue
            seen.add(term)
            out.append((term, list(tr.get("sources", []))))
    return out


# --------------------------------------------------------------------------- #
# Rankers (pluggable) — built incrementally so each signal's delta is visible:
#   insertion     baseline (today's export order)
#   srcrank       source reliability only
#   srcrank_corr  + cross-source corroboration
#   confidence    + cognate proximity (full)
# --------------------------------------------------------------------------- #
def rank_insertion(lemma: str, cands: List[Candidate]) -> List[Candidate]:
    """Baseline: keep insertion order (what export_vortaro emits today)."""
    return list(cands)


def _score_ranker(*, use_corroboration: bool, use_cognate: bool) -> Ranker | None:
    try:
        from conflict_resolution import confidence_score  # type: ignore
    except Exception:
        return None

    def rank(lemma: str, cands: List[Candidate]) -> List[Candidate]:
        # higher score = better; Python's sort is stable so original order
        # breaks ties (keeps the change minimal where scores are equal).
        return sorted(cands, key=lambda c: -confidence_score(
            c[0], c[1], lemma, use_corroboration=use_corroboration,
            use_cognate=use_cognate))

    return rank


def build_rankers() -> Dict[str, Ranker]:
    rankers: Dict[str, Ranker] = {"insertion": rank_insertion}
    specs = {
        "srcrank": dict(use_corroboration=False, use_cognate=False),
        "srcrank_corr": dict(use_corroboration=True, use_cognate=False),
        "confidence": dict(use_corroboration=True, use_cognate=True),
    }
    for name, kw in specs.items():
        r = _score_ranker(**kw)
        if r is not None:
            rankers[name] = r
    return rankers


# --------------------------------------------------------------------------- #
# precision@1
# --------------------------------------------------------------------------- #
def precision_at_1(bidix: List[dict], ranker: Ranker, *, dedupe: bool = True,
                   max_misses: int = 40) -> Tuple[int, int, List[Tuple[str, str, str]]]:
    """Return (correct, eligible, all_misses) — misses are the false-friend set."""
    correct = eligible = 0
    misses: List[Tuple[str, str, str]] = []
    for entry in bidix:
        lemma = entry.get("lemma", "?")
        cands = eo_candidates(entry)
        if dedupe:
            cands = dedupe_eo_candidates(lemma, cands)
        if not cands:
            continue
        reference = {t.casefold() for t, s in cands if IO_WIKT in s}
        if not reference:
            continue
        # Need a real ranking decision: >=2 distinct candidates.
        if len(cands) < 2:
            continue
        # Hold out io_wiktionary as a *scoring signal* but keep every candidate
        # term in the pool — so a Wiktionary-only cognate (e.g. `abako`) is still
        # present to be surfaced by cognate/corroboration, just no longer wins on
        # the Wiktionary source tag itself. (Dropping such terms from the pool was
        # a bug: it removed exactly the entries cognate ranking is meant to fix.)
        pool = [(t, [x for x in s if x != IO_WIKT]) for t, s in cands]
        eligible += 1
        top = ranker(lemma, pool)[0][0]
        if top.casefold() in reference:
            correct += 1
        elif len(misses) < max_misses:
            misses.append((lemma, top, "/".join(sorted(
                {t for t, s in cands if IO_WIKT in s}))))
    return correct, eligible, misses


# --------------------------------------------------------------------------- #
# recall (lemmatized, frequency-weighted)
# --------------------------------------------------------------------------- #
# The Ido monodix emits the bare *root*, not the citation form
# (`urbi -> urb<n><pl>`, `habitas -> habit<vblex>`), but the bidix is keyed on
# citation forms (`urbo`, `habitar`). Reattach the regular citation ending per
# POS so the root matches the lemma it actually shares; without this every
# inflected token is a spurious recall miss.
_CITATION_ENDING = {
    "n": "o", "vblex": "ar", "vbser": "ar", "vbmod": "ar",
    "adj": "a", "adv": "e",
}


def lemmatize(tokens: Sequence[str], morf_bin: Path) -> Dict[str, List[str]]:
    """surface -> candidate citation-form lemmas via the monodix analyser.

    Returns the root reattached to its POS citation ending plus the root and the
    surface as fallbacks (so an already-citation or irregular token still has a
    chance to match). Unknown analysis -> [surface].
    """
    proc = subprocess.run(
        ["lt-proc", str(morf_bin)], input="\n".join(tokens),
        capture_output=True, text=True,
    )
    out: Dict[str, List[str]] = {}
    for m in TOKEN_RE.finditer(proc.stdout):
        surface, analyses = m.group("surface"), m.group("analyses")
        if analyses.startswith("*"):
            out[surface] = [surface]
            continue
        first = analyses.split("/")[0]
        pm = re.match(r"([^<+]+)<([^>]+)>", first)
        if not pm:
            out[surface] = [surface]
            continue
        root, pos = pm.group(1), pm.group(2)
        cands = [surface, root]
        ending = _CITATION_ENDING.get(pos)
        if ending:
            cands.append(root + ending)
        out[surface] = cands
    return out


def translated_lemmas(bidix: List[dict]) -> Set[str]:
    out: Set[str] = set()
    for entry in bidix:
        if eo_candidates(entry):
            lm = entry.get("lemma")
            if lm:
                out.add(lm.lower())
    return out


def _eligible_token(tok: str) -> bool:
    """A frequency token worth measuring: a real word, not numerals or
    MediaWiki/foreign-script junk (reuses the shared lexicon filter so the
    denominator matches what the dict accepts as a lemma)."""
    return (bool(HAS_LETTER_RE.search(tok)) and not tok.isdigit()
            and not is_junk_lemma(tok))


def recall(bidix: List[dict], freq_path: Path, morf_bin: Path, top_n: int
           ) -> Tuple[float, float, int, int, List[str]]:
    items = read_json(freq_path)["items"][:top_n]
    have = translated_lemmas(bidix)
    surfaces = [it["token"] for it in items if _eligible_token(it["token"])]
    lemma_of = lemmatize(surfaces, morf_bin)

    tok_total = tok_covered = 0
    type_total = type_covered = 0
    misses: List[str] = []
    for it in items:
        tok = it["token"]
        if not _eligible_token(tok):
            continue
        cands = [c.lower() for c in lemma_of.get(tok, [tok])]
        covered = any(c in have for c in cands)
        type_total += 1
        tok_total += it["count"]
        if covered:
            type_covered += 1
            tok_covered += it["count"]
        elif len(misses) < 60:
            misses.append(tok)
    type_r = 100.0 * type_covered / type_total if type_total else 0.0
    tok_r = 100.0 * tok_covered / tok_total if tok_total else 0.0
    return type_r, tok_r, type_covered, type_total, misses


# --------------------------------------------------------------------------- #
# Report
# --------------------------------------------------------------------------- #
def write_report(path: Path, ranker_name: str, p_correct: int, p_eligible: int,
                 misranks, type_r, tok_r, type_cov, type_tot, misses, top_n,
                 ranker_p1: Dict[str, float]) -> None:
    p1 = 100.0 * p_correct / p_eligible if p_eligible else 0.0
    # Render the "ranking is closed" comparison from LIVE numbers (ranker_p1)
    # rather than frozen prose, so the record can never drift from the bidix.
    order = ["insertion", "srcrank", "srcrank_corr", "confidence"]
    labels = {"insertion": "insertion", "srcrank": "srcrank",
              "srcrank_corr": "srcrank_corr (corroboration)",
              "confidence": "confidence (cognate)"}
    rank_line = ", ".join(
        f"`{labels.get(n, n)}` {ranker_p1[n]:.1f}%"
        for n in order if n in ranker_p1)
    lines = [
        "# Vortaro Quality",
        "",
        f"_Generated {date.today().isoformat()} — ranker: `{ranker_name}`, recall top-N: {top_n}_",
        "",
        "## precision@1 (ranking)",
        f"**{p1:.1f}%** ({p_correct}/{p_eligible} eligible entries)",
        "",
        "Top-1 of held-out non-Wiktionary candidates vs the io_wiktionary reference.",
        "",
        "### Ranking: closed (measured negative result)",
        "Every ranker smarter than insertion *regresses* precision@1 (computed live):",
        rank_line + ".",
        "precision@1 also holds out io_wiktionary, so it is blind to",
        "no-curated-source entries — exactly where ranking picks the user-visible",
        "#1 — and the live export keeps io_wiktionary on top by source rank, so live",
        "ranking is ≥ measured. The export stays on the source-rank order",
        "(`conflict_resolution.confidence_key`); `confidence_score` remains in the",
        "tree as the measured-and-rejected alternative. Do not reopen.",
        "",
        "### Sample misranks (chosen → reference)",
        *[f"- `{lm}`: {got} → {ref}" for lm, got, ref in misranks[:25]],
        "",
        "## recall (coverage)",
        f"**type {type_r:.1f}%** ({type_cov}/{type_tot} lemmas) · **token-weighted {tok_r:.1f}%**",
        "",
        f"Top-{top_n} io.wiki tokens, junk-stripped (shared `lexicon_filters`), then",
        "lemmatized to citation form via the monodix (root + POS ending, since the",
        "analyser emits bare roots); covered = the lemma has any EO translation.",
        "",
        "Two effects lift this over the old 61.2% type / 76.0% token baseline:",
        "citation-form reconstruction alone (inflected tokens now map to their",
        "lemma) reaches ~79.7% type, and junk-stripping the denominator — which",
        "drops foreign-script proper nouns (`białystok`, `łódź`) and MediaWiki",
        "artifacts, by design — narrows it to the current figure. This measures",
        "ASCII common-vocabulary coverage, not proper-noun recall.",
        "",
        "### Sample misses",
        "- " + ", ".join(misses[:50]),
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    here = Path(__file__).resolve().parent.parent  # extractor/
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--bidix", type=Path, default=here / "dist/bidix_big.json")
    ap.add_argument("--freq", type=Path, default=here / "work/io_wiki_frequency.json")
    ap.add_argument("--morf-bin", type=Path,
                    default=here.parent / "apertium-ido/ido.automorf.bin")
    ap.add_argument("--reports-dir", type=Path, default=here / "reports")
    ap.add_argument("--top-n", type=int, default=5000)
    ap.add_argument("--ranker", default="insertion",
                    help="insertion | srcrank | srcrank_corr | confidence")
    ap.add_argument("--no-dedupe", action="store_true",
                    help="skip case-variant candidate dedup (for A/B measurement)")
    ap.add_argument("--show-misses", type=int, default=0,
                    help="print N precision@1 misses (the false-friend set) and exit")
    args = ap.parse_args()

    rankers = build_rankers()
    if args.ranker not in rankers:
        print(f"ranker '{args.ranker}' unavailable (have: {sorted(rankers)})", file=sys.stderr)
        return 2
    ranker = rankers[args.ranker]
    dedupe = not args.no_dedupe

    bidix = read_json(args.bidix)

    if args.show_misses:
        _, _, misses = precision_at_1(bidix, ranker, dedupe=dedupe,
                                      max_misses=args.show_misses)
        for lemma, got, ref in misses:
            print(f"{lemma}\t{got}\t→ ref: {ref}")
        return 0

    p_correct, p_eligible, misranks = precision_at_1(bidix, ranker, dedupe=dedupe)
    type_r, tok_r, type_cov, type_tot, misses = recall(
        bidix, args.freq, args.morf_bin, args.top_n)

    # All rankers' precision@1, computed live, so the "ranking is closed" record
    # in the report is regenerated from the bidix and can never go stale.
    ranker_p1: Dict[str, float] = {}
    for name, r in rankers.items():
        c, e, _ = precision_at_1(bidix, r, dedupe=dedupe)
        ranker_p1[name] = 100.0 * c / e if e else 0.0

    args.reports_dir.mkdir(parents=True, exist_ok=True)
    write_report(args.reports_dir / "vortaro_quality.md", args.ranker,
                 p_correct, p_eligible, misranks, type_r, tok_r,
                 type_cov, type_tot, misses, args.top_n, ranker_p1)

    p1 = 100.0 * p_correct / p_eligible if p_eligible else 0.0
    print(f"precision@1: {p1:.1f}%  ({p_correct}/{p_eligible})  ranker={args.ranker}")
    print(f"recall: type {type_r:.1f}%  token-weighted {tok_r:.1f}%  "
          f"({type_cov}/{type_tot} lemmas, top-{args.top_n})")
    print(f"→ {args.reports_dir / 'vortaro_quality.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
