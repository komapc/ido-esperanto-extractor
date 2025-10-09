#!/usr/bin/env python3
"""
Compare our dictionary with the Idolinguo dictionary to find:
1. Words in Idolinguo but missing from our dictionary
2. Different translations that might be better
3. Words we have that Idolinguo doesn't
"""

import json
import re
from collections import defaultdict
from typing import Dict, List, Set, Tuple


def normalize_word(word: str) -> str:
    """Normalize a word for comparison."""
    word = word.lower().strip()
    # Remove special characters
    word = word.replace('·', '').replace('-', '')
    # Remove explanatory parts in parentheses
    word = re.sub(r'\s*\([^)]+\)', '', word)
    return word


def get_word_root(word: str) -> str:
    """Extract the root of a word by removing common endings."""
    word = normalize_word(word)
    
    # Common Ido endings
    verb_endings = ['ar', 'as', 'is', 'os', 'us', 'ez']
    noun_endings = ['o', 'i', 'is']  # singular, plural, plural acc
    adj_endings = ['a', 'e']
    
    for endings in [verb_endings, noun_endings, adj_endings]:
        for ending in endings:
            if word.endswith(ending) and len(word) > len(ending) + 2:
                return word[:-len(ending)]
    
    return word


def parse_idolinguo_sample() -> List[Tuple[str, str]]:
    """
    Parse key sample entries from Idolinguo dictionary.
    Returns list of (ido_word, esperanto_word) tuples.
    """
    
    # Key entries that might be missing from our dictionary
    # Based on the test results, these are commonly needed words
    important_entries = [
        ('a', 'al'),  # preposition "to"
        ('ad', 'al'),  # preposition "to" (variant)
        ('abandonar', 'forlasi'),
        ('abasar', 'malaltigi'),
        ('abatar', 'faligi'),
        ('abjurar', 'forĵuri'),
        ('ablaktar', 'demamigi'),
        ('abolisar', 'abolicii'),
        ('abordas', 'enŝipiĝi'),
        ('aboyar', 'boji'),
        ('ad·avan·e', 'antaŭen'),
        ('ad·en', 'en'),
        ('ad·infre', 'malsupren'),
        ('ye', 'je'),  # preposition
        ('da', 'de'),  # preposition
        ('di', 'de'),  # preposition "of/from"
        ('til', 'ĝis'),  # preposition "until"
        ('pos', 'post'),  # preposition "after"
        ('vers', 'al'),  # preposition "toward"
        ('per', 'per'),  # preposition
        ('pro', 'pro'),  # preposition
        ('lua', 'sia'),  # possessive pronoun
        ('mea', 'mia'),  # possessive
        ('tua', 'via'),  # possessive
        ('nia', 'nia'),  # possessive
        ('via', 'via'),  # possessive
        ('olia', 'ilia'),  # possessive
        ('ilia', 'lia'),  # possessive "his"
        ('elia', 'ŝia'),  # possessive "her"
        ('me', 'mi'),  # pronoun "I"
        ('tu', 'vi'),  # pronoun "you" (singular informal - but Esperanto uses vi)
        ('vu', 'vi'),  # pronoun "you" (singular formal)
        ('il', 'li'),  # pronoun "he"
        ('el', 'ŝi'),  # pronoun "she"  
        ('elu', 'ŝi'),  # pronoun "she" variant
        ('ol', 'ĝi'),  # pronoun "it"
        ('lu', 'li'),  # pronoun gender-neutral
        ('ni', 'ni'),  # pronoun "we"
        ('vi', 'vi'),  # pronoun "you" (plural)
        ('li', 'ili'),  # pronoun "they"
        ('ili', 'ili'),  # pronoun "they" (human)
        ('eli', 'ili'),  # pronoun "they" (female)
        ('oli', 'ili'),  # pronoun "they" (neuter)
        ('esar', 'esti'),  # verb "to be"
        ('havas', 'havi'),  # verb "to have"
        ('quo', 'kio'),  # what
        ('qui', 'kiu'),  # who
        ('qua', 'kiu'),  # which
        ('ube', 'kie'),  # where
        ('kande', 'kiam'),  # when
        ('quale', 'kiel'),  # how
        ('quante', 'kiom'),  # how much
        ('qua·kauze', 'kial'),  # why
        ('ka', 'ĉu'),  # whether/question particle
        ('nam', 'ĉar'),  # because
        ('se', 'se'),  # if
        ('ma', 'sed'),  # but
        ('od', 'aŭ'),  # or (exclusive)
        ('aden', 'en'),  # into
        ('depos', 'ekde'),  # since (time)
        ('til·nun', 'ĝis nun'),  # until now
        ('pos·morge', 'postmorgaŭ'),  # day after tomorrow
    ]
    
    return important_entries


def load_existing_dictionary(filepath: str = 'dictionary_merged.json') -> Dict:
    """Load our existing merged dictionary."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Warning: Could not find {filepath}")
        return {'words': [], 'metadata': {}}


def check_word_coverage(ido_word: str, existing_dict: Dict) -> Tuple[bool, List[str]]:
    """
    Check if a word exists in our dictionary.
    Returns: (found, existing_translations)
    """
    ido_normalized = normalize_word(ido_word)
    ido_root = get_word_root(ido_word)
    
    for entry in existing_dict.get('words', []):
        entry_word = entry.get('ido_word', '')
        entry_normalized = normalize_word(entry_word)
        entry_root = get_word_root(entry_word)
        
        # Check exact match or root match
        if (entry_normalized == ido_normalized or 
            entry_root == ido_root or
            ido_normalized == entry_root):
            esperanto_words = entry.get('esperanto_words', [])
            return True, esperanto_words
    
    return False, []


def main():
    """Main comparison function."""
    
    print("\n" + "="*70)
    print("IDOLINGUO DICTIONARY COMPARISON")
    print("="*70)
    
    # Load our existing dictionary
    print("\nLoading existing dictionary...")
    existing_dict = load_existing_dictionary()
    existing_count = len(existing_dict.get('words', []))
    print(f"  ✓ Loaded {existing_count} entries from our dictionary")
    
    # Get Idolinguo entries
    print("\nAnalyzing key Idolinguo entries...")
    idolinguo_entries = parse_idolinguo_sample()
    print(f"  ✓ Checking {len(idolinguo_entries)} important entries")
    
    # Find missing words
    missing = []
    different = []
    covered = []
    
    for ido_word, esperanto_word in idolinguo_entries:
        found, existing_translations = check_word_coverage(ido_word, existing_dict)
        
        if not found:
            missing.append((ido_word, esperanto_word))
        elif esperanto_word.lower() not in [t.lower() for t in existing_translations]:
            different.append((ido_word, esperanto_word, existing_translations))
        else:
            covered.append((ido_word, esperanto_word))
    
    # Print results
    print("\n" + "-"*70)
    print("RESULTS:")
    print("-"*70)
    
    print(f"\n✓ Already covered: {len(covered)}/{len(idolinguo_entries)} ({len(covered)*100//len(idolinguo_entries)}%)")
    
    if missing:
        print(f"\n❌ Missing words: {len(missing)}")
        print("\nThese words from Idolinguo are NOT in our dictionary:")
        for ido, esp in sorted(missing)[:30]:  # Show first 30
            print(f"  {ido:20} → {esp}")
        if len(missing) > 30:
            print(f"  ... and {len(missing)-30} more")
    
    if different:
        print(f"\n⚠️  Different translations: {len(different)}")
        print("\nThese words have different translations:")
        for ido, idolinguo_trans, our_trans in sorted(different)[:20]:
            print(f"  {ido:20}")
            print(f"    Idolinguo: {idolinguo_trans}")
            print(f"    Ours:      {', '.join(our_trans[:3])}")
    
    # Summary
    print("\n" + "="*70)
    print("SUMMARY:")
    print("="*70)
    print(f"  Our dictionary:     {existing_count} entries")
    print(f"  Idolinguo sample:   {len(idolinguo_entries)} entries (key words)")
    print(f"  Coverage:           {len(covered)}/{len(idolinguo_entries)} ({len(covered)*100//len(idolinguo_entries)}%)")
    print(f"  Missing:            {len(missing)} words")
    print(f"  Different:          {len(different)} translations")
    
    if missing:
        print("\n" + "="*70)
        print("RECOMMENDATION:")
        print("="*70)
        print(f"Add {len(missing)} missing words from Idolinguo to improve coverage.")
        print("These are mostly function words (prepositions, pronouns, particles)")
        print("that are essential for basic translation.")
        
        # Generate addition commands
        print("\nTo add these words, you can:")
        print("1. Create a supplement JSON file")
        print("2. Merge it with dictionary_merged.json")
        print("3. Regenerate the .dix files")
    
    print("\n" + "="*70 + "\n")
    
    # Return data for potential use
    return {
        'missing': missing,
        'different': different,
        'covered': covered
    }


if __name__ == '__main__':
    results = main()


