#!/usr/bin/env python3
"""
Fix POS tagging - distinguish true proper nouns from international vocabulary.

Issue: Words like "Aborto", "Acetato", "Albumino" are international scientific terms,
       not proper nouns, even though they're identical in Ido and Esperanto.

Solution: Use smarter heuristics based on word patterns and context.
"""

import json


# International scientific/medical/technical term patterns
INTERNATIONAL_TERMS = {
    # Medical terms
    'aborto', 'adenino', 'adenito', 'albumino', 'anestezio', 'antibiotiko',
    # Chemical elements/compounds
    'acetato', 'aluminio', 'argono', 'arseniko', 'astato', 'azoto',
    # Scientific concepts
    'algoritmo', 'akronimo', 'atomо', 'bakterio',
    # Abstract concepts
    'abstraktismo', 'abulio', 'afazio', 'afelio',
}


def is_international_term(ido_word: str) -> bool:
    """Check if word is an international scientific/technical term."""
    lower = ido_word.lower()
    
    # Check against known list
    if lower in INTERNATIONAL_TERMS:
        return True
    
    # Patterns for international terms
    # Often end in: -ino, -ato, -io, -ismo, -ito
    international_endings = [
        'ino', 'ato', 'io', 'ismo', 'ito', 'iko', 'io'
    ]
    
    for ending in international_endings:
        if lower.endswith(ending) and len(lower) > len(ending) + 3:
            return True
    
    return False


def fix_entry_pos(entry: dict) -> dict:
    """Fix POS tag AND capitalization if incorrectly marked as proper noun."""
    
    ido_word = entry['ido_word']
    pos = entry.get('part_of_speech', 'n')
    original_pos = entry.get('original_pos', 'n')
    
    # If currently tagged as np, check if it should be regular noun
    if pos == 'np':
        # Check if it's an international term
        if is_international_term(ido_word):
            # Restore original POS (likely 'n')
            entry['part_of_speech'] = original_pos
            entry['was_retagged'] = True
            
            # ALSO lowercase it (not a proper noun!)
            entry['ido_word'] = ido_word[0].lower() + ido_word[1:] if len(ido_word) > 0 else ido_word
            
            # Lowercase the root in morfologio too
            if 'morfologio' in entry and entry['morfologio']:
                root = entry['morfologio'][0]
                entry['morfologio'][0] = root[0].lower() + root[1:] if len(root) > 0 else root
            
            return entry
    
    return entry


def main():
    """Fix POS tagging in merged dictionary."""
    
    print("="*70)
    print("FIXING POS TAGGING")
    print("="*70)
    print()
    
    # Load merged dictionary
    with open('dictionary_merged.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    words = data['words']
    print(f"Total entries: {len(words):,}")
    print()
    
    # Fix tagging
    stats = {
        'total': len(words),
        'retagged': 0,
        'kept_np': 0,
        'by_new_pos': {},
    }
    
    retagged_examples = []
    
    for i, entry in enumerate(words):
        original_pos = entry.get('part_of_speech')
        
        words[i] = fix_entry_pos(entry)
        
        if entry.get('was_retagged'):
            stats['retagged'] += 1
            new_pos = entry['part_of_speech']
            stats['by_new_pos'][new_pos] = stats['by_new_pos'].get(new_pos, 0) + 1
            
            if len(retagged_examples) < 20:
                retagged_examples.append({
                    'word': entry['ido_word'],
                    'from': original_pos,
                    'to': new_pos
                })
        elif entry.get('part_of_speech') == 'np':
            stats['kept_np'] += 1
    
    # Save
    with open('dictionary_merged.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print("="*70)
    print("RETAGGING RESULTS")
    print("="*70)
    print(f"Total entries:                {stats['total']:6,}")
    print(f"Retagged (np → n):            {stats['retagged']:6,}")
    print(f"Kept as proper noun (np):     {stats['kept_np']:6,}")
    print()
    
    if retagged_examples:
        print("Examples of retagged entries:")
        for ex in retagged_examples[:15]:
            print(f"  {ex['word']:20} {ex['from']} → {ex['to']}")
    
    print()
    print("✅ POS tagging fixed!")
    print(f"   Saved: dictionary_merged.json")


if __name__ == '__main__':
    main()

