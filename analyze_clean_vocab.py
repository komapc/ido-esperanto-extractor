#!/usr/bin/env python3
"""
Analyze cleaned vocabulary to help decide on additional filters.
"""

import csv
import re
from collections import defaultdict


def analyze_file(filename):
    """Analyze patterns in vocabulary file."""
    
    stats = {
        'total': 0,
        'identical': 0,
        'identical_with_ending': 0,
        'no_ido_ending': 0,
        'has_ido_ending': 0,
        'person_suffix': 0,
        'very_long': 0,
        'meta_patterns': 0,
    }
    
    # Track examples
    examples = defaultdict(list)
    
    # Ido grammatical endings
    ido_endings = re.compile(r'(o|i|a|e|ar|ir|or|as|is|os|us|ez|on|in)$')
    
    # Person name suffixes
    person_suffixes = re.compile(r'(sson|sen|ovich|escu|ini|ová|sky|vich|wicz)$', re.IGNORECASE)
    
    # Meta patterns
    meta_patterns = re.compile(r'^(Listo|Historio de|Geografia de|Regno di|Stato de|Imperio de)', re.IGNORECASE)
    
    with open(filename, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            stats['total'] += 1
            
            ido = row['ido_word']
            epo = row['esperanto_word']
            
            # Check identical
            if ido == epo:
                stats['identical'] += 1
                if ido_endings.search(ido):
                    stats['identical_with_ending'] += 1
                    if len(examples['identical_with_ending']) < 10:
                        examples['identical_with_ending'].append(f"{ido} → {epo}")
                else:
                    if len(examples['identical_no_ending']) < 10:
                        examples['identical_no_ending'].append(f"{ido} → {epo}")
            
            # Check Ido ending
            if ido_endings.search(ido):
                stats['has_ido_ending'] += 1
            else:
                stats['no_ido_ending'] += 1
                if len(examples['no_ido_ending']) < 10:
                    examples['no_ido_ending'].append(f"{ido} → {epo}")
            
            # Check person suffix
            if person_suffixes.search(ido):
                stats['person_suffix'] += 1
                if len(examples['person_suffix']) < 10:
                    examples['person_suffix'].append(f"{ido} → {epo}")
            
            # Check length
            if len(ido) > 25:
                stats['very_long'] += 1
                if len(examples['very_long']) < 10:
                    examples['very_long'].append(f"{ido} → {epo}")
            
            # Check meta patterns
            if meta_patterns.match(ido):
                stats['meta_patterns'] += 1
                if len(examples['meta_patterns']) < 10:
                    examples['meta_patterns'].append(f"{ido} → {epo}")
    
    return stats, examples


def main():
    """Analyze vocabulary files."""
    
    print("="*70)
    print("VOCABULARY ANALYSIS FOR ADDITIONAL FILTERING")
    print("="*70)
    print()
    
    filename = 'ido_wiki_vocab_vocabulary_clean.csv'
    
    stats, examples = analyze_file(filename)
    
    print(f"Analyzing: {filename}")
    print(f"Total entries: {stats['total']:,}")
    print()
    
    # Print statistics
    print("━"*70)
    print("PATTERN ANALYSIS")
    print("━"*70)
    
    print(f"\n1. Identical in both languages: {stats['identical']:,} ({stats['identical']/stats['total']*100:.1f}%)")
    print(f"   - With Ido ending (-o,-a,-e,-ar): {stats['identical_with_ending']:,}")
    print(f"   - Without Ido ending: {stats['identical'] - stats['identical_with_ending']:,}")
    print(f"   Examples with ending (KEEP these):")
    for ex in examples.get('identical_with_ending', [])[:5]:
        print(f"     {ex}")
    print(f"   Examples without ending (REMOVE these):")
    for ex in examples.get('identical_no_ending', [])[:5]:
        print(f"     {ex}")
    
    print(f"\n2. Ido grammatical endings:")
    print(f"   - Has Ido ending: {stats['has_ido_ending']:,} ({stats['has_ido_ending']/stats['total']*100:.1f}%)")
    print(f"   - NO Ido ending: {stats['no_ido_ending']:,} ({stats['no_ido_ending']/stats['total']*100:.1f}%)")
    print(f"   Examples without Ido ending (might be proper nouns):")
    for ex in examples.get('no_ido_ending', [])[:8]:
        print(f"     {ex}")
    
    print(f"\n3. Person name suffixes (-sson, -sen, etc.): {stats['person_suffix']:,}")
    print(f"   Examples:")
    for ex in examples.get('person_suffix', [])[:5]:
        print(f"     {ex}")
    
    print(f"\n4. Very long words (>25 chars): {stats['very_long']:,}")
    print(f"   Examples:")
    for ex in examples.get('very_long', [])[:5]:
        print(f"     {ex}")
    
    print(f"\n5. Meta/compound patterns: {stats['meta_patterns']:,}")
    print(f"   Examples:")
    for ex in examples.get('meta_patterns', [])[:5]:
        print(f"     {ex}")
    
    # Recommendations
    print("\n" + "="*70)
    print("FILTER IMPACT ESTIMATES")
    print("="*70)
    print()
    
    # Calculate cumulative impact
    current = stats['total']
    
    print(f"Current state:                          {current:5,} entries")
    print()
    print("If we apply:")
    
    # Filter identical without ending
    identical_no_ending = stats['identical'] - stats['identical_with_ending']
    after_filter3 = current - identical_no_ending
    print(f"  Filter 3 (identical, no Ido ending):  -{identical_no_ending:4,} → {after_filter3:5,} entries")
    
    # Filter no Ido ending
    after_filter7 = current - stats['no_ido_ending']
    print(f"  Filter 7 (no Ido ending at all):      -{stats['no_ido_ending']:4,} → {after_filter7:5,} entries")
    
    # Filter person suffixes
    after_person = current - stats['person_suffix']
    print(f"  Filter 1 (person name suffixes):      -{stats['person_suffix']:4,} → {after_person:5,} entries")
    
    # Filter very long
    after_long = current - stats['very_long']
    print(f"  Filter 4 (very long >25 chars):       -{stats['very_long']:4,} → {after_long:5,} entries")
    
    # Filter meta
    after_meta = current - stats['meta_patterns']
    print(f"  Filter 6 (meta patterns):             -{stats['meta_patterns']:4,} → {after_meta:5,} entries")
    
    # Combined aggressive
    aggressive = after_filter7 - stats['person_suffix'] - stats['very_long'] - stats['meta_patterns']
    print()
    print(f"  AGGRESSIVE (3+7+1+4+6):               ~{aggressive:5,} entries (estimate)")
    
    print()
    print("="*70)
    print("RECOMMENDATION")
    print("="*70)
    print()
    print("BEST APPROACH: Apply Filter 7 (keep only Ido grammatical endings)")
    print(f"  → Reduces from {current:,} to ~{after_filter7:,} entries")
    print(f"  → Removes borrowed terms and proper nouns without Ido endings")
    print(f"  → Keeps all legitimate Ido vocabulary")
    print()
    print("This ensures we get actual Ido words, not just any Wikipedia article title.")


if __name__ == '__main__':
    main()

