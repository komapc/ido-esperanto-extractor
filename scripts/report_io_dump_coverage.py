#!/usr/bin/env python3
import argparse
import json
import logging
from pathlib import Path
from typing import Any, Dict, Iterable

from _common import read_json, save_text, configure_logging


def compute_io_dump_coverage(io_wikt_path: Path) -> Dict[str, int]:
    data = read_json(io_wikt_path) if io_wikt_path.exists() else []
    
    # Handle both old format (list) and new format (dict with entries key)
    if isinstance(data, dict):
        data = data.get(\"entries\", [])
    
    no_eo_total = 0
    no_eo_any_other = 0
    no_eo_en = 0
    for e in data:
        if e.get("language") != "io":
            continue
        has_eo = False
        has_other = False
        has_en = False
        for s in e.get("senses", []) or []:
            for tr in s.get("translations", []) or []:
                term = (tr.get("term") or "").strip()
                if not term:
                    continue
                lang = tr.get("lang")
                if lang == "eo":
                    has_eo = True
                elif lang:
                    has_other = True
                    if lang == "en":
                        has_en = True
        if not has_eo:
            no_eo_total += 1
            if has_other:
                no_eo_any_other += 1
            if has_en:
                no_eo_en += 1
    return {
        "io_wikt_entries": len(data),
        "ido_no_eo_total": no_eo_total,
        "ido_no_eo_with_any_other": no_eo_any_other,
        "ido_no_eo_with_en": no_eo_en,
    }


def main(argv: Iterable[str]) -> int:
    ap = argparse.ArgumentParser(description="Report IO Wiktionary dump coverage (Ido without EO translations)")
    ap.add_argument("--io-wikt", type=Path, default=Path(__file__).resolve().parents[1] / "work/io_wikt_io_eo.json")
    ap.add_argument("--out", type=Path, default=Path(__file__).resolve().parents[1] / "reports/io_dump_coverage.md")
    ap.add_argument("-v", "--verbose", action="count", default=0)
    args = ap.parse_args(list(argv))

    configure_logging(args.verbose)
    stats = compute_io_dump_coverage(args.io_wikt)
    lines = []
    a = lines.append
    a("# IO Wiktionary Dump Coverage (Ido without EO translations)\n")
    a(f"- IO Wiktionary entries: {stats['io_wikt_entries']}")
    a(f"- Ido entries without EO translation: {stats['ido_no_eo_total']}")
    a(f"- Among those: with any other translation: {stats['ido_no_eo_with_any_other']}")
    a(f"- Among those: with English translation: {stats['ido_no_eo_with_en']}")
    save_text(args.out, "\n".join(lines) + "\n")
    logging.info("Wrote %s", args.out)
    return 0


if __name__ == "__main__":
    import sys
    raise SystemExit(main(sys.argv[1:]))


