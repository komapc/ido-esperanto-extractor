#!/usr/bin/env python3
"""
Create test Apertium dictionaries from test merged dictionary.

This uses the existing converter code but operates on test data.
"""

import sys
import os

# Import the existing converters
sys.path.insert(0, os.path.dirname(__file__))

from create_ido_monolingual import IdoMonolingualConverter
from create_ido_epo_bilingual import IdoEsperantoBilingualConverter


def main():
    """Create test dictionaries."""
    
    print("="*70)
    print("CREATING TEST APERTIUM DICTIONARIES")
    print("="*70)
    print()
    
    test_json = 'dictionary_merged_test.json'
    test_mono_output = 'apertium-ido.ido.TEST.dix'
    test_bi_output = 'apertium-ido-epo.ido-epo.TEST.dix'
    
    if not os.path.exists(test_json):
        print(f"✗ Test dictionary not found: {test_json}")
        print("  Run test_merge.py first!")
        return 1
    
    # Create monolingual dictionary
    print("Creating test monolingual dictionary...")
    print("-"*70)
    
    try:
        mono_converter = IdoMonolingualConverter(test_json)
        stats_mono = mono_converter.create_apertium_dix(test_mono_output)
        
        print()
        print("Monolingual statistics:")
        print(f"  Entries with morphology:    {stats_mono['with_morfologio']:5,}")
        print(f"  Entries without morphology: {stats_mono['without_morfologio']:5,}")
        print()
        print("By POS:")
        for pos, count in sorted(stats_mono['by_pos'].items(), key=lambda x: -x[1]):
            print(f"  {pos:10} {count:5,} entries")
        
    except Exception as e:
        print(f"✗ Error creating monolingual dictionary: {e}")
        return 1
    
    print()
    print("="*70)
    
    # Create bilingual dictionary
    print("Creating test bilingual dictionary...")
    print("-"*70)
    
    try:
        bi_converter = IdoEsperantoBilingualConverter(test_json)
        stats_bi = bi_converter.create_bilingual_dix(test_bi_output)
        
        print()
        print("Bilingual statistics:")
        print(f"  Valid translations:         {stats_bi['valid_translations']:5,}")
        print(f"  Skipped (no translation):   {stats_bi['skipped_no_translation']:5,}")
        print(f"  Skipped (invalid):          {stats_bi['skipped_invalid']:5,}")
        print()
        print("By POS:")
        for pos, count in sorted(stats_bi['by_pos'].items(), key=lambda x: -x[1]):
            print(f"  {pos:10} {count:5,} entries")
        
    except Exception as e:
        print(f"✗ Error creating bilingual dictionary: {e}")
        return 1
    
    print()
    print("="*70)
    print("TEST DICTIONARIES CREATED")
    print("="*70)
    print(f"  Monolingual: {test_mono_output}")
    print(f"  Bilingual:   {test_bi_output}")
    print()
    print("Next step: Validate XML and test translations")
    print()
    print("Commands:")
    print(f"  xmllint --noout {test_mono_output}")
    print(f"  xmllint --noout {test_bi_output}")
    print()
    print("✅ Test dictionaries ready for validation!")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())

