#!/usr/bin/env python3
"""Add missing vocabulary from Islando article test"""

import json

with open('dictionary_merged.json') as f:
    data = json.load(f)

words = data['words']
added = 0

# Add missing words from Islando test
new_words = {
    # Proper nouns - countries and places
    'Islando': (['Islando'], None),
    'Reykjavik': (['Rejkjaviko'], None),
    'Atlantiko': (['Atlantiko'], None),
    'Europa': (['Eŭropo'], ['Europ', '.a']),
    
    # Nouns
    'insulo': (['insulo'], ['insul', '.o']),
    'lando': (['lando'], ['land', '.o']),
    'nordo': (['nordo'], ['nord', '.o']),
    'maro': (['maro'], ['mar', '.o']),
    'republiko': (['respubliko'], ['republik', '.o']),
    'ekonomio': (['ekonomio'], ['ekonomi', '.o']),
    'linguo': (['lingvo'], ['lingu', '.o']),
    'turismo': (['turismo'], ['turism', '.o']),
    'peshado': (['fiŝkaptado'], ['peshad', '.o']),
    
    # Adjectives
    'demokratiala': (['demokratia'], ['demokratial', '.a']),
    'Islandana': (['Islanda'], None),
    'Polare': (['Polusa'], None),
    
    # Verbs
    'situar': (['situi'], ['situ', '.ar']),
    'bazar': (['bazi'], ['baz', '.ar']),
}

for ido_word, (epo_words, morfologio) in new_words.items():
    if not any(w.get('ido_word') == ido_word for w in words):
        entry = {
            'ido_word': ido_word,
            'esperanto_words': epo_words,
        }
        if morfologio:
            entry['morfologio'] = morfologio
        words.append(entry)
        added += 1
        print(f"Added: {ido_word:20s} → {', '.join(epo_words)}")

data['words'] = words
with open('dictionary_merged.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(f"\n✅ Added {added} words")
print(f"Total: {len(words)} words")
