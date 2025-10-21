#!/usr/bin/env python3
import argparse
import sys
import logging
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from _common import read_json, write_json, configure_logging, clean_lemma, is_valid_lemma


def normalize(entries: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """Normalize entries: clean lemmas, remove duplicates, filter invalid.
    
    Returns: (cleaned_entries, stats_dict)
    """
    stats = {
        'input_count': len(entries),
        'cleaned_lemmas': 0,
        'invalid_lemmas': 0,
        'duplicates_removed': 0,
        'output_count': 0
    }
    
    # First pass: Clean all lemmas and translation terms
    for e in entries:
        original_lemma = e.get("lemma") or ""
        cleaned = clean_lemma(original_lemma)
        
        if cleaned != original_lemma:
            stats['cleaned_lemmas'] += 1
            e['_original_lemma'] = original_lemma  # Keep for debugging
        
        e["lemma"] = cleaned
        
        # Also clean translation terms and filter invalid translations
        cleaned_senses = []
        for sense in e.get("senses", []):
            cleaned_translations = []
            for trans in sense.get("translations", []):
                if "term" in trans:
                    original_term = trans["term"]
                    cleaned_term = clean_lemma(str(original_term))
                    
                    # Only keep translation if it's valid after cleaning
                    if is_valid_lemma(cleaned_term):
                        trans["term"] = cleaned_term
                        cleaned_translations.append(trans)
            
            # Only keep sense if it has valid translations
            if cleaned_translations:
                sense["translations"] = cleaned_translations
                cleaned_senses.append(sense)
        
        e["senses"] = cleaned_senses
    
    # Second pass: Filter invalid lemmas and entries without translations
    valid_entries = []
    for e in entries:
        if not is_valid_lemma(e.get("lemma", "")):
            stats['invalid_lemmas'] += 1
            continue
        
        # Skip if no valid senses remain after cleaning
        if not e.get("senses"):
            stats['invalid_lemmas'] += 1
            continue
        
        valid_entries.append(e)
    
    # Third pass: Deduplicate by (lemma, pos, language, translations set)
    seen = set()
    out: List[Dict[str, Any]] = []
    for e in valid_entries:
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
            stats['duplicates_removed'] += 1
            continue
        seen.add(key)
        out.append(e)
    
    # Sort by lemma, pos, language
    out.sort(key=lambda x: (str(x.get("lemma", "")), str(x.get("pos", "")), str(x.get("language", ""))))
    
    stats['output_count'] = len(out)
    
    return out, stats


def main(argv: Iterable[str]) -> int:
    ap = argparse.ArgumentParser(description="Normalize and deduplicate bilingual entries")
    ap.add_argument("--input", type=Path, default=Path(__file__).resolve().parents[1] / "work/bilingual_raw.json")
    ap.add_argument("--out", type=Path, default=Path(__file__).resolve().parents[1] / "work/bilingual_normalized.json")
    ap.add_argument("-v", "--verbose", action="count", default=0)
    args = ap.parse_args(list(argv))

    configure_logging(args.verbose)
    entries = read_json(args.input)
    result, stats = normalize(entries)
    write_json(args.out, result)
    
    # Log statistics
    logging.info("Normalization stats:")
    logging.info("  Input entries: %d", stats['input_count'])
    logging.info("  Cleaned lemmas: %d", stats['cleaned_lemmas'])
    logging.info("  Invalid lemmas removed: %d", stats['invalid_lemmas'])
    logging.info("  Duplicates removed: %d", stats['duplicates_removed'])
    logging.info("  Output entries: %d", stats['output_count'])
    logging.info("Wrote %s (%d entries)", args.out, len(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))


