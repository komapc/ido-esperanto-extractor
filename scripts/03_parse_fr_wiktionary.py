#!/usr/bin/env python3
"""
Orthogonal Parser: French Wiktionary

Parses French Wiktionary dump and produces standardized source JSON.
This is used for pivot translations (IO→FR→EO and EO→FR→IO).

Input:  dumps/frwiktionary-latest-pages-articles.xml.bz2
Output: sources/source_fr_wiktionary.json

Structure:
{
  "metadata": {...},
  "entries": [
    {
      "lemma": "cheval",
      "pos": "noun",
      "translations": {"io": ["kavalo"], "eo": ["ĉevalo"]},
      "source_page": "https://fr.wiktionary.org/wiki/cheval"
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
    
    For French Wiktionary, we want translations to both IO and EO (pivot data).
    
    Old format: List of entries with structure:
      [{lemma, pos, language, senses: [{translations: [{lang, term}]}]}, ...]
    
    New format: {"metadata": {...}, "entries": [...]}
    """
    # Create metadata
    metadata = create_metadata(
        source_name="fr_wiktionary",
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
                        
                        # Only keep IO and EO translations (pivot data)
                        if lang in ['io', 'eo'] and term:
                            if lang not in translations:
                                translations[lang] = []
                            if term not in translations[lang]:
                                translations[lang].append(term)
        
        # Skip entries with no IO or EO translations
        if not translations:
            continue
        
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
            "source_page": f"https://fr.wiktionary.org/wiki/{lemma}"
        }
        
        # Remove empty/null fields
        if not entry['pos']:
            del entry['pos']
        if not entry['morphology']:
            del entry['morphology']
        
        entries.append(entry)
    
    # Update metadata statistics
    update_statistics(metadata, len(entries), with_translations, with_morphology)
    
    return {
        "metadata": metadata,
        "entries": entries
    }


def main(argv):
    ap = argparse.ArgumentParser(description="Parse French Wiktionary (Orthogonal)")
    ap.add_argument(
        "--dump",
        type=Path,
        help="Path to Wiktionary dump file"
    )
    ap.add_argument(
        "--output",
        type=Path,
        default=Path("sources/source_fr_wiktionary.json"),
        help="Output path for standardized JSON"
    )
    ap.add_argument("--limit", type=int, help="Limit number of pages to parse (for testing)")
    ap.add_argument("--progress-every", type=int, default=5000)
    ap.add_argument("-v", "--verbose", action="count", default=0)
    args = ap.parse_args(list(argv))
    
    configure_logging(args.verbose)
    
    # Find dump file
    if args.dump:
        dump_file = args.dump
    else:
        # Look in dumps/ directory
        dumps_dir = Path(__file__).parent.parent / "dumps"
        candidates = list(dumps_dir.glob("frwiktionary-*.xml.bz2"))
        if not candidates:
            # Fallback to old location
            dump_file = Path(__file__).parent.parent / "data" / "raw" / "frwiktionary-latest-pages-articles.xml.bz2"
        else:
            # Use most recent
            dump_file = max(candidates, key=lambda p: p.stat().st_mtime)
    
    if not dump_file.exists():
        print(f"❌ Error: Dump file not found: {dump_file}")
        print(f"   Run: ./scripts/download_dumps.sh")
        print(f"   Note: French Wiktionary is OPTIONAL and can be skipped")
        return 1
    
    print(f"📖 Parsing French Wiktionary (Pivot data)")
    print(f"   Input: {dump_file}")
    print(f"   Size: {get_file_size_mb(dump_file):.1f} MB")
    print(f"   Output: {args.output}")
    print(f"   Note: Extracting only IO and EO translations for pivot mapping")
    
    # Use existing parser - we need to run it twice to get both IO and EO translations
    import tempfile
    
    try:
        # Parse for IO translations
        print(f"\n📖 Pass 1: Extracting IO translations...")
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp:
            temp_output_io = Path(tmp.name)
        
        cfg_io = ParserConfig(source_code="fr", target_code="io")
        parse_wiktionary(dump_file, cfg_io, temp_output_io, args.limit, progress_every=args.progress_every)
        
        # Parse for EO translations
        print(f"\n📖 Pass 2: Extracting EO translations...")
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp:
            temp_output_eo = Path(tmp.name)
        
        cfg_eo = ParserConfig(source_code="fr", target_code="eo")
        parse_wiktionary(dump_file, cfg_eo, temp_output_eo, args.limit, progress_every=args.progress_every)
        
        # Load both outputs
        with open(temp_output_io, 'r', encoding='utf-8') as f:
            data_io = json.load(f)
        with open(temp_output_eo, 'r', encoding='utf-8') as f:
            data_eo = json.load(f)
        
        # Merge the two datasets
        print(f"\n📦 Merging IO and EO translations...")
        
        # Create a combined dataset
        combined_entries = {}
        
        # Handle list or dict format
        if isinstance(data_io, dict):
            entries_io = data_io.get('words', data_io.get('entries', []))
        else:
            entries_io = data_io
        
        if isinstance(data_eo, dict):
            entries_eo = data_eo.get('words', data_eo.get('entries', []))
        else:
            entries_eo = data_eo
        
        # Add IO translations
        for entry in entries_io:
            lemma = entry.get('lemma', '').strip()
            if lemma:
                combined_entries[lemma] = entry
        
        # Add EO translations to existing entries
        for entry in entries_eo:
            lemma = entry.get('lemma', '').strip()
            if not lemma:
                continue
            
            if lemma in combined_entries:
                # Merge EO translations into existing entry
                if 'senses' in entry:
                    if 'senses' not in combined_entries[lemma]:
                        combined_entries[lemma]['senses'] = []
                    combined_entries[lemma]['senses'].extend(entry['senses'])
            else:
                # New entry with only EO translations
                combined_entries[lemma] = entry
        
        combined_data = list(combined_entries.values())
        
        # Convert to standardized format
        print(f"📦 Converting to standardized format...")
        standardized_data = convert_to_standardized_format(
            combined_data, 
            dump_file,
            Path(__file__)
        )
        
        # Save standardized output
        save_json(standardized_data, args.output)
        
        # Print statistics
        stats = standardized_data['metadata']['statistics']
        print(f"\n✅ Parsing complete!")
        print(f"   Total entries with IO/EO: {stats['total_entries']:,}")
        print(f"   With translations: {stats['with_translations']:,}")
        print(f"   With morphology: {stats['with_morphology']:,}")
        print(f"   Output size: {get_file_size_mb(args.output):.1f} MB")
        
    finally:
        # Clean up temp files
        if 'temp_output_io' in locals() and temp_output_io.exists():
            temp_output_io.unlink()
        if 'temp_output_eo' in locals() and temp_output_eo.exists():
            temp_output_eo.unlink()
    
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

