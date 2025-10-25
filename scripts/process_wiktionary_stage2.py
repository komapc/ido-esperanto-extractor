#!/usr/bin/env python3
"""
Stage 2: Wiktionary Filtered JSON → Final Processing
Convert filtered JSON to final parsed/cleaned format for BIG BIDIX and MONO.
"""
import argparse
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).parent))

from _common import read_json, write_json, configure_logging, is_valid_lemma, clean_lemma


def process_wiktionary_entries(filtered_path: Path, out_path: Path, source_code: str) -> None:
    """Process filtered Wiktionary entries into final format."""
    logging.info("Stage 2: Processing filtered %s Wiktionary entries from %s", source_code, filtered_path)
    
    # Load filtered entries
    filtered_data = read_json(filtered_path)
    entries = filtered_data.get('entries', [])
    metadata = filtered_data.get('metadata', {})
    
    logging.info("Loaded %d filtered Wiktionary entries", len(entries))
    
    processed_entries: List[Dict[str, Any]] = []
    stats = {
        'input_count': len(entries),
        'valid_entries': 0,
        'invalid_entries': 0,
        'cleaned_lemmas': 0,
        'with_translations': 0,
        'with_morphology': 0,
        'by_pos': {}
    }
    
    for entry in entries:
        original_lemma = entry.get('lemma', '')
        
        # Clean lemma
        cleaned_lemma = clean_lemma(original_lemma)
        if cleaned_lemma != original_lemma:
            stats['cleaned_lemmas'] += 1
        
        # Validate lemma
        if not is_valid_lemma(cleaned_lemma):
            stats['invalid_entries'] += 1
            continue
        
        # Create processed entry
        processed_entry = {
            'id': f'{source_code}:{cleaned_lemma}:{entry.get("pos", "n")}',
            'lemma': cleaned_lemma,
            'pos': entry.get('pos', 'n'),
            'language': source_code,
            'senses': entry.get('senses', []),
            'morphology': entry.get('morphology', {}),
            'provenance': entry.get('provenance', []),
            'metadata': {
                'source': f'{source_code}_wiktionary',
                'has_translations': bool(entry.get('senses')),
                'original_lemma': original_lemma if original_lemma != cleaned_lemma else None
            }
        }
        
        # Track statistics
        pos = processed_entry['pos']
        stats['by_pos'][pos] = stats['by_pos'].get(pos, 0) + 1
        
        if processed_entry['senses']:
            stats['with_translations'] += 1
        
        if processed_entry['morphology']:
            stats['with_morphology'] += 1
        
        processed_entries.append(processed_entry)
        stats['valid_entries'] += 1
    
    # Sort by lemma
    processed_entries.sort(key=lambda x: x['lemma'].lower())
    
    # Create final output
    final_data = {
        'metadata': {
            **metadata,
            'processing_stage': 'final',
            'source_code': source_code,
            'processing_stats': stats
        },
        'entries': processed_entries
    }
    
    # Write output
    write_json(out_path, final_data)
    
    # Log statistics
    logging.info("Stage 2 complete: Processed %d entries (%d valid, %d invalid)", 
                stats['input_count'], stats['valid_entries'], stats['invalid_entries'])
    logging.info("  - Cleaned lemmas: %d", stats['cleaned_lemmas'])
    logging.info("  - With translations: %d", stats['with_translations'])
    logging.info("  - With morphology: %d", stats['with_morphology'])
    
    if stats['by_pos']:
        logging.info("  - By POS:")
        for pos, count in sorted(stats['by_pos'].items(), key=lambda x: (x[0] is None, x[0])):
            logging.info("    %s: %d", pos or 'null', count)


def main(argv):
    ap = argparse.ArgumentParser(description="Stage 2: Process filtered Wiktionary entries to final format")
    ap.add_argument("--source", required=True, choices=['io', 'eo', 'fr', 'en'], 
                   help="Source language code")
    ap.add_argument("--input", type=Path, help="Input filtered JSON file")
    ap.add_argument("--output", type=Path, help="Output final JSON file")
    ap.add_argument("-v", "--verbose", action="count", default=0)
    args = ap.parse_args(list(argv))
    
    configure_logging(args.verbose)
    
    # Set default paths
    if not args.input:
        base_dir = Path(__file__).parent.parent
        args.input = base_dir / "work" / f"{args.source}_wiktionary_filtered.json"
    
    if not args.output:
        base_dir = Path(__file__).parent.parent
        args.output = base_dir / "work" / f"{args.source}_wiktionary_processed.json"
    
    # Check if input exists
    if not args.input.exists():
        logging.error("Input file %s does not exist. Run Stage 1 first.", args.input)
        return 1
    
    # Check if output already exists (resumability)
    if args.output.exists():
        logging.info("Output file %s already exists, skipping Stage 2", args.output)
        return 0
    
    process_wiktionary_entries(args.input, args.output, args.source)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
