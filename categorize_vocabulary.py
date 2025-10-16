#!/usr/bin/env python3
"""
Categorize filtered vocabulary into useful groups for review.

Categories:
1. Common nouns/terms (likely to be vocabulary)
2. Geographic names (cities, countries, regions)
3. People names
4. Other (compounds, technical terms)
"""

import csv
import re


def categorize_entry(ido_word: str, esperanto_word: str) -> str:
    """
    Categorize an entry based on patterns.
    
    Returns: 'vocabulary', 'geographic', 'person', 'other'
    """
    # Check if it's a person name (typically has 2+ capitalized words)
    words = ido_word.split()
    if len(words) >= 2:
        # All words capitalized = likely person or place name
        if all(w[0].isupper() for w in words if w):
            # Check for common person name patterns
            person_indicators = [
                'Jr.', 'Sr.', 'von', 'van', 'de', 'da', 'bin', 'ibn',
                # Common first names patterns
                len(words) == 2 and len(words[0]) >= 3 and len(words[1]) >= 3
            ]
            if any(person_indicators):
                return 'person'
    
    # Geographic indicators
    geo_patterns = [
        r'(cheflando|urbo|civito|stando|provinco|gubernio|insulo|oceano|monto|lago|fluvio)',
        r'(lando|stato|regno|imperio|respubliko|federaciono)',
    ]
    
    for pattern in geo_patterns:
        if re.search(pattern, ido_word.lower()):
            return 'geographic'
    
    # Check Esperanto translation for geographic hints
    epo_geo_patterns = [
        r'(urbo|provinco|distrikto|regiono|gubernio)',
    ]
    for pattern in epo_geo_patterns:
        if re.search(pattern, esperanto_word.lower()):
            return 'geographic'
    
    # Single capitalized word ending in common suffixes = likely vocabulary
    if len(words) == 1:
        vocab_endings = [
            'o', 'i', 'a', 'e', 'ar', 'as', 'is', 'os', 'us',
            'uro', 'eso', 'ato', 'isto', 'anto', 'ero', 'ajo',
            'iko', 'io', 'ido', 'ito', 'alo', 'ano', 'ino',
        ]
        for ending in vocab_endings:
            if ido_word.lower().endswith(ending):
                return 'vocabulary'
    
    # Compound words with hyphens
    if '-' in ido_word:
        return 'vocabulary'
    
    # Default: other
    return 'other'


def main():
    input_file = 'ido_wiki_vocabulary_filtered.csv'
    
    categories = {
        'vocabulary': [],
        'geographic': [],
        'person': [],
        'other': [],
    }
    
    stats = {
        'total': 0,
        'new_only': 0,
        'vocabulary': 0,
        'geographic': 0,
        'person': 0,
        'other': 0,
    }
    
    print("Categorizing vocabulary...")
    
    with open(input_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            stats['total'] += 1
            
            ido_word = row['ido_word']
            esperanto_word = row['esperanto_word']
            in_dict = row['in_current_dict'] == 'True'
            
            # Only process new words
            if in_dict:
                continue
            
            stats['new_only'] += 1
            
            category = categorize_entry(ido_word, esperanto_word)
            categories[category].append(row)
            stats[category] += 1
    
    # Save categorized files
    for category, entries in categories.items():
        if entries:
            output_file = f'ido_wiki_vocab_{category}.csv'
            
            # Sort alphabetically
            entries.sort(key=lambda x: x['ido_word'].lower())
            
            with open(output_file, 'w', newline='', encoding='utf-8') as f:
                fieldnames = ['ido_word', 'esperanto_word', 'in_current_dict']
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(entries)
            
            print(f"✓ Saved {len(entries):5,} {category:12} entries to {output_file}")
    
    # Print statistics
    print("\n" + "="*70)
    print("CATEGORIZATION STATISTICS")
    print("="*70)
    print(f"Total entries:                {stats['total']:6,}")
    print(f"New words only:               {stats['new_only']:6,}")
    print(f"\nBy category:")
    print(f"  - Vocabulary (common):      {stats['vocabulary']:6,}")
    print(f"  - Geographic names:         {stats['geographic']:6,}")
    print(f"  - People names:             {stats['person']:6,}")
    print(f"  - Other:                    {stats['other']:6,}")
    print("="*70)
    
    # Recommendations
    print("\n📝 RECOMMENDATIONS:")
    print(f"  1. Review 'ido_wiki_vocab_vocabulary.csv' first ({stats['vocabulary']:,} entries)")
    print(f"     → Common nouns, verbs, compounds - highest priority")
    print(f"  2. Review 'ido_wiki_vocab_geographic.csv' ({stats['geographic']:,} entries)")
    print(f"     → Cities, countries, regions - useful for translations")
    print(f"  3. Consider 'ido_wiki_vocab_other.csv' ({stats['other']:,} entries)")
    print(f"     → Mixed content, may contain useful terms")
    print(f"  4. Skip 'ido_wiki_vocab_person.csv' ({stats['person']:,} entries)")
    print(f"     → People names - lower priority for dictionary")


if __name__ == '__main__':
    main()

