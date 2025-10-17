#!/usr/bin/env python3
import argparse
import sys
import logging
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from _common import read_json, write_json, configure_logging


def normalize(entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    # Deduplicate by (lemma, pos, language, translations set)
    seen = set()
    out: List[Dict[str, Any]] = []
    for e in entries:
        lemma = (e.get("lemma") or "").strip()
        pos = (e.get("pos") or "").strip()
        lang = (e.get("language") or "").strip()
        trans = []
        for s in e.get("senses", []) or []:
            for tr in s.get("translations", []) or []:
                if tr.get("lang") == "eo":
                    trans.append((tr.get("lang"), (tr.get("term") or "").strip()))
        key = (lemma.lower(), pos.lower(), lang.lower(), tuple(sorted(set(trans))))
        if key in seen:
            continue
        seen.add(key)
        out.append(e)
    out.sort(key=lambda x: (str(x.get("lemma", "")), str(x.get("pos", "")), str(x.get("language", ""))))
    return out


def main(argv: Iterable[str]) -> int:
    ap = argparse.ArgumentParser(description="Normalize and deduplicate bilingual entries")
    ap.add_argument("--input", type=Path, default=Path(__file__).resolve().parents[1] / "work/bilingual_raw.json")
    ap.add_argument("--out", type=Path, default=Path(__file__).resolve().parents[1] / "work/bilingual_normalized.json")
    ap.add_argument("-v", "--verbose", action="count", default=0)
    args = ap.parse_args(list(argv))

    configure_logging(args.verbose)
    entries = read_json(args.input)
    result = normalize(entries)
    write_json(args.out, result)
    logging.info("Wrote %s (%d entries)", args.out, len(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))


