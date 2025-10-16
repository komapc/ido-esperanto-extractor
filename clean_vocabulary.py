#!/usr/bin/env python3
"""
Deep cleaning of vocabulary to remove invalid/problematic entries.

Filters:
1. Items with comma in either language
2. Items with numbers
3. Items with invalid characters (non-Ido in Ido, non-Esperanto in Esperanto)
4. Additional filters for quality

Input: categorized CSV files
Output: cleaned versions
"""

import csv
import re
import sys
from typing import Tuple


# Valid character sets
# Ido: standard Latin alphabet a-z (no special chars)
IDO_VALID_CHARS = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ-\' ')

# Esperanto: a-z plus ĉ, ĝ, ĥ, ĵ, ŝ, ŭ
ESPERANTO_VALID_CHARS = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZĉĝĥĵŝŭĈĜĤĴŜŬ-\' ')


def has_comma(text: str) -> bool:
    """Check if text contains comma."""
    return ',' in text


def has_number(text: str) -> bool:
    """Check if text contains any digit."""
    return any(char.isdigit() for char in text)


def has_invalid_ido_chars(text: str) -> bool:
    """Check if Ido word has non-Ido characters."""
    for char in text:
        if char not in IDO_VALID_CHARS:
            return True
    return False


def has_invalid_esperanto_chars(text: str) -> bool:
    """Check if Esperanto word has non-Esperanto characters."""
    for char in text:
        if char not in ESPERANTO_VALID_CHARS:
            return True
    return False


def has_colon(text: str) -> bool:
    """Check if text contains colon (usually indicates special pages)."""
    return ':' in text


def has_parentheses_content(text: str) -> bool:
    """Check if text contains parentheses (disambiguation, clarification)."""
    return '(' in text or ')' in text


def is_too_short(text: str) -> bool:
    """Check if word is too short (< 3 chars)."""
    # Remove spaces and hyphens for length check
    clean_text = text.replace(' ', '').replace('-', '')
    return len(clean_text) < 3


def has_suspicious_patterns(ido_word: str, esperanto_word: str) -> bool:
    """Check for suspicious patterns that indicate non-vocabulary."""
    suspicious = [
        # Same in both languages (might be proper name or borrowed word)
        # Actually this is fine - many words are identical
        
        # Wikipedia/meta patterns
        r'^Kategorio:',
        r'^Category:',
        r'^Template:',
        r'^Ŝablono:',
        r'^Help:',
        r'^Helpo:',
        r'^User:',
        r'^Uzanto:',
        
        # File/media patterns
        r'^File:',
        r'^Image:',
        r'^Dosiero:',
        
        # List patterns
        r'^Listo de',
        r'^Listo pri',
        r'^List of',
        
        # Multiple spaces (indicates formatting issues)
        r'  ',
    ]
    
    for pattern in suspicious:
        if re.search(pattern, ido_word, re.IGNORECASE):
            return True
        if re.search(pattern, esperanto_word, re.IGNORECASE):
            return True
    
    return False


def is_all_caps_acronym(text: str) -> bool:
    """Check if text is an all-caps acronym (like NATO, USA)."""
    # Remove spaces and hyphens
    clean = text.replace(' ', '').replace('-', '')
    # Must be 2-6 chars, all uppercase letters
    return (len(clean) >= 2 and len(clean) <= 6 and 
            clean.isupper() and clean.isalpha())


def has_multiple_capital_words(text: str) -> bool:
    """Check if text has multiple capitalized words (likely proper name)."""
    words = text.split()
    if len(words) <= 1:
        return False
    
    # Count capitalized words
    capital_count = sum(1 for w in words if w and w[0].isupper())
    
    # If 2+ capitalized words, likely a person/place name
    return capital_count >= 2


def clean_vocabulary(input_file: str, output_file: str) -> Tuple[int, int, dict]:
    """
    Clean vocabulary file and save to output.
    
    Returns: (total_processed, kept, stats_dict)
    """
    stats = {
        'total': 0,
        'removed_comma': 0,
        'removed_number': 0,
        'removed_invalid_ido': 0,
        'removed_invalid_epo': 0,
        'removed_colon': 0,
        'removed_parens': 0,
        'removed_short': 0,
        'removed_suspicious': 0,
        'removed_acronym': 0,
        'removed_multi_capital': 0,
        'kept': 0,
    }
    
    cleaned_entries = []
    
    with open(input_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            stats['total'] += 1
            
            ido_word = row['ido_word']
            esperanto_word = row['esperanto_word']
            
            # Apply filters
            if has_comma(ido_word) or has_comma(esperanto_word):
                stats['removed_comma'] += 1
                continue
            
            if has_number(ido_word) or has_number(esperanto_word):
                stats['removed_number'] += 1
                continue
            
            if has_invalid_ido_chars(ido_word):
                stats['removed_invalid_ido'] += 1
                continue
            
            if has_invalid_esperanto_chars(esperanto_word):
                stats['removed_invalid_epo'] += 1
                continue
            
            if has_colon(ido_word) or has_colon(esperanto_word):
                stats['removed_colon'] += 1
                continue
            
            if has_parentheses_content(esperanto_word):
                stats['removed_parens'] += 1
                continue
            
            if is_too_short(ido_word):
                stats['removed_short'] += 1
                continue
            
            if has_suspicious_patterns(ido_word, esperanto_word):
                stats['removed_suspicious'] += 1
                continue
            
            if is_all_caps_acronym(ido_word):
                stats['removed_acronym'] += 1
                continue
            
            if has_multiple_capital_words(ido_word):
                stats['removed_multi_capital'] += 1
                continue
            
            # Keep this entry
            stats['kept'] += 1
            cleaned_entries.append(row)
    
    # Save cleaned vocabulary
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        fieldnames = ['ido_word', 'esperanto_word', 'in_current_dict']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(cleaned_entries)
    
    return stats['total'], stats['kept'], stats


def main():
    """Clean all vocabulary files."""
    
    print("="*70)
    print("DEEP VOCABULARY CLEANING")
    print("="*70)
    print()
    
    # Files to clean
    files_to_clean = [
        ('ido_wiki_vocab_vocabulary.csv', 'ido_wiki_vocab_vocabulary_clean.csv'),
        ('ido_wiki_vocab_geographic.csv', 'ido_wiki_vocab_geographic_clean.csv'),
        ('ido_wiki_vocab_other.csv', 'ido_wiki_vocab_other_clean.csv'),
    ]
    
    total_before = 0
    total_after = 0
    all_stats = {}
    
    for input_file, output_file in files_to_clean:
        try:
            print(f"Cleaning {input_file}...")
            before, after, stats = clean_vocabulary(input_file, output_file)
            
            total_before += before
            total_after += after
            
            # Aggregate stats
            for key, value in stats.items():
                all_stats[key] = all_stats.get(key, 0) + value
            
            removal_pct = ((before - after) / before * 100) if before > 0 else 0
            print(f"  ✓ {before:5,} → {after:5,} entries ({removal_pct:.1f}% removed)")
            print(f"  → Saved to {output_file}")
            print()
        
        except FileNotFoundError:
            print(f"  ⚠ File not found: {input_file}")
            print()
    
    # Print detailed statistics
    print("="*70)
    print("DETAILED CLEANING STATISTICS")
    print("="*70)
    print(f"Total processed:              {all_stats['total']:6,}")
    print()
    print("Removed:")
    print(f"  - Has comma:                {all_stats['removed_comma']:6,}")
    print(f"  - Has number:               {all_stats['removed_number']:6,}")
    print(f"  - Invalid Ido chars:        {all_stats['removed_invalid_ido']:6,}")
    print(f"  - Invalid Esperanto chars:  {all_stats['removed_invalid_epo']:6,}")
    print(f"  - Has colon:                {all_stats['removed_colon']:6,}")
    print(f"  - Has parentheses:          {all_stats['removed_parens']:6,}")
    print(f"  - Too short (< 3 chars):    {all_stats['removed_short']:6,}")
    print(f"  - Suspicious patterns:      {all_stats['removed_suspicious']:6,}")
    print(f"  - All-caps acronym:         {all_stats['removed_acronym']:6,}")
    print(f"  - Multi-capital name:       {all_stats['removed_multi_capital']:6,}")
    
    total_removed = all_stats['total'] - all_stats['kept']
    print(f"  TOTAL REMOVED:              {total_removed:6,}")
    print()
    print(f"KEPT (clean):                 {all_stats['kept']:6,}")
    print("="*70)
    
    removal_pct = (total_removed / all_stats['total'] * 100) if all_stats['total'] > 0 else 0
    print(f"\nOverall removal rate: {removal_pct:.1f}%")
    print(f"Clean vocabulary ready: {all_stats['kept']:,} entries")
    
    print("\n" + "="*70)
    print("SUGGESTIONS FOR ADDITIONAL FILTERING")
    print("="*70)
    print()
    print("Consider also filtering:")
    print("  1. Words ending in specific suffixes that indicate person names:")
    print("     -sson, -sen, -ovich, -escu, -ini, -ová")
    print()
    print("  2. Geographic compound patterns:")
    print("     'Stato de...', 'Regno di...', 'Imperio de...'")
    print()
    print("  3. Very rare words (check frequency in Ido Wikipedia corpus)")
    print()
    print("  4. Words that are exactly identical in both languages")
    print("     (might be proper names or borrowed terms)")
    print()
    print("  5. Filter by word length (e.g., keep only 3-20 chars)")
    print()
    print("Would you like me to add any of these filters? (Y/n)")
    print("="*70)


if __name__ == '__main__':
    main()

