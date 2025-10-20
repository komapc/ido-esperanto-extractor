#!/usr/bin/env python3
import argparse
import logging
from pathlib import Path
from typing import Any, Dict, Iterable, List

from _common import read_json, write_json, configure_logging


def merge_entries(inputs: List[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    merged: List[Dict[str, Any]] = []
    for chunk in inputs:
        if not chunk:
            continue
        merged.extend(chunk)
    # Deduplicate by (language, lemma, pos)
    seen = set()
    unique: List[Dict[str, Any]] = []
    for e in merged:
        key = (e.get("language"), (e.get("lemma") or "").strip().lower(), (e.get("pos") or "").strip().lower())
        if key in seen:
            continue
        seen.add(key)
        unique.append(e)
    return unique


def build_monolingual(entries: List[Dict[str, Any]], language: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for e in entries:
        if e.get("language") != language:
            continue
        out.append(e)
    out.sort(key=lambda x: (str(x.get("lemma", "")), str(x.get("pos", ""))))
    return out


def main(argv: Iterable[str]) -> int:
    ap = argparse.ArgumentParser(description="Build monolingual dictionaries from bilingual entries")
    ap.add_argument("--input", type=Path, action="append", help="Input JSON file(s) to merge (can be specified multiple times)")
    ap.add_argument("--out-io", type=Path, default=Path(__file__).resolve().parents[1] / "dist/ido_dictionary.json")
    ap.add_argument("--out-eo", type=Path, default=Path(__file__).resolve().parents[1] / "dist/esperanto_dictionary.json")
    ap.add_argument("-v", "--verbose", action="count", default=0)
    args = ap.parse_args(list(argv))

    configure_logging(args.verbose)
    base_dir = Path(__file__).resolve().parents[1]
    input_paths = args.input or [
        base_dir / "work/final_vocabulary.json",
        base_dir / "work/fr_wikt_meanings.json",
    ]
    inputs: List[List[Dict[str, Any]]] = []
    for p in input_paths:
        if p.exists():
            logging.info("Loading %s", p)
            inputs.append(read_json(p))
        else:
            logging.warning("File not found: %s (skipping)", p)
    entries = merge_entries(inputs)
    io = build_monolingual(entries, "io")
    eo = build_monolingual(entries, "eo")
    write_json(args.out_io, io)
    write_json(args.out_eo, eo)
    logging.info("Wrote %s (%d entries)", args.out_io, len(io))
    logging.info("Wrote %s (%d entries)", args.out_eo, len(eo))
    return 0


if __name__ == "__main__":
    import sys
    raise SystemExit(main(sys.argv[1:]))




