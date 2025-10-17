#!/usr/bin/env python3
import argparse
import logging
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from _common import read_json, write_json, configure_logging


DEMONYM_NOUN_SUFFIXES = ("ano", "iano")
DEMONYM_ADJ_SUFFIXES = ("ana", "iana")


def has_wikipedia_provenance(entry: Dict[str, Any]) -> bool:
    for p in entry.get("provenance", []) or []:
        src = str(p.get("source") or "")
        if src.endswith("wikipedia") or "wikipedia" in src:
            return True
    return False


def infer_paradigm(entry: Dict[str, Any]) -> Optional[str]:
    lemma = str(entry.get("lemma") or "")
    pos = entry.get("pos")
    if not lemma:
        return None

    lower_lemma = lemma.lower()

    # Multi-token (spaces or hyphens): treat as noun (proper name or compound)
    if " " in lemma or "-" in lemma:
        return "o__n"

    # Demonyms: prefer noun for -ano/-iano and adjective for -ana/-iana
    if lower_lemma.endswith(DEMONYM_NOUN_SUFFIXES):
        return "o__n"
    if lower_lemma.endswith(DEMONYM_ADJ_SUFFIXES):
        return "a__adj"

    # Toponyms ending with -ia (Brazilia, Chinia, etc.) → treat as noun
    if lower_lemma.endswith("ia") and len(lemma) > 3:
        return "o__n"

    # POS-informed rules
    if pos == "noun":
        return "o__n"
    if pos == "adjective":
        return "a__adj"
    if pos == "adverb":
        return "e__adv"
    if pos == "verb":
        return "ar__vblex"

    # Heuristic fallback by endings
    if lower_lemma.endswith("a"):
        return "a__adj"
    if lower_lemma.endswith("e"):
        return "e__adv"
    if lower_lemma.endswith("o"):
        return "o__n"
    if lower_lemma.endswith("ar") or lower_lemma.endswith("ir"):
        return "ar__vblex"

    # Wikipedia proper names and single-token titles → noun fallback
    if has_wikipedia_provenance(entry):
        if lemma[:1].isupper() or lower_lemma.endswith("i"):
            return "o__n"

    # Capitalized fallback
    if lemma[:1].isupper() and len(lemma) > 2:
        return "o__n"
    return None


def infer(entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    existing_lemmas = set()

    def add_entry(entry: Dict[str, Any]) -> None:
        lemma_key = str(entry.get("lemma") or "")
        if not lemma_key:
            return
        existing_lemmas.add(lemma_key)
        out.append(entry)

    def maybe_add_demonym_twin(base_entry: Dict[str, Any]) -> None:
        lemma = str(base_entry.get("lemma") or "")
        if not lemma:
            return
        lower = lemma.lower()
        par = (base_entry.get("morphology") or {}).get("paradigm")
        # noun -> adjective twin
        if lower.endswith("iano") and par == "o__n":
            twin = lemma[:-4] + "iana"
            if twin not in existing_lemmas:
                twin_entry = {**base_entry, "lemma": twin, "pos": "adjective", "morphology": {"paradigm": "a__adj", "features": {}}}
                add_entry(twin_entry)
        elif lower.endswith("ano") and par == "o__n":
            twin = lemma[:-3] + "ana"
            if twin not in existing_lemmas:
                twin_entry = {**base_entry, "lemma": twin, "pos": "adjective", "morphology": {"paradigm": "a__adj", "features": {}}}
                add_entry(twin_entry)
        # adjective -> noun twin
        elif lower.endswith("iana") and par == "a__adj":
            twin = lemma[:-4] + "iano"
            if twin not in existing_lemmas:
                twin_entry = {**base_entry, "lemma": twin, "pos": "noun", "morphology": {"paradigm": "o__n", "features": {}}}
                add_entry(twin_entry)
        elif lower.endswith("ana") and par == "a__adj":
            twin = lemma[:-3] + "ano"
            if twin not in existing_lemmas:
                twin_entry = {**base_entry, "lemma": twin, "pos": "noun", "morphology": {"paradigm": "o__n", "features": {}}}
                add_entry(twin_entry)

    for e in entries:
        par = infer_paradigm(e)
        morph = {"paradigm": par, "features": {}}
        e2 = {**e, "morphology": morph}
        add_entry(e2)
        maybe_add_demonym_twin(e2)
        # Toponym twin: -ia noun -> -iana adjective
        lemma = str(e2.get("lemma") or "")
        par2 = (e2.get("morphology") or {}).get("paradigm")
        if lemma and lemma.lower().endswith("ia") and par2 == "o__n":
            twin = lemma + "na"  # e.g., Germania -> Germaniana
            if twin not in existing_lemmas:
                twin_entry = {**e2, "lemma": twin, "pos": "adjective", "morphology": {"paradigm": "a__adj", "features": {}}}
                add_entry(twin_entry)
        # Wikipedia proper noun ending with -a noun -> add -ana adjective
        if lemma and has_wikipedia_provenance(e2) and lemma.lower().endswith("a") and par2 == "o__n" and len(lemma) > 3:
            twin = lemma + "na"
            if twin not in existing_lemmas:
                twin_entry = {**e2, "lemma": twin, "pos": "adjective", "morphology": {"paradigm": "a__adj", "features": {}}}
                add_entry(twin_entry)
        # Adjective -iana -> noun -ia twin
        if lemma and lemma.lower().endswith("iana") and par2 == "a__adj":
            twin = lemma[:-2]  # remove 'na'
            if twin not in existing_lemmas:
                twin_entry = {**e2, "lemma": twin, "pos": "noun", "morphology": {"paradigm": "o__n", "features": {}}}
                add_entry(twin_entry)
        # Adjective -ana -> noun -a twin (for region nouns ending with -a)
        if lemma and lemma.lower().endswith("ana") and par2 == "a__adj":
            twin = lemma[:-2]
            if twin not in existing_lemmas:
                twin_entry = {**e2, "lemma": twin, "pos": "noun", "morphology": {"paradigm": "o__n", "features": {}}}
                add_entry(twin_entry)
    return out


def main(argv: Iterable[str]) -> int:
    ap = argparse.ArgumentParser(description="Infer morphology and paradigms for entries")
    ap.add_argument("--input", type=Path, default=Path(__file__).resolve().parents[1] / "work/bilingual_normalized.json")
    ap.add_argument("--out", type=Path, default=Path(__file__).resolve().parents[1] / "work/bilingual_with_morph.json")
    ap.add_argument("-v", "--verbose", action="count", default=0)
    args = ap.parse_args(list(argv))

    configure_logging(args.verbose)
    entries = read_json(args.input)
    result = infer(entries)
    write_json(args.out, result)
    logging.info("Wrote %s (%d entries)", args.out, len(result))
    return 0


if __name__ == "__main__":
    import sys
    raise SystemExit(main(sys.argv[1:]))


