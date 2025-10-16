#!/usr/bin/env python3
"""
Validate test additions by checking quality and structure.

This script:
1. Reviews what was added
2. Checks for potential issues
3. Validates morphology consistency
4. Generates quality report
"""

import json
import re
from collections import defaultdict


def load_added_entries(filepath: str = 'test_merge_added.json'):
    """Load added entries."""
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data['added']


def validate_morphology(entry: dict) -> tuple:
    """
    Validate morphology consistency.
    
    Returns: (is_valid, issues)
    """
    issues = []
    
    ido_word = entry.get('ido_word', '')
    morfologio = entry.get('morfologio', [])
    
    if not morfologio or len(morfologio) < 2:
        issues.append("Missing or incomplete morfologio")
        return False, issues
    
    root = morfologio[0]
    suffix = morfologio[1]
    
    # Check if root + suffix = ido_word
    expected = root + suffix[1:] if suffix.startswith('.') else root + suffix
    
    if expected.lower() != ido_word.lower():
        issues.append(f"Morphology mismatch: {root}+{suffix} ≠ {ido_word}")
        return False, issues
    
    return True, issues


def analyze_additions(entries: list):
    """Analyze quality of additions."""
    
    stats = {
        'total': len(entries),
        'valid_morphology': 0,
        'invalid_morphology': 0,
        'by_pos': defaultdict(int),
        'issues_found': 0,
    }
    
    problematic = []
    excellent = []
    
    for entry in entries:
        ido_word = entry.get('ido_word', '')
        pos = entry.get('part_of_speech', 'unknown')
        
        stats['by_pos'][pos] += 1
        
        # Validate morphology
        is_valid, issues = validate_morphology(entry)
        
        if is_valid:
            stats['valid_morphology'] += 1
            excellent.append(entry)
        else:
            stats['invalid_morphology'] += 1
            stats['issues_found'] += len(issues)
            problematic.append({
                'entry': entry,
                'issues': issues
            })
    
    return stats, problematic, excellent


def main():
    """Generate validation report."""
    
    print("="*70)
    print("TEST ADDITIONS VALIDATION REPORT")
    print("="*70)
    print()
    
    # Load additions
    try:
        added = load_added_entries()
        print(f"✓ Loaded {len(added)} added entries for validation")
    except FileNotFoundError:
        print("✗ test_merge_added.json not found")
        print("  Run test_merge.py first!")
        return 1
    
    print()
    
    # Analyze
    stats, problematic, excellent = analyze_additions(added)
    
    # Print statistics
    print("="*70)
    print("VALIDATION STATISTICS")
    print("="*70)
    print(f"Total entries added:          {stats['total']:6}")
    print()
    print("Morphology validation:")
    print(f"  - Valid:                    {stats['valid_morphology']:6}")
    print(f"  - Invalid/Issues:           {stats['invalid_morphology']:6}")
    print()
    print("By part of speech:")
    for pos, count in sorted(stats['by_pos'].items(), key=lambda x: -x[1]):
        print(f"  {pos:10} {count:6} entries")
    print()
    
    # Show problematic entries
    if problematic:
        print("="*70)
        print("PROBLEMATIC ENTRIES (for review)")
        print("="*70)
        for item in problematic[:15]:
            entry = item['entry']
            issues = item['issues']
            print(f"\n{entry['ido_word']} → {entry['esperanto_words'][0]}")
            print(f"  Morfologio: {entry.get('morfologio', [])}")
            print(f"  Issues: {', '.join(issues)}")
        
        if len(problematic) > 15:
            print(f"\n... and {len(problematic) - 15} more problematic entries")
    
    # Show excellent examples
    print()
    print("="*70)
    print("EXCELLENT ADDITIONS (sample)")
    print("="*70)
    
    # Group by POS for display
    by_pos_excellent = defaultdict(list)
    for entry in excellent:
        pos = entry.get('part_of_speech', 'unknown')
        by_pos_excellent[pos].append(entry)
    
    for pos in ['n', 'vblex', 'adj', 'adv']:
        if pos in by_pos_excellent:
            print(f"\n{pos.upper()} (sample):")
            for entry in by_pos_excellent[pos][:5]:
                ido = entry['ido_word']
                epo = entry['esperanto_words'][0]
                morfologio = ' + '.join(entry.get('morfologio', []))
                print(f"  {ido:20} → {epo:20} ({morfologio})")
    
    # Summary
    print()
    print("="*70)
    print("SUMMARY")
    print("="*70)
    
    valid_pct = (stats['valid_morphology'] / stats['total'] * 100) if stats['total'] > 0 else 0
    
    print(f"Total additions:              {stats['total']}")
    print(f"Valid morphology:             {stats['valid_morphology']} ({valid_pct:.1f}%)")
    print(f"Problematic:                  {stats['invalid_morphology']}")
    print()
    
    if stats['invalid_morphology'] == 0:
        print("✅ ALL ENTRIES VALID! Test dictionaries are good quality.")
    elif stats['invalid_morphology'] < 10:
        print("✅ MOSTLY VALID. Few issues, can proceed with testing.")
    else:
        print("⚠ SOME ISSUES. Review problematic entries before full merge.")
    
    print()
    print("Next step: Copy test dictionaries to main directory and build")
    
    return 0


if __name__ == '__main__':
    exit(main())

