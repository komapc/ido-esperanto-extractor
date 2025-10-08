#!/usr/bin/env python3
"""Add missing vocabulary identified from Stockholm article analysis"""

import json

with open('dictionary_merged.json') as f:
    data = json.load(f)

words = data['words']
added = 0

# Common vocabulary from Stockholm analysis
new_words = {
    # Nouns
    'cheflando': (['ĉefurbo'], ['chefland', '.o']),  # capital city
    'habitanto': (['loĝanto'], ['habitant', '.o']),  # inhabitant
    'yarcento': (['jarcento'], ['yarcent', '.o']),   # century
    'centro': (['centro'], ['centr', '.o']),          # center
    'klimato': (['klimato'], ['klimat', '.o']),       # climate
    'persono': (['persono'], ['person', '.o']),       # person
    
    # Verbs
    'kreiar': (['krei'], ['krei', '.ar']),            # to create
    'vizitar': (['viziti'], ['vizit', '.ar']),        # to visit
    'decentar': (['deveni'], ['decent', '.ar']),      # to come from/descend
    
    # Adjectives
    'situita': (['situata'], None),                   # situated (past participle)
    'orienta': (['orienta'], ['orient', '.a']),       # eastern
    'ekonomiala': (['ekonomia'], ['ekonomial', '.a']), # economic
    'politikala': (['politika'], ['politikal', '.a']), # political
    'turista': (['turista'], ['turist', '.a']),       # tourist
    'maritima': (['maristrana'], ['maritim', '.a']),   # maritime
    'varma': (['varma'], ['varm', '.a']),             # warm
    'kolda': (['malvarma'], ['kold', '.a']),          # cold
    'populara': (['populara'], ['popular', '.a']),    # popular
    
    # Adverbs
    'cirke': (['ĉirkaŭ'], None),                      # approximately
    
    # Prepositions
    'ye': (['ĉe'], None),                             # at
    'kun': (['kun'], None),                           # with
    
    # Proper nouns - CRITICAL FIX
    'Suedia': (['Svedio'], ['Suedi', '.a']),          # Sweden (country, not person!)
    'Svediana': (['Svedia'], None),                   # Swedish (adjective)
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

# Save
data['words'] = words
with open('dictionary_merged.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(f"\n✅ Added {added} words")
print(f"Total: {len(words)} words")

# Add past tense verb forms (Ido -is)
print("\n" + "="*60)
print("Adding past tense verb forms...")

# Common verbs we need in past tense
past_tense_verbs = {
    'kreiesis': (['kreiĝis'], None),      # was created
    'esis': (['estis'], None),             # was
    'havis': (['havis'], None),            # had
    'vizitis': (['vizitis'], None),        # visited
}

for ido_verb, (epo_words, morfologio) in past_tense_verbs.items():
    if not any(w.get('ido_word') == ido_verb for w in words):
        words.append({
            'ido_word': ido_verb,
            'esperanto_words': epo_words,
        })
        added += 1
        print(f"Added past tense: {ido_verb} → {', '.join(epo_words)}")

# Save again
data['words'] = words
with open('dictionary_merged.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(f"\n✅ Total added this session: {added} words")
print(f"Final total: {len(words)} words")
