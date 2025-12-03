#!/usr/bin/env python3
"""
Merge all source JSON files into unified merged files.

All sources must use the unified format. No conversion needed - direct merge.
Keeps ALL entries and ALL translations from ALL sources (no deduplication).
"""

import json
import sys
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime
from collections import defaultdict

# Import validation
sys.path.insert(0, str(Path(__file__).parent))
from validate_schema import load_schema, validate_file


def load_source_file(file_path: Path, schema: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Load and validate a source file."""
    print(f"Loading {file_path.name}...")
    
    is_valid, errors = validate_file(file_path, schema)
    if not is_valid:
        print(f"ERROR: {file_path.name} failed validation:")
        for error in errors:
            print(f"  {error}")
        sys.exit(1)
    
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    entries = data.get('entries', [])
    source_name = data.get('metadata', {}).get('source_name', file_path.stem)
    
    print(f"  ✅ Loaded {len(entries):,} entries from {source_name}")
    return entries


def merge_all_sources(sources_dir: Path, schema: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merge all source_*.json files.
    
    Returns merged data with all entries from all sources.
    """
    source_files = sorted(sources_dir.glob('source_*.json'))
    
    if not source_files:
        print(f"ERROR: No source_*.json files found in {sources_dir}")
        sys.exit(1)
    
    print(f"\n{'='*70}")
    print(f"MERGING {len(source_files)} SOURCE FILES")
    print(f"{'='*70}\n")
    
    all_entries = []
    source_stats = defaultdict(int)
    
    for source_file in source_files:
        entries = load_source_file(source_file, schema)
        all_entries.extend(entries)
        
        # Track statistics
        source_name = source_file.stem.replace('source_', '')
        source_stats[source_name] = len(entries)
    
    print(f"\n{'='*70}")
    print(f"MERGE COMPLETE")
    print(f"{'='*70}")
    print(f"Total entries: {len(all_entries):,}")
    print(f"\nPer-source breakdown:")
    for source, count in sorted(source_stats.items()):
        print(f"  {source}: {count:,} entries")
    
    # Create merged metadata
    merged_metadata = {
        "source_name": "merged",
        "version": "1.0",
        "generation_date": datetime.now().isoformat(),
        "statistics": {
            "total_entries": len(all_entries),
            "sources": dict(source_stats),
            "entries_with_translations": sum(1 for e in all_entries if e.get('translations')),
            "entries_with_morphology": sum(1 for e in all_entries if e.get('morphology', {}).get('paradigm'))
        }
    }
    
    return {
        "metadata": merged_metadata,
        "entries": all_entries
    }


def separate_bidix_monodix(merged_data: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Separate merged data into bidix (with translations) and monodix (all entries).
    
    Returns:
        (bidix_data, monodix_data)
    """
    entries = merged_data['entries']
    
    # Bidix: entries with Esperanto translations
    bidix_entries = [
        entry for entry in entries
        if any(t.get('lang') == 'eo' for t in entry.get('translations', []))
    ]
    
    # Monodix: all Ido entries (for morphological analysis)
    monodix_entries = entries
    
    bidix_metadata = {
        **merged_data['metadata'],
        "source_name": "merged_bidix",
        "statistics": {
            **merged_data['metadata']['statistics'],
            "total_entries": len(bidix_entries)
        }
    }
    
    monodix_metadata = {
        **merged_data['metadata'],
        "source_name": "merged_monodix",
        "statistics": {
            **merged_data['metadata']['statistics'],
            "total_entries": len(monodix_entries)
        }
    }
    
    return (
        {"metadata": bidix_metadata, "entries": bidix_entries},
        {"metadata": monodix_metadata, "entries": monodix_entries}
    )


def main():
    script_dir = Path(__file__).parent
    data_dir = script_dir.parent
    sources_dir = data_dir / 'sources'
    merged_dir = data_dir / 'merged'
    schema_path = data_dir / 'schema.json'
    
    if not sources_dir.exists():
        print(f"ERROR: Sources directory not found: {sources_dir}")
        sys.exit(1)
    
    if not schema_path.exists():
        print(f"ERROR: Schema not found: {schema_path}")
        sys.exit(1)
    
    schema = load_schema(schema_path)
    
    # Merge all sources
    merged_data = merge_all_sources(sources_dir, schema)
    
    # Separate into bidix and monodix
    bidix_data, monodix_data = separate_bidix_monodix(merged_data)
    
    # Save merged files
    merged_dir.mkdir(parents=True, exist_ok=True)
    
    bidix_path = merged_dir / 'merged_bidix.json'
    monodix_path = merged_dir / 'merged_monodix.json'
    
    print(f"\n{'='*70}")
    print(f"SAVING MERGED FILES")
    print(f"{'='*70}")
    
    with open(bidix_path, 'w', encoding='utf-8') as f:
        json.dump(bidix_data, f, indent=2, ensure_ascii=False)
    print(f"✅ Saved bidix: {bidix_path}")
    print(f"   Entries: {len(bidix_data['entries']):,}")
    
    with open(monodix_path, 'w', encoding='utf-8') as f:
        json.dump(monodix_data, f, indent=2, ensure_ascii=False)
    print(f"✅ Saved monodix: {monodix_path}")
    print(f"   Entries: {len(monodix_data['entries']):,}")
    
    print(f"\n{'='*70}")
    print(f"✅ MERGE COMPLETE")
    print(f"{'='*70}")


if __name__ == '__main__':
    main()

