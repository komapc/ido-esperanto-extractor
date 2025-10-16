#!/usr/bin/env python3
"""
Detect and separate geographic names from vocabulary.

Strategy:
1. Check if Esperanto translation is capitalized (indicates proper noun)
2. Check for geographic keywords in translation
3. Check if identical + capitalized (likely borrowed place name)
4. Cross-reference with known geographic lists
5. Pattern matching for cities/countries

This will split vocabulary into:
- Pure vocabulary (lowercase or common terms)
- Geographic names (for proper noun dictionary)
- Ambiguous (for manual review)
"""

import json
import re
from collections import defaultdict


class GeographicNameDetector:
    """Detect geographic names in vocabulary."""
    
    # Geographic indicators in Esperanto
    GEO_KEYWORDS = [
        'urbo', 'provinco', 'distrikto', 'gubernio', 'regiono',
        'insulo', 'monto', 'rivero', 'lago', 'oceano', 'maro',
        'lando', 'regno', 'imperio', 'respubliko', 'ŝtato',
        'kontinento', 'parto', 'golfo', 'duoninsulo'
    ]
    
    # Common city/country name patterns
    PLACE_SUFFIXES = [
        'polis', 'grad', 'burg', 'ville', 'town', 'city',
        'land', 'stan', 'ia'
    ]
    
    def __init__(self):
        self.stats = {
            'total': 0,
            'geographic': 0,
            'vocabulary': 0,
            'ambiguous': 0,
            'by_indicator': defaultdict(int),
        }
    
    def is_geographic_name(self, ido_word: str, esperanto_word: str) -> tuple:
        """
        Check if entry is a geographic name.
        
        Returns: (is_geographic, confidence, reason)
        """
        indicators = []
        
        # NOTE: We can't use capitalization alone because Wikipedia titles are always capitalized
        
        # STRONG Indicator 1: Contains geographic keyword in Esperanto
        epo_lower = esperanto_word.lower()
        has_geo_keyword = False
        for keyword in self.GEO_KEYWORDS:
            if keyword in epo_lower:
                indicators.append(f'has_{keyword}')
                self.stats['by_indicator'][keyword] += 1
                has_geo_keyword = True
        
        # STRONG Indicator 2: Identical + capitalized (borrowed place name)
        if ido_word == esperanto_word and ido_word[0].isupper():
            indicators.append('identical_capitalized')
        
        # MEDIUM Indicator 3: Esperanto has common place suffix patterns
        for suffix in self.PLACE_SUFFIXES:
            if epo_lower.endswith(suffix):
                indicators.append(f'suffix_{suffix}')
        
        # WEAK Indicator 4: Both capitalized BUT no Ido grammatical ending
        # This catches "Stockholm" but not "Stokholmo"
        if (ido_word[0].isupper() and esperanto_word[0].isupper() and 
            not ido_word.lower().endswith(('o', 'a', 'e', 'i', 'ar'))):
            indicators.append('both_capital_no_ending')
        
        # Decision logic (much more conservative)
        # Geographic only if:
        # - Has geographic keyword (STRONG evidence)
        # - OR identical+capitalized (likely borrowed place name)
        # - OR has place suffix + capitalized
        
        if has_geo_keyword:
            return True, 'high', indicators
        elif 'identical_capitalized' in indicators:
            return True, 'high', indicators
        elif any('suffix_' in ind for ind in indicators) and ido_word[0].isupper():
            return True, 'medium', indicators
        elif 'both_capital_no_ending' in indicators:
            return True, 'medium', indicators
        else:
            return False, 'low', indicators
    
    def categorize_entry(self, entry: dict) -> str:
        """
        Categorize entry as geographic, vocabulary, or ambiguous.
        
        Returns: 'geographic', 'vocabulary', 'ambiguous'
        """
        ido_word = entry['ido_word']
        esperanto_words = entry.get('esperanto_words', [])
        esperanto_word = esperanto_words[0] if esperanto_words else ''
        
        is_geo, confidence, indicators = self.is_geographic_name(ido_word, esperanto_word)
        
        # Store detection info
        entry['geo_detection'] = {
            'is_geographic': is_geo,
            'confidence': confidence,
            'indicators': indicators
        }
        
        if is_geo and confidence in ['high', 'medium']:
            self.stats['geographic'] += 1
            return 'geographic'
        elif not is_geo:
            self.stats['vocabulary'] += 1
            return 'vocabulary'
        else:
            self.stats['ambiguous'] += 1
            return 'ambiguous'
    
    def process_vocabulary(self, input_file: str):
        """Process vocabulary and split into categories."""
        
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        words = data.get('words', [])
        self.stats['total'] = len(words)
        
        categorized = {
            'geographic': [],
            'vocabulary': [],
            'ambiguous': []
        }
        
        for entry in words:
            category = self.categorize_entry(entry)
            categorized[category].append(entry)
        
        return categorized, data.get('metadata', {})


def main():
    """Detect and separate geographic names."""
    
    print("="*70)
    print("GEOGRAPHIC NAME DETECTION")
    print("="*70)
    print()
    
    detector = GeographicNameDetector()
    
    input_file = 'wikipedia_vocabulary_with_morphology.json'
    
    try:
        categorized, metadata = detector.process_vocabulary(input_file)
    except FileNotFoundError:
        print(f"✗ Input file not found: {input_file}")
        return 1
    
    # Save categorized files
    for category, entries in categorized.items():
        output_file = f'vocabulary_{category}.json'
        
        output_data = {
            'metadata': {
                **metadata,
                'category': category,
                'filtered_date': '2025-10-16',
                'total_entries': len(entries)
            },
            'words': entries
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        
        print(f"✓ Saved {len(entries):5,} {category:12} entries → {output_file}")
    
    # Statistics
    print()
    print("="*70)
    print("DETECTION STATISTICS")
    print("="*70)
    print(f"Total processed:              {detector.stats['total']:6,}")
    print()
    print("Categorized as:")
    print(f"  - Geographic names:         {detector.stats['geographic']:6,}")
    print(f"  - Vocabulary (pure):        {detector.stats['vocabulary']:6,}")
    print(f"  - Ambiguous (review):       {detector.stats['ambiguous']:6,}")
    print()
    print("Geographic indicators found:")
    for indicator, count in sorted(detector.stats['by_indicator'].items(), key=lambda x: -x[1])[:10]:
        print(f"  - {indicator:20} {count:6,} times")
    print("="*70)
    
    geo_pct = (detector.stats['geographic'] / detector.stats['total'] * 100) if detector.stats['total'] > 0 else 0
    vocab_pct = (detector.stats['vocabulary'] / detector.stats['total'] * 100) if detector.stats['total'] > 0 else 0
    
    print(f"\nGeographic names: {geo_pct:.1f}% of total")
    print(f"Pure vocabulary: {vocab_pct:.1f}% of total")
    print()
    print("✅ Vocabulary split complete!")
    print()
    print("Next: Generate new test sample from 'vocabulary_vocabulary.json'")


if __name__ == '__main__':
    exit(main())

