#!/usr/bin/env python3
"""
Final preparation for dictionary merge.

Strategy:
1. Accept that Wikipedia vocabulary includes both common words AND proper nouns
2. Properly TAG entries (not just filter them out):
   - Regular vocabulary → n, vblex, adj, adv
   - Place names → np (proper noun)
   - Both are useful for translation!

3. Create final merge-ready files with proper tagging
"""

import json
from collections import defaultdict


def detect_proper_noun_type(ido_word: str, esperanto_word: str) -> str:
    """
    Detect if entry should be tagged as proper noun.
    
    Returns: 'np' (proper noun) or original POS
    """
    # Strong indicators for proper noun:
    
    # 1. Identical + capitalized = borrowed place name
    if ido_word == esperanto_word and ido_word[0].isupper():
        return 'np'
    
    # 2. Esperanto has geographic terms
    geo_keywords = ['urbo', 'provinco', 'lando', 'insulo', 'monto', 'oceano', 'maro', 'lago', 'golfo']
    epo_lower = esperanto_word.lower()
    if any(keyword in epo_lower for keyword in geo_keywords):
        return 'np'
    
    # 3. Known place name patterns in Esperanto
    # Cities often end in -o: Londono, Parizo, Berlino
    # But so do regular nouns, so this alone isn't enough
    
    # Otherwise, keep original POS
    return None  # Will keep original


def prepare_for_merge(input_file: str, output_file: str):
    """Prepare vocabulary with proper tagging."""
    
    print("="*70)
    print("FINAL PREPARATION FOR MERGE")
    print("="*70)
    print()
    
    # Load vocabulary
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    words = data.get('words', [])
    
    print(f"Total entries: {len(words):,}")
    print()
    
    stats = {
        'total': len(words),
        'retagged_as_np': 0,
        'kept_original_pos': 0,
        'by_final_pos': defaultdict(int),
    }
    
    # Process each entry
    for entry in words:
        ido_word = entry['ido_word']
        esperanto_word = entry['esperanto_words'][0] if entry.get('esperanto_words') else ''
        original_pos = entry.get('part_of_speech', 'n')
        
        # Check if should be proper noun
        new_pos = detect_proper_noun_type(ido_word, esperanto_word)
        
        if new_pos == 'np':
            entry['part_of_speech'] = 'np'
            entry['original_pos'] = original_pos  # Keep for reference
            stats['retagged_as_np'] += 1
        else:
            stats['kept_original_pos'] += 1
        
        final_pos = entry['part_of_speech']
        stats['by_final_pos'][final_pos] += 1
    
    # Save
    output_data = {
        'metadata': {
            **data.get('metadata', {}),
            'preparation_date': '2025-10-16',
            'total_entries': len(words),
            'ready_for_merge': True
        },
        'words': words
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    
    print(f"✓ Saved {len(words):,} entries to {output_file}")
    print()
    
    # Statistics
    print("="*70)
    print("TAGGING STATISTICS")
    print("="*70)
    print(f"Total entries:                {stats['total']:6,}")
    print()
    print(f"Retagged as proper noun (np): {stats['retagged_as_np']:6,}")
    print(f"Kept original POS:            {stats['kept_original_pos']:6,}")
    print()
    print("Final POS distribution:")
    for pos, count in sorted(stats['by_final_pos'].items(), key=lambda x: -x[1]):
        print(f"  {pos:10} {count:6,} entries")
    print("="*70)
    
    np_pct = (stats['retagged_as_np'] / stats['total'] * 100)
    print(f"\nProper nouns: {np_pct:.1f}% of total")
    print()
    print("✅ Vocabulary ready for merge!")
    print(f"   File: {output_file}")
    
    return output_file


if __name__ == '__main__':
    output = prepare_for_merge(
        'wikipedia_vocabulary_with_morphology.json',
        'wikipedia_vocabulary_merge_ready.json'
    )
    print()
    print("Next: Generate test sample and merge")

