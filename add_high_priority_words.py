#!/usr/bin/env python3
"""
Add high-priority missing words to the dictionary
"""

import json

# High-priority missing words for political/governmental texts
HIGH_PRIORITY_WORDS = {
    # Function words
    'nur': {'esperanto': 'nur', 'pos': 'adv'},
    'til': {'esperanto': 'ĝis', 'pos': 'pr'},
    'pos': {'esperanto': 'post', 'pos': 'pr'},
    'dum': {'esperanto': 'dum', 'pos': 'cnjsub'},
    'segun': {'esperanto': 'laŭ', 'pos': 'pr'},
    'kom': {'esperanto': 'kiel', 'pos': 'cnjsub'},
    
    # Nouns
    'prezidanto': {'esperanto': 'prezidanto', 'pos': 'n', 'morfologio': ['prezidant', '.o']},
    'titulo': {'esperanto': 'titolo', 'pos': 'n', 'morfologio': ['titul', '.o']},
    'guvernerio': {'esperanto': 'registaro', 'pos': 'n', 'morfologio': ['guverneri', '.o']},
    'povo': {'esperanto': 'povo', 'pos': 'n', 'morfologio': ['pov', '.o']},
    'konstituco': {'esperanto': 'konstitucio', 'pos': 'n', 'morfologio': ['konstituc', '.o']},
    'deputato': {'esperanto': 'deputito', 'pos': 'n', 'morfologio': ['deputat', '.o']},
    'koalisuro': {'esperanto': 'koalicio', 'pos': 'n', 'morfologio': ['koalisur', '.o']},
    'partopreno': {'esperanto': 'partopreno', 'pos': 'n', 'morfologio': ['partopren', '.o']},
    'civitano': {'esperanto': 'civitano', 'pos': 'n', 'morfologio': ['civitan', '.o']},
    'reprezento': {'esperanto': 'reprezento', 'pos': 'n', 'morfologio': ['reprezent', '.o']},
    'institucuro': {'esperanto': 'institucio', 'pos': 'n', 'morfologio': ['institucar', '.o']},
    'prepondoro': {'esperanto': 'prepondereco', 'pos': 'n', 'morfologio': ['prepondor', '.o']},
    'konceptajo': {'esperanto': 'koncepto', 'pos': 'n', 'morfologio': ['koncept', '.aj.o']},
    'rielekto': {'esperanto': 'reelekto', 'pos': 'n', 'morfologio': ['rielekt', '.o']},
    
    # Verbs
    'transmisar': {'esperanto': 'transdoni', 'pos': 'vblex', 'morfologio': ['transmis', '.ar']},
    'nominesar': {'esperanto': 'nomiĝi', 'pos': 'vblex', 'morfologio': ['nomines', '.ar']},
    'limitizar': {'esperanto': 'limiti', 'pos': 'vblex', 'morfologio': ['limitiz', '.ar']},
    'aparisar': {'esperanto': 'aperi', 'pos': 'vblex', 'morfologio': ['aparis', '.ar']},
    'divenisar': {'esperanto': 'fariĝi', 'pos': 'vblex', 'morfologio': ['divenis', '.ar']},
    'adoptisar': {'esperanto': 'adopti', 'pos': 'vblex', 'morfologio': ['adoptis', '.ar']},
    'rielektesar': {'esperanto': 'reelektiĝi', 'pos': 'vblex', 'morfologio': ['rielektes', '.ar']},
    'disputar': {'esperanto': 'disputi', 'pos': 'vblex', 'morfologio': ['disput', '.ar']},
    'selektesar': {'esperanto': 'elektiĝi', 'pos': 'vblex', 'morfologio': ['selektes', '.ar']},
    
    # Adjectives
    'nedependanta': {'esperanto': 'sendependa', 'pos': 'adj', 'morfologio': ['nedependant', '.a']},
    'fundamentala': {'esperanto': 'fundamenta', 'pos': 'adj', 'morfologio': ['fundamental', '.a']},
    'guvernala': {'esperanto': 'registara', 'pos': 'adj', 'morfologio': ['guvernal', '.a']},
    'prezidantala': {'esperanto': 'prezidanta', 'pos': 'adj', 'morfologio': ['prezidantal', '.a']},
    'parlamentala': {'esperanto': 'parlamenta', 'pos': 'adj', 'morfologio': ['parlamental', '.a']},
    'prezidantal': {'esperanto': 'prezidanta', 'pos': 'adj', 'morfologio': ['prezidantal', '']},
    
    # Adverbs
    'exemple': {'esperanto': 'ekzemple', 'pos': 'adv'},
    'heredale': {'esperanto': 'heredale', 'pos': 'adv'},
    'absolute': {'esperanto': 'absolute', 'pos': 'adv'},
    'unfoye': {'esperanto': 'unufoje', 'pos': 'adv'},
    'sequante': {'esperanto': 'sinsekve', 'pos': 'adv'},
    
    # Other
    'tota': {'esperanto': 'ĉiuj', 'pos': 'adj', 'morfologio': ['tot', '.a']},
    
    # Proper nouns
    'Roma': {'esperanto': 'Romo', 'pos': 'np'},
    'Brazilia': {'esperanto': 'Brazilo', 'pos': 'np'},
    'Arjentinia': {'esperanto': 'Argentino', 'pos': 'np'},
    'Uruguay': {'esperanto': 'Urugvajo', 'pos': 'np'},
    'Chili': {'esperanto': 'Ĉilio', 'pos': 'np'},
    'Venezuela': {'esperanto': 'Venezuelo', 'pos': 'np'},
    'Portugal': {'esperanto': 'Portugalio', 'pos': 'np'},
    'Francia': {'esperanto': 'Francio', 'pos': 'np'},
    'Aristoteles': {'esperanto': 'Aristotelo', 'pos': 'np'},
}

def add_high_priority_words(input_file='dictionary_merged.json', output_file='dictionary_merged.json'):
    """Add high-priority words to the merged dictionary"""
    
    # Load existing dictionary
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Track what we're adding
    added_count = 0
    updated_count = 0
    
    # Create a lookup of existing words
    existing_words = {word['ido_word']: word for word in data['words']}
    
    # Add/update high-priority words
    for ido_word, info in HIGH_PRIORITY_WORDS.items():
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
    print(f"   - Saved to: {output_file}")

if __name__ == '__main__':
    add_high_priority_words()

