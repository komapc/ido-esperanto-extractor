#!/usr/bin/env python3
"""Ido->Esperanto translation evaluation harness (roadmap item #1, first slice).

Runs a gold parallel set through the live Apertium pipeline and computes two
deterministic metrics, so translation quality is a number that moves rather than
a stale hand-written markdown report:

  1. coverage  -- fraction of word tokens the Ido analyser recognises
                  (unknown = lt-proc emits `^word/*word$`). Higher is better.
  2. chrF      -- character n-gram F-score (beta=2) of the translation vs the
                  reference. Self-contained implementation, no external deps.
                  Higher is better.

Outputs:
  reports/quality_trend.md   -- one appended row per run (the trend signal)
  reports/quality_latest.md  -- full per-sentence detail of the most recent run

Deferred to later slices (see FLOW_REVIEW.md): frequency-weighted coverage and an
LLM-as-judge adequacy/fluency layer. This slice is intentionally deterministic.

Usage:
  python3 scripts/eval_translation.py
  python3 scripts/eval_translation.py --gold data/gold/ido_epo.tsv --pair-dir ../apertium-ido-epo
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

TOKEN_RE = re.compile(r"\^(?P<surface>[^/^$]*)/(?P<analyses>[^$]*)\$")
HAS_LETTER_RE = re.compile(r"[^\W\d_]", re.UNICODE)


# --------------------------------------------------------------------------- #
# Metrics
# --------------------------------------------------------------------------- #
def _char_ngrams(text: str, n: int) -> list[str]:
    s = re.sub(r"\s+", " ", text.strip().lower())
    return [s[i : i + n] for i in range(len(s) - n + 1)] if len(s) >= n else []


def chrf(hyp: str, ref: str, max_n: int = 6, beta: float = 2.0) -> float:
    """chrF score in [0, 100]. Averaged over char n-gram orders 1..max_n."""
    if not hyp.strip() or not ref.strip():
        return 0.0
    f_scores: list[float] = []
    for n in range(1, max_n + 1):
        h, r = _char_ngrams(hyp, n), _char_ngrams(ref, n)
        if not h or not r:
            continue
        hc, rc = defaultdict(int), defaultdict(int)
        for g in h:
            hc[g] += 1
        for g in r:
            rc[g] += 1
        overlap = sum(min(hc[g], rc[g]) for g in hc)
        prec = overlap / len(h)
        rec = overlap / len(r)
        if prec + rec == 0:
            f_scores.append(0.0)
            continue
        b2 = beta * beta
        f_scores.append((1 + b2) * prec * rec / (b2 * prec + rec))
    return 100.0 * sum(f_scores) / len(f_scores) if f_scores else 0.0


# --------------------------------------------------------------------------- #
# Apertium calls
# --------------------------------------------------------------------------- #
def analyse_coverage(text: str, morf_bin: Path) -> tuple[int, int, list[str]]:
    """Return (known_tokens, total_word_tokens, unknown_surfaces) for one line."""
    proc = subprocess.run(
        ["lt-proc", str(morf_bin)], input=text, capture_output=True, text=True
    )
    known = total = 0
    unknown: list[str] = []
    for m in TOKEN_RE.finditer(proc.stdout):
        surface, analyses = m.group("surface"), m.group("analyses")
        if not HAS_LETTER_RE.search(surface):
            continue  # skip pure punctuation/number tokens
        total += 1
        if analyses.startswith("*"):
            unknown.append(surface)
        else:
            known += 1
    return known, total, unknown


def translate(text: str, pair_dir: Path, mode: str) -> str:
    proc = subprocess.run(
        ["apertium", "-d", str(pair_dir), mode],
        input=text,
        capture_output=True,
        text=True,
    )
    return proc.stdout.strip()


# --------------------------------------------------------------------------- #
# Gold IO
# --------------------------------------------------------------------------- #
def load_gold(path: Path) -> list[tuple[str, str, list[str]]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        ido, eo = parts[0].strip(), parts[1].strip()
        tags = [t.strip() for t in parts[2].split(",")] if len(parts) > 2 else []
        rows.append((ido, eo, tags))
    return rows


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    here = Path(__file__).resolve().parent.parent  # extractor/
    ap.add_argument("--gold", type=Path, default=here / "data/gold/ido_epo.tsv")
    ap.add_argument("--pair-dir", type=Path, default=here.parent / "apertium-ido-epo")
    ap.add_argument("--mode", default="ido-epo")
    ap.add_argument("--reports-dir", type=Path, default=here / "reports")
    ap.add_argument(
        "--chrf-fail", type=float, default=70.0,
        help="chrF below this flags a sentence as a regression in the detail report",
    )
    args = ap.parse_args()

    morf_bin = args.pair_dir / f"{args.mode}.automorf.bin"
    for needed in (args.gold, morf_bin):
        if not needed.exists():
            print(f"ERROR: missing {needed}", file=sys.stderr)
            return 2

    gold = load_gold(args.gold)
    if not gold:
        print(f"ERROR: no gold rows in {args.gold}", file=sys.stderr)
        return 2

    results = []
    tot_known = tot_words = 0
    chrf_sum = 0.0
    per_tag: dict[str, list[float]] = defaultdict(list)

    for ido, eo, tags in gold:
        known, total, unknown = analyse_coverage(ido, morf_bin)
        hyp = translate(ido, args.pair_dir, args.mode)
        score = chrf(hyp, eo)
        tot_known += known
        tot_words += total
        chrf_sum += score
        for t in tags:
            per_tag[t].append(score)
        results.append(
            {"ido": ido, "ref": eo, "hyp": hyp, "tags": tags,
             "chrf": score, "unknown": unknown}
        )

    coverage = 100.0 * tot_known / tot_words if tot_words else 0.0
    mean_chrf = chrf_sum / len(results)
    today = date.today().isoformat()

    # --- trend table (append one row) ---
    args.reports_dir.mkdir(parents=True, exist_ok=True)
    trend = args.reports_dir / "quality_trend.md"
    if not trend.exists():
        trend.write_text(
            "# Ido->Esperanto Quality Trend\n\n"
            "Generated by `scripts/eval_translation.py`. One row per run. "
            "Higher is better for both metrics.\n\n"
            "| Date | Sentences | Coverage % | Mean chrF |\n"
            "|------|-----------|-----------|-----------|\n",
            encoding="utf-8",
        )
    with trend.open("a", encoding="utf-8") as f:
        f.write(f"| {today} | {len(results)} | {coverage:.1f} | {mean_chrf:.1f} |\n")

    # --- per-run detail ---
    latest = args.reports_dir / "quality_latest.md"
    lines = [
        f"# Quality detail — {today}",
        "",
        f"- Gold set: `{args.gold}` ({len(results)} sentences)",
        f"- Coverage: **{coverage:.1f}%** ({tot_known}/{tot_words} word tokens analysed)",
        f"- Mean chrF: **{mean_chrf:.1f}**",
        "",
        "## By phenomenon",
        "",
        "| Tag | N | Mean chrF |",
        "|-----|---|-----------|",
    ]
    for tag in sorted(per_tag, key=lambda t: sum(per_tag[t]) / len(per_tag[t])):
        s = per_tag[tag]
        lines.append(f"| {tag} | {len(s)} | {sum(s)/len(s):.1f} |")

    flagged = [r for r in results if r["chrf"] < args.chrf_fail or r["unknown"]]
    lines += [
        "",
        f"## Flagged sentences ({len(flagged)}) — chrF < {args.chrf_fail:g} or unknown words",
        "",
    ]
    for r in sorted(flagged, key=lambda r: r["chrf"]):
        unk = f"  unknown={r['unknown']}" if r["unknown"] else ""
        lines += [
            f"- chrF {r['chrf']:.0f} [{','.join(r['tags']) or '-'}]{unk}",
            f"    - in : {r['ido']}",
            f"    - got: {r['hyp']}",
            f"    - ref: {r['ref']}",
        ]
    latest.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Coverage: {coverage:.1f}%   Mean chrF: {mean_chrf:.1f}   "
          f"({len(results)} sentences, {len(flagged)} flagged)")
    print(f"Wrote {trend} and {latest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
