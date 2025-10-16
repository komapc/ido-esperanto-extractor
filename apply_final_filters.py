#!/usr/bin/env python3
"""
Apply final recommended filters to create ultra-clean vocabulary.

Recommended filters:
1. Keep only words with Ido grammatical endings (-o,-a,-e,-ar,etc.)
2. Remove person name suffixes
3. Remove very long words (>25 chars)
4. Remove entries with quotes/special formatting

This ensures we get genuine Ido vocabulary, not borrowed terms or noise.
"""

import csv
import re
import sys


def has_ido_grammatical_ending(word: str) -> bool:
    """Check if word has proper Ido grammatical ending."""
    # Ido grammatical endings
    endings = [
        'o', 'i',           # noun (sg, pl)
        'on', 'in',         # noun accusative (sg, pl)
        'a',                # adjective
        'e',                # adverb
        'ar', 'ir', 'or',   # verb infinitive
        'as', 'is', 'os', 'us', 'ez',  # verb conjugations
    ]
    
    word_lower = word.lower()
    
    # Check if ends with any Ido ending
    for ending in endings:
        if word_lower.endswith(ending):
            # Make sure it's not just the ending (word should be longer)
            if len(word) > len(ending) + 1:
                return True
    
    # Special case: compound words with hyphens
    # Check if last part has Ido ending
    if '-' in word:
        parts = word.split('-')
        last_part = parts[-1].lower()
        for ending in endings:
            if last_part.endswith(ending) and len(last_part) > len(ending) + 1:
                return True
    
    return False


def has_person_name_suffix(word: str) -> bool:
    """Check for person name suffixes."""
    person_suffixes = [
        'sson', 'sen', 'ovich', 'escu', 'ini', 'ová', 
        'sky', 'vich', 'wicz', 'berg', 'stein'
    ]
    
    word_lower = word.lower()
    for suffix in person_suffixes:
        if word_lower.endswith(suffix):
            return True
    
    return False


def is_very_long(word: str) -> bool:
    """Check if word is suspiciously long."""
    return len(word) > 25


def has_special_formatting(word: str) -> bool:
    """Check for special formatting characters."""
    return '"""' in word or "'''" in word or '`' in word


def apply_filters(input_file: str, output_file: str):
    """Apply final filters to vocabulary file."""
    
    stats = {
        'total': 0,
        'removed_no_ending': 0,
        'removed_person_suffix': 0,
        'removed_too_long': 0,
        'removed_special_format': 0,
        'kept': 0,
    }
    
    cleaned_entries = []
    
    with open(input_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            stats['total'] += 1
            
            ido_word = row['ido_word']
            
            # Apply filters
            if not has_ido_grammatical_ending(ido_word):
                stats['removed_no_ending'] += 1
                continue
            
            if has_person_name_suffix(ido_word):
                stats['removed_person_suffix'] += 1
                continue
            
            if is_very_long(ido_word):
                stats['removed_too_long'] += 1
                continue
            
            if has_special_formatting(ido_word):
                stats['removed_special_format'] += 1
                continue
            
            # Keep this entry
            stats['kept'] += 1
            cleaned_entries.append(row)
    
    # Save
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        fieldnames = ['ido_word', 'esperanto_word', 'in_current_dict']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(cleaned_entries)
    
    return stats


def main():
    """Apply final filters to all vocabulary categories."""
    
    print("="*70)
    print("APPLYING FINAL FILTERS - ULTRA CLEAN VOCABULARY")
    print("="*70)
    print()
    
    files = [
        ('ido_wiki_vocab_vocabulary_clean.csv', 'ido_wiki_vocab_vocabulary_final.csv', 'Vocabulary'),
        ('ido_wiki_vocab_geographic_clean.csv', 'ido_wiki_vocab_geographic_final.csv', 'Geographic'),
        ('ido_wiki_vocab_other_clean.csv', 'ido_wiki_vocab_other_final.csv', 'Other'),
    ]
    
    total_stats = {
        'total': 0,
        'removed_no_ending': 0,
        'removed_person_suffix': 0,
        'removed_too_long': 0,
        'removed_special_format': 0,
        'kept': 0,
    }
    
    for input_file, output_file, category in files:
        try:
            print(f"Processing {category}...")
            stats = apply_filters(input_file, output_file)
            
            # Aggregate
            for key in total_stats:
                total_stats[key] += stats[key]
            
            removal = stats['total'] - stats['kept']
            removal_pct = (removal / stats['total'] * 100) if stats['total'] > 0 else 0
            
            print(f"  {stats['total']:5,} → {stats['kept']:5,} entries ({removal_pct:.1f}% removed)")
            print(f"  → Saved to {output_file}")
            print()
        
        except FileNotFoundError:
            print(f"  ⚠ File not found: {input_file}\n")
    
    # Summary
    print("="*70)
    print("FINAL FILTERING SUMMARY")
    print("="*70)
    print(f"Total processed:              {total_stats['total']:6,}")
    print()
    print("Removed:")
    print(f"  - No Ido ending:            {total_stats['removed_no_ending']:6,}")
    print(f"  - Person name suffix:       {total_stats['removed_person_suffix']:6,}")
    print(f"  - Too long (>25 chars):     {total_stats['removed_too_long']:6,}")
    print(f"  - Special formatting:       {total_stats['removed_special_format']:6,}")
    
    total_removed = total_stats['total'] - total_stats['kept']
    print(f"  TOTAL REMOVED:              {total_removed:6,}")
    print()
    print(f"KEPT (ultra-clean):           {total_stats['kept']:6,} ✨")
    print("="*70)
    
    removal_pct = (total_removed / total_stats['total'] * 100) if total_stats['total'] > 0 else 0
    print(f"\nFinal removal rate: {removal_pct:.1f}%")
    print(f"\n🎉 Ultra-clean vocabulary ready: {total_stats['kept']:,} entries")
    print("   → All entries have proper Ido grammatical structure")
    print("   → Ready for dictionary addition after review")


if __name__ == '__main__':
    main()

