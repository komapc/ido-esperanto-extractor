#!/usr/bin/env python3
import argparse
import logging
from pathlib import Path
from typing import Any, Dict, Iterable, List

from _common import read_json, write_json, configure_logging


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
    ap.add_argument("--input", type=Path, default=Path(__file__).resolve().parents[1] / "work/final_vocabulary.json")
    ap.add_argument("--out-io", type=Path, default=Path(__file__).resolve().parents[1] / "dist/ido_dictionary.json")
    ap.add_argument("--out-eo", type=Path, default=Path(__file__).resolve().parents[1] / "dist/esperanto_dictionary.json")
    ap.add_argument("-v", "--verbose", action="count", default=0)
    args = ap.parse_args(list(argv))

    configure_logging(args.verbose)
    entries = read_json(args.input)
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




