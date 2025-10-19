#!/usr/bin/env python3
import argparse
import logging
from pathlib import Path
from typing import Any, Dict, Iterable, List

from _common import read_json, write_json, configure_logging


def merge_entries(primary: List[Dict[str, Any]], additions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    # Merge by lemma, language, pos, and translations set
    seen = set()
    out: List[Dict[str, Any]] = []
    def key(e: Dict[str, Any]) -> tuple:
        trans = []
        for s in e.get("senses", []) or []:
            for tr in s.get("translations", []) or []:
                if tr.get("lang") == "eo":
                    term = (tr.get("term") or "").strip()
                    if term:
                        trans.append((tr.get("lang"), term))
        return (
            (e.get("lemma") or "").lower(),
            (e.get("language") or "").lower(),
            (e.get("pos") or "").lower(),
            tuple(sorted(set(trans))),
        )

    for e in primary + additions:
        k = key(e)
        if k in seen:
            continue
        seen.add(k)
        out.append(e)
    out.sort(key=lambda x: (str(x.get("lemma", "")), str(x.get("pos", "")), str(x.get("language", ""))))
    return out


def main(argv: Iterable[str]) -> int:
    ap = argparse.ArgumentParser(description="Merge existing bilingual with pivot-aligned pairs")
    ap.add_argument("--base", type=Path, default=Path(__file__).resolve().parents[1] / "work/bilingual_raw.json")
    ap.add_argument("--pivot-en", type=Path, default=Path(__file__).resolve().parents[1] / "work/bilingual_pivot_en.json")
    ap.add_argument("--pivot-fr", type=Path, default=Path(__file__).resolve().parents[1] / "work/bilingual_pivot_fr.json")
    ap.add_argument("--out", type=Path, default=Path(__file__).resolve().parents[1] / "work/bilingual_with_pivots.json")
    ap.add_argument("-v", "--verbose", action="count", default=0)
    args = ap.parse_args(list(argv))

    configure_logging(args.verbose)
    base = read_json(args.base) if args.base.exists() else []
    en = read_json(args.pivot_en) if args.pivot_en.exists() else []
    fr = read_json(args.pivot_fr) if args.pivot_fr.exists() else []
    merged = merge_entries(base, en + fr)
    write_json(args.out, merged)
    logging.info("Wrote %s (%d entries)", args.out, len(merged))
    return 0


if __name__ == "__main__":
    import sys
    raise SystemExit(main(sys.argv[1:]))


