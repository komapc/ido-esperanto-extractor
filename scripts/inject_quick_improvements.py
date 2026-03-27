import json
import os

def main():
    with open('extractor/quick_improvements.json', 'r', encoding='utf-8') as f:
        improvements = json.load(f)['words']

    for file_path in ['extractor/dist/ido_dictionary.json', 'extractor/dist/bidix_big.json']:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        lemmas_in_data = {entry['lemma'] for entry in data}
        
        for item in improvements:
            ido_word = item['ido_word']
            eo_word = item['esperanto_words'][0]
            morfologio = item.get('morfologio')
            
            # Update existing or add new
            entry = next((e for e in data if e['lemma'] == ido_word), None)
            
            if not entry:
                entry = {
                    "lemma": ido_word,
                    "pos": None,
                    "language": "io",
                    "senses": [
                        {
                            "senseId": None,
                            "gloss": None,
                            "translations": []
                        }
                    ],
                    "raw_par": None,
                    "tags": None
                }
                data.append(entry)
            
            # Ensure translation exists
            translations = entry['senses'][0]['translations']
            if not any(t['term'] == eo_word for t in translations):
                translations.append({
                    "lang": "eo",
                    "term": eo_word,
                    "confidence": 1.0,
                    "source": "quick_improvements",
                    "sources": ["quick_improvements"]
                })
                
            # Update morphology if present
            if morfologio:
                paradigm = "o__n"
                if len(morfologio) > 1:
                    suffix = morfologio[-1]
                    if suffix == ".e":
                        paradigm = "e__adv"
                    elif suffix == ".a":
                        paradigm = "a__adj"
                    elif suffix in {".ar", ".ir", ".iar"}:
                        paradigm = "ar__vblex"
                    elif suffix == ".i":
                        paradigm = "o__n" # plurals are usually nouns
                entry['morphology'] = {"paradigm": paradigm, "features": {}}
                
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            
    print("Injected quick improvements into dictionaries.")

if __name__ == '__main__':
    main()
