#!/usr/bin/env python3
"""
Full merge of Wikipedia vocabulary with current dictionary.

This script:
1. Backs up current dictionary
2. Merges all Wikipedia entries (keeping existing on conflicts)
3. Sorts alphabetically
4. Saves enhanced dictionary
5. Generates detailed report
"""

import json
import shutil
from datetime import datetime
from collections import defaultdict


def backup_current_dictionary(source: str = 'dictionary_merged.json'):
    """Create backup of current dictionary."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_file = f'dictionary_merged_backup_{timestamp}.json'
    
    shutil.copy(source, backup_file)
    print(f"✓ Backup created: {backup_file}")
    return backup_file


def load_dictionaries():
    """Load current and Wikipedia dictionaries."""
    # Current dictionary
    with open('dictionary_merged.json', 'r', encoding='utf-8') as f:
        current = json.load(f)
    
    # Wikipedia vocabulary
    with open('wikipedia_vocabulary_merge_ready.json', 'r', encoding='utf-8') as f:
        wikipedia = json.load(f)
    
    return current, wikipedia


def merge_dictionaries(current: dict, wikipedia: dict):
    """
    Merge Wikipedia vocabulary into current dictionary.
    
    Strategy: Keep existing entries on conflicts
    """
    
    stats = {
        'current_entries': len(current['words']),
        'wikipedia_entries': len(wikipedia['words']),
        'added': 0,
        'skipped_exists': 0,
        'skipped_conflict': 0,
        'by_pos_added': defaultdict(int),
        'by_source': defaultdict(int),
    }
    
    # Create lookup
    existing = {}
    for entry in current['words']:
        key = entry['ido_word'].lower()
        existing[key] = entry
    
    # Track additions
    added_entries = []
    skipped_entries = []
    
    print("Merging Wikipedia vocabulary...")
    print()
    
    for entry in wikipedia['words']:
        ido_word = entry['ido_word']
        key = ido_word.lower()
        
        # Check if exists
        if key in existing:
            stats['skipped_exists'] += 1
            skipped_entries.append({
                'ido_word': ido_word,
                'reason': 'exists',
                'current': existing[key],
                'new': entry
            })
            continue
        
        # Add entry
        stats['added'] += 1
        pos = entry.get('part_of_speech', 'unknown')
        stats['by_pos_added'][pos] += 1
        
        added_entries.append(entry)
        current['words'].append(entry)
        
        # Progress indicator
        if stats['added'] % 500 == 0:
            print(f"  Added {stats['added']:,} entries...")
    
    # Sort alphabetically
    current['words'].sort(key=lambda x: x['ido_word'].lower())
    
    stats['total_after'] = len(current['words'])
    
    return current, stats, added_entries, skipped_entries


def save_enhanced_dictionary(dict_data: dict, output_file: str = 'dictionary_merged_enhanced.json'):
    """Save enhanced dictionary."""
    
    # Update metadata
    dict_data['metadata']['last_updated'] = datetime.now().isoformat()
    dict_data['metadata']['wikipedia_integration'] = {
        'date': '2025-10-16',
        'entries_added': len(dict_data['words']) - 7809,  # Approximate
        'source': 'Ido Wikipedia langlinks'
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(dict_data, f, ensure_ascii=False, indent=2)
    
    print(f"✓ Saved enhanced dictionary: {output_file}")


def generate_report(stats: dict, added: list, skipped: list):
    """Generate detailed merge report."""
    
    report = []
    report.append("="*70)
    report.append("FULL MERGE REPORT")
    report.append("="*70)
    report.append(f"Date: {datetime.now().isoformat()}")
    report.append("")
    report.append("MERGE STATISTICS")
    report.append("-"*70)
    report.append(f"Current dictionary size:      {stats['current_entries']:6,} entries")
    report.append(f"Wikipedia vocabulary:         {stats['wikipedia_entries']:6,} entries")
    report.append("")
    report.append(f"Added to dictionary:          {stats['added']:6,} entries")
    report.append(f"Skipped (already exists):     {stats['skipped_exists']:6,} entries")
    report.append("")
    report.append(f"Final dictionary size:        {stats['total_after']:6,} entries")
    report.append(f"Growth:                       +{stats['added']/stats['current_entries']*100:.1f}%")
    report.append("")
    report.append("ADDITIONS BY POS")
    report.append("-"*70)
    for pos, count in sorted(stats['by_pos_added'].items(), key=lambda x: -x[1]):
        report.append(f"  {pos:10} {count:6,} entries")
    report.append("")
    report.append("SAMPLE ADDITIONS (first 20)")
    report.append("-"*70)
    for i, entry in enumerate(added[:20], 1):
        ido = entry['ido_word']
        epo = ', '.join(entry['esperanto_words'])
        pos = entry.get('part_of_speech', '?')
        report.append(f"{i:3}. {ido:20} → {epo:20} [{pos}]")
    
    if len(added) > 20:
        report.append(f"     ... and {len(added) - 20:,} more")
    
    report.append("")
    report.append("="*70)
    report.append("MERGE COMPLETE")
    report.append("="*70)
    report.append(f"✅ Successfully added {stats['added']:,} new entries")
    report.append(f"✅ Dictionary size: {stats['current_entries']:,} → {stats['total_after']:,}")
    report.append("")
    report.append("Next steps:")
    report.append("  1. Run create_ido_monolingual.py")
    report.append("  2. Run create_ido_epo_bilingual.py")
    report.append("  3. Rebuild translation system")
    report.append("  4. Test translations")
    report.append("")
    
    report_text = '\n'.join(report)
    
    # Save to file
    with open('FULL_MERGE_REPORT.txt', 'w', encoding='utf-8') as f:
        f.write(report_text)
    
    # Print to console
    print(report_text)


def main():
    """Execute full merge."""
    
    print("="*70)
    print("FULL WIKIPEDIA VOCABULARY MERGE")
    print("="*70)
    print()
    
    # Backup
    print("Step 1: Backing up current dictionary...")
    backup_file = backup_current_dictionary()
    print()
    
    # Load
    print("Step 2: Loading dictionaries...")
    current, wikipedia = load_dictionaries()
    print(f"  Current: {len(current['words']):,} entries")
    print(f"  Wikipedia: {len(wikipedia['words']):,} entries")
    print()
    
    # Merge
    print("Step 3: Merging...")
    enhanced, stats, added, skipped = merge_dictionaries(current, wikipedia)
    print(f"  ✓ Added {stats['added']:,} entries")
    print()
    
    # Save
    print("Step 4: Saving enhanced dictionary...")
    save_enhanced_dictionary(enhanced)
    print()
    
    # Report
    print("Step 5: Generating report...")
    generate_report(stats, added, skipped)
    
    return 0


if __name__ == '__main__':
    exit(main())

