#!/usr/bin/env python3
"""
Convert old pipeline pivot data to standardized source format.

Instead of re-parsing FR/EN Wiktionary (hours), use already-processed pivot data.
"""

import json
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))
from utils.json_utils import save_json

def convert_pivot_to_source(pivot_file, source_name, output_file):
    """Convert old pivot format to standardized source format."""
    
    print(f"📦 Converting {pivot_file.name} to standardized format...")
    
    # Load old pivot data
    with open(pivot_file, 'r') as f:
        old_data = json.load(f)
    
    print(f"   Loaded {len(old_data):,} entries")
    
    # Create metadata
    metadata = {
        "source_name": source_name,
        "file_type": "source_json",
        "origin": {
            "dump_file": f"Converted from {pivot_file.name}",
            "dump_date": "2025-10-21",
            "note": "Pre-processed pivot data from old pipeline"
        },
        "extraction": {
            "date": datetime.now().isoformat(),
            "script": str(Path(__file__)),
            "version": "2.0-converted"
        },
        "statistics": {
            "total_entries": 0,
            "with_translations": 0,
            "with_morphology": 0
        }
    }
    
    # Convert entries
    entries = []
    for old_entry in old_data:
        lemma = old_entry.get('lemma', '').strip()
        if not lemma:
            continue
        
        # Extract translations
        translations = {}
        if 'senses' in old_entry:
            for sense in old_entry['senses']:
                if 'translations' in sense:
                    for trans in sense['translations']:
                        lang = trans.get('lang', '')
                        term = trans.get('term', '').strip()
                        
                        if lang and term:
                            if lang not in translations:
                                translations[lang] = []
                            if term not in translations[lang]:
                                translations[lang].append(term)
        
        if not translations:
            continue
        
        # Create standardized entry
        entry = {
            "lemma": lemma,
            "pos": old_entry.get('pos'),
            "translations": translations,
            "source_page": f"Pivot: {source_name}"
        }
        
        # Remove empty fields
        if not entry['pos']:
            del entry['pos']
        
        entries.append(entry)
    
    # Update metadata
    metadata['statistics'] = {
        "total_entries": len(entries),
        "with_translations": len(entries),
        "with_morphology": 0
    }
    
    # Create output
    output = {
        "metadata": metadata,
        "entries": entries
    }
    
    # Save
    save_json(output, output_file)
    
    print(f"   ✅ Converted {len(entries):,} entries")
    print(f"   ✅ Saved: {output_file}")
    
    return len(entries)

if __name__ == '__main__':
    base_dir = Path(__file__).parent.parent
    
    # Convert FR pivot
    fr_count = convert_pivot_to_source(
        base_dir / 'work/bilingual_pivot_fr.json',
        'fr_pivot',
        base_dir / 'sources/source_fr_pivot.json'
    )
    
    # Convert EN pivot
    en_count = convert_pivot_to_source(
        base_dir / 'work/bilingual_pivot_en.json',
        'en_pivot',
        base_dir / 'sources/source_en_pivot.json'
    )
    
    print()
    print(f"✅ Conversion complete!")
    print(f"   FR pivot: {fr_count:,} entries")
    print(f"   EN pivot: {en_count:,} entries")
    print(f"   Total: {fr_count + en_count:,} pivot entries")

