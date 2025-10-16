#!/usr/bin/env python3
"""
Smart categorization using simple, reliable rules.

SIMPLE RULE:
- If Ido word starts with LOWERCASE → VOCABULARY
- If Ido word starts with UPPERCASE → Check further
  - Has geographic keyword → GEOGRAPHIC
  - Identical to Esperanto → GEOGRAPHIC (borrowed place name)
  - Otherwise → VOCABULARY (might be technical term like "Aborto")
"""

import json
from collections import defaultdict


class SmartCategorizer:
    """Simple, reliable categorization."""
    
    GEO_KEYWORDS = [
        'urbo', 'provinco', 'distrikto', 'gubernio', 'regiono',
        'insulo', 'monto', 'rivero', 'lago', 'oceano', 'maro',
        'lando', 'regno', 'imperio', 'respubliko', 'ŝtato',
        'kontinento', 'golfo', 'duoninsulo', 'arkipelago'
    ]
    
    def __init__(self):
        self.stats = {
            'total': 0,
            'vocabulary': 0,
            'geographic': 0,
            'lowercase': 0,
            'uppercase_vocab': 0,
            'uppercase_geo': 0,
        }
    
    def categorize(self, entry: dict) -> str:
        """
        Categorize using simple reliable rules.
        
        Returns: 'vocabulary' or 'geographic'
        """
        ido_word = entry['ido_word']
        esperanto_words = entry.get('esperanto_words', [])
        esperanto_word = esperanto_words[0] if esperanto_words else ''
        
        # RULE 1: Lowercase Ido word = VOCABULARY (100% confidence)
        if ido_word[0].islower():
            self.stats['lowercase'] += 1
            self.stats['vocabulary'] += 1
            return 'vocabulary'
        
        # RULE 2: Uppercase - need to check further
        epo_lower = esperanto_word.lower()
        
        # Sub-rule 2a: Has geographic keyword = GEOGRAPHIC
        for keyword in self.GEO_KEYWORDS:
            if keyword in epo_lower:
                self.stats['uppercase_geo'] += 1
                self.stats['geographic'] += 1
                return 'geographic'
        
        # Sub-rule 2b: Identical + uppercase = GEOGRAPHIC (borrowed place name)
        if ido_word == esperanto_word:
            self.stats['uppercase_geo'] += 1
            self.stats['geographic'] += 1
            return 'geographic'
        
        # Sub-rule 2c: Otherwise = VOCABULARY (technical/medical term)
        # Examples: "Aborto", "Albumino", "Adenino" (international scientific terms)
        self.stats['uppercase_vocab'] += 1
        self.stats['vocabulary'] += 1
        return 'vocabulary'
    
    def process(self, input_file: str):
        """Process vocabulary file."""
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        words = data.get('words', [])
        self.stats['total'] = len(words)
        
        categorized = {
            'vocabulary': [],
            'geographic': []
        }
        
        for entry in words:
            category = self.categorize(entry)
            categorized[category].append(entry)
        
        return categorized, data.get('metadata', {})


def main():
    """Smart categorization."""
    
    print("="*70)
    print("SMART CATEGORIZATION (Simple + Reliable)")
    print("="*70)
    print()
    
    categorizer = SmartCategorizer()
    
    input_file = 'wikipedia_vocabulary_with_morphology.json'
    
    try:
        categorized, metadata = categorizer.process(input_file)
    except FileNotFoundError:
        print(f"✗ Input file not found: {input_file}")
        return 1
    
    # Save files
    for category, entries in categorized.items():
        output_file = f'final_{category}.json'
        
        output_data = {
            'metadata': {
                **metadata,
                'category': category,
                'categorization_date': '2025-10-16',
                'total_entries': len(entries),
                'method': 'smart_simple'
            },
            'words': entries
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        
        print(f"✓ Saved {len(entries):5,} {category:12} entries → {output_file}")
    
    # Statistics
    print()
    print("="*70)
    print("CATEGORIZATION STATISTICS")
    print("="*70)
    print(f"Total processed:              {categorizer.stats['total']:6,}")
    print()
    print("By category:")
    print(f"  - Vocabulary (pure):        {categorizer.stats['vocabulary']:6,}")
    print(f"  - Geographic names:         {categorizer.stats['geographic']:6,}")
    print()
    print("Vocabulary breakdown:")
    print(f"  - Lowercase (certain):      {categorizer.stats['lowercase']:6,}")
    print(f"  - Uppercase (technical):    {categorizer.stats['uppercase_vocab']:6,}")
    print()
    print("Geographic breakdown:")
    print(f"  - With geo keyword:         {categorizer.stats['uppercase_geo']:6,}")
    print("="*70)
    
    vocab_pct = (categorizer.stats['vocabulary'] / categorizer.stats['total'] * 100)
    geo_pct = (categorizer.stats['geographic'] / categorizer.stats['total'] * 100)
    
    print(f"\nVocabulary: {vocab_pct:.1f}%")
    print(f"Geographic: {geo_pct:.1f}%")
    print()
    print("✅ Smart categorization complete!")
    print()
    print(f"📚 Ready to use: final_vocabulary.json ({categorizer.stats['vocabulary']:,} entries)")
    print(f"🌍 Geographic names: final_geographic.json ({categorizer.stats['geographic']:,} entries)")


if __name__ == '__main__':
    exit(main())

