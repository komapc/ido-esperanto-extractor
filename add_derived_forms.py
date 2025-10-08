#!/usr/bin/env python3
"""
Add support for Ido derived forms:
- Suffix -ala (adjective from noun): ekonomio → ekonomiala
- Suffix -ana (relating to): Suedia → Svediana  
- Suffix -oza (full of): aquo → aquoza
- Suffix -ala endings map to -a in Esperanto
"""

import json

with open('dictionary_merged.json') as f:
    data = json.load(f)

words = data['words']
added = 0

# Strategy: For common -ala/-ana suffixed words, add them manually
# Later could auto-generate from base words

derived_adjectives = {
    # -ala forms (relational adjectives)
    'ekonomiala': (['ekonomia'], ['ekonomial', '.a']),    # economic
    'politikala': (['politika'], ['politikal', '.a']),    # political
    'sociala': (['sociala'], ['social', '.a']),           # social
    'naturala': (['naturala'], ['natural', '.a']),        # natural
    'kulturala': (['kultura'], ['kultural', '.a']),       # cultural
    'centrala': (['centra'], ['central', '.a']),          # central
    'lokala': (['loka'], ['lokal', '.a']),                # local
    'nasionala': (['nacia'], ['nasional', '.a']),         # national
    'internasionala': (['internacia'], ['internasional', '.a']), # international
    
    # -ana forms (relating to place/person)
    'Svediana': (['Svedia'], None),                       # Swedish
    'Amerikana': (['Amer ika'], None),                    # American
    'Europana': (['Eŭropa'], None),                       # European
    'Italiana': (['Itala'], None),                        # Italian
    
    # -oza forms (full of)
    'aquoza': (['akva'], ['aquoz', '.a']),                # watery
    
    # -atra/-ita (passive participles - often adjectival)
    'situita': (['situata'], None),                       # situated
}

# Base words needed
base_words = {
    'yarcento': (['jarcento'], ['yarcent', '.o']),        # century
    'kosto': (['marbordo'], ['kost', '.o']),              # coast
}

all_new = {**derived_adjectives, **base_words}

for ido_word, (epo_words, morfologio) in all_new.items():
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
