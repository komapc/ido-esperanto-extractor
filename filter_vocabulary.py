#!/usr/bin/env python3
"""
Filter the extracted vocabulary to remove noise and keep only useful words.

This script removes:
- Domain names (starting with .)
- Pure numbers and years
- Dates in "aK" format
- Very short entries (< 2 chars)
- Entries with special characters that indicate noise

Outputs: ido_wiki_vocabulary_filtered.csv
"""

import csv
import re
import sys


def is_domain_name(word: str) -> bool:
    """Check if word is a domain name."""
    return word.startswith('.')


def is_year_or_number(word: str) -> bool:
    """Check if word is just a year or number."""
    # Pure numbers
    if word.isdigit():
        return True
    
    # Years like "1949", "2026"
    if re.match(r'^\d{1,4}$', word):
        return True
    
    # Dates in "aK" format like "10 aK", "100 aK"
    if re.match(r'^\d+\s*aK$', word):
        return True
    
    # Decade format like "Yari 1950a"
    if re.match(r'^Yari\s+\d+a$', word):
        return True
    
    # Asteroid numbers like "4062 Schiaparelli"
    if re.match(r'^\d+\s+[A-Z]', word):
        return True
    
    return False


def is_meta_page(word: str) -> bool:
    """Check if word is a meta/special page."""
    meta_patterns = [
        r'^WP-',  # Wikipedia pages
        r'^Provinco\s+',  # Province pages (keep as geographic)
        r'^Distrikto\s+',  # District pages (keep as geographic)
    ]
    
    for pattern in meta_patterns:
        if re.match(pattern, word):
            return True
    
    return False


def is_too_short(word: str) -> bool:
    """Check if word is too short to be useful."""
    return len(word) < 2


def has_noise_characters(word: str) -> bool:
    """Check if word has characters indicating it's noise."""
    # Triple quotes, special formatting
    if '"""' in word or "'''" in word:
        return True
    
    # Contains only special characters
    if re.match(r'^[^a-zA-Z]+$', word):
        return True
    
    return False


def filter_vocabulary(input_file: str, output_file: str):
    """Filter vocabulary and save to new file."""
    
    stats = {
        'total': 0,
        'removed_domain': 0,
        'removed_year': 0,
        'removed_meta': 0,
        'removed_short': 0,
        'removed_noise': 0,
        'kept': 0,
        'kept_new': 0,
        'kept_in_dict': 0,
    }
    
    filtered_entries = []
    
    print(f"Filtering vocabulary from {input_file}...")
    
    with open(input_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            stats['total'] += 1
            
            ido_word = row['ido_word']
            esperanto_word = row['esperanto_word']
            in_dict = row['in_current_dict'] == 'True'
            
            # Apply filters
            if is_domain_name(ido_word):
                stats['removed_domain'] += 1
                continue
            
            if is_year_or_number(ido_word):
                stats['removed_year'] += 1
                continue
            
            if is_meta_page(ido_word):
                stats['removed_meta'] += 1
                continue
            
            if is_too_short(ido_word):
                stats['removed_short'] += 1
                continue
            
            if has_noise_characters(ido_word):
                stats['removed_noise'] += 1
                continue
            
            # Keep this entry
            stats['kept'] += 1
            if in_dict:
                stats['kept_in_dict'] += 1
            else:
                stats['kept_new'] += 1
            
            filtered_entries.append(row)
    
    # Save filtered vocabulary
    print(f"\nSaving filtered vocabulary to {output_file}...")
    
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        fieldnames = ['ido_word', 'esperanto_word', 'in_current_dict']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(filtered_entries)
    
    print(f"✓ Saved {len(filtered_entries)} filtered entries")
    
    # Print statistics
    print("\n" + "="*70)
    print("FILTERING STATISTICS")
    print("="*70)
    print(f"Total entries processed:      {stats['total']:6,}")
    print(f"\nRemoved:")
    print(f"  - Domain names:             {stats['removed_domain']:6,}")
    print(f"  - Years/numbers:            {stats['removed_year']:6,}")
    print(f"  - Meta pages:               {stats['removed_meta']:6,}")
    print(f"  - Too short:                {stats['removed_short']:6,}")
    print(f"  - Noise characters:         {stats['removed_noise']:6,}")
    total_removed = (stats['removed_domain'] + stats['removed_year'] + 
                    stats['removed_meta'] + stats['removed_short'] + stats['removed_noise'])
    print(f"  TOTAL REMOVED:              {total_removed:6,}")
    print(f"\nKept:")
    print(f"  - Already in dictionary:    {stats['kept_in_dict']:6,}")
    print(f"  - NEW words:                {stats['kept_new']:6,}")
    print(f"  TOTAL KEPT:                 {stats['kept']:6,}")
    print("="*70)
    
    # Calculate percentages
    if stats['total'] > 0:
        removal_pct = (total_removed / stats['total']) * 100
        new_words_pct = (stats['kept_new'] / stats['total']) * 100
        print(f"\nRemoval rate: {removal_pct:.1f}%")
        print(f"New useful words: {stats['kept_new']:,} ({new_words_pct:.1f}% of total)")


def main():
    input_file = 'ido_wiki_vocabulary_langlinks.csv'
    output_file = 'ido_wiki_vocabulary_filtered.csv'
    
    try:
        filter_vocabulary(input_file, output_file)
        print(f"\n✅ Filtering complete! Review {output_file}")
        return 0
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())

