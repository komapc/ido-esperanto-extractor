#!/usr/bin/env python3
"""
Apply Idolinguo supplement to the existing dictionary.
This will add missing words and correct erroneous translations.
"""

import json
from datetime import datetime


def load_json(filepath):
    """Load a JSON file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_json(data, filepath):
    """Save data to JSON file."""
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def normalize_word(word):
    """Normalize word for comparison."""
    return word.lower().strip().replace('·', '').replace('-', '')


def merge_supplement(main_dict, supplement):
    """
    Merge supplement into main dictionary.
    - Add new words
    - Update existing words if marked as correction
    """
    
    # Create index of existing words
    existing_index = {}
    for i, entry in enumerate(main_dict['words']):
        ido_word = entry.get('ido_word', '')
        if ido_word:
            norm_word = normalize_word(ido_word)
            existing_index[norm_word] = i
    
    added_count = 0
    updated_count = 0
    
    for supp_entry in supplement['words']:
        ido_word = supp_entry.get('ido_word', '')
        norm_word = normalize_word(ido_word)
        is_correction = supp_entry.get('source', '').endswith('_correction')
        
        if norm_word in existing_index:
            # Word exists
            if is_correction:
                # Update the existing entry
                idx = existing_index[norm_word]
                old_entry = main_dict['words'][idx]
                old_esp = old_entry.get('esperanto_words', [])
                new_esp = supp_entry.get('esperanto_words', [])
                
                print(f"  ✏️  Updating '{ido_word}': {old_esp} → {new_esp}")
                
                main_dict['words'][idx]['esperanto_words'] = new_esp
                if 'note' in supp_entry:
                    main_dict['words'][idx]['note'] = supp_entry['note']
                updated_count += 1
        else:
            # New word
            print(f"  ➕ Adding '{ido_word}' → {supp_entry.get('esperanto_words', [])}")
            main_dict['words'].append(supp_entry)
            added_count += 1
    
    return added_count, updated_count


def main():
    """Main function."""
    
    print("\n" + "="*70)
    print("APPLYING IDOLINGUO SUPPLEMENT")
    print("="*70)
    
    # Load files
    print("\nLoading dictionaries...")
    main_dict = load_json('dictionary_merged.json')
    supplement = load_json('idolinguo_supplement.json')
    
    original_count = len(main_dict['words'])
    print(f"  ✓ Main dictionary: {original_count} entries")
    print(f"  ✓ Supplement: {len(supplement['words'])} entries")
    
    # Backup
    backup_file = f'dictionary_merged_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
    print(f"\n💾 Creating backup: {backup_file}")
    save_json(main_dict, backup_file)
    
    # Merge
    print("\n📝 Merging supplement...")
    added, updated = merge_supplement(main_dict, supplement)
    
    final_count = len(main_dict['words'])
    
    # Update metadata
    if 'metadata' not in main_dict:
        main_dict['metadata'] = {}
    
    main_dict['metadata']['last_supplement'] = {
        'date': datetime.now().isoformat(),
        'source': 'idolinguo',
        'added': added,
        'updated': updated
    }
    
    # Save
    print(f"\n💾 Saving updated dictionary...")
    save_json(main_dict, 'dictionary_merged.json')
    
    # Summary
    print("\n" + "="*70)
    print("SUMMARY:")
    print("="*70)
    print(f"  Original entries:  {original_count}")
    print(f"  Added:             {added}")
    print(f"  Updated:           {updated}")
    print(f"  Final entries:     {final_count}")
    print(f"  Backup saved:      {backup_file}")
    
    print("\n✅ Dictionary updated successfully!")
    print("\nNext steps:")
    print("  1. Regenerate .dix files: python3 json_to_dix_converter.py")
    print("  2. Copy to apertium-ido-epo directory")
    print("  3. Rebuild: cd ../apertium-ido-epo && make clean && make")
    print("  4. Test: echo 'Test sentence' | apertium -d . ido-epo")
    
    print("\n" + "="*70 + "\n")


if __name__ == '__main__':
    main()


