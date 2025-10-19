#!/usr/bin/env python3
import argparse
import sys
import logging
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from _common import read_json, write_json, configure_logging


def identical_form_heuristic(io_entries: List[Dict[str, Any]], eo_entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    # Build index by lemma+pos for quick lookup
    def index_by_lemma_pos(entries: List[Dict[str, Any]]) -> Dict[Tuple[str, str], Dict[str, Any]]:
        idx: Dict[Tuple[str, str], Dict[str, Any]] = {}
        for e in entries:
            lemma = (e.get("lemma") or "").lower()
            pos = (e.get("pos") or "").lower()
            if lemma and pos:
                idx[(lemma, pos)] = e
        return idx

    io_idx = index_by_lemma_pos(io_entries)
    eo_idx = index_by_lemma_pos(eo_entries)

    aligned: List[Dict[str, Any]] = []
    for key, io_e in io_idx.items():
        if key not in eo_idx:
            continue
        eo_e = eo_idx[key]
        # Safety: POS already matches; now check overlapping English translations if present in senses
        def english_set(entry: Dict[str, Any]) -> set:
            out = set()
            for s in entry.get("senses", []) or []:
                for tr in s.get("translations", []) or []:
                    if tr.get("lang") == "en":
                        term = (tr.get("term") or "").strip().lower()
                        if term:
                            out.add(term)
            return out

        en_io = english_set(io_e)
        en_eo = english_set(eo_e)
        safe = True
        if en_io and en_eo and en_io.isdisjoint(en_eo):
            # If both sides have English translations but no overlap, skip
            safe = False
        if not safe:
            continue

        # Build a merged bilingual item with boosted confidence
        translations = []
        for s in io_e.get("senses", []) or []:
            for tr in s.get("translations", []) or []:
                if tr.get("lang") == "eo":
                    tr2 = dict(tr)
                    tr2["confidence"] = min(1.0, float(tr.get("confidence", 0.6)) + 0.2)
                    translations.append(tr2)
        item = {
            "lemma": io_e.get("lemma"),
            "pos": io_e.get("pos"),
            "language": "io",
            "senses": [{"senseId": None, "gloss": None, "translations": translations}],
            "provenance": [
                *list(io_e.get("provenance", []) or []),
                *list(eo_e.get("provenance", []) or []),
            ],
        }
        aligned.append(item)
    return aligned


def align(io_path: Path, eo_path: Path, out_path: Path, wiki_path: Path | None = None) -> None:
    logging.info("Aligning bilingual dictionaries: %s + %s", io_path, eo_path)
    io_entries = read_json(io_path)
    eo_entries = read_json(eo_path)

    aligned = identical_form_heuristic(io_entries, eo_entries)
    # Pass-through: include IO→EO entries as bilingual items even without EO confirmation
    for io_e in io_entries:
        translations = []
        for s in io_e.get("senses", []) or []:
            for tr in s.get("translations", []) or []:
                if tr.get("lang") == "eo" and tr.get("term"):
                    translations.append({"lang": "eo", "term": tr.get("term"), "confidence": float(tr.get("confidence", 0.5)), "source": tr.get("source", "io_wiktionary")})
        if not translations:
            continue
        item = {
            "lemma": io_e.get("lemma"),
            "pos": io_e.get("pos"),
            "language": "io",
            "senses": [{"senseId": None, "gloss": None, "translations": translations}],
            "provenance": list(io_e.get("provenance", []) or []),
        }
        aligned.append(item)
    # Include Wikipedia titles (monolingual Ido entries) so they flow downstream
    if wiki_path is not None and wiki_path.exists():
        try:
            wiki_entries = read_json(wiki_path)
        except Exception:
            wiki_entries = []
        added = 0
        for we in wiki_entries or []:
            if (we.get("language") or "") != "io":
                continue
            item = {
                "lemma": we.get("lemma"),
                "pos": we.get("pos"),
                "language": "io",
                "senses": [],  # no translations; may be kept in monolingual via filter step
                "provenance": list(we.get("provenance", []) or []),
            }
            aligned.append(item)
            added += 1
        logging.info("Added %d Wikipedia title entries", added)

    write_json(out_path, aligned)
    logging.info("Wrote %s (%d aligned items)", out_path, len(aligned))


def main(argv: Iterable[str]) -> int:
    ap = argparse.ArgumentParser(description="Align IO→EO and EO→IO wiktionary outputs")
    ap.add_argument("--io", type=Path, default=Path(__file__).resolve().parents[1] / "work/io_wikt_io_eo.json")
    ap.add_argument("--eo", type=Path, default=Path(__file__).resolve().parents[1] / "work/eo_wikt_eo_io.json")
    ap.add_argument("--wiki", type=Path, default=Path(__file__).resolve().parents[1] / "work/io_wiki_vocab.json")
    ap.add_argument("--out", type=Path, default=Path(__file__).resolve().parents[1] / "work/bilingual_raw.json")
    ap.add_argument("-v", "--verbose", action="count", default=0)
    args = ap.parse_args(list(argv))

    configure_logging(args.verbose)
    align(args.io, args.eo, args.out, args.wiki)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))


