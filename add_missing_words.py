#!/usr/bin/env python3
"""
Add missing words to dictionary_merged.json:
1. Ordinal numbers (1ma-31ma, 100ma, 1000ma)
2. Common compound words (mortodio, sundio, lundio, etc.)
3. Missing base words (fonduro, etc.)
"""

import json

# Load existing dictionary
with open('dictionary_merged.json') as f:
    data = json.load(f)

words = data['words']
added_count = 0

# 1. Add ordinal numbers (for dates)
ordinals = {
    '1ma': 'unua', '2ma': 'dua', '3ma': 'tria', '4ma': 'kvara', '5ma': 'kvina',
    '6ma': 'sesa', '7ma': 'sepa', '8ma': 'oka', '9ma': 'naŭa', '10ma': 'deka',
    '11ma': 'dek-unua', '12ma': 'dek-dua', '13ma': 'dek-tria', '14ma': 'dek-kvara',
    '15ma': 'dek-kvina', '16ma': 'dek-sesa', '17ma': 'dek-sepa', '18ma': 'dek-oka',
    '19ma': 'dek-naŭa', '20ma': 'dudeka', '21ma': 'dudek-unua', '22ma': 'dudek-dua',
    '23ma': 'dudek-tria', '24ma': 'dudek-kvara', '25ma': 'dudek-kvina',
    '26ma': 'dudek-sesa', '27ma': 'dudek-sepa', '28ma': 'dudek-oka',
    '29ma': 'dudek-naŭa', '30ma': 'trideka', '31ma': 'tridek-unua',
    '100ma': 'centa', '1000ma': 'mila'
}

for ido_ord, epo_ord in ordinals.items():
    if not any(w.get('ido_word') == ido_ord for w in words):
        words.append({
            'ido_word': ido_ord,
            'esperanto_words': [epo_ord],
            'part_of_speech': 'ordinal'
        })
        added_count += 1
        print(f"Added ordinal: {ido_ord} → {epo_ord}")

# 2. Add compound words (day names and common compounds)
compounds = {
    'mortodio': 'mortotago',      # death day
    'sundio': 'dimanĉo',          # Sunday
    'lundio': 'lundo',            # Monday
    'mardio': 'mardo',            # Tuesday
    'merkurdio': 'merkredo',      # Wednesday
    'jovdio': 'ĵaŭdo',            # Thursday
    'venerdio': 'vendredo',       # Friday
    'saturdio': 'sabato',         # Saturday
    'fonduro': 'fondaĵo',         # foundation
}

for ido_comp, epo_comp in compounds.items():
    if not any(w.get('ido_word') == ido_comp for w in words):
        # Check if it's a noun ending in -o
        if ido_comp.endswith('o'):
            morfologio = [ido_comp[:-1], '.o']
        else:
            morfologio = None
            
        entry = {
            'ido_word': ido_comp,
            'esperanto_words': [epo_comp],
        }
        if morfologio:
            entry['morfologio'] = morfologio
            
        words.append(entry)
        added_count += 1
        print(f"Added compound: {ido_comp} → {epo_comp}")

# Save updated dictionary
data['words'] = words
with open('dictionary_merged.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(f"\n✅ Added {added_count} new words to dictionary_merged.json")
print(f"Total words: {len(words)}")

# Add proper nouns
print("\n" + "="*60)
print("Adding proper nouns...")

proper_nouns = {
    'Nobel': 'Nobel',
    'Alfred': 'Alfredo', 
    'Stockholm': 'Stokholmo',
    'Oslo': 'Oslo',
    'Paris': 'Parizo',
    'London': 'Londono',
    'Berlin': 'Berlino',
    'New York': 'Novjorko',
    'Amerika': 'Ameriko',
    'Europa': 'Eŭropo',
}

for ido_name, epo_name in proper_nouns.items():
    if not any(w.get('ido_word') == ido_name for w in words):
        words.append({
            'ido_word': ido_name,
            'esperanto_words': [epo_name],
            'part_of_speech': 'proper_noun'
        })
        added_count += 1
        print(f"Added proper noun: {ido_name} → {epo_name}")

# Save again
data['words'] = words
with open('dictionary_merged.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(f"\n✅ Total added: {added_count} words")
print(f"Total words now: {len(words)}")
