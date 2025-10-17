#!/usr/bin/env python3
import argparse
import logging
from pathlib import Path
from typing import Any, Dict, Iterable, List, Set

from _common import read_json, save_text, configure_logging


def load_vocab(entries_path: Path) -> Set[str]:
    entries = read_json(entries_path)
    lemmas = {str(e.get("lemma", "")).lower() for e in entries}
    return {l for l in lemmas if l}


def top_n_tokens(freq_path: Path, top_n: int) -> List[str]:
    data = read_json(freq_path)
    items = data.get("items", [])
    return [str(it.get("token")) for it in items[:top_n] if it.get("token")]


def report(freq_path: Path, entries_path: Path, out_md: Path, top_n: int) -> None:
    lemmas = load_vocab(entries_path)
    top_tokens = top_n_tokens(freq_path, top_n)
    missing = [tok for tok in top_tokens if tok.lower() not in lemmas]
    coverage = 1.0 - (len(missing) / max(1, len(top_tokens)))

    lines = []
    lines.append(f"# Frequency Coverage Report\n")
    lines.append(f"Top-N: {top_n}\n")
    lines.append(f"Coverage: {coverage*100:.2f}% ({len(top_tokens)-len(missing)}/{len(top_tokens)})\n")
    lines.append("\n## Missing Tokens\n")
    for tok in missing:
        lines.append(f"- {tok}")
    save_text(out_md, "\n".join(lines) + "\n")


def main(argv: Iterable[str]) -> int:
    ap = argparse.ArgumentParser(description="Generate frequency coverage report")
    ap.add_argument("--freq", type=Path, default=Path(__file__).resolve().parents[1] / "work/io_wiki_frequency.json")
    ap.add_argument("--entries", type=Path, default=Path(__file__).resolve().parents[1] / "work/final_vocabulary.json")
    ap.add_argument("--out", type=Path, default=Path(__file__).resolve().parents[1] / "reports/frequency_coverage.md")
    ap.add_argument("--top", type=int, default=5000)
    ap.add_argument("-v", "--verbose", action="count", default=0)
    args = ap.parse_args(list(argv))

    configure_logging(args.verbose)
    out = report(args.freq, args.entries, args.out, args.top)
    logging.info("Wrote %s", args.out)
    return 0


if __name__ == "__main__":
    import sys
    raise SystemExit(main(sys.argv[1:]))


