#!/usr/bin/env python3
"""
Advanced filtering for Wikipedia vocabulary.

Applies strict quality criteria:
1. Remove multi-capital names (person names)
2. Remove suspicious identical pairs
3. Remove multi-hyphen compounds (likely article titles)
4. Clean Esperanto translations (remove parentheses, flag for review)
5. Remove entries with 3+ word Esperanto translations
6. Cross-validate with Wiktionary extraction (optional boost, not filter)

Output: High-quality vocabulary ready for morphology analysis
"""

import csv
import json
import re
from typing import List, Dict, Tuple


class AdvancedVocabularyFilter:
    def __init__(self, wiktionary_file: str = 'dictionary_io_eo.json'):
        """Initialize filter with Wiktionary data for reference."""
        self.wiktionary_words = set()
        
        # Load Wiktionary data
        try:
            with open(wiktionary_file, 'r', encoding='utf-8') as f:
                wikt_data = json.load(f)
                for entry in wikt_data.get('words', []):
                    ido_word = entry.get('ido_word', '').lower()
                    if ido_word:
                        self.wiktionary_words.add(ido_word)
                print(f"✓ Loaded {len(self.wiktionary_words):,} Wiktionary words for reference")
        except FileNotFoundError:
            print(f"⚠ Wiktionary file not found, continuing without cross-reference")
        
        self.stats = {
            'total': 0,
            'removed_multi_capital': 0,
            'removed_suspicious_identical': 0,
            'removed_multi_hyphen': 0,
            'removed_long_translation': 0,
            'flagged_parentheses': 0,
            'in_wiktionary': 0,
            'not_in_wiktionary': 0,
            'kept': 0,
        }
    
    def has_multi_capital_words(self, text: str) -> bool:
        """Check if text has multiple capitalized words (person name pattern)."""
        words = text.split()
        if len(words) < 2:
            return False
        
        # Count words starting with capital
        capital_count = sum(1 for w in words if w and w[0].isupper())
        
        # If 2+ capitalized words = likely person name
        return capital_count >= 2
    
    def is_suspicious_identical(self, ido: str, epo: str) -> bool:
        """Check if identical pair is suspicious (likely proper name)."""
        if ido != epo:
            return False
        
        # Identical words are OK if:
        # 1. They have Ido grammatical endings
        ido_endings = ['o', 'a', 'e', 'i', 'ar', 'ir', 'or', 'as', 'is', 'os', 'us', 'ez']
        for ending in ido_endings:
            if ido.lower().endswith(ending):
                return False  # Has ending, keep it
        
        # 2. They're in Wiktionary (validated)
        if ido.lower() in self.wiktionary_words:
            return False  # In Wiktionary, keep it
        
        # Otherwise, suspicious (probably proper name)
        return True
    
    def has_multi_hyphen(self, text: str) -> bool:
        """Check if text has 2+ hyphens (complex compound, likely article title)."""
        return text.count('-') >= 2
    
    def clean_esperanto_translation(self, epo: str) -> Tuple[str, bool]:
        """
        Clean Esperanto translation and flag if modified.
        
        Returns: (cleaned_translation, was_flagged)
        """
        original = epo
        flagged = False
        
        # Remove content in parentheses
        if '(' in epo:
            epo = re.sub(r'\s*\([^)]+\)', '', epo).strip()
            flagged = True
        
        # Remove extra whitespace
        epo = re.sub(r'\s+', ' ', epo).strip()
        
        return epo, flagged
    
    def has_long_translation(self, epo: str) -> bool:
        """Check if Esperanto translation is 3+ words (might be definition)."""
        # After cleaning, check word count
        words = epo.split()
        return len(words) >= 3
    
    def filter_entry(self, row: Dict) -> Tuple[bool, Dict]:
        """
        Filter a single entry.
        
        Returns: (keep_entry, modified_row)
        """
        ido = row['ido_word']
        epo = row['esperanto_word']
        
        # Filter 1: Multi-capital names (person names)
        if self.has_multi_capital_words(ido):
            self.stats['removed_multi_capital'] += 1
            return False, row
        
        # Filter 2: Suspicious identical pairs
        if self.is_suspicious_identical(ido, epo):
            self.stats['removed_suspicious_identical'] += 1
            return False, row
        
        # Filter 3: Multi-hyphen compounds
        if self.has_multi_hyphen(ido):
            self.stats['removed_multi_hyphen'] += 1
            return False, row
        
        # Clean Esperanto translation
        epo_clean, was_flagged = self.clean_esperanto_translation(epo)
        
        if was_flagged:
            self.stats['flagged_parentheses'] += 1
            row['review_flag'] = 'parentheses_removed'
        
        # Update row with cleaned translation
        row['esperanto_word'] = epo_clean
        
        # Filter 4: Long translations (might be definitions)
        if self.has_long_translation(epo_clean):
            self.stats['removed_long_translation'] += 1
            return False, row
        
        # Track Wiktionary presence (for info only, not filtering)
        if ido.lower() in self.wiktionary_words:
            self.stats['in_wiktionary'] += 1
            row['in_wiktionary'] = 'yes'
        else:
            self.stats['not_in_wiktionary'] += 1
            row['in_wiktionary'] = 'no'
        
        return True, row
    
    def process_file(self, input_file: str, output_file: str) -> int:
        """Process a vocabulary file."""
        entries = []
        
        with open(input_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                self.stats['total'] += 1
                
                keep, modified_row = self.filter_entry(row)
                
                if keep:
                    self.stats['kept'] += 1
                    entries.append(modified_row)
        
        # Save filtered entries
        if entries:
            # Determine fieldnames
            fieldnames = ['ido_word', 'esperanto_word', 'in_current_dict', 'in_wiktionary']
            if any('review_flag' in e for e in entries):
                fieldnames.append('review_flag')
            
            with open(output_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
                writer.writeheader()
                writer.writerows(entries)
        
        return len(entries)


def main():
    """Apply advanced filtering to all vocabulary files."""
    
    print("="*70)
    print("ADVANCED VOCABULARY FILTERING")
    print("="*70)
    print()
    
    filter_engine = AdvancedVocabularyFilter()
    
    files = [
        ('ido_wiki_vocab_vocabulary_final.csv', 'ido_wiki_vocab_advanced.csv', 'Vocabulary'),
        ('ido_wiki_vocab_geographic_final.csv', 'ido_wiki_vocab_geographic_advanced.csv', 'Geographic'),
        ('ido_wiki_vocab_other_final.csv', 'ido_wiki_vocab_other_advanced.csv', 'Other'),
    ]
    
    for input_file, output_file, category in files:
        try:
            print(f"Processing {category}...")
            count = filter_engine.process_file(input_file, output_file)
            print(f"  ✓ Saved {count:,} entries to {output_file}")
            print()
        except FileNotFoundError:
            print(f"  ⚠ File not found: {input_file}\n")
    
    # Print statistics
    print("="*70)
    print("ADVANCED FILTERING STATISTICS")
    print("="*70)
    print(f"Total processed:              {filter_engine.stats['total']:6,}")
    print()
    print("Removed:")
    print(f"  - Multi-capital names:      {filter_engine.stats['removed_multi_capital']:6,}")
    print(f"  - Suspicious identical:     {filter_engine.stats['removed_suspicious_identical']:6,}")
    print(f"  - Multi-hyphen compounds:   {filter_engine.stats['removed_multi_hyphen']:6,}")
    print(f"  - Long translations (3+ w): {filter_engine.stats['removed_long_translation']:6,}")
    
    total_removed = filter_engine.stats['total'] - filter_engine.stats['kept']
    print(f"  TOTAL REMOVED:              {total_removed:6,}")
    print()
    print(f"Kept (advanced clean):        {filter_engine.stats['kept']:6,}")
    print()
    print("Additional info:")
    print(f"  - Flagged for review:       {filter_engine.stats['flagged_parentheses']:6,}")
    print(f"  - In Wiktionary (bonus):    {filter_engine.stats['in_wiktionary']:6,}")
    print(f"  - Not in Wiktionary:        {filter_engine.stats['not_in_wiktionary']:6,}")
    print("="*70)
    
    removal_pct = (total_removed / filter_engine.stats['total'] * 100) if filter_engine.stats['total'] > 0 else 0
    wikt_pct = (filter_engine.stats['in_wiktionary'] / filter_engine.stats['kept'] * 100) if filter_engine.stats['kept'] > 0 else 0
    
    print(f"\nRemoval rate: {removal_pct:.1f}%")
    print(f"Wiktionary validation: {wikt_pct:.1f}% of kept entries")
    print(f"\n🎉 Advanced filtering complete: {filter_engine.stats['kept']:,} entries ready")


if __name__ == '__main__':
    main()

