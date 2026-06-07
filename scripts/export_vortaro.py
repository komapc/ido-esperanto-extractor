#!/usr/bin/env python3
"""
Convert the new bidix_big.json format to vortaro dictionary format.
Includes filtering of junk entries (numbers, corrupted data, etc).
"""

import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lexicon_filters import is_junk_lemma  # shared junk filter (consolidated)
from conflict_resolution import confidence_key  # source-rank ordering (== MT pick_best)

def convert_to_vortaro_format(bidix_path: str, output_path: str):
    """Convert bidix_big.json to vortaro's dictionary.json format."""

    print(f"Loading {bidix_path}...")
    with open(bidix_path, 'r', encoding='utf-8') as f:
        bidix = json.load(f)

    # Build vortaro format
    vortaro = {
        "metadata": {
            "last_updated": datetime.now().isoformat(),
            "total_unique_ido_words": 0,
            "source_stats": {},
            "version": "3.2"
        }
    }

    source_counts: dict = {}

    # Convert each entry
    junk_count = 0
    for entry in bidix:
        lemma = entry.get('lemma')
        if not lemma:
            continue

        # Filter out junk entries
        if is_junk_lemma(lemma):
            junk_count += 1
            continue
            
        # Collect EO candidates with per-term sources, in insertion order.
        order = []          # term, deduped, in first-seen order
        term_sources = {}   # term -> set(sources)
        sources = set()
        for sense in entry.get('senses', []):
            for translation in sense.get('translations', []):
                if translation.get('lang') == 'eo':
                    term = translation.get('term')
                    if not term:
                        continue
                    if term not in term_sources:
                        term_sources[term] = set()
                        order.append(term)
                    for src in translation.get('sources', []):
                        term_sources[term].add(src)
                        sources.add(src)

        # Skip entries without Esperanto translations
        if not order:
            continue

        # Order esperanto_words by source reliability (then insertion order) using
        # the SAME deterministic key as the MT bidix (conflict_resolution.pick_best),
        # so the vortaro's primary gloss matches what the translator emits — curated
        # io_wiktionary terms surface above noisy pivots (avokado, not advokato).
        esperanto_words = sorted(
            order,
            key=lambda t: confidence_key(t, sorted(term_sources[t]), order.index(t)),
        )

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
        for src in sources:
            source_counts[src] = source_counts.get(src, 0) + 1

    # Merge capitalized common-noun entries into their lowercase twin. Wikipedia
    # -title-cased langlink/wikidata commons (Antropologio, Veterano) duplicate
    # the correct lowercase form; the lowercase entry keeps its (better-sourced)
    # #1 gloss and absorbs any unique glosses from the capital one. True proper
    # nouns (Nauvoo, Korea) have no lowercase twin and are left untouched. This
    # is export-only — the MT bidix is unaffected.
    merged_pairs = 0
    for cap in [k for k in vortaro if k != 'metadata' and k[:1].isupper()]:
        low = cap.lower()
        if low == cap or low not in vortaro:
            continue
        cap_e, low_e = vortaro[cap], vortaro[low]
        seen, words = set(), []
        for w in low_e['esperanto_words'] + cap_e['esperanto_words']:
            if w.casefold() not in seen:
                seen.add(w.casefold())
                words.append(w)
        low_e['esperanto_words'] = words
        low_e['sources'] = sorted(set(low_e['sources']) | set(cap_e['sources']))
        if not low_e.get('morfologio') and cap_e.get('morfologio'):
            low_e['morfologio'] = cap_e['morfologio']
        del vortaro[cap]
        merged_pairs += 1

    # Update metadata
    vortaro["metadata"]["total_unique_ido_words"] = len(vortaro) - 1
    vortaro["metadata"]["source_stats"] = source_counts
    vortaro["metadata"]["junk_removed"] = junk_count
    vortaro["metadata"]["case_pairs_merged"] = merged_pairs

    print(f"Writing {output_path}...")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(vortaro, f, ensure_ascii=False, indent=2)

    print(f"✅ Converted {len(vortaro) - 1} entries")
    print(f"🗑️  Filtered {junk_count} junk lemmas")
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

