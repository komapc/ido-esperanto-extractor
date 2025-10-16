#!/usr/bin/env python3
"""
Normalize Wikipedia vocabulary to lowercase and merge.

CRITICAL FIX: Wikipedia titles are capitalized, but dictionary should use lowercase
(except for true proper nouns that are ALWAYS capitalized).
"""

import json
import shutil
from datetime import datetime
from collections import defaultdict


def should_keep_capitalized(entry: dict) -> bool:
    """
    Determine if entry should remain capitalized (true proper noun).
    
    True proper nouns (always capitalized):
    - People names: "Alfred Nobel"
    - Place names: "Stockholm", "Acapulco"
    - Organizations: "UNESCO"
    
    Common vocabulary (should be lowercase):
    - Regular nouns: "aborto", "acensilo"
    - Adjectives: "abstrakta"
    - Verbs: "acelerar"
    """
    ido_word = entry['ido_word']
    pos = entry.get('part_of_speech', 'n')
    
    # If tagged as proper noun, keep capitalized
    if pos == 'np':
        return True
    
    # Otherwise, should be lowercase
    return False


def normalize_entry(entry: dict) -> dict:
    """Normalize entry capitalization."""
    
    if should_keep_capitalized(entry):
        # Keep as-is (proper noun)
        return entry
    
    # Normalize to lowercase
    normalized = entry.copy()
    normalized['ido_word'] = entry['ido_word'][0].lower() + entry['ido_word'][1:]  if len(entry['ido_word']) > 0 else entry['ido_word']
    
    # Update morfologio to lowercase
    if 'morfologio' in normalized and normalized['morfologio']:
        root = normalized['morfologio'][0]
        normalized['morfologio'][0] = root[0].lower() + root[1:] if len(root) > 0 else root
    
    return normalized


def full_merge_normalized():
    """Execute full merge with normalization."""
    
    print("="*70)
    print("NORMALIZED WIKIPEDIA VOCABULARY MERGE")
    print("="*70)
    print()
    
    # Backup
    print("Step 1: Backing up...")
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    shutil.copy('dictionary_merged.json', f'dictionary_merged_backup_{timestamp}.json')
    print(f"  ✓ Backup: dictionary_merged_backup_{timestamp}.json")
    print()
    
    # Load
    print("Step 2: Loading dictionaries...")
    with open('dictionary_merged.json', 'r', encoding='utf-8') as f:
        current = json.load(f)
    
    with open('wikipedia_vocabulary_merge_ready.json', 'r', encoding='utf-8') as f:
        wikipedia = json.load(f)
    
    print(f"  Current: {len(current['words']):,} entries")
    print(f"  Wikipedia: {len(wikipedia['words']):,} entries")
    print()
    
    # Normalize Wikipedia entries
    print("Step 3: Normalizing capitalization...")
    normalized_count = 0
    kept_capital_count = 0
    
    for i, entry in enumerate(wikipedia['words']):
        if should_keep_capitalized(entry):
            kept_capital_count += 1
        else:
            wikipedia['words'][i] = normalize_entry(entry)
            normalized_count += 1
    
    print(f"  Normalized to lowercase: {normalized_count:,}")
    print(f"  Kept capitalized (np):   {kept_capital_count:,}")
    print()
    
    # Merge
    print("Step 4: Merging...")
    stats = {
        'added': 0,
        'skipped': 0,
        'by_pos': defaultdict(int),
    }
    
    # Create lookup
    existing = {e['ido_word'].lower(): e for e in current['words']}
    
    added_entries = []
    
    for entry in wikipedia['words']:
        key = entry['ido_word'].lower()
        
        if key in existing:
            stats['skipped'] += 1
            continue
        
        stats['added'] += 1
        pos = entry.get('part_of_speech', 'unknown')
        stats['by_pos'][pos] += 1
        
        added_entries.append(entry)
        current['words'].append(entry)
        
        if stats['added'] % 500 == 0:
            print(f"  Added {stats['added']:,} entries...")
    
    print(f"  ✓ Added {stats['added']:,} entries")
    print()
    
    # Sort
    print("Step 5: Sorting alphabetically...")
    current['words'].sort(key=lambda x: x['ido_word'].lower())
    print("  ✓ Sorted")
    print()
    
    # Save
    print("Step 6: Saving...")
    current['metadata']['last_updated'] = datetime.now().isoformat()
    current['metadata']['wikipedia_integration'] = {
        'date': '2025-10-16',
        'entries_added': stats['added'],
        'normalized_to_lowercase': normalized_count,
        'kept_capitalized_np': kept_capital_count
    }
    
    with open('dictionary_merged.json', 'w', encoding='utf-8') as f:
        json.dump(current, f, ensure_ascii=False, indent=2)
    
    print(f"  ✓ Saved: dictionary_merged.json")
    print()
    
    # Report
    print("="*70)
    print("MERGE COMPLETE")
    print("="*70)
    print(f"Dictionary: 7,809 → {len(current['words']):,} entries (+{stats['added']:,})")
    print()
    print("Additions by POS:")
    for pos, count in sorted(stats['by_pos'].items(), key=lambda x: -x[1]):
        print(f"  {pos:10} {count:6,} entries")
    print()
    print("✅ Enhanced dictionary saved!")
    print()
    print("Sample additions:")
    for entry in added_entries[:10]:
        ido = entry['ido_word']
        epo = ', '.join(entry['esperanto_words'])
        pos = entry.get('part_of_speech', '?')
        print(f"  {ido:20} → {epo:20} [{pos}]")
    
    return stats['added']


if __name__ == '__main__':
    added = full_merge_normalized()
    print()
    print(f"Next: Regenerate .dix files with {added:,} new entries!")

