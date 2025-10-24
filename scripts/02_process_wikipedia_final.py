#!/usr/bin/env python3
"""
Stage 2: Wikipedia Filtered JSON → Final Processing
Convert filtered JSON to final parsed/cleaned format for BIG BIDIX and MONO.
"""
import argparse
import logging
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List

from _common import read_json, write_json, configure_logging, is_valid_lemma


def process_wikipedia_entries(filtered_path: Path, out_path: Path) -> None:
    """Process filtered Wikipedia entries into final format."""
    logging.info("Stage 2: Processing filtered Wikipedia entries from %s", filtered_path)
    
    # Load filtered entries
    filtered_entries = read_json(filtered_path)
    logging.info("Loaded %d filtered Wikipedia entries", len(filtered_entries))
    
    processed_entries: List[Dict[str, Any]] = []
    stats = {
        'input_count': len(filtered_entries),
        'valid_entries': 0,
        'invalid_entries': 0,
        'by_category': {}
    }
    
    for entry in filtered_entries:
        lemma = entry.get('lemma', '')
        
        # Validate lemma
        if not is_valid_lemma(lemma):
            stats['invalid_entries'] += 1
            continue
        
        # Create processed entry
        processed_entry = {
            'id': f'io:wikipedia:{lemma}',
            'lemma': lemma,
            'pos': 'propn',  # All Wikipedia entries are proper nouns
            'language': 'io',
            'senses': [],  # No translations for proper nouns
            'morphology': {
                'paradigm': 'o__n',  # Default noun paradigm
                'features': {}
            },
            'provenance': entry.get('provenance', []),
            'metadata': {
                'source': 'wikipedia',
                'categories': entry.get('categories', []),
                'text_length': entry.get('text_length', 0),
                'has_translations': False
            }
        }
        
        processed_entries.append(processed_entry)
        stats['valid_entries'] += 1
        
        # Track by category
        categories = entry.get('categories', [])
        for category in categories:
            stats['by_category'][category] = stats['by_category'].get(category, 0) + 1
    
    # Sort by lemma
    processed_entries.sort(key=lambda x: x['lemma'].lower())
    
    # Write output
    write_json(out_path, processed_entries)
    
    # Log statistics
    logging.info("Stage 2 complete: Processed %d entries (%d valid, %d invalid)", 
                stats['input_count'], stats['valid_entries'], stats['invalid_entries'])
    
    if stats['by_category']:
        logging.info("Top categories:")
        sorted_categories = sorted(stats['by_category'].items(), key=lambda x: x[1], reverse=True)
        for category, count in sorted_categories[:10]:
            logging.info("  %s: %d entries", category, count)


def main(argv: Iterable[str]) -> int:
    ap = argparse.ArgumentParser(description="Stage 2: Process filtered Wikipedia entries to final format")
    ap.add_argument(
        "--input",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "work/io_wikipedia_filtered.json",
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "work/io_wikipedia_processed.json",
    )
    ap.add_argument("-v", "--verbose", action="count", default=0)
    args = ap.parse_args(list(argv))

    configure_logging(args.verbose)
    
    # Check if input exists
    if not args.input.exists():
        logging.error("Input file %s does not exist. Run Stage 1 first.", args.input)
        return 1
    
    # Check if output already exists (resumability)
    if args.out.exists():
        logging.info("Output file %s already exists, skipping Stage 2", args.out)
        return 0
    
    process_wikipedia_entries(args.input, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
