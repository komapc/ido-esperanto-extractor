#!/usr/bin/env python3
"""
Orthogonal Merge Script

Auto-discovers all source JSON files and merges them into final outputs:
- output/BIG_BIDIX.json - For Apertium (all IO→EO translations)
- output/MONO_IDO.json - Monolingual Ido dictionary
- output/vortaro.json - Optimized for vortaro website
- output/metadata.json - Pipeline metadata

Key Features:
- Auto-discovers sources/*.json files
- Multi-source provenance tracking
- Conflict resolution with source priority
- Deterministic merge (same inputs → same output)
"""

import argparse
import sys
import json
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from typing import Dict, List, Set

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent))

from _common import configure_logging
from utils.json_utils import save_json, load_json, validate_source_json
from utils.metadata import create_merge_metadata


# Source priority (higher = more trusted)
SOURCE_PRIORITY = {
    'io_wiktionary': 100,
    'eo_wiktionary': 90,
    'io_wikipedia': 50,
    'fr_wiktionary': 30,
    'en_wiktionary': 20,
}


def discover_sources(sources_dir='sources'):
    """Auto-discover all source JSON files."""
    sources_path = Path(sources_dir)
    if not sources_path.exists():
        print(f"⚠️  Sources directory not found: {sources_dir}")
        return []
    
    source_files = list(sources_path.glob('source_*.json'))
    source_files.sort()  # Deterministic order
    
    return source_files


def load_and_validate_source(source_file):
    """Load a source file and validate its structure."""
    try:
        data = load_json(source_file)
        validate_source_json(data)
        return data
    except Exception as e:
        print(f"⚠️  Warning: Could not load {source_file.name}: {e}")
        return None


def merge_sources(sources_data):
    """
    Merge multiple sources into unified dictionary.
    
    Returns:
        dict: {lemma: {translations: {...}, sources: [...], morphology: {...}}}
    """
    print(f"\n🔄 Merging {len(sources_data)} sources...")
    
    merged = {}
    stats = defaultdict(int)
    
    for source_data in sources_data:
        source_name = source_data['metadata']['source_name']
        entries = source_data['entries']
        
        print(f"   Processing {source_name}: {len(entries):,} entries...")
        
        for entry in entries:
            lemma = entry['lemma']
            
            # Initialize lemma if new
            if lemma not in merged:
                merged[lemma] = {
                    'lemma': lemma,
                    'translations': {},
                    'sources': [],
                    'morphology': {},
                    'pos': None
                }
            
            # Add source
            if source_name not in merged[lemma]['sources']:
                merged[lemma]['sources'].append(source_name)
            
            # Merge translations
            if 'translations' in entry:
                for lang, terms in entry['translations'].items():
                    if lang not in merged[lemma]['translations']:
                        merged[lemma]['translations'][lang] = []
                    
                    # Add new translations
                    for term in terms:
                        if term not in merged[lemma]['translations'][lang]:
                            merged[lemma]['translations'][lang].append(term)
            
            # Merge morphology (prefer higher priority source)
            if 'morphology' in entry and entry['morphology']:
                current_priority = SOURCE_PRIORITY.get(source_name, 0)
                
                # If we don't have morphology yet, or this source has higher priority
                if not merged[lemma]['morphology']:
                    merged[lemma]['morphology'] = entry['morphology']
                else:
                    # Check if current source has higher priority
                    existing_sources = merged[lemma]['sources']
                    max_existing_priority = max(
                        (SOURCE_PRIORITY.get(s, 0) for s in existing_sources if s != source_name),
                        default=0
                    )
                    if current_priority > max_existing_priority:
                        merged[lemma]['morphology'] = entry['morphology']
            
            # Set POS (prefer non-null values from higher priority sources)
            if 'pos' in entry and entry['pos']:
                if not merged[lemma]['pos']:
                    merged[lemma]['pos'] = entry['pos']
            
            stats[source_name] += 1
    
    print(f"\n📊 Merge statistics:")
    print(f"   Total unique lemmas: {len(merged):,}")
    for source, count in sorted(stats.items(), key=lambda x: x[1], reverse=True):
        print(f"   {source:20s}: {count:,} entries")
    
    return merged


def create_big_bidix(merged_dict):
    """
    Create BIG BIDIX: All IO→EO translations with full provenance.
    
    Format: List of entries, one per IO lemma, with all EO translations and sources.
    """
    print(f"\n📚 Creating BIG_BIDIX...")
    
    bidix_entries = []
    
    for lemma, data in sorted(merged_dict.items()):
        # Only include entries with EO translations
        if 'eo' not in data['translations']:
            continue
        
        entry = {
            'lemma': lemma,
            'pos': data.get('pos'),
            'eo_translations': data['translations']['eo'],
            'sources': data['sources'],
            'morphology': data.get('morphology', {})
        }
        
        # Clean up empty fields
        if not entry['pos']:
            del entry['pos']
        if not entry['morphology']:
            del entry['morphology']
        
        bidix_entries.append(entry)
    
    print(f"   BIG_BIDIX entries: {len(bidix_entries):,}")
    
    return bidix_entries


def create_mono_ido(merged_dict):
    """
    Create monolingual Ido dictionary.
    
    Format: All Ido lemmas with morphology, sources, and ALL translations (not just EO).
    """
    print(f"\n📖 Creating MONO_IDO...")
    
    mono_entries = []
    
    for lemma, data in sorted(merged_dict.items()):
        entry = {
            'lemma': lemma,
            'pos': data.get('pos'),
            'translations': data['translations'],
            'sources': data['sources'],
            'morphology': data.get('morphology', {})
        }
        
        # Clean up empty fields
        if not entry['pos']:
            del entry['pos']
        if not entry['morphology']:
            del entry['morphology']
        
        mono_entries.append(entry)
    
    print(f"   MONO_IDO entries: {len(mono_entries):,}")
    
    return mono_entries


def create_vortaro(merged_dict):
    """
    Create vortaro.json optimized for the dictionary website.
    
    Format: Simplified, flat structure optimized for fast client-side loading.
    Structure: {
        "metadata": {...},
        "word1": {
            "esperanto_words": ["..."],
            "sources": ["..."],
            "morfologio": ["..."]
        },
        ...
    }
    """
    print(f"\n🌐 Creating vortaro.json...")
    
    vortaro = {}
    
    for lemma, data in merged_dict.items():
        # Only include entries with EO translations
        if 'eo' not in data['translations']:
            continue
        
        # Map source names to badges
        source_badges = []
        for source in data['sources']:
            if 'io_wiktionary' in source:
                source_badges.append('IO')
            elif 'eo_wiktionary' in source:
                source_badges.append('EO')
            elif 'fr_wiktionary' in source:
                source_badges.append('FR')
            elif 'io_wikipedia' in source:
                source_badges.append('WIKI')
        
        # Create vortaro entry
        vortaro[lemma] = {
            'esperanto_words': data['translations']['eo'],
            'sources': source_badges,
            'morfologio': []
        }
        
        # Add morphology/POS if available
        if data.get('morphology') and data['morphology'].get('paradigm'):
            vortaro[lemma]['morfologio'].append(data['morphology']['paradigm'])
        elif data.get('pos'):
            vortaro[lemma]['morfologio'].append(data['pos'])
    
    print(f"   Vortaro entries: {len(vortaro):,}")
    
    return vortaro


def main(argv):
    ap = argparse.ArgumentParser(description="Merge all sources into final outputs (Orthogonal)")
    ap.add_argument(
        "--sources-dir",
        type=Path,
        default=Path("sources"),
        help="Directory containing source_*.json files"
    )
    ap.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output"),
        help="Output directory for merged files"
    )
    ap.add_argument("-v", "--verbose", action="count", default=0)
    args = ap.parse_args(list(argv))
    
    configure_logging(args.verbose)
    
    print("=" * 70)
    print("🔄 ORTHOGONAL MERGE - Auto-discovering and merging sources")
    print("=" * 70)
    
    # Discover sources
    print(f"\n📂 Discovering sources in {args.sources_dir}...")
    source_files = discover_sources(args.sources_dir)
    
    if not source_files:
        print(f"❌ No source files found in {args.sources_dir}/")
        print(f"   Run parsers first (01_parse_*.py, 02_parse_*.py, etc.)")
        return 1
    
    print(f"   Found {len(source_files)} source file(s):")
    for sf in source_files:
        print(f"      - {sf.name}")
    
    # Load and validate sources
    print(f"\n📖 Loading sources...")
    sources_data = []
    for source_file in source_files:
        data = load_and_validate_source(source_file)
        if data:
            source_name = data['metadata']['source_name']
            entry_count = data['metadata']['statistics']['total_entries']
            print(f"   ✅ {source_name:20s}: {entry_count:,} entries")
            sources_data.append(data)
    
    if not sources_data:
        print(f"❌ No valid sources loaded")
        return 1
    
    # Merge sources
    merged_dict = merge_sources(sources_data)
    
    # Create outputs
    args.output_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. BIG_BIDIX.json
    bidix = create_big_bidix(merged_dict)
    bidix_path = args.output_dir / "BIG_BIDIX.json"
    save_json({'entries': bidix}, bidix_path)
    print(f"   ✅ Saved: {bidix_path}")
    
    # 2. MONO_IDO.json
    mono = create_mono_ido(merged_dict)
    mono_path = args.output_dir / "MONO_IDO.json"
    save_json({'entries': mono}, mono_path)
    print(f"   ✅ Saved: {mono_path}")
    
    # 3. vortaro.json
    vortaro = create_vortaro(merged_dict)
    
    # Add metadata to vortaro
    vortaro_metadata = {
        'creation_date': datetime.now().isoformat(),
        'total_words': len(vortaro),
        'sources': [s['metadata']['source_name'] for s in sources_data],
        'version': '2.0-orthogonal'
    }
    
    vortaro_output = {'metadata': vortaro_metadata}
    vortaro_output.update(vortaro)
    
    vortaro_path = args.output_dir / "vortaro.json"
    save_json(vortaro_output, vortaro_path)
    print(f"   ✅ Saved: {vortaro_path}")
    
    # 4. metadata.json
    source_stats = {s['metadata']['source_name']: s['metadata']['statistics']['total_entries'] 
                    for s in sources_data}
    
    metadata = create_merge_metadata(
        source_files=[str(sf) for sf in source_files],
        total_words=len(merged_dict),
        source_stats=source_stats
    )
    
    metadata_path = args.output_dir / "metadata.json"
    save_json(metadata, metadata_path)
    print(f"   ✅ Saved: {metadata_path}")
    
    # Final summary
    print("\n" + "=" * 70)
    print("✅ MERGE COMPLETE!")
    print("=" * 70)
    print(f"\n📊 Output Summary:")
    print(f"   BIG_BIDIX.json : {len(bidix):,} IO→EO translations")
    print(f"   MONO_IDO.json  : {len(mono):,} Ido lemmas")
    print(f"   vortaro.json   : {len(vortaro):,} website entries")
    print(f"   metadata.json  : Pipeline metadata")
    
    print(f"\n📂 Output directory: {args.output_dir}/")
    
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

