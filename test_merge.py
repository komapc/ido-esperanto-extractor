#!/usr/bin/env python3
"""
Test merge of sample vocabulary with current dictionary.

This script:
1. Loads current dictionary
2. Loads test sample
3. Merges (keeping existing on conflicts)
4. Creates test dictionary
5. Reports what was added/skipped

Does NOT modify the original dictionary!
"""

import json
import sys
from collections import defaultdict


def load_current_dictionary(filepath: str = 'dictionary_merged.json'):
    """Load current dictionary."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            print(f"✓ Loaded current dictionary: {len(data.get('words', [])):,} entries")
            return data
    except FileNotFoundError:
        print(f"✗ Dictionary not found: {filepath}")
        sys.exit(1)


def load_test_sample(filepath: str = 'test_sample_200.json'):
    """Load test sample."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            print(f"✓ Loaded test sample: {len(data.get('words', [])):,} entries")
            return data
    except FileNotFoundError:
        print(f"✗ Test sample not found: {filepath}")
        sys.exit(1)


def merge_dictionaries(current_dict: dict, test_sample: dict):
    """
    Merge test sample with current dictionary.
    
    Strategy: Keep existing on conflicts
    """
    
    stats = {
        'current_entries': len(current_dict['words']),
        'sample_entries': len(test_sample['words']),
        'added': 0,
        'skipped_exists': 0,
        'skipped_conflict': 0,
        'total_after_merge': 0,
    }
    
    # Create lookup of existing words
    existing_words = {}
    for entry in current_dict['words']:
        ido_word = entry['ido_word'].lower()
        existing_words[ido_word] = entry
    
    # Track what we're doing
    added_entries = []
    skipped_entries = []
    
    print("\n" + "="*70)
    print("MERGING TEST SAMPLE")
    print("="*70)
    print()
    
    for entry in test_sample['words']:
        ido_word = entry['ido_word']
        ido_lower = ido_word.lower()
        
        # Check if exists
        if ido_lower in existing_words:
            stats['skipped_exists'] += 1
            skipped_entries.append({
                'ido_word': ido_word,
                'reason': 'already_in_dict',
                'current': existing_words[ido_lower],
                'new': entry
            })
            continue
        
        # Add new entry
        stats['added'] += 1
        added_entries.append(entry)
        current_dict['words'].append(entry)
    
    # Sort alphabetically
    current_dict['words'].sort(key=lambda x: x['ido_word'].lower())
    
    stats['total_after_merge'] = len(current_dict['words'])
    
    # Print first few additions
    print("Sample additions (first 10):")
    print("-"*70)
    for entry in added_entries[:10]:
        ido = entry['ido_word']
        epo = ', '.join(entry['esperanto_words'])
        pos = entry.get('part_of_speech', '?')
        morfologio = ' + '.join(entry.get('morfologio', []))
        print(f"  + {ido:20} → {epo:20} [{pos:5}] ({morfologio})")
    
    if len(added_entries) > 10:
        print(f"  ... and {len(added_entries) - 10} more")
    
    print()
    print("Sample skipped (first 10):")
    print("-"*70)
    for skip in skipped_entries[:10]:
        print(f"  ⊗ {skip['ido_word']:20} (already exists)")
    
    if len(skipped_entries) > 10:
        print(f"  ... and {len(skipped_entries) - 10} more")
    
    return current_dict, stats, added_entries, skipped_entries


def save_test_dictionary(dict_data: dict, output_file: str):
    """Save test dictionary."""
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(dict_data, f, ensure_ascii=False, indent=2)
    print(f"\n✓ Saved test dictionary: {output_file}")


def save_reports(added: list, skipped: list):
    """Save detailed reports."""
    
    # Added entries report
    with open('test_merge_added.json', 'w', encoding='utf-8') as f:
        json.dump({'added': added}, f, ensure_ascii=False, indent=2)
    
    # Skipped entries report
    with open('test_merge_skipped.json', 'w', encoding='utf-8') as f:
        json.dump({'skipped': skipped}, f, ensure_ascii=False, indent=2)
    
    print(f"✓ Saved reports: test_merge_added.json, test_merge_skipped.json")


def main():
    """Main test merge function."""
    
    print("="*70)
    print("TEST MERGE - 200 WORD SAMPLE")
    print("="*70)
    print()
    
    # Load data
    current_dict = load_current_dictionary()
    test_sample = load_test_sample()
    
    # Merge
    merged_dict, stats, added, skipped = merge_dictionaries(current_dict, test_sample)
    
    # Save test dictionary
    save_test_dictionary(merged_dict, 'dictionary_merged_test.json')
    
    # Save reports
    save_reports(added, skipped)
    
    # Print statistics
    print()
    print("="*70)
    print("MERGE STATISTICS")
    print("="*70)
    print(f"Current dictionary:           {stats['current_entries']:6,} entries")
    print(f"Test sample:                  {stats['sample_entries']:6,} entries")
    print()
    print(f"Added to dictionary:          {stats['added']:6,} entries")
    print(f"Skipped (already exists):     {stats['skipped_exists']:6,} entries")
    print()
    print(f"Test dictionary size:         {stats['total_after_merge']:6,} entries")
    print("="*70)
    
    addition_rate = (stats['added'] / stats['sample_entries'] * 100) if stats['sample_entries'] > 0 else 0
    print(f"\nAddition rate: {addition_rate:.1f}% of test sample")
    print(f"Dictionary growth: +{stats['added']} entries")
    
    print()
    print("="*70)
    print("NEXT STEPS")
    print("="*70)
    print()
    print("1. Review test_merge_added.json to see what was added")
    print("2. Run converters on test dictionary:")
    print("   python3 create_ido_monolingual_test.py")
    print("   python3 create_ido_epo_bilingual_test.py")
    print("3. Test translations with new vocabulary")
    print("4. If successful, proceed with full merge")
    print()
    print(f"✅ Test merge complete! {stats['added']} new entries added to test dictionary")


if __name__ == '__main__':
    main()

