#!/usr/bin/env python3
"""
Dictionary Merger for Ido-Esperanto Bilingual Dictionary

This script merges the Ido→Esperanto and Esperanto→Ido dictionaries
into a unified bidirectional dictionary.

Usage:
    python3 merge_dictionaries.py
"""

import json
import argparse
from datetime import datetime
from typing import Dict, List, Any, Optional


class DictionaryMerger:
    def __init__(self):
        self.io_eo_dict = None
        self.eo_io_dict = None
        self.merged_dict = {}
        self.stats = {
            'ido_to_esperanto_entries': 0,
            'esperanto_to_ido_entries': 0,
            'bidirectional_entries': 0,
            'total_unique_words': 0
        }

    def load_dictionaries(self, io_eo_file: str = 'dictionary_io_eo.json', 
                         eo_io_file: str = 'dictionary_eo_io.json') -> None:
        """Load both dictionary files."""
        print(f"Loading Ido→Esperanto dictionary from {io_eo_file}...")
        with open(io_eo_file, 'r', encoding='utf-8') as f:
            self.io_eo_dict = json.load(f)
        
        print(f"Loading Esperanto→Ido dictionary from {eo_io_file}...")
        with open(eo_io_file, 'r', encoding='utf-8') as f:
            self.eo_io_dict = json.load(f)
        
        print(f"Loaded {self.io_eo_dict['metadata']['total_words']} Ido→Esperanto entries")
        print(f"Loaded {self.eo_io_dict['metadata']['total_words']} Esperanto→Ido entries")

    def normalize_word(self, word: str) -> str:
        """Normalize word for comparison (lowercase, strip whitespace)."""
        return word.lower().strip()

    def extract_translations(self, translations_list: List[List[str]]) -> List[str]:
        """Extract flat list of translations from nested structure."""
        flat_translations = []
        for meaning_group in translations_list:
            if isinstance(meaning_group, list):
                flat_translations.extend(meaning_group)
            else:
                flat_translations.append(meaning_group)
        return flat_translations

    def merge_entries(self) -> None:
        """Merge both dictionaries into a unified structure."""
        print("Merging dictionaries...")
        
        # Process Ido→Esperanto entries
        for entry in self.io_eo_dict['words']:
            ido_word = entry['ido_word']
            esperanto_translations = self.extract_translations(entry['esperanto_translations'])
            
            normalized_ido = self.normalize_word(ido_word)
            
            if normalized_ido not in self.merged_dict:
                self.merged_dict[normalized_ido] = {
                    'ido_word': ido_word,
                    'esperanto_words': [],
                    'metadata': {}
                }
            
            self.merged_dict[normalized_ido]['esperanto_words'].extend(esperanto_translations)
            
            # Copy metadata if available
            if 'morfologio' in entry:
                self.merged_dict[normalized_ido]['metadata']['morfologio'] = entry['morfologio']
            if 'part_of_speech' in entry:
                self.merged_dict[normalized_ido]['metadata']['part_of_speech'] = entry['part_of_speech']
        
        self.stats['ido_to_esperanto_entries'] = len(self.io_eo_dict['words'])
        
        # Process Esperanto→Ido entries
        for entry in self.eo_io_dict['words']:
            esperanto_word = entry['esperanto_word']
            ido_translations = self.extract_translations(entry['ido_translations'])
            
            # Find corresponding Ido word in merged dict
            found_ido_word = None
            for ido_key, merged_entry in self.merged_dict.items():
                if any(self.normalize_word(translation) == self.normalize_word(esperanto_word) 
                       for translation in merged_entry['esperanto_words']):
                    found_ido_word = ido_key
                    break
            
            if found_ido_word:
                # Add to existing entry
                if esperanto_word not in [self.normalize_word(w) for w in self.merged_dict[found_ido_word]['esperanto_words']]:
                    self.merged_dict[found_ido_word]['esperanto_words'].append(esperanto_word)
                self.stats['bidirectional_entries'] += 1
            else:
                # Create new entry using first Ido translation
                if ido_translations:
                    ido_word = ido_translations[0]
                    normalized_ido = self.normalize_word(ido_word)
                    
                    if normalized_ido not in self.merged_dict:
                        self.merged_dict[normalized_ido] = {
                            'ido_word': ido_word,
                            'esperanto_words': [],
                            'metadata': {}
                        }
                    
                    self.merged_dict[normalized_ido]['esperanto_words'].append(esperanto_word)
            
            # Copy metadata if available
            if 'part_of_speech' in entry:
                if found_ido_word:
                    self.merged_dict[found_ido_word]['metadata']['part_of_speech'] = entry['part_of_speech']
        
        self.stats['esperanto_to_ido_entries'] = len(self.eo_io_dict['words'])
        
        # Remove duplicates and sort
        for entry in self.merged_dict.values():
            entry['esperanto_words'] = list(set(entry['esperanto_words']))
            entry['esperanto_words'].sort()
        
        self.stats['total_unique_words'] = len(self.merged_dict)

    def create_merged_dictionary(self) -> Dict[str, Any]:
        """Create the final merged dictionary structure."""
        merged_entries = []
        
        for normalized_ido, entry_data in sorted(self.merged_dict.items()):
            merged_entry = {
                'ido_word': entry_data['ido_word'],
                'esperanto_words': entry_data['esperanto_words']
            }
            
            # Add metadata if available
            if entry_data['metadata']:
                merged_entry.update(entry_data['metadata'])
            
            merged_entries.append(merged_entry)
        
        # Create merged metadata
        merged_metadata = {
            'creation_date': datetime.now().isoformat(),
            'source_io_eo_dict': {
                'file': 'dictionary_io_eo.json',
                'entries': self.io_eo_dict['metadata']['total_words'],
                'extraction_date': self.io_eo_dict['metadata']['extraction_date'],
                'source_dump': self.io_eo_dict['metadata']['source_dump']
            },
            'source_eo_io_dict': {
                'file': 'dictionary_eo_io.json',
                'entries': self.eo_io_dict['metadata']['total_words'],
                'extraction_date': self.eo_io_dict['metadata']['extraction_date'],
                'source_dump': self.eo_io_dict['metadata']['source_dump']
            },
            'merge_stats': self.stats,
            'total_unique_ido_words': self.stats['total_unique_words']
        }
        
        return {
            'metadata': merged_metadata,
            'words': merged_entries
        }

    def save_merged_dictionary(self, output_file: str = 'dictionary_merged.json') -> None:
        """Save the merged dictionary to file."""
        print(f"Saving merged dictionary to {output_file}...")
        
        merged_dict = self.create_merged_dictionary()
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(merged_dict, f, ensure_ascii=False, indent=2)
        
        print(f"✓ Merged dictionary saved: {output_file}")
        print(f"✓ Total unique Ido words: {self.stats['total_unique_words']}")
        print(f"✓ Ido→Esperanto entries: {self.stats['ido_to_esperanto_entries']}")
        print(f"✓ Esperanto→Ido entries: {self.stats['esperanto_to_ido_entries']}")
        print(f"✓ Bidirectional entries: {self.stats['bidirectional_entries']}")

    def print_sample_entries(self, count: int = 5) -> None:
        """Print sample entries from the merged dictionary."""
        print(f"\n📖 Sample merged entries:")
        print("=" * 50)
        
        merged_dict = self.create_merged_dictionary()
        
        for i, entry in enumerate(merged_dict['words'][:count]):
            print(f"\n{i+1}. {entry['ido_word']}")
            print(f"   Esperanto: {', '.join(entry['esperanto_words'])}")
            if 'morfologio' in entry:
                print(f"   Morphology: {entry['morfologio']}")
            if 'part_of_speech' in entry:
                print(f"   Part of speech: {entry['part_of_speech']}")


def main():
    parser = argparse.ArgumentParser(description='Merge Ido-Esperanto dictionaries')
    parser.add_argument('--io-eo-file', default='dictionary_io_eo.json',
                       help='Ido→Esperanto dictionary file (default: dictionary_io_eo.json)')
    parser.add_argument('--eo-io-file', default='dictionary_eo_io.json',
                       help='Esperanto→Ido dictionary file (default: dictionary_eo_io.json)')
    parser.add_argument('--output', '-o', default='dictionary_merged.json',
                       help='Output file for merged dictionary (default: dictionary_merged.json)')
    parser.add_argument('--sample', type=int, default=5,
                       help='Number of sample entries to display (default: 5)')
    
    args = parser.parse_args()
    
    print("🔄 Ido-Esperanto Dictionary Merger")
    print("=" * 40)
    
    merger = DictionaryMerger()
    
    try:
        merger.load_dictionaries(args.io_eo_file, args.eo_io_file)
        merger.merge_entries()
        merger.save_merged_dictionary(args.output)
        merger.print_sample_entries(args.sample)
        
        print(f"\n✅ Dictionary merge completed successfully!")
        
    except FileNotFoundError as e:
        print(f"❌ Error: File not found - {e}")
        return 1
    except json.JSONDecodeError as e:
        print(f"❌ Error: Invalid JSON - {e}")
        return 1
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1
    
    return 0


if __name__ == '__main__':
    exit(main())
