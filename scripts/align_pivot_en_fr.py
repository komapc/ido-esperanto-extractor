#!/usr/bin/env python3
import argparse
import logging
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from _common import read_json, write_json, configure_logging


def index_language(entries: List[Dict[str, Any]], my_lang: str, target_lang: str) -> Dict[Tuple[str, str], Dict[str, Any]]:
    idx: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for e in entries:
        if e.get("language") != my_lang:
            continue
        lemma = (e.get("lemma") or "").strip()
        pos = (e.get("pos") or "").strip()
        if not lemma:
            continue
        has_target = False
        targets: List[str] = []
        for s in e.get("senses", []) or []:
            for tr in s.get("translations", []) or []:
                if (tr.get("lang") == target_lang) and (tr.get("term") or "").strip():
                    has_target = True
                    targets.append(str(tr.get("term")).strip())
        if has_target:
            idx[(lemma.lower(), pos.lower())] = {**e, "_targets": list(sorted(set(targets)))}
    return idx


def build_pivot_pairs(io_entries: List[Dict[str, Any]], eo_entries: List[Dict[str, Any]], pivot_lang: str) -> List[Dict[str, Any]]:
    # Map IO and EO by pivot_lang targets
    io_idx = index_language(io_entries, "io", pivot_lang)
    eo_idx = index_language(eo_entries, "eo", pivot_lang)

    # Reverse map: pivot_term -> list of IOs / EOs
    piv2io: Dict[str, List[Dict[str, Any]]] = {}
    for e in io_idx.values():
        for t in e.get("_targets", []):
            piv2io.setdefault(t.lower(), []).append(e)
    piv2eo: Dict[str, List[Dict[str, Any]]] = {}
    for e in eo_idx.values():
        for t in e.get("_targets", []):
            piv2eo.setdefault(t.lower(), []).append(e)

    aligned: List[Dict[str, Any]] = []
    for piv, ios in piv2io.items():
        eos = piv2eo.get(piv) or []
        if not eos:
            continue
        for io_e in ios:
            for eo_e in eos:
                item = {
                    "lemma": io_e.get("lemma"),
                    "pos": io_e.get("pos"),
                    "language": "io",
                    "senses": [{
                        "senseId": None,
                        "gloss": None,
                        "translations": [{"lang": "eo", "term": eo_e.get("lemma"), "confidence": 0.7, "source": f"pivot_{pivot_lang}"}],
                    }],
                    "provenance": [
                        *list(io_e.get("provenance", []) or []),
                        *list(eo_e.get("provenance", []) or []),
                        {"source": f"pivot_{pivot_lang}", "pivot_term": piv},
                    ],
                }
                aligned.append(item)
    return aligned


def main(argv: Iterable[str]) -> int:
    ap = argparse.ArgumentParser(description="Align IO and EO via pivot translations (EN/FR)")
    ap.add_argument("--io", type=Path, default=Path(__file__).resolve().parents[1] / "work/io_wikt_io_eo.json")
    ap.add_argument("--eo", type=Path, default=Path(__file__).resolve().parents[1] / "work/eo_wikt_eo_io.json")
    ap.add_argument("--pivot", choices=["en", "fr"], required=True)
    ap.add_argument("--out", type=Path, default=Path(__file__).resolve().parents[1] / "work/bilingual_pivot.json")
    ap.add_argument("-v", "--verbose", action="count", default=0)
    args = ap.parse_args(list(argv))

    configure_logging(args.verbose)
    io_entries = read_json(args.io)
    eo_entries = read_json(args.eo)
    out = build_pivot_pairs(io_entries, eo_entries, args.pivot)
    write_json(args.out, out)
    logging.info("Wrote %s (%d items)", args.out, len(out))
    return 0


if __name__ == "__main__":
    import sys
    raise SystemExit(main(sys.argv[1:]))


