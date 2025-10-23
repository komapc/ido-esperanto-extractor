#!/usr/bin/env python3
"""
Convert the new bidix_big.json format to vortaro dictionary format.
"""

import json
from datetime import datetime
from pathlib import Path

def convert_to_vortaro_format(bidix_path: str, output_path: str):
    """Convert bidix_big.json to vortaro's dictionary.json format."""
    
    print(f"Loading {bidix_path}...")
    with open(bidix_path, 'r', encoding='utf-8') as f:
        bidix = json.load(f)
    
    # Build vortaro format
    vortaro = {
        "metadata": {
            "creation_date": datetime.now().isoformat(),
            "total_words": 0,
            "sources": [
                "io_wiktionary",
                "eo_wiktionary", 
                "io_wikipedia",
                "fr_wiktionary",
                "whitelist"
            ],
            "version": "3.0-regenerate-fast"
        }
    }
    
    # Convert each entry
    for entry in bidix:
        lemma = entry.get('lemma')
        if not lemma:
            continue
            
        # Get all Esperanto translations
        esperanto_words = []
        sources = set()
        
        for sense in entry.get('senses', []):
            for translation in sense.get('translations', []):
                if translation.get('lang') == 'eo':
                    term = translation.get('term')
                    if term and term not in esperanto_words:
                        esperanto_words.append(term)
                    
                    # Add sources
                    for src in translation.get('sources', []):
                        sources.add(src)
        
        # Skip entries without Esperanto translations
        if not esperanto_words:
            continue
        
        # Get morphology
        morph = entry.get('morphology', {})
        paradigm = morph.get('paradigm')
        morfologio = [paradigm] if paradigm else []
        
        # Get provenance sources
        for prov in entry.get('provenance', []):
            src = prov.get('source')
            if src:
                sources.add(src)
        
        # Add to vortaro dictionary
        vortaro[lemma] = {
            "esperanto_words": esperanto_words,
            "sources": sorted(list(sources)),
            "morfologio": morfologio
        }
    
    # Update metadata
    vortaro["metadata"]["total_words"] = len(vortaro) - 1  # Exclude metadata itself
    
    print(f"Writing {output_path}...")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(vortaro, f, ensure_ascii=False, indent=2)
    
    print(f"✅ Converted {len(vortaro) - 1} entries")
    print(f"   Output: {output_path}")

if __name__ == '__main__':
    import sys
    
    bidix_path = 'dist/bidix_big.json'
    output_path = 'dist/vortaro_dictionary.json'
    
    if len(sys.argv) > 1:
        bidix_path = sys.argv[1]
    if len(sys.argv) > 2:
        output_path = sys.argv[2]
    
    convert_to_vortaro_format(bidix_path, output_path)

