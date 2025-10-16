#!/usr/bin/env python3
"""
Add morphology analysis to vocabulary entries.

For each Ido word:
1. Extract root and suffix
2. Generate morfologio field
3. Infer part of speech
4. Extract Esperanto root (keep full lemma)
5. Validate consistency

Uses simple approach - ignores complex derivational morphology.
"""

import csv
import json
import re
from typing import Optional, Tuple, List, Dict


class MorphologyAnalyzer:
    """Analyze Ido morphology and add to vocabulary entries."""
    
    # Ido grammatical suffixes (ordered by length - longest first)
    SUFFIXES = [
        # Verb forms
        ('.ar', 'vblex', 'inf'),   # infinitive
        ('.ir', 'vblex', 'inf'),   # passive infinitive
        ('.or', 'vblex', 'inf'),   # future infinitive
        ('.as', 'vblex', 'pri'),   # present
        ('.is', 'vblex', 'pii'),   # past
        ('.os', 'vblex', 'fti'),   # future
        ('.us', 'vblex', 'cni'),   # conditional
        ('.ez', 'vblex', 'imp'),   # imperative
        # Noun forms
        ('.on', 'n', 'acc'),       # accusative singular
        ('.in', 'n', 'acc'),       # accusative plural
        ('.o', 'n', 'nom'),        # nominative singular
        ('.i', 'n', 'nom'),        # nominative plural
        # Adjective/Adverb
        ('.a', 'adj', ''),         # adjective
        ('.e', 'adv', ''),         # adverb
    ]
    
    def __init__(self):
        self.stats = {
            'total': 0,
            'found_morphology': 0,
            'failed_morphology': 0,
            'by_pos': {},
        }
        self.failed_cases = []
    
    def extract_ido_morphology(self, ido_word: str) -> Optional[Tuple[str, str, str]]:
        """
        Extract Ido root, suffix, and POS.
        
        Returns: (root, suffix, pos) or None
        
        Examples:
          "aborto" → ("abort", ".o", "n")
          "acelerar" → ("aceler", ".ar", "vblex")
          "abstrakta" → ("abstrakt", ".a", "adj")
        """
        if not ido_word or len(ido_word) < 2:
            return None
        
        # Try each suffix pattern (longest first)
        for suffix, pos, subpos in self.SUFFIXES:
            suffix_without_dot = suffix[1:]  # Remove the dot
            
            if ido_word.lower().endswith(suffix_without_dot):
                # Extract root
                root = ido_word[:-len(suffix_without_dot)]
                
                # Validate root length (must be at least 2 chars)
                if len(root) >= 2:
                    return (root, suffix, pos)
        
        # No suffix matched
        return None
    
    def extract_esperanto_root(self, epo_word: str, pos: str) -> str:
        """
        Extract Esperanto root based on POS.
        
        For now, we keep the full lemma (as per current dictionary practice).
        This matches the existing bilingual dictionary structure.
        
        Returns: full lemma (unchanged)
        """
        # Current dictionary uses full Esperanto lemmas
        # Example: "lifto" not "lift"
        return epo_word.strip()
    
    def analyze_entry(self, row: Dict) -> Optional[Dict]:
        """
        Analyze morphology for an entry.
        
        Returns: enriched entry dict or None if failed
        """
        self.stats['total'] += 1
        
        ido_word = row['ido_word']
        epo_word = row['esperanto_word']
        
        # Extract Ido morphology
        morphology = self.extract_ido_morphology(ido_word)
        
        if not morphology:
            self.stats['failed_morphology'] += 1
            self.failed_cases.append(f"{ido_word} → {epo_word}")
            return None
        
        root, suffix, pos = morphology
        
        self.stats['found_morphology'] += 1
        self.stats['by_pos'][pos] = self.stats['by_pos'].get(pos, 0) + 1
        
        # Extract Esperanto root (full lemma)
        epo_root = self.extract_esperanto_root(epo_word, pos)
        
        # Create enriched entry
        enriched = {
            'ido_word': ido_word,
            'esperanto_words': [epo_root],  # Note: array format for consistency
            'morfologio': [root, suffix],
            'part_of_speech': pos,
            'source': 'wikipedia',
        }
        
        # Copy additional fields
        if 'review_flag' in row:
            enriched['review_flag'] = row['review_flag']
        if 'in_wiktionary' in row:
            enriched['in_wiktionary'] = row['in_wiktionary']
        
        return enriched


def process_vocabulary_files():
    """Process all advanced filtered files and add morphology."""
    
    print("="*70)
    print("MORPHOLOGY ANALYSIS")
    print("="*70)
    print()
    
    files = [
        ('ido_wiki_vocab_advanced.csv', 'Vocabulary'),
        ('ido_wiki_vocab_geographic_advanced.csv', 'Geographic'),
        ('ido_wiki_vocab_other_advanced.csv', 'Other'),
    ]
    
    analyzer = MorphologyAnalyzer()
    all_entries = []
    
    for filename, category in files:
        try:
            print(f"Analyzing {category} ({filename})...")
            
            with open(filename, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                
                for row in reader:
                    enriched = analyzer.analyze_entry(row)
                    if enriched:
                        all_entries.append(enriched)
            
            print(f"  ✓ Processed")
            
        except FileNotFoundError:
            print(f"  ⚠ File not found: {filename}")
    
    # Save to JSON
    output_file = 'wikipedia_vocabulary_with_morphology.json'
    
    output_data = {
        'metadata': {
            'extraction_date': '2025-10-16',
            'source': 'Ido Wikipedia (langlinks)',
            'total_entries': len(all_entries),
            'stats': analyzer.stats,
        },
        'words': all_entries
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    
    print()
    print("="*70)
    print("MORPHOLOGY ANALYSIS COMPLETE")
    print("="*70)
    print(f"Total processed:              {analyzer.stats['total']:6,}")
    print(f"  - Morphology extracted:     {analyzer.stats['found_morphology']:6,}")
    print(f"  - Failed (no pattern):      {analyzer.stats['failed_morphology']:6,}")
    print()
    print("By part of speech:")
    for pos, count in sorted(analyzer.stats['by_pos'].items(), key=lambda x: -x[1]):
        print(f"  - {pos:10} {count:6,} entries")
    print()
    print(f"Saved to: {output_file}")
    print(f"Total entries: {len(all_entries):,}")
    
    if analyzer.failed_cases and len(analyzer.failed_cases) <= 20:
        print()
        print("Failed cases (no morphology pattern found):")
        for case in analyzer.failed_cases[:20]:
            print(f"  {case}")
    
    print()
    print("✅ Ready for test sample generation!")
    
    return output_file, len(all_entries)


if __name__ == '__main__':
    process_vocabulary_files()

