#!/usr/bin/env python3
"""
Merge all source JSON files into unified merged files.

All sources must use the unified format. Implements intelligent deduplication
with multi-source provenance tracking.

Deduplication strategy:
- Same lemma + same translation → Merge sources, take max confidence
- Same lemma + different translations → Keep all variants
- Same lemma + different POS → Keep as separate entries, flag conflict
- Same lemma + different morphology → Prefer lexicon > wiktionary > bert

Morphology inference:
- If an entry has no morphology, infer from Ido word endings
- Ido is highly regular: -o (noun), -a (adj), -ar (verb), -e (adv)
"""

import json
import sys
import re
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime
from collections import defaultdict

# Import validation
sys.path.insert(0, str(Path(__file__).parent))
from validate_schema import load_schema, validate_file


SOURCE_PRIORITY = {
    'ido_lexicon': 4,
    'io_wiktionary': 3,
    'eo_wiktionary': 3,
    'io_wikipedia': 2,
    'bert_embeddings': 1,
    'bert': 1,
}


def choose_canonical_lemma(entries: List[Dict[str, Any]]) -> str:
    """
    Choose a canonical lemma for a group of entries.

    Rules:
    - Prefer exact case if it comes from a high priority source (Seed > Wiktionary)
    - Prefer lowercase for common words (from BERT/Wikipedia)
    - Fallback to the first lemma lowercased
    """
    # 1. Try to find if any high-priority source has this lemma
    # Sort by priority descending
    sorted_entries = sorted(entries, key=lambda e: SOURCE_PRIORITY.get(e.get('source', ''), 0), reverse=True)
    best_source_priority = SOURCE_PRIORITY.get(sorted_entries[0].get('source', ''), 0)
    
    if best_source_priority >= 3: # Wiktionary or higher
        # Use the lemma exactly as it appears in the highest priority source
        return sorted_entries[0].get('lemma', '').strip()

    # 2. Otherwise, prefer lowercase forms
    best: Optional[Tuple[int, int, str]] = None  # (is_lower, priority, lemma_lower)
    for entry in entries:
        lemma = entry.get('lemma', '').strip()
        if not lemma:
            continue
        is_lower = 1 if lemma.islower() else 0
        priority = SOURCE_PRIORITY.get(entry.get('source', ''), 0)
        lemma_lower = lemma.lower()
        candidate = (is_lower, priority, lemma_lower)
        if best is None or candidate > best:
            best = candidate
    if best:
        return best[2]
    # Fallback: lowercased first lemma
    for entry in entries:
        lemma = entry.get('lemma', '').strip()
        if lemma:
            return lemma.lower()
    return ''


def infer_ido_morphology(lemma: str, source: Optional[str] = None, existing_pos: Optional[str] = None) -> Dict[str, str]:
    """
    Infer POS and paradigm from Ido word endings.
    """
    lemma_lower = lemma.lower().strip()
    
    # Skip very short words or non-alphabetic
    if len(lemma_lower) < 2:
        return {}
    
    # Skip if not mostly alphabetic
    if not lemma_lower.replace('-', '').replace('.', '').isalpha():
        return {}
    
    # Proper nouns from Wikipedia often end in -is
    is_wikipedia = source and 'wikipedia' in source.lower()
    is_proper_noun = existing_pos and existing_pos.lower() in {'np', 'proper noun', 'proper_noun'}
    
    if is_wikipedia or is_proper_noun:
        pass
    else:
        # Verb conjugated forms
        if lemma_lower.endswith('is') and len(lemma_lower) > 3:
            return {'pos': 'vblex', 'paradigm': 'ar__vblex'}
    
    # Verb infinitives
    if lemma_lower.endswith('ar'):
        return {'pos': 'vblex', 'paradigm': 'ar__vblex'}
    
    # Verb conjugated forms
    if lemma_lower.endswith('as') and len(lemma_lower) > 3:
        return {'pos': 'vblex', 'paradigm': 'ar__vblex'}
    
    if lemma_lower.endswith('os') and len(lemma_lower) > 3:
        return {'pos': 'vblex', 'paradigm': 'ar__vblex'}
    
    if lemma_lower.endswith('us') and len(lemma_lower) > 3:
        return {'pos': 'vblex', 'paradigm': 'ar__vblex'}
    
    if lemma_lower.endswith('ez') and len(lemma_lower) > 3:
        return {'pos': 'vblex', 'paradigm': 'ar__vblex'}
    
    # Nouns
    if lemma_lower.endswith('o'):
        return {'pos': 'n', 'paradigm': 'o__n'}
    
    # Nouns (plural)
    if lemma_lower.endswith('i') and len(lemma_lower) > 2:
        return {'pos': 'n', 'paradigm': 'o__n'}
    
    # Adjectives
    if lemma_lower.endswith('a'):
        return {'pos': 'adj', 'paradigm': 'a__adj'}
    
    # Adverbs
    if lemma_lower.endswith('e') and len(lemma_lower) > 2:
        return {'pos': 'adv', 'paradigm': 'e__adv'}
    
    return {}


def assign_paradigm_from_pos(pos: str, lemma: str = "") -> Optional[str]:
    """Assign paradigm based on POS tag and lemma."""
    pos_lower = pos.lower().strip()
    lemma_lower = lemma.lower().strip() if lemma else ""
    
    if pos_lower in {'pr', 'prep', 'preposition'}:
        return '__pr'
    elif pos_lower in {'cnjcoo', 'coordinating conjunction', 'conjunction'}:
        return '__cnjcoo'
    elif pos_lower in {'cnjsub', 'subordinating conjunction'}:
        return '__cnjsub'
    elif pos_lower in {'det', 'determiner'}:
        return '__det'
    elif pos_lower in {'prn', 'pronoun'}:
        return '__prn'
    elif pos_lower in {'np', 'proper noun', 'proper_noun'}:
        return 'np__np'
    
    if pos_lower in {'n', 'noun', 'substantivo'}:
        return 'o__n'
    elif pos_lower in {'adj', 'adjective', 'adjektivo'}:
        return 'a__adj'
    elif pos_lower in {'adv', 'adverb', 'adverbo'}:
        if lemma_lower and not lemma_lower.endswith('e'):
            return '__adv'
        return 'e__adv'
    elif pos_lower in {'v', 'vblex', 'verb', 'verbo'}:
        return 'ar__vblex'
    
    return None


def apply_morphology_inference(entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Apply morphology inference to all entries that don't have morphology."""
    inferred_count = 0
    paradigm_assigned_count = 0
    
    for entry in entries:
        lemma = entry.get('lemma', '').strip()
        if not lemma:
            continue
        
        if entry.get('morphology', {}).get('paradigm'):
            continue
        
        source = entry.get('source', '')
        existing_pos = entry.get('pos')
        lemma_lower = lemma.lower()
        
        is_wikipedia = source and 'wikipedia' in source.lower()
        if is_wikipedia:
            if not existing_pos:
                entry['pos'] = 'np'
                existing_pos = 'np'
            elif existing_pos == 'vblex' and lemma_lower.endswith('is') and len(lemma_lower) > 3:
                entry['pos'] = 'np'
                existing_pos = 'np'
        
        # Don't overwrite explicitly-set function-word POS with morphological guesses.
        # Words like 'ka' (ends in -a but is cnjsub) must keep their declared POS.
        function_word_pos = {'prn', 'det', 'pr', 'prep', 'cnjcoo', 'cnjsub', 'ij'}
        if existing_pos and existing_pos.lower() in function_word_pos:
            # Skip morphological inference entirely — just assign paradigm from POS
            paradigm = assign_paradigm_from_pos(existing_pos, lemma)
            if paradigm:
                if 'morphology' not in entry:
                    entry['morphology'] = {}
                entry['morphology']['paradigm'] = paradigm
                paradigm_assigned_count += 1
            continue

        inferred = infer_ido_morphology(lemma, source=source, existing_pos=existing_pos)
        if inferred:
            if inferred.get('pos') and not (is_wikipedia and existing_pos == 'np'):
                entry['pos'] = inferred.get('pos')
            if inferred.get('paradigm'):
                if 'morphology' not in entry:
                    entry['morphology'] = {}
                entry['morphology']['paradigm'] = inferred.get('paradigm')
                inferred_count += 1
                continue
        
        pos = entry.get('pos')
        if pos:
            paradigm = assign_paradigm_from_pos(pos, lemma)
            if paradigm:
                if 'morphology' not in entry:
                    entry['morphology'] = {}
                entry['morphology']['paradigm'] = paradigm
                paradigm_assigned_count += 1
    
    print(f"  Morphology inferred for {inferred_count:,} entries")
    print(f"  Paradigm assigned from POS for {paradigm_assigned_count:,} entries")
    return entries


def load_source_file(file_path: Path, schema: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Load and validate a source file."""
    print(f"Loading {file_path.name}...")
    
    is_valid, errors = validate_file(file_path, schema)
    if not is_valid:
        print(f"ERROR: {file_path.name} failed validation:")
        for error in errors:
            print(f"  {error}")
        sys.exit(1)
    
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    entries = data.get('entries', [])
    source_name = data.get('metadata', {}).get('source_name', file_path.stem)
    
    print(f"  ✅ Loaded {len(entries):,} entries from {source_name}")
    return entries


def clean_translation_term(term: str) -> str:
    """Clean translation term by removing metadata markers."""
    if '↓' in term:
        term = term.split('↓')[0].strip()
    if '(' in term and ')' in term:
        if 'indikante' in term or 'vortospeco' in term or '{' in term:
             term = term.split('(')[0].strip()
    return term.strip()


def deduplicate_translations(translations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Deduplicate translations."""
    grouped = defaultdict(list)
    for trans in translations:
        cleaned_term = clean_translation_term(trans['term'])
        trans['term'] = cleaned_term
        key = (cleaned_term, trans['lang'])
        grouped[key].append(trans)
    
    deduplicated = []
    for (term, lang), trans_group in grouped.items():
        if len(trans_group) == 1:
            trans = trans_group[0].copy()
            if 'source' in trans and 'sources' not in trans:
                trans['sources'] = [trans['source']]
                del trans['source']
            deduplicated.append(trans)
        else:
            merged_trans = {
                'term': term,
                'lang': lang,
                'confidence': max(t['confidence'] for t in trans_group),
                'sources': []
            }
            for trans in trans_group:
                if 'source' in trans:
                    merged_trans['sources'].append(trans['source'])
                elif 'sources' in trans:
                    merged_trans['sources'].extend(trans['sources'])
            merged_trans['sources'] = sorted(list(set(merged_trans['sources'])))
            deduplicated.append(merged_trans)
    return deduplicated


def merge_entry_group(entries: List[Dict[str, Any]], canonical_lemma: str) -> Dict[str, Any]:
    """Merge multiple entries with same lemma."""
    base_entry = entries[0].copy()
    if canonical_lemma:
        base_entry['lemma'] = canonical_lemma
    
    all_translations = []
    for entry in entries:
        all_translations.extend(entry.get('translations', []))
    
    merged_translations = deduplicate_translations(all_translations)
    base_entry['translations'] = merged_translations
    
    pos_priority = {'ido_lexicon': 4, 'io_wiktionary': 3, 'eo_wiktionary': 3, 'io_wikipedia': 2, 'bert_embeddings': 1, 'bert': 1}
    best_pos = None
    best_pos_priority = 0
    has_wikipedia_np = False
    
    for entry in entries:
        if entry.get('pos'):
            source = entry.get('source', '')
            pos = entry.get('pos')
            if pos == 'np' or pos == 'proper noun':
                has_wikipedia_np = True
            priority = pos_priority.get(source, 0)
            if pos == 'np' or pos == 'proper noun':
                priority += 10
            if priority > best_pos_priority:
                best_pos = pos
                best_pos_priority = priority
    
    if has_wikipedia_np:
        best_pos = 'np'
    if best_pos:
        base_entry['pos'] = best_pos
    
    morphology_priority = {'ido_lexicon': 4, 'io_wiktionary': 3, 'eo_wiktionary': 3, 'io_wikipedia': 2, 'bert_embeddings': 1, 'bert': 1}
    best_morphology = None
    best_priority = 0
    
    for entry in entries:
        if 'morphology' in entry and entry['morphology'].get('paradigm'):
            source = entry.get('source', '')
            priority = morphology_priority.get(source, 0)
            if priority > best_priority:
                best_morphology = entry['morphology']
                best_priority = priority
    
    if best_pos == 'np':
        if 'morphology' not in base_entry:
            base_entry['morphology'] = {}
        base_entry['morphology']['paradigm'] = 'np__np'
    elif best_morphology:
        expected_paradigm = assign_paradigm_from_pos(best_pos) if best_pos else None
        is_function_word_paradigm = expected_paradigm and expected_paradigm.startswith('__')
        if is_function_word_paradigm and best_morphology.get('paradigm') != expected_paradigm:
            base_entry['morphology'] = {'paradigm': expected_paradigm}
        else:
            base_entry['morphology'] = best_morphology
    
    all_sources = list(set(entry.get('source') for entry in entries if entry.get('source')))
    if len(all_sources) > 1:
        base_entry['metadata'] = base_entry.get('metadata', {})
        base_entry['metadata']['merged_from_sources'] = sorted(all_sources)
    
    return base_entry


def deduplicate_entries(entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Deduplicate entries with multi-source provenance."""
    grouped = defaultdict(list)
    infinitive_lemmas = set()
    for entry in entries:
        lemma = entry['lemma'].strip().lower()
        if lemma.endswith('ar'):
            infinitive_lemmas.add(lemma)

    for entry in entries:
        key = entry['lemma'].strip().lower()
        grouped[key].append(entry)
    
    deduplicated = []
    stats = {'original_count': len(entries), 'merged_count': 0, 'conjugated_dropped': 0}
    
    for lemma, entry_group in grouped.items():
        suffix = None
        if lemma.endswith('as'): suffix = 'as'
        elif lemma.endswith('is'): suffix = 'is'
        elif lemma.endswith('os'): suffix = 'os'
        elif lemma.endswith('ez'): suffix = 'ez'
        elif lemma.endswith('us'): suffix = 'us'
        
        if suffix and len(lemma) > 3:
            root = lemma[:-2]
            infinitive = root + 'ar'
            if infinitive in infinitive_lemmas:
                has_non_verb = False
                for e in entry_group:
                    p = e.get('pos', '').lower()
                    if p and p not in {'v', 'vblex', 'verb'}:
                        has_non_verb = True
                        break
                if not has_non_verb:
                    stats['conjugated_dropped'] += 1
                    continue

        canonical_lemma = choose_canonical_lemma(entry_group)
        if len(entry_group) == 1:
            entry = entry_group[0]
            if canonical_lemma:
                entry['lemma'] = canonical_lemma
            for trans in entry.get('translations', []):
                if 'source' in trans and 'sources' not in trans:
                    trans['sources'] = [trans['source']]
                    del trans['source']
            deduplicated.append(entry)
            continue
        
        merged_entry = merge_entry_group(entry_group, canonical_lemma)
        deduplicated.append(merged_entry)
        stats['merged_count'] += len(entry_group) - 1
    
    return deduplicated


def merge_all_sources(sources_dir: Path, schema: Dict[str, Any]) -> Dict[str, Any]:
    """Merge all source JSON files."""
    source_files = sorted(sources_dir.glob('source_*.json'))
    if not source_files:
        print(f"ERROR: No source_*.json files found in {sources_dir}")
        sys.exit(1)
    
    all_entries = []
    source_stats = defaultdict(int)
    for source_file in source_files:
        entries = load_source_file(source_file, schema)
        all_entries.extend(entries)
        source_name = source_file.stem.replace('source_', '')
        source_stats[source_name] = len(entries)
    
    deduplicated_entries = deduplicate_entries(all_entries)
    
    overrides = [
        {"lemma": "Ido", "pos": "np", "morphology": {"paradigm": "np__np"}, "translations": [{"term": "Ido<np><al><sg><nom>", "lang": "eo", "confidence": 1.0}]},
        {"lemma": "Esperanto", "pos": "np", "morphology": {"paradigm": "np__np"}, "translations": [{"term": "Esperanto<np><al><sg><nom>", "lang": "eo", "confidence": 1.0}]},
        {"lemma": "Paris", "pos": "np", "morphology": {"paradigm": "np__np"}, "translations": [{"term": "Parizo<np><loc><sg><nom>", "lang": "eo", "confidence": 1.0}]},
        {"lemma": "Lerna", "pos": "np", "morphology": {"paradigm": "np__np"}, "translations": [{"term": "Lerno (Grekujo)<np><al><sg><nom>", "lang": "eo", "confidence": 1.0}]},
        {"lemma": "la", "pos": "det", "translations": [{"term": "la", "lang": "eo", "confidence": 1.0}]},
        {"lemma": "l'", "pos": "det", "translations": [{"term": "la", "lang": "eo", "confidence": 1.0}]},
        {"lemma": "l", "pos": "det", "translations": [{"term": "la", "lang": "eo", "confidence": 1.0}]},
        {"lemma": "kreesar", "pos": "vblex", "morphology": {"paradigm": "ar__vblex"}, "translations": [{"term": "kreiĝi", "lang": "eo", "confidence": 1.0}]},
        {"lemma": "nomizar", "pos": "vblex", "morphology": {"paradigm": "ar__vblex"}, "translations": [{"term": "nomi", "lang": "eo", "confidence": 1.0}]},
        {"lemma": "qui<prn><pl><acc>", "pos": "prn", "translations": [{"term": "kiu<prn><rel><pl><acc>", "lang": "eo", "confidence": 1.0}]},
        {"lemma": "maxim", "pos": "adv", "translations": [{"term": "plej", "lang": "eo", "confidence": 1.0}]},
        {"lemma": "sat", "pos": "adv", "translations": [{"term": "sate", "lang": "eo", "confidence": 1.0}]},
        {"lemma": "sucesoza", "pos": "adj", "translations": [{"term": "sukcesa", "lang": "eo", "confidence": 1.0}]},
        {"lemma": "polisemio", "pos": "n", "morphology": {"paradigm": "o__n"}, "translations": [{"term": "polisemio", "lang": "eo", "confidence": 1.0}]},
        {"lemma": "Delegitaro", "pos": "np", "morphology": {"paradigm": "np__np"}, "translations": [{"term": "Delegitaro<np><al><sg><nom>", "lang": "eo", "confidence": 1.0}]},
        {"lemma": "esperantido", "pos": "n", "morphology": {"paradigm": "o__n"}, "translations": [{"term": "Esperantido", "lang": "eo", "confidence": 1.0}]},
        {"lemma": "kreinto", "pos": "n", "morphology": {"paradigm": "o__n"}, "translations": [{"term": "kreinto", "lang": "eo", "confidence": 1.0}]},
        {"lemma": "originala", "pos": "adj", "translations": [{"term": "originala", "lang": "eo", "confidence": 1.0}]},
        # Ido 3rd-person pronouns absent from wiktionary — translation overridden by
        # EPO_PRONOUN_FORMS in generate_bidix.py; pos=prn is what matters here.
        {"lemma": "il", "pos": "prn", "translations": [{"term": "li", "lang": "eo", "confidence": 1.0}]},
        {"lemma": "el", "pos": "prn", "translations": [{"term": "ŝi", "lang": "eo", "confidence": 1.0}]},
        {"lemma": "ol", "pos": "prn", "translations": [{"term": "ĝi", "lang": "eo", "confidence": 1.0}]},
        {"lemma": "on", "pos": "prn", "translations": [{"term": "oni", "lang": "eo", "confidence": 1.0}]},
        # ka = short form of kad (yes/no question particle), not in wiktionary
        {"lemma": "ka", "pos": "cnjsub", "translations": [{"term": "ĉu", "lang": "eo", "confidence": 1.0}]},
        {"lemma": "qui", "pos": "prn", "translations": [{"term": "kiu<prn><rel><sg><nom>", "lang": "eo", "confidence": 1.0}]},
        {"lemma": "quon", "pos": "prn", "translations": [{"term": "kio<prn><rel><sg><acc>", "lang": "eo", "confidence": 1.0}]},
        {"lemma": "quo", "pos": "prn", "translations": [{"term": "kio<prn><rel><sg><nom>", "lang": "eo", "confidence": 1.0}]},
        {"lemma": "qui", "pos": "prn", "morphology": {"paradigm": "np__np"}, "translations": [{"term": "kiuj<prn><rel><pl><nom>", "lang": "eo", "confidence": 1.0}]},
        {"lemma": "quin", "pos": "prn", "translations": [{"term": "kiujn<prn><rel><pl><acc>", "lang": "eo", "confidence": 1.0}]}
    ]
    
    override_lemmas = {o["lemma"].lower() for o in overrides}
    deduplicated_entries = [e for e in deduplicated_entries if e.get("lemma", "").lower() not in override_lemmas]
    deduplicated_entries.extend(overrides)
    
    deduplicated_entries = apply_morphology_inference(deduplicated_entries)
    
    merged_metadata = {
        "source_name": "merged",
        "version": "1.0",
        "generation_date": datetime.now().isoformat(),
        "statistics": {
            "total_entries": len(deduplicated_entries),
            "original_entries_before_dedup": len(all_entries),
            "sources": dict(source_stats),
            "entries_with_translations": sum(1 for e in deduplicated_entries if e.get('translations')),
            "entries_with_morphology": sum(1 for e in deduplicated_entries if e.get('morphology', {}).get('paradigm'))
        }
    }
    
    return {"metadata": merged_metadata, "entries": deduplicated_entries}


def separate_bidix_monodix(merged_data: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Separate merged data into bidix and monodix."""
    entries = merged_data['entries']
    bidix_entries = [entry for entry in entries if any(t.get('lang') == 'eo' for t in entry.get('translations', []))]
    monodix_entries = entries
    
    bidix_metadata = {**merged_data['metadata'], "source_name": "merged_bidix", "statistics": {**merged_data['metadata']['statistics'], "total_entries": len(bidix_entries)}}
    monodix_metadata = {**merged_data['metadata'], "source_name": "merged_monodix", "statistics": {**merged_data['metadata']['statistics'], "total_entries": len(monodix_entries)}}
    
    return ({"metadata": bidix_metadata, "entries": bidix_entries}, {"metadata": monodix_metadata, "entries": monodix_entries})


def clean_target_dictionaries(base_dir: Path):
    """Surgically clean up target dictionaries to remove ambiguity markers."""
    import xml.etree.ElementTree as ET
    
    epo_dix_path = base_dir.parent.parent / 'apertium' / 'apertium-epo' / 'apertium-epo.epo.dix'
    if not epo_dix_path.exists():
        return

    print(f"\nSURGICAL CLEANING: {epo_dix_path.name}")
    
    try:
        tree = ET.parse(epo_dix_path)
        root = tree.getroot()
        
        def get_base_name(name: str) -> str:
            if not name: return ""
            return name.split('___')[0]

        # 1. Remove duplicate paradigms (base-name aware)
        pardefs = root.find('pardefs')
        if pardefs is not None:
            base_to_preferred = {}
            all_paradefs = pardefs.findall('pardef')
            for pardef in all_paradefs:
                name = pardef.get('n', '')
                base_name = get_base_name(name)
                is_clean = '___' not in name
                if base_name not in base_to_preferred or is_clean:
                    base_to_preferred[base_name] = name
            
            preferred_names = set(base_to_preferred.values())
            to_remove = []
            for pardef in all_paradefs:
                if pardef.get('n') not in preferred_names:
                    to_remove.append(pardef)
            for p in to_remove:
                pardefs.remove(p)
            print(f"  Removed {len(to_remove)} redundant paradigms")

        # 2. Fix la__det paradigm
        for pardef in root.findall('.//pardef'):
            name = pardef.get('n', '')
            if get_base_name(name) == 'la__det':
                for e in pardef.findall('e'):
                    if e.get('r') == 'LR':
                        e.attrib.pop('r')
                        break

        # 3. Remove duplicate main entries (base-name aware)
        sections = root.findall('section')
        for section in sections:
            if section.get('id') == 'main':
                base_to_preferred_lm = {}
                all_entries = section.findall('e')
                for entry in all_entries:
                    lm = entry.get('lm', '')
                    base_lm = get_base_name(str(lm))
                    is_clean = '___' not in str(lm)
                    if base_lm not in base_to_preferred_lm or is_clean:
                        base_to_preferred_lm[base_lm] = str(lm)
                
                preferred_lemmas = set(base_to_preferred_lm.values())
                to_remove = []
                for entry in all_entries:
                    if str(entry.get('lm', '')) not in preferred_lemmas:
                        to_remove.append(entry)
                for e in to_remove:
                    section.remove(e)
                print(f"  Removed {len(to_remove)} redundant main entries")

        tree.write(epo_dix_path, encoding='UTF-8', xml_declaration=True)
        print(f"✅ Surgical cleaning complete")
    except Exception as e:
        print(f"⚠️  Warning: Failed to clean target dictionary: {e}")


def main():
    script_dir = Path(__file__).parent
    data_dir = script_dir.parent
    sources_dir = data_dir / 'sources'
    merged_dir = data_dir / 'merged'
    schema_path = data_dir / 'schema.json'
    
    schema = load_schema(schema_path)
    merged_data = merge_all_sources(sources_dir, schema)
    bidix_data, monodix_data = separate_bidix_monodix(merged_data)
    merged_dir.mkdir(parents=True, exist_ok=True)
    
    with open(merged_dir / 'merged_bidix.json', 'w', encoding='utf-8') as f:
        json.dump(bidix_data, f, indent=2, ensure_ascii=False)
    with open(merged_dir / 'merged_monodix.json', 'w', encoding='utf-8') as f:
        json.dump(monodix_data, f, indent=2, ensure_ascii=False)
    
    clean_target_dictionaries(data_dir)
    print(f"\n✅ MERGE COMPLETE")


if __name__ == '__main__':
    main()
