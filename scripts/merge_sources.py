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
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime
from collections import defaultdict

# Import validation
sys.path.insert(0, str(Path(__file__).parent))
from validate_schema import load_schema, validate_file


SOURCE_PRIORITY = {
    'function_words_seed': 5,  # Highest priority for manually curated function words
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
    - Prefer lowercase forms (function words and common lemmas are lowercase)
    - Within casing, prefer higher source priority: lexicon > wiktionary > wikipedia > bert
    - Fallback to the first lemma lowercased
    """
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
    
    Ido is highly regular:
    - Nouns end in -o (singular), -i (plural)
    - Adjectives end in -a
    - Adverbs end in -e
    - Verbs end in -ar (infinitive), -as (present), -is (past), -os (future)
    
    Also checks known function words.
    
    Args:
        lemma: The word to analyze
        source: Source name (e.g., 'io_wikipedia') - used for proper noun detection
        existing_pos: Existing POS tag - if 'np', don't override with verb endings
    """
    lemma_lower = lemma.lower().strip()
    
    # Skip very short words or non-alphabetic
    if len(lemma_lower) < 2:
        return {}
    
    # Skip if not mostly alphabetic
    if not lemma_lower.replace('-', '').replace('.', '').isalpha():
        return {}
    
    # CRITICAL: If entry is from Wikipedia or already has np POS, treat -is endings as proper nouns
    # Wikipedia entries are almost always proper nouns (places, people, etc.)
    # Examples: Paris, Adonis, Artemis, Briseis - these are proper nouns, not verbs
    is_wikipedia = source and 'wikipedia' in source.lower()
    is_proper_noun = existing_pos and existing_pos.lower() in {'np', 'proper noun', 'proper_noun'}
    
    if is_wikipedia or is_proper_noun:
        # For Wikipedia entries, don't treat -is as verb ending
        # They're likely proper nouns (Greek names, place names, etc.)
        pass
    else:
        # Verb conjugated forms (only if not from Wikipedia and not already proper noun)
        if lemma_lower.endswith('is') and len(lemma_lower) > 3:
            return {'pos': 'vblex', 'paradigm': 'ar__vblex'}
    
    # Verb infinitives (most specific)
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
    
    # Nouns (singular -o)
    if lemma_lower.endswith('o'):
        return {'pos': 'n', 'paradigm': 'o__n'}
    
    # Nouns (plural -i)
    if lemma_lower.endswith('i') and len(lemma_lower) > 2:
        return {'pos': 'n', 'paradigm': 'o__n'}
    
    # Adjectives
    if lemma_lower.endswith('a'):
        return {'pos': 'adj', 'paradigm': 'a__adj'}
    
    # Adverbs
    if lemma_lower.endswith('e') and len(lemma_lower) > 2:
        return {'pos': 'adv', 'paradigm': 'e__adv'}
    
    # Unknown
    return {}


def assign_paradigm_from_pos(pos: str) -> Optional[str]:
    """
    Assign paradigm based on POS tag.
    
    Maps POS tags to Apertium paradigms:
    - pr (preposition) → __pr
    - cnjcoo (coordinating conjunction) → __cnjcoo
    - cnjsub (subordinating conjunction) → __cnjsub
    - det (determiner) → __det
    - prn (pronoun) → __prn
    - np (proper noun) → np__np
    - n (noun) → o__n (if not already set)
    - adj (adjective) → a__adj (if not already set)
    - adv (adverb) → e__adv (if not already set)
    - vblex (verb) → ar__vblex (if not already set)
    """
    pos_lower = pos.lower().strip()
    
    # Function word paradigms (invariable)
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
    
    # Regular word paradigms (only if not already set)
    # These are typically inferred from word endings, not POS
    # But we can use them as fallback
    if pos_lower in {'n', 'noun', 'substantivo'}:
        return 'o__n'
    elif pos_lower in {'adj', 'adjective', 'adjektivo'}:
        return 'a__adj'
    elif pos_lower in {'adv', 'adverb', 'adverbo'}:
        return 'e__adv'
    elif pos_lower in {'v', 'vblex', 'verb', 'verbo'}:
        return 'ar__vblex'
    
    return None


def apply_morphology_inference(entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Apply morphology inference to all entries that don't have morphology.
    
    Strategy:
    1. Try to infer from word form (endings)
    2. If POS exists but no paradigm, assign paradigm from POS
    3. If neither exists, try to infer both from word form
    """
    inferred_count = 0
    paradigm_assigned_count = 0
    
    for entry in entries:
        lemma = entry.get('lemma', '').strip()
        if not lemma:
            continue
        
        # Skip if already has paradigm
        if entry.get('morphology', {}).get('paradigm'):
            continue
        
        source = entry.get('source', '')
        existing_pos = entry.get('pos')
        lemma_lower = lemma.lower()
        
        # CRITICAL: Wikipedia entries are almost always proper nouns
        # If entry is from Wikipedia and has no POS, default to proper noun
        # Also: Wikipedia entries ending in -is are likely proper nouns (Greek names, etc.)
        # Override incorrect verb classification
        is_wikipedia = source and 'wikipedia' in source.lower()
        if is_wikipedia:
            if not existing_pos:
                entry['pos'] = 'np'
                existing_pos = 'np'
            elif existing_pos == 'vblex' and lemma_lower.endswith('is') and len(lemma_lower) > 3:
                # Override: Wikipedia entries ending in -is should be proper nouns, not verbs
                entry['pos'] = 'np'
                existing_pos = 'np'
        
        # Try to infer from word form
        # Pass source and existing POS to handle Wikipedia proper nouns correctly
        inferred = infer_ido_morphology(lemma, source=source, existing_pos=existing_pos)
        if inferred:
            # Don't override np with inferred pos if it's from Wikipedia
            if inferred.get('pos') and not (is_wikipedia and existing_pos == 'np'):
                entry['pos'] = inferred.get('pos')
            if inferred.get('paradigm'):
                if 'morphology' not in entry:
                    entry['morphology'] = {}
                entry['morphology']['paradigm'] = inferred.get('paradigm')
                inferred_count += 1
                continue
        
        # If we have POS but no paradigm, assign paradigm from POS
        pos = entry.get('pos')
        if pos:
            paradigm = assign_paradigm_from_pos(pos)
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
    # Remove arrows and what follows
    if '↓' in term:
        term = term.split('↓')[0].strip()
    
    # Remove parenthetical hints like (indikante aganton)
    # But be careful not to remove valid parentheses in math/chemistry if any
    if '(' in term and ')' in term:
        # Simple check for now: if it looks like a hint
        if 'indikante' in term or 'vortospeco' in term or '{' in term:
             term = term.split('(')[0].strip()
    
    return term.strip()


def deduplicate_translations(translations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Deduplicate translations: merge identical ones, keep different ones.
    
    Returns translations with sources array and max confidence.
    """
    # Group by (term, lang)
    grouped = defaultdict(list)
    for trans in translations:
        # Clean the term first
        cleaned_term = clean_translation_term(trans['term'])
        trans['term'] = cleaned_term
        
        key = (cleaned_term, trans['lang'])
        grouped[key].append(trans)
    
    deduplicated = []
    for (term, lang), trans_group in grouped.items():
        if len(trans_group) == 1:
            # Single translation - convert to sources array
            trans = trans_group[0].copy()
            if 'source' in trans and 'sources' not in trans:
                trans['sources'] = [trans['source']]
                del trans['source']
            deduplicated.append(trans)
        else:
            # Multiple identical translations - merge
            merged_trans = {
                'term': term,
                'lang': lang,
                'confidence': max(t['confidence'] for t in trans_group),
                'sources': []
            }
            
            # Collect all sources
            for trans in trans_group:
                if 'source' in trans:
                    merged_trans['sources'].append(trans['source'])
                elif 'sources' in trans:
                    merged_trans['sources'].extend(trans['sources'])
            
            # Deduplicate sources
            merged_trans['sources'] = sorted(list(set(merged_trans['sources'])))
            deduplicated.append(merged_trans)
    
    return deduplicated


def merge_entry_group(entries: List[Dict[str, Any]], canonical_lemma: str) -> Dict[str, Any]:
    """Merge multiple entries with same lemma (handles entries with/without POS)."""
    base_entry = entries[0].copy()
    if canonical_lemma:
        base_entry['lemma'] = canonical_lemma
    
    # Collect all translations
    all_translations = []
    for entry in entries:
        all_translations.extend(entry.get('translations', []))
    
    # Deduplicate translations
    merged_translations = deduplicate_translations(all_translations)
    base_entry['translations'] = merged_translations
    
    # Merge POS (prefer lexicon > wiktionary > wikipedia > bert)
    # CRITICAL: Wikipedia entries are almost always proper nouns when tagged as np
    # Override BERT's suffix-based guesses for proper nouns
    pos_priority = {'function_words_seed': 5, 'ido_lexicon': 4, 'io_wiktionary': 3, 'eo_wiktionary': 3, 'io_wikipedia': 2, 'bert_embeddings': 1, 'bert': 1}
    best_pos = None
    best_pos_priority = 0
    has_wikipedia_np = False
    
    for entry in entries:
        if entry.get('pos'):
            source = entry.get('source', '')
            pos = entry.get('pos')
            
            # Check if Wikipedia has np (proper noun) - this should override BERT's vblex
            if source == 'io_wikipedia' and pos == 'np':
                has_wikipedia_np = True
            
            priority = pos_priority.get(source, 0)
            if priority > best_pos_priority:
                best_pos = pos
                best_pos_priority = priority
    
    # If Wikipedia says it's a proper noun, use that (override BERT's suffix guess)
    if has_wikipedia_np:
        best_pos = 'np'
    
    if best_pos:
        base_entry['pos'] = best_pos
    
    # Merge morphology (prefer lexicon > wiktionary > wikipedia > bert)
    # CRITICAL: If we overrode POS to np, also override paradigm
    # CRITICAL: For function words, prefer Wiktionary (more accurate POS/paradigm)
    morphology_priority = {'function_words_seed': 5, 'ido_lexicon': 4, 'io_wiktionary': 3, 'eo_wiktionary': 3, 'io_wikipedia': 2, 'bert_embeddings': 1, 'bert': 1}
    best_morphology = None
    best_priority = 0
    has_wikipedia_morphology = False
    
    # Check if this is a function word (conjunction, preposition, etc.)
    is_function_word = best_pos and best_pos.lower() in {'cnjcoo', 'cnjsub', 'pr', 'prep', 'det', 'prn'}
    
    for entry in entries:
        if 'morphology' in entry and entry['morphology'].get('paradigm'):
            source = entry.get('source', '')
            paradigm = entry['morphology'].get('paradigm')
            
            # Check if Wikipedia has np__np paradigm
            if source == 'io_wikipedia' and paradigm == 'np__np':
                has_wikipedia_morphology = True
            
            priority = morphology_priority.get(source, 0)
            if priority > best_priority:
                best_morphology = entry['morphology']
                best_priority = priority
    
    # If we overrode POS to np, also override paradigm to np__np
    if has_wikipedia_np:
        if 'morphology' not in base_entry:
            base_entry['morphology'] = {}
        base_entry['morphology']['paradigm'] = 'np__np'
    elif best_morphology:
        # For function words, verify the paradigm matches the POS
        # Wikipedia might have wrong paradigm (e.g., "e" as e__adv instead of __cnjcoo)
        # Check if POS maps to a function word paradigm
        expected_paradigm = assign_paradigm_from_pos(best_pos) if best_pos else None
        is_function_word_paradigm = expected_paradigm and expected_paradigm.startswith('__')
        
        if is_function_word_paradigm and best_morphology.get('paradigm') != expected_paradigm:
            # Override with correct paradigm for function words
            base_entry['morphology'] = {'paradigm': expected_paradigm}
        else:
            base_entry['morphology'] = best_morphology
    elif best_pos:
        # For entries without morphology, assign paradigm from POS
        paradigm = assign_paradigm_from_pos(best_pos)
        if paradigm:
            if 'morphology' not in base_entry:
                base_entry['morphology'] = {}
            base_entry['morphology']['paradigm'] = paradigm
    elif is_function_word:
        # For function words without morphology, assign paradigm from POS
        paradigm = assign_paradigm_from_pos(best_pos)
        if paradigm:
            if 'morphology' not in base_entry:
                base_entry['morphology'] = {}
            base_entry['morphology']['paradigm'] = paradigm
    
    # Collect all sources
    all_sources = list(set(entry.get('source') for entry in entries if entry.get('source')))
    if len(all_sources) > 1:
        base_entry['metadata'] = base_entry.get('metadata', {})
        base_entry['metadata']['merged_from_sources'] = sorted(all_sources)
    
    return base_entry


def deduplicate_entries(entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Intelligently deduplicate entries with multi-source provenance.
    
    Strategy:
    - Group by (lemma, pos)
    - Merge identical translations → sources array, max confidence
    - Keep different translations
    - Prefer lexicon morphology
    """
    # Group entries by lemma only (not pos)
    # This allows merging entries where one source has POS and another doesn't
    grouped = defaultdict(list)
    
    # First pass: collect all infinitive verbs to help filter conjugated forms
    infinitive_lemmas = set()
    for entry in entries:
        lemma = entry['lemma'].strip().lower()
        if lemma.endswith('ar'):
            infinitive_lemmas.add(lemma)

    for entry in entries:
        key = entry['lemma'].strip().lower()  # Just lemma, not (lemma, pos)
        grouped[key].append(entry)
    
    deduplicated = []
    stats = {
        'original_count': len(entries),
        'merged_count': 0,
        'pos_conflicts': 0,
        'conjugated_dropped': 0
    }
    
    for lemma, entry_group in grouped.items():
        # FILTER: If this is a conjugated verb form (ends in -as, -is, -os, -ez, -us)
        # AND we have the infinitive (-ar) form in our dataset
        # AND the source isn't explicitly defining it as a separate lemma (e.g. noun form)
        # THEN drop it to prevent "Tense Mismatch" where conjugated form is treated as lemma
        
        # Check if it looks like a conjugated verb
        suffix = None
        if lemma.endswith('as'): suffix = 'as'
        elif lemma.endswith('is'): suffix = 'is'
        elif lemma.endswith('os'): suffix = 'os'
        elif lemma.endswith('ez'): suffix = 'ez'
        elif lemma.endswith('us'): suffix = 'us'
        
        if suffix and len(lemma) > 3:
            root = lemma[:-2] # remove suffix
            infinitive = root + 'ar'
            
            # If we have the infinitive, this is likely a duplicate/garbage entry
            if infinitive in infinitive_lemmas:
                # Check if it's being used as a Noun or Adjective?
                # If any entry in the group has POS 'n' or 'adj', keep it.
                # If all are 'vblex' or unknown, drop it.
                has_non_verb = False
                for e in entry_group:
                    p = e.get('pos', '').lower()
                    if p and p not in {'v', 'vblex', 'verb'}:
                        has_non_verb = True
                        break
                
                if not has_non_verb:
                    # Drop this group
                    stats['conjugated_dropped'] += 1
                    continue

        # Choose canonical lemma (prefer lowercase + higher priority source)
        canonical_lemma = choose_canonical_lemma(entry_group)
        if len(entry_group) == 1:
            # No duplicates
            entry = entry_group[0]
            if canonical_lemma:
                entry['lemma'] = canonical_lemma
            # Convert single source to sources array in translations
            for trans in entry.get('translations', []):
                if 'source' in trans and 'sources' not in trans:
                    trans['sources'] = [trans['source']]
                    del trans['source']
            deduplicated.append(entry)
            continue
        
        # Multiple entries with same lemma - merge them
        merged_entry = merge_entry_group(entry_group, canonical_lemma)
        deduplicated.append(merged_entry)
        stats['merged_count'] += len(entry_group) - 1
    
    print(f"\nDeduplication stats:")
    print(f"  Original entries: {stats['original_count']:,}")
    print(f"  After deduplication: {len(deduplicated):,}")
    print(f"  Entries merged: {stats['merged_count']:,}")
    print(f"  Conjugated forms dropped: {stats['conjugated_dropped']:,}")
    
    return deduplicated


def merge_all_sources(sources_dir: Path, schema: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merge all source JSON files with intelligent deduplication.
    
    Returns merged data with deduplicated entries and multi-source provenance.
    """
    source_files = sorted(sources_dir.glob('source_*.json'))
    
    if not source_files:
        print(f"ERROR: No source_*.json files found in {sources_dir}")
        sys.exit(1)
    
    print(f"\n{'='*70}")
    print(f"MERGING {len(source_files)} SOURCE FILES")
    print(f"{'='*70}\n")
    
    all_entries = []
    source_stats = defaultdict(int)
    
    for source_file in source_files:
        entries = load_source_file(source_file, schema)
        all_entries.extend(entries)
        
        # Track statistics
        source_name = source_file.stem.replace('source_', '')
        source_stats[source_name] = len(entries)
    
    print(f"\n{'='*70}")
    print(f"DEDUPLICATING ENTRIES")
    print(f"{'='*70}")
    
    # Deduplicate with multi-source provenance
    deduplicated_entries = deduplicate_entries(all_entries)
    
    print(f"\n{'='*70}")
    print(f"INFERRING MORPHOLOGY")
    print(f"{'='*70}")
    
    # Apply morphology inference to entries without paradigms
    deduplicated_entries = apply_morphology_inference(deduplicated_entries)
    
    print(f"\n{'='*70}")
    print(f"MERGE COMPLETE")
    print(f"{'='*70}")
    print(f"Total entries after deduplication: {len(deduplicated_entries):,}")
    print(f"\nPer-source breakdown (before deduplication):")
    for source, count in sorted(source_stats.items()):
        print(f"  {source}: {count:,} entries")
    
    # Create merged metadata
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
    
    return {
        "metadata": merged_metadata,
        "entries": deduplicated_entries
    }


def separate_bidix_monodix(merged_data: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Separate merged data into bidix (with translations) and monodix (all entries).
    
    Returns:
        (bidix_data, monodix_data)
    """
    entries = merged_data['entries']
    
    # Bidix: entries with Esperanto translations
    bidix_entries = [
        entry for entry in entries
        if any(t.get('lang') == 'eo' for t in entry.get('translations', []))
    ]
    
    # Monodix: all Ido entries (for morphological analysis)
    monodix_entries = entries
    
    bidix_metadata = {
        **merged_data['metadata'],
        "source_name": "merged_bidix",
        "statistics": {
            **merged_data['metadata']['statistics'],
            "total_entries": len(bidix_entries)
        }
    }
    
    monodix_metadata = {
        **merged_data['metadata'],
        "source_name": "merged_monodix",
        "statistics": {
            **merged_data['metadata']['statistics'],
            "total_entries": len(monodix_entries)
        }
    }
    
    return (
        {"metadata": bidix_metadata, "entries": bidix_entries},
        {"metadata": monodix_metadata, "entries": monodix_entries}
    )


def main():
    script_dir = Path(__file__).parent
    data_dir = script_dir.parent
    sources_dir = data_dir / 'sources'
    merged_dir = data_dir / 'merged'
    schema_path = data_dir / 'schema.json'
    
    if not sources_dir.exists():
        print(f"ERROR: Sources directory not found: {sources_dir}")
        sys.exit(1)
    
    if not schema_path.exists():
        print(f"ERROR: Schema not found: {schema_path}")
        sys.exit(1)
    
    schema = load_schema(schema_path)
    
    # Merge all sources
    merged_data = merge_all_sources(sources_dir, schema)
    
    # Separate into bidix and monodix
    bidix_data, monodix_data = separate_bidix_monodix(merged_data)
    
    # Save merged files
    merged_dir.mkdir(parents=True, exist_ok=True)
    
    bidix_path = merged_dir / 'merged_bidix.json'
    monodix_path = merged_dir / 'merged_monodix.json'
    
    print(f"\n{'='*70}")
    print(f"SAVING MERGED FILES")
    print(f"{'='*70}")
    
    with open(bidix_path, 'w', encoding='utf-8') as f:
        json.dump(bidix_data, f, indent=2, ensure_ascii=False)
    print(f"✅ Saved bidix: {bidix_path}")
    print(f"   Entries: {len(bidix_data['entries']):,}")
    
    with open(monodix_path, 'w', encoding='utf-8') as f:
        json.dump(monodix_data, f, indent=2, ensure_ascii=False)
    print(f"✅ Saved monodix: {monodix_path}")
    print(f"   Entries: {len(monodix_data['entries']):,}")
    
    print(f"\n{'='*70}")
    print(f"✅ MERGE COMPLETE")
    print(f"{'='*70}")


if __name__ == '__main__':
    main()
