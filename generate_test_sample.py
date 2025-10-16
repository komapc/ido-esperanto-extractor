#!/usr/bin/env python3
"""
Generate test sample of 200 words for validation.

Distribution:
- 100 nouns (most common)
- 50 verbs
- 30 adjectives  
- 20 adverbs

Selection strategy:
- Diverse alphabetically
- Mix of simple and complex
- Include some in Wiktionary (if available)
"""

import json
import random
from collections import defaultdict


def generate_test_sample(input_file: str, output_file: str, sample_size: int = 200):
    """Generate test sample with POS distribution."""
    
    print("="*70)
    print("GENERATING TEST SAMPLE")
    print("="*70)
    print()
    
    # Load vocabulary with morphology
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    words = data['words']
    
    print(f"Total vocabulary: {len(words):,} entries")
    print()
    
    # Group by POS
    by_pos = defaultdict(list)
    for entry in words:
        pos = entry.get('part_of_speech', 'unknown')
        by_pos[pos].append(entry)
    
    print("Available by POS:")
    for pos, entries in sorted(by_pos.items(), key=lambda x: -len(x[1])):
        print(f"  {pos:10} {len(entries):5,} entries")
    print()
    
    # Target distribution
    targets = {
        'n': 100,      # nouns
        'vblex': 50,   # verbs
        'adj': 30,     # adjectives
        'adv': 20,     # adverbs
    }
    
    print("Target sample distribution:")
    for pos, count in targets.items():
        print(f"  {pos:10} {count:3} entries")
    print()
    
    # Select samples
    sample_entries = []
    
    for pos, target_count in targets.items():
        available = by_pos.get(pos, [])
        
        if len(available) == 0:
            print(f"⚠ No {pos} entries available")
            continue
        
        # Sample count (can't exceed available)
        sample_count = min(target_count, len(available))
        
        # Sort alphabetically for diversity
        available_sorted = sorted(available, key=lambda x: x['ido_word'])
        
        # Select evenly distributed across alphabet
        if len(available) >= sample_count:
            step = len(available) // sample_count
            selected = [available_sorted[i * step] for i in range(sample_count)]
        else:
            selected = available_sorted
        
        sample_entries.extend(selected)
        print(f"  ✓ Selected {len(selected):3} {pos} entries")
    
    # Sort sample alphabetically
    sample_entries.sort(key=lambda x: x['ido_word'].lower())
    
    # Create output
    output_data = {
        'metadata': {
            'sample_date': '2025-10-16',
            'source_file': input_file,
            'total_available': len(words),
            'sample_size': len(sample_entries),
            'distribution': {pos: sum(1 for e in sample_entries if e.get('part_of_speech') == pos) 
                           for pos in targets.keys()}
        },
        'words': sample_entries
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    
    print()
    print("="*70)
    print("TEST SAMPLE GENERATED")
    print("="*70)
    print(f"Sample size: {len(sample_entries)} entries")
    print()
    print("Actual distribution:")
    for pos in targets.keys():
        count = sum(1 for e in sample_entries if e.get('part_of_speech') == pos)
        print(f"  {pos:10} {count:3} entries")
    print()
    print(f"Saved to: {output_file}")
    
    # Show sample
    print()
    print("Sample entries (first 15):")
    print("-"*70)
    for entry in sample_entries[:15]:
        ido = entry['ido_word']
        epo = entry['esperanto_words'][0]
        pos = entry['part_of_speech']
        morfologio = ' + '.join(entry['morfologio'])
        print(f"  {ido:20} → {epo:25} [{pos:5}] ({morfologio})")
    
    print()
    print("✅ Test sample ready for merge testing!")
    
    return output_file, len(sample_entries)


if __name__ == '__main__':
    input_file = 'wikipedia_vocabulary_with_morphology.json'
    output_file = 'test_sample_200.json'
    
    generate_test_sample(input_file, output_file, sample_size=200)

