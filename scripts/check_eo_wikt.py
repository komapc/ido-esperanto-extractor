#!/usr/bin/env python3
import json

with open('terraform/extractor-results/20251031-093639/sources/source_eo_wiktionary.json', 'r') as f:
    data = json.load(f)
    print(f'Total entries: {len(data["entries"])}')
    print(f'\nFirst 10 entries:')
    for i, entry in enumerate(data['entries'][:10]):
        lemma = entry['lemma']
        io_trans = entry.get('translations', {}).get('io', [])
        print(f'{i+1}. {lemma} -> {io_trans}')
    print(f'\nLast 10 entries:')
    for i, entry in enumerate(data['entries'][-10:]):
        lemma = entry['lemma']
        io_trans = entry.get('translations', {}).get('io', [])
        print(f'{len(data["entries"])-9+i}. {lemma} -> {io_trans}')
