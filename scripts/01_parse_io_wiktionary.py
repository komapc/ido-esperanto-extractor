#!/usr/bin/env python3
"""
Orthogonal Parser: Ido Wiktionary

Parses Ido Wiktionary dump and produces standardized source JSON.

Input:  dumps/iowiktionary-latest-pages-articles.xml.bz2
Output: sources/source_io_wiktionary.json

Structure:
{
  "metadata": {...},
  "entries": [
    {
      "lemma": "vorto",
      "pos": "noun",
      "translations": {"eo": ["vorto"]},
      "morphology": {"paradigm": "o__n"},
      "source_page": "https://io.wiktionary.org/wiki/vorto"
    }
  ]
}
"""

import argparse
import sys
import re
import json
from pathlib import Path
from datetime import datetime

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent))

from _common import configure_logging
from wiktionary_parser import ParserConfig, parse_wiktionary
from utils.json_utils import save_json, get_file_size_mb
from utils.metadata import create_metadata, update_statistics


def convert_to_standardized_format(old_format_data, dump_file, script_path):
    """
    Convert from wiktionary_parser output to standardized format.
    
    Old format: List of entries with structure:
      [{lemma, pos, language, senses: [{translations: [{lang, term}]}]}, ...]
    
    New format: {"metadata": {...}, "entries": [...]}
    """
    # Create metadata
    metadata = create_metadata(
        source_name="io_wiktionary",
        dump_file=dump_file,
        script_path=script_path,
        version="2.0"
    )
    
    # Handle both list and dict formats
    if isinstance(old_format_data, dict):
        # If it's a dict, it might have 'words' key
        entries_list = old_format_data.get('words', old_format_data.get('entries', []))
    else:
        # It's already a list
        entries_list = old_format_data
    
    # Convert entries to standardized format
    entries = []
    total_entries = 0
    with_translations = 0
    with_morphology = 0
    
    for entry_data in entries_list:
        lemma = entry_data.get('lemma', '').strip()
        if not lemma:
            continue
        
        total_entries += 1
        
        # Extract translations from senses
        translations = {}
        if 'senses' in entry_data:
            for sense in entry_data['senses']:
                if 'translations' in sense:
                    for trans in sense['translations']:
                        lang = trans.get('lang', '')
                        term = trans.get('term', '').strip()
                        
                        # Clean up term (remove markup)
                        if term:
                            # Remove Wiktionary categories and markup
                            term = re.sub(r'\s*Kategorio:.*$', '', term)
                            term = re.sub(r'\s*\[\[.*?\]\]', '', term)
                            term = term.strip()
                        
                        if lang and term:
                            if lang not in translations:
                                translations[lang] = []
                            if term not in translations[lang]:
                                translations[lang].append(term)
        
        if translations:
            with_translations += 1
        
        # Extract morphology
        morphology = {}
        if 'morphology' in entry_data and entry_data['morphology']:
            morph_data = entry_data['morphology']
            if isinstance(morph_data, dict) and morph_data.get('paradigm'):
                morphology = {"paradigm": morph_data['paradigm']}
                with_morphology += 1
        
        # Create standardized entry
        entry = {
            "lemma": lemma,
            "pos": entry_data.get('pos'),
            "translations": translations,
            "morphology": morphology,
            "source_page": f"https://io.wiktionary.org/wiki/{lemma}"
        }
        
        # Remove empty/null fields
        if not entry['pos']:
            del entry['pos']
        if not entry['translations']:
            del entry['translations']
        if not entry['morphology']:
            del entry['morphology']
        
        entries.append(entry)
    
    # Update metadata statistics
    update_statistics(metadata, total_entries, with_translations, with_morphology)
    
    return {
        "metadata": metadata,
        "entries": entries
    }


def main(argv):
    ap = argparse.ArgumentParser(description="Parse Ido Wiktionary (Orthogonal)")
    ap.add_argument(
        "--dump",
        type=Path,
        help="Path to Wiktionary dump file"
    )
    ap.add_argument(
        "--output",
        type=Path,
        default=Path("sources/source_io_wiktionary.json"),
        help="Output path for standardized JSON"
    )
    ap.add_argument("--limit", type=int, help="Limit number of pages to parse (for testing)")
    ap.add_argument("--progress-every", type=int, default=1000)
    ap.add_argument("-v", "--verbose", action="count", default=0)
    args = ap.parse_args(list(argv))
    
    configure_logging(args.verbose)
    
    # Find dump file
    if args.dump:
        dump_file = args.dump
    else:
        # Look in dumps/ directory
        dumps_dir = Path(__file__).parent.parent / "dumps"
        candidates = list(dumps_dir.glob("iowiktionary-*.xml.bz2"))
        if not candidates:
            # Fallback to old location
            dump_file = Path(__file__).parent.parent / "data" / "iowiktionary-latest-pages-articles.xml.bz2"
        else:
            # Use most recent
            dump_file = max(candidates, key=lambda p: p.stat().st_mtime)
    
    if not dump_file.exists():
        print(f"❌ Error: Dump file not found: {dump_file}")
        print(f"   Run: ./scripts/00_download_dumps.sh")
        return 1
    
    print(f"📖 Parsing Ido Wiktionary")
    print(f"   Input: {dump_file}")
    print(f"   Size: {get_file_size_mb(dump_file):.1f} MB")
    print(f"   Output: {args.output}")
    
    # Use existing parser
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp:
        temp_output = Path(tmp.name)
    
    try:
        # Parse using existing logic with optimizations
        cfg = ParserConfig(source_code="io", target_code="eo")
        # OPTIMIZATION: Skip EN/FR extraction (15-20% speedup for orthogonal pipeline)
        parse_wiktionary(dump_file, cfg, temp_output, args.limit, 
                        progress_every=args.progress_every, skip_pivot=True)
        
        # Load old format
        import json
        with open(temp_output, 'r', encoding='utf-8') as f:
            old_data = json.load(f)
        
        # Convert to standardized format
        print(f"\n📦 Converting to standardized format...")
        standardized_data = convert_to_standardized_format(
            old_data, 
            dump_file,
            Path(__file__)
        )
        
        # Save standardized output
        save_json(standardized_data, args.output)
        
        # Print statistics
        stats = standardized_data['metadata']['statistics']
        print(f"\n✅ Parsing complete!")
        print(f"   Total entries: {stats['total_entries']:,}")
        print(f"   With EO translations: {stats['with_translations']:,}")
        print(f"   With morphology: {stats['with_morphology']:,}")
        print(f"   Output size: {get_file_size_mb(args.output):.1f} MB")
        
    finally:
        # Clean up temp file
        if temp_output.exists():
            temp_output.unlink()
    
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

