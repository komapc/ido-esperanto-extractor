#!/usr/bin/env python3
"""
Stage 1: Wiktionary XML → Filtered JSON
Convert zipped XML dump to filtered JSON with basic parsing and relevance filtering.
"""
import argparse
import logging
import sys
from pathlib import Path
from typing import Dict, Any, List

sys.path.insert(0, str(Path(__file__).parent))

from _common import configure_logging
from wiktionary_parser import ParserConfig
from utils.parser_base import parse_wiktionary_wrapper, find_dump_file, convert_wiktionary_to_standardized


def filter_wiktionary_entries(entries: List[Dict[str, Any]], source_code: str) -> List[Dict[str, Any]]:
    """Filter Wiktionary entries for relevance and quality."""
    filtered_entries = []
    stats = {
        'total': len(entries),
        'has_translations': 0,
        'has_morphology': 0,
        'valid_lemma': 0,
        'filtered': 0
    }
    
    for entry in entries:
        lemma = entry.get('lemma', '').strip()
        
        # Basic validation
        if not lemma or len(lemma) < 2:
            continue
        
        # Check if entry has translations (for bilingual dictionary)
        has_translations = False
        for sense in entry.get('senses', []):
            if sense.get('translations'):
                has_translations = True
                break
        
        # Check if entry has morphology information
        has_morphology = bool(entry.get('morphology', {}).get('paradigm'))
        
        # For monolingual dictionary, we want entries even without translations
        # For bilingual dictionary, we need translations
        is_relevant = True
        
        # Skip entries that are clearly not dictionary words
        if any(char in lemma for char in ['/', '\\', ':', '|', '{', '}']):
            is_relevant = False
        
        # Skip very long lemmas (likely not real words)
        if len(lemma) > 50:
            is_relevant = False
        
        # Skip entries that look like templates or categories
        if lemma.startswith('Template:') or lemma.startswith('Category:'):
            is_relevant = False
        
        if is_relevant:
            filtered_entries.append(entry)
            stats['filtered'] += 1
            
            if has_translations:
                stats['has_translations'] += 1
            if has_morphology:
                stats['has_morphology'] += 1
            if lemma:
                stats['valid_lemma'] += 1
    
    logging.info("Filtering stats: %d/%d entries kept (%.1f%%)", 
                stats['filtered'], stats['total'], 
                (stats['filtered'] / stats['total'] * 100) if stats['total'] > 0 else 0)
    logging.info("  - With translations: %d", stats['has_translations'])
    logging.info("  - With morphology: %d", stats['has_morphology'])
    logging.info("  - Valid lemmas: %d", stats['valid_lemma'])
    
    return filtered_entries


def extract_filtered_wiktionary(dump_path: Path, output_path: Path, source_code: str, target_code: str, 
                               limit: int = None, progress_every: int = 1000) -> None:
    """Extract and filter Wiktionary entries from XML dump."""
    logging.info("Stage 1: Extracting filtered %s Wiktionary from %s", source_code, dump_path)
    
    # Check if output already exists (resumability)
    if output_path.exists():
        logging.info("Output file %s already exists, skipping Stage 1", output_path)
        return
    
    # Parse Wiktionary using existing parser
    cfg = ParserConfig(source_code=source_code, target_code=target_code)
    
    # Create temporary file for raw output
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
        temp_path = Path(temp_file.name)
    
    try:
        # Parse to temporary file
        result = parse_wiktionary_wrapper(
            dump_path, cfg, temp_path, 
            argparse.Namespace(limit=limit, progress_every=progress_every, verbose=1),
            f"{source_code}_wiktionary",
            f"https://{source_code}.wiktionary.org/wiki/",
            dump_path
        )
        
        if result != 0:
            raise RuntimeError(f"Wiktionary parsing failed with exit code {result}")
        
        # Load parsed data
        from _common import read_json
        raw_data = read_json(temp_path)
        
        # Convert to standardized format
        standardized_data = convert_wiktionary_to_standardized(
            raw_data, 
            f"{source_code}_wiktionary",
            f"https://{source_code}.wiktionary.org/wiki/",
            dump_path,
            Path(__file__)
        )
        
        # Filter entries
        filtered_entries = filter_wiktionary_entries(standardized_data['entries'], source_code)
        
        # Create filtered output
        filtered_data = {
            'metadata': standardized_data['metadata'],
            'entries': filtered_entries,
            'filtering_stats': {
                'original_count': len(standardized_data['entries']),
                'filtered_count': len(filtered_entries),
                'retention_rate': len(filtered_entries) / len(standardized_data['entries']) if standardized_data['entries'] else 0
            }
        }
        
        # Write filtered output
        from _common import write_json
        write_json(output_path, filtered_data)
        
        logging.info("Stage 1 complete: Wrote %s (%d filtered entries from %d total)", 
                    output_path, len(filtered_entries), len(standardized_data['entries']))
        
    finally:
        # Clean up temporary file
        if temp_path.exists():
            temp_path.unlink()


def main(argv):
    ap = argparse.ArgumentParser(description="Stage 1: Extract filtered Wiktionary entries")
    ap.add_argument("--source", required=True, choices=['io', 'eo', 'fr', 'en'], 
                   help="Source language code")
    ap.add_argument("--target", default="eo", help="Target language code")
    ap.add_argument("--dump", type=Path, help="Path to Wiktionary dump file")
    ap.add_argument("--output", type=Path, help="Output path for filtered JSON")
    ap.add_argument("--limit", type=int, help="Limit number of pages to parse (for testing)")
    ap.add_argument("--progress-every", type=int, default=1000)
    ap.add_argument("-v", "--verbose", action="count", default=0)
    args = ap.parse_args(list(argv))
    
    configure_logging(args.verbose)
    
    # Set default output path
    if not args.output:
        base_dir = Path(__file__).parent.parent
        args.output = base_dir / "work" / f"{args.source}_wiktionary_filtered.json"
    
    # Find dump file
    if not args.dump:
        base_dir = Path(__file__).parent.parent
        dump_pattern = f"{args.source}wiktionary-*.xml.bz2"
        dumps_dir = base_dir / "dumps"
        fallback_paths = [
            base_dir / "data" / "raw"
        ]
        args.dump = find_dump_file(dump_pattern, dumps_dir, fallback_paths)
    
    if not args.dump or not args.dump.exists():
        logging.error("Dump file not found for %s Wiktionary", args.source)
        logging.error("Run: ./scripts/download_dumps.sh")
        return 1
    
    extract_filtered_wiktionary(
        args.dump, args.output, args.source, args.target, 
        args.limit, args.progress_every
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
