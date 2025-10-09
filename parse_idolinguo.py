#!/usr/bin/env python3
"""
Parse the Idolinguo Ido-Esperanto dictionary from HTML format
and compare with our existing dictionary.
"""

import json
import re
from typing import Dict, List, Tuple

# Sample entries from the Idolinguo dictionary
IDOLINGUO_DATA = """
**a (= ad)** – al  
**abado** – abato  
abako  
**abandonas** _(tr)_ – forlasas  
**abaniko** – ventumilo (mana)  
**abasas** _(tr)_ – malaltigas; _(fig.)_ malnobligas  
**abatas** _(tr)_ – faligas per bato  
**abceso** – absceso  
**abciso** – absciso  
abdikas  
**abdomino** – abdomeno  
abelo  
**abel·eyo** – abelejo  
**aberacas** – estas aberacia  
**abieto** – abio  
abismo  
**abjekta** – malestiminda  
"""

def parse_idolinguo_line(line: str) -> Tuple[str, str, str]:
    """
    Parse a line from the Idolinguo dictionary.
    Returns: (ido_word, esperanto_translation, notes)
    """
    line = line.strip()
    
    # Skip empty lines
    if not line:
        return None, None, None
    
    # Skip header lines
    if line.startswith('#') or line.startswith('---') or 'Noto:' in line:
        return None, None, None
    
    # Format 1: **word** – translation
    match = re.match(r'\*\*([^*]+)\*\*\s*–\s*(.+)', line)
    if match:
        ido_word = match.group(1).strip()
        esperanto = match.group(2).strip()
        
        # Extract notes (like _(tr)_, _(ntr)_, etc.)
        notes = ''
        note_match = re.search(r'_\([^)]+\)_', ido_word)
        if note_match:
            notes = note_match.group(0)
            ido_word = ido_word.replace(notes, '').strip()
        
        # Clean up the Esperanto side
        note_match = re.search(r'_\([^)]+\)_', esperanto)
        if note_match:
            notes += ' ' + note_match.group(0)
            esperanto = re.sub(r'\s*_\([^)]+\)_\s*', ' ', esperanto).strip()
        
        # Remove parenthetical notes from esperanto
        esperanto = re.sub(r'\s*\([^)]+\)', '', esperanto).strip()
        
        # Handle multiple translations separated by ;
        esperanto = esperanto.split(';')[0].strip()
        
        # Remove "~" which indicates approximate translation
        esperanto = esperanto.replace('~', '').strip()
        
        return ido_word, esperanto, notes
    
    # Format 2: word (no bold, means same in both languages)
    if not line.startswith('*') and not '–' in line:
        word = line.strip()
        # Skip if it has special characters or is very short
        if len(word) > 2 and word.isalpha():
            return word, word, ''
    
    return None, None, None


def load_existing_dictionary(filepath: str = 'dictionary_merged.json') -> Dict:
    """Load our existing merged dictionary."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {'words': [], 'metadata': {}}


def find_new_words(idolinguo_entries: List[Tuple[str, str, str]], 
                   existing_dict: Dict) -> List[Dict]:
    """Find words in Idolinguo that are missing from our dictionary."""
    
    # Create a set of existing Ido words
    existing_words = set()
    for entry in existing_dict.get('words', []):
        ido_word = entry.get('ido_word', '')
        if ido_word:
            existing_words.add(ido_word.lower())
    
    # Find new words
    new_words = []
    for ido_word, esperanto, notes in idolinguo_entries:
        if ido_word and esperanto:
            # Normalize the word (remove endings for comparison)
            base_word = ido_word.lower()
            # Remove common verb/noun/adjective endings for matching
            for ending in ['ar', 'as', 'is', 'os', 'us', 'o', 'a', 'e', 'i']:
                if base_word.endswith(ending) and len(base_word) > len(ending) + 2:
                    check_word = base_word[:-len(ending)]
                    if check_word in existing_words:
                        break
            else:
                if base_word not in existing_words:
                    new_words.append({
                        'ido_word': ido_word,
                        'esperanto_words': [esperanto],
                        'notes': notes,
                        'source': 'idolinguo'
                    })
    
    return new_words


def main():
    """Main function to parse and compare dictionaries."""
    
    print("Idolinguo Dictionary Parser")
    print("=" * 60)
    
    # For now, just demonstrate the parser with sample data
    print("\nTesting parser with sample data:")
    print("-" * 60)
    
    sample_lines = [
        '**a (= ad)** – al',
        '**abado** – abato',
        'abako',
        '**abandonas** _(tr)_ – forlasas',
        '**abaniko** – ventumilo (mana)',
        '**abasas** _(tr)_ – malaltigas; _(fig.)_ malnobligas',
    ]
    
    entries = []
    for line in sample_lines:
        ido, esp, notes = parse_idolinguo_line(line)
        if ido and esp:
            entries.append((ido, esp, notes))
            print(f"  {ido:20} → {esp:30} {notes}")
    
    print(f"\nParsed {len(entries)} sample entries")
    
    # Load existing dictionary
    print("\nLoading existing dictionary...")
    existing_dict = load_existing_dictionary()
    existing_count = len(existing_dict.get('words', []))
    print(f"  Existing dictionary has {existing_count} entries")
    
    # Find new words (from sample)
    new_words = find_new_words(entries, existing_dict)
    print(f"\n  Found {len(new_words)} potentially new words from sample")
    
    if new_words:
        print("\nNew words:")
        for word in new_words:
            print(f"  - {word['ido_word']} → {word['esperanto_words'][0]}")
    
    print("\n" + "=" * 60)
    print("To use this script with the full Idolinguo dictionary:")
    print("1. Save the HTML content to a file")
    print("2. Parse all entries")
    print("3. Compare with existing dictionary")
    print("4. Generate a supplement file for missing words")


if __name__ == '__main__':
    main()

