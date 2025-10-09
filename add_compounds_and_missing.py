#!/usr/bin/env python3
"""
Add compound words, contractions, prepositions, and possessive pronouns
"""

import json

# Compound words
COMPOUND_WORDS = {
    'maxim-multa-kaze': {'esperanto': 'plej-multe-kaze', 'pos': 'adv'},
    'maxim-multa': {'esperanto': 'plej-multe', 'pos': 'adv'},
    'maxim-bona': {'esperanto': 'plej-bona', 'pos': 'adj', 'morfologio': ['maxim-bon', '.a']},
    'maxim-granda': {'esperanto': 'plej-granda', 'pos': 'adj', 'morfologio': ['maxim-grand', '.a']},
    'maxim-mikra': {'esperanto': 'plej-mikra', 'pos': 'adj', 'morfologio': ['maxim-mikr', '.a']},
    'pluri-kaze': {'esperanto': 'plur-kaze', 'pos': 'adv'},
}

# Contractions (preposition + article)
CONTRACTIONS = {
    'dal': {'esperanto': 'de la', 'pos': 'pr'},  # da + la
    'del': {'esperanto': 'de la', 'pos': 'pr'},  # de + la
    'al': {'esperanto': 'al la', 'pos': 'pr'},   # a + la
    'pol': {'esperanto': 'por la', 'pos': 'pr'}, # por + la
    'sul': {'esperanto': 'sur la', 'pos': 'pr'}, # sur + la
}

# Prepositions that were missing
PREPOSITIONS = {
    'di': {'esperanto': 'de', 'pos': 'pr'},      # of, from
    'a': {'esperanto': 'al', 'pos': 'pr'},       # to
    'da': {'esperanto': 'de', 'pos': 'pr'},      # of (quantity)
    'ye': {'esperanto': 'je', 'pos': 'pr'},      # at (time/place)
    'pri': {'esperanto': 'pri', 'pos': 'pr'},    # about
    'pro': {'esperanto': 'pro', 'pos': 'pr'},    # for (reason)
    'kun': {'esperanto': 'kun', 'pos': 'pr'},    # with
    'sen': {'esperanto': 'sen', 'pos': 'pr'},    # without
    'sur': {'esperanto': 'sur', 'pos': 'pr'},    # on
    'sub': {'esperanto': 'sub', 'pos': 'pr'},    # under
    'ante': {'esperanto': 'antaŭ', 'pos': 'pr'}, # before
    'apud': {'esperanto': 'apud', 'pos': 'pr'},  # beside
    'kontre': {'esperanto': 'kontraŭ', 'pos': 'pr'}, # against
    'tra': {'esperanto': 'tra', 'pos': 'pr'},    # through
    'inter': {'esperanto': 'inter', 'pos': 'pr'}, # between
    'ultre': {'esperanto': 'trans', 'pos': 'pr'}, # beyond
}

# Possessive pronouns
POSSESSIVE_PRONOUNS = {
    'mea': {'esperanto': 'mia', 'pos': 'prn'},   # my
    'tua': {'esperanto': 'via', 'pos': 'prn'},   # your (singular)
    'lua': {'esperanto': 'sia', 'pos': 'prn'},   # his/her/its (reflexive)
    'nia': {'esperanto': 'nia', 'pos': 'prn'},   # our
    'via': {'esperanto': 'via', 'pos': 'prn'},   # your (plural)
    'olia': {'esperanto': 'ilia', 'pos': 'prn'}, # their
    'ilia': {'esperanto': 'lia', 'pos': 'prn'},  # his (non-reflexive)
    'elia': {'esperanto': 'ŝia', 'pos': 'prn'},  # her (non-reflexive)
}

# Personal pronouns
PERSONAL_PRONOUNS = {
    'me': {'esperanto': 'mi', 'pos': 'prn'},     # I
    'tu': {'esperanto': 'vi', 'pos': 'prn'},     # you (singular)
    'il': {'esperanto': 'li', 'pos': 'prn'},     # he
    'el': {'esperanto': 'ŝi', 'pos': 'prn'},     # she (short form)
    'ela': {'esperanto': 'ŝi', 'pos': 'prn'},    # she
    'lu': {'esperanto': 'li', 'pos': 'prn'},     # he/she/it (gender-neutral)
    'ol': {'esperanto': 'ĝi', 'pos': 'prn'},     # it
    'ni': {'esperanto': 'ni', 'pos': 'prn'},     # we
    'vi': {'esperanto': 'vi', 'pos': 'prn'},     # you (plural)
    'li': {'esperanto': 'ili', 'pos': 'prn'},    # they
    'ili': {'esperanto': 'ili', 'pos': 'prn'},   # they (masculine)
    'eli': {'esperanto': 'ili', 'pos': 'prn'},   # they (feminine)
    'oli': {'esperanto': 'ili', 'pos': 'prn'},   # they (neuter)
}

# Additional common words
ADDITIONAL_COMMON = {
    # Conjunctions
    'ma': {'esperanto': 'sed', 'pos': 'cnjcoo'}, # but
    'nam': {'esperanto': 'ĉar', 'pos': 'cnjcoo'}, # for (because)
    'ka': {'esperanto': 'ĉu', 'pos': 'cnjcoo'},  # whether
    
    # Common verbs missing
    'eventar': {'esperanto': 'okazi', 'pos': 'vblex', 'morfologio': ['event', '.ar']},
    'havas': {'esperanto': 'havas', 'pos': 'vblex'},  # has (fixed form)
    
    # Determiners
    'la': {'esperanto': 'la', 'pos': 'det'},     # the
    'un': {'esperanto': 'unu', 'pos': 'det'},    # a, one
    'omna': {'esperanto': 'ĉiuj', 'pos': 'det'}, # all
    'ula': {'esperanto': 'iu', 'pos': 'prn'},    # some, any
    'nula': {'esperanto': 'neniu', 'pos': 'prn'}, # no one
    
    # Adverbs
    'tre': {'esperanto': 'tre', 'pos': 'adv'},   # very
    'multe': {'esperanto': 'multe', 'pos': 'adv'}, # much
    'pluse': {'esperanto': 'pli', 'pos': 'adv'}, # more
    'maxime': {'esperanto': 'plej', 'pos': 'adv'}, # most
    
    # Fix wrong translation
    'populo': {'esperanto': 'popolo', 'pos': 'n', 'morfologio': ['popul', '.o']},
}

def add_words(input_file='dictionary_merged.json', output_file='dictionary_merged.json'):
    """Add all the missing words to the merged dictionary"""
    
    # Load existing dictionary
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Track what we're adding
    added_count = 0
    updated_count = 0
    
    # Create a lookup of existing words
    existing_words = {word['ido_word']: word for word in data['words']}
    
    # Combine all word lists
    all_words = {}
    all_words.update(COMPOUND_WORDS)
    all_words.update(CONTRACTIONS)
    all_words.update(PREPOSITIONS)
    all_words.update(POSSESSIVE_PRONOUNS)
    all_words.update(PERSONAL_PRONOUNS)
    all_words.update(ADDITIONAL_COMMON)
    
    # Add/update words
    for ido_word, info in all_words.items():
        if ido_word in existing_words:
            # Update existing entry
            existing_words[ido_word]['esperanto_words'] = [info['esperanto']]
            if 'morfologio' in info:
                existing_words[ido_word]['morfologio'] = info['morfologio']
            updated_count += 1
            print(f"✓ Updated: {ido_word} → {info['esperanto']}")
        else:
            # Add new entry
            new_entry = {
                'ido_word': ido_word,
                'esperanto_words': [info['esperanto']]
            }
            if 'morfologio' in info:
                new_entry['morfologio'] = info['morfologio']
            data['words'].append(new_entry)
            added_count += 1
            print(f"+ Added: {ido_word} → {info['esperanto']}")
    
    # Update metadata
    data['metadata']['total_words'] = len(data['words'])
    
    # Save updated dictionary
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"\n✨ Summary:")
    print(f"   - Added: {added_count} words")
    print(f"   - Updated: {updated_count} words")
    print(f"   - Total words: {data['metadata']['total_words']}")
    print(f"   - Categories:")
    print(f"     * Compound words: {len(COMPOUND_WORDS)}")
    print(f"     * Contractions: {len(CONTRACTIONS)}")
    print(f"     * Prepositions: {len(PREPOSITIONS)}")
    print(f"     * Possessive pronouns: {len(POSSESSIVE_PRONOUNS)}")
    print(f"     * Personal pronouns: {len(PERSONAL_PRONOUNS)}")
    print(f"     * Additional common: {len(ADDITIONAL_COMMON)}")
    print(f"   - Saved to: {output_file}")

if __name__ == '__main__':
    add_words()

