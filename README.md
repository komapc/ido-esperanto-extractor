# Ido-Esperanto Dictionary Extractor

Extracts Ido words with Esperanto translations from Ido Wiktionary dump files. The dictionaries are supplemented with manually added function words, proper nouns, ordinals, and compounds.

## Usage

```bash
# Extract from Wiktionary dump
python3 ido_esperanto_extractor.py

# Create Ido monolingual dictionary
python3 create_ido_monolingual.py

# Create bilingual dictionary
python3 create_ido_epo_bilingual.py
```

## Scripts

- `ido_esperanto_extractor.py` - Extracts Ido-Esperanto word pairs from Wiktionary
- `create_ido_monolingual.py` - Converts to Apertium monolingual format
- `create_ido_epo_bilingual.py` - Creates bilingual dictionary
- `add_missing_words.py` - Adds ordinals, compounds, and proper nouns
- `merge_dictionaries.py` - Merges bidirectional extractions

## Notes

- Extraction from Wiktionary is supplemented with manually added entries
- Function words, proper nouns, ordinals (1ma-31ma), and common compounds added manually
- Past tense forms and derived adjectives (-ala, -ana) added as needed