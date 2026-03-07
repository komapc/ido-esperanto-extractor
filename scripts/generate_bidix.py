#!/usr/bin/env python3
"""
Generate Apertium bidix (.dix) file from merged JSON.

Reads: projects/data/merged/merged_bidix.json
Outputs: Apertium bilingual dictionary XML file

Usage:
    python3 generate_bidix.py --input merged_bidix.json --output ido-epo.ido-epo.dix

CRITICAL RULE: NEVER add words manually to dictionary files (.dix).
All dictionary entries MUST be generated from source JSON files.
If a word is missing, add it to the appropriate source file and regenerate.
"""

import json
import argparse
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional
import re


# Precompiled regex patterns for cleaning translations
# These strip Wiktionary metadata that pollutes dictionary entries
RE_ARROW_MARKERS = re.compile(r'\s*[↓→←↑]\s*')
RE_PARENTHETICAL = re.compile(r'\s*\([^)]*\)\s*')
RE_BRACKET_HINTS = re.compile(r'\s*\[[^\]]*\]\s*')
RE_MULTIPLE_SPACES = re.compile(r'\s+')
_JUNK_LEMMA_RE = re.compile(r'[\d,;()%²³]')


def is_valid_lemma(lemma: str, stem: Optional[str] = None) -> bool:
    """Return False for numbers, dates, units, and other non-word noise."""
    if not lemma:
        return False
    if _JUNK_LEMMA_RE.search(lemma):
        return False
    
    # Filter out participle stems that often appear as junk lemmas from BERT/Wikipedia
    # Examples: "facit", "kreit", "donant", "iront"
    # We check both the lemma and the extracted stem
    for text in [lemma.lower(), stem.lower() if stem else ""]:
        if not text: continue
        if text.endswith(('it', 'ant', 'int', 'ont', 'at', 'ot')):
            # Allow-list for valid short words that happen to end in these suffixes
            if text in {'kant', 'sant', 'granit', 'spirit', 'vundit', 'esperant', 'konstrukt', 'fac', 'dikant', 'indikant', 'sat', 'sucesoz', 'maxim'}:
                continue
            return False
        
    return True


def clean_translation(text: str) -> str:
    """
    Clean translation text by removing Wiktionary metadata markers.
    
    Removes:
    - Arrow markers: ↓, →, ←, ↑
    - Parenthetical hints: (indikante aganton), (noun), etc.
    - Bracket hints: [see also], etc.
    - Multiple spaces
    
    Examples:
        "de ↓ (indikante aganton)" → "de"
        "en ↓" → "en"
        "dika ↓" → "dika"
        "klara ↓, distinta" → "klara, distinta"
    """
    if not text:
        return text
    
    # Remove arrow markers
    text = RE_ARROW_MARKERS.sub(' ', text)
    
    # Remove parenthetical hints
    text = RE_PARENTHETICAL.sub(' ', text)
    
    # Remove bracket hints
    text = RE_BRACKET_HINTS.sub(' ', text)
    
    # Normalize spaces
    text = RE_MULTIPLE_SPACES.sub(' ', text)
    
    # Clean up commas with extra spaces
    text = text.replace(' ,', ',').replace(',  ', ', ')
    
    return text.strip()


# Ido pronoun → correct Esperanto analysis form with full morphological tags.
# The Esperanto autogen requires these tags to produce the right surface form.
# Format: ido_stem -> "epo_lemma<tag1><tag2>..." (parsed by create_bidix_entry)
# Ido pronoun → correct Esperanto analysis form with full morphological tags.
# The Esperanto autogen uses the nomacc paradigm: prpers<prn><p?><mf><sg/pl>
# The transfer adds <nom>, so we omit <subj> here — the pipeline produces the right form.
EPO_PRONOUN_FORMS = {
    'me':  'prpers<prn><p1><mf><sg>',   # mi
    'tu':  'prpers<prn><p2><mf><sp>',   # vi (Esperanto doesn't distinguish sg/pl for p2)
    'il':  'prpers<prn><p3><m><sg>',    # li
    'el':  'prpers<prn><p3><f><sg>',    # ŝi
    'ol':  'prpers<prn><p3><nt><sg>',   # ĝi
    'on':  'oni<prn><tn><sg>',           # oni
    'vu':  'prpers<prn><p2><mf><sp>',   # vi (sg/pl formal)
    'ni':  'prpers<prn><p1><mf><pl>',   # ni
    'vi':  'prpers<prn><p2><mf><sp>',   # vi (pl → same as sg in Esperanto)
    'ili': 'prpers<prn><p3><mf><pl>',   # ili
    'quin': 'prpers<prn><p3><mf><pl>',  # kiujn - approximate
}

# POS mapping from JSON to Apertium symbol definitions
POS_MAP = {
    'n': 'n',           # noun
    'noun': 'n',        # noun (full name)
    'v': 'vblex',       # verb
    'verb': 'vblex',    # verb (full name)
    'vblex': 'vblex',   # verb (already mapped)
    'adj': 'adj',       # adjective
    'adjective': 'n',   # adjective full-name (often misclassified nouns from Wikipedia)
    'adv': 'adv',       # adverb
    'adverb': 'adv',    # adverb (full name)
    'pr': 'pr',         # preposition - must match monodix tag
    'prep': 'pr',       # preposition - normalize to 'pr' to match monodix
    'preposition': 'pr',# preposition (full name)
    'prn': 'prn',       # pronoun
    'pronoun': 'prn',   # pronoun (full name)
    'det': 'det',       # determiner
    'determiner': 'det',# determiner (full name)
    'num': 'num',       # numeral
    'numeral': 'num',   # numeral (full name)
    'cnjcoo': 'cnjcoo', # coordinating conjunction
    'np': 'np',         # proper noun
    'cnjsub': 'cnjsub', # subordinating conjunction
    'ij': 'ij',         # interjection
}


def guess_pos_ido(word: str) -> Optional[str]:
    """Guess POS from Ido word ending."""
    if not word:
        return None
    
    word = word.lower().strip()
    
    if word.endswith('o'):
        return 'n'
    elif word.endswith('ar'):
        return 'vblex'
    elif word.endswith('a') and not word.endswith('ar'):
        return 'adj'
    elif word.endswith('e'):
        return 'adv'
    
    return None


def guess_pos_esperanto(word: str) -> Optional[str]:
    """Guess POS from Esperanto word ending."""
    if not word:
        return None
    
    word = word.lower().strip()
    
    if word.endswith('o'):
        return 'n'
    elif word.endswith('i'):
        return 'vblex'
    elif word.endswith('a') and not word.endswith('i'):
        return 'adj'
    elif word.endswith('e'):
        return 'adv'
    
    return None


def extract_lemma_ido(word: str, pos: Optional[str] = None) -> str:
    """
    Extract lemma (stem) from Ido word.
    
    For Ido:
    - Nouns ending in -o → remove -o (persono → person)
    - Verbs ending in -ar → remove -ar (irar → ir)
    - Adjectives ending in -a → remove -a (bona → bon)
    - Adverbs ending in -e → remove -e (bone → bon)
    - Invariable words (prepositions, conjunctions, etc.) → return as-is
    - Others → return as-is
    
    CRITICAL: If POS is None or unknown, don't guess and strip stems.
    Only strip stems when we're confident about the POS.
    """
    if not word:
        return word
    
    word = word.strip()
    
    # Normalize POS to standard form
    if pos:
        pos_lower = pos.lower()
        if pos_lower in {'conjunction', 'coordinating conjunction'}:
            pos = 'cnjcoo'
        elif pos_lower in {'subordinating conjunction'}:
            pos = 'cnjsub'
        elif pos_lower in {'preposition'}:
            pos = 'prep'
        elif pos_lower in {'determiner', 'article', 'art', 'det'}:
            pos = 'det'
        elif pos_lower in {'pronoun', 'prn'}:
            pos = 'prn'
        elif pos_lower in {'adverb', 'adv'}:
            pos = 'adv'
        elif pos_lower in {'noun', 'adjective'}:
            pos = 'n'
        elif pos_lower in {'verb'}:
            pos = 'vblex'

    # Invariable words (function words) should not have stems extracted
    invariable_pos = {'pr', 'prep', 'cnjcoo', 'cnjsub', 'det', 'prn', 'ij', 'num', 'np'}
    if pos in invariable_pos:
        if pos == 'np':
            return word.strip()
        return word.lower()  # Normalize to lowercase for function words
    
    # CRITICAL FIX: If POS is None, don't guess for short words (likely function words)
    # Short words (2-3 chars) are usually function words and shouldn't have stems stripped
    if not pos:
        if len(word) <= 3:
            # Don't guess POS for short words - they're likely function words
            return word.lower()
        # Only guess POS for longer words
        pos = guess_pos_ido(word)
    
    # Extract stems based on POS (only if we have a confident POS)
    if pos == 'n' and word.endswith('o'):
        return word[:-1]
    elif pos in ('v', 'vblex') and word.endswith('ar'):
        return word[:-2]
    elif pos == 'adj' and word.endswith('a'):
        return word[:-1]
    elif pos == 'adv' and word.endswith('e'):
        return word[:-1]
    
    return word


def extract_lemma_esperanto(word: str, pos: Optional[str] = None) -> str:
    """
    Extract lemma (stem) from Esperanto word.
    
    For Esperanto:
    - Nouns ending in -o → remove -o (homo → hom)
    - Verbs ending in -i → remove -i (iri → ir)
    - Adjectives ending in -a → remove -a (bona → bon)
    - Adverbs ending in -e → remove -e (bone → bon)
    - Others → return as-is
    """
    if not word:
        return word
    
    word = word.strip()
    
    # If POS not provided, guess it
    if not pos:
        pos = guess_pos_esperanto(word)
    
    if pos == 'n' and word.endswith('o'):
        return word[:-1]
    elif pos in ('v', 'vblex') and word.endswith('i'):
        return word[:-1]
    elif pos == 'adj' and word.endswith('a'):
        return word[:-1]
    elif pos == 'adv' and word.endswith('e'):
        return word[:-1]
    
    return word


def create_bidix_entry(ido_lemma: str, epo_lemma: str, confidence: float, 
                       pos: Optional[str] = None, add_pos: bool = True) -> ET.Element:
    """
    Create a bidix entry element.
    Supports lemmas with explicit tags like "Word<tag1><tag2>".
    """
    entry = ET.Element('e')
    
    # Add confidence comment
    comment = ET.Comment(f' confidence: {confidence:.4f} ')
    entry.append(comment)
    
    pair = ET.SubElement(entry, 'p')
    left = ET.SubElement(pair, 'l')
    right = ET.SubElement(pair, 'r')
    
    def add_lemma_with_tags(elem, lemma_str, default_pos):
        if '<' in lemma_str:
            # Parse Word<tag1><tag2>
            parts = re.split(r'[<>]', lemma_str)
            base = parts[0]
            elem.text = base
            for tag in parts[1:]:
                if tag:
                    ET.SubElement(elem, 's').set('n', tag)
        else:
            elem.text = lemma_str
            if add_pos and default_pos and default_pos in POS_MAP:
                ET.SubElement(elem, 's').set('n', POS_MAP[default_pos])

    add_lemma_with_tags(left, ido_lemma, pos)
    add_lemma_with_tags(right, epo_lemma, pos)
    
    return entry


def generate_bidix(input_file: Path, output_file: Path, min_confidence: float = 0.0,
                   add_pos: bool = True):
    """
    Generate Apertium bidix from merged JSON.
    
    Args:
        input_file: Path to merged_bidix.json
        output_file: Path to output .dix file
        min_confidence: Minimum confidence threshold for including translations
        add_pos: Whether to add POS tags to entries
    """
    print(f"Loading merged bidix from {input_file}...")
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    entries = data.get('entries', [])
    metadata = data.get('metadata', {})
    stats = metadata.get('statistics', {})
    
    print(f"Total entries: {len(entries)}")
    print(f"Statistics: {stats}")
    print(f"Min confidence: {min_confidence}")
    print(f"Add POS tags: {add_pos}")
    
    # Create root element
    root = ET.Element('dictionary')
    
    # Add alphabet
    alphabet = ET.SubElement(root, 'alphabet')
    # Empty alphabet for bidix is standard
    
    # Add symbol definitions
    sdefs = ET.SubElement(root, 'sdefs')
    
    # Standard symbol definitions for bidix (must match monodix tag names)
    sdef_list = ['n', 'vblex', 'adj', 'adv', 'prn', 'det', 'pr',
                 'cnjcoo', 'cnjsub', 'num', 'np', 'ord',
                 'sg', 'pl', 'nom', 'acc', 'al', 'loc', 'ant', 'cog',
                 'rel', 'itg', 'p1', 'p2', 'p3', 'm', 'f', 'mf', 'nt',
                 'subj', 'obj', 'tn',
                 'def', 'sp', 'qnt', 'ref', 'pos', 'ij']
    
    for sdef_name in sdef_list:
        sdef = ET.SubElement(sdefs, 'sdef')
        sdef.set('n', sdef_name)
    
    # Add section with entries
    section = ET.SubElement(root, 'section')
    section.set('id', 'main')
    section.set('type', 'standard')
    
    # Track statistics
    entries_added = 0
    
    # Add static entries for numbers and other special cases
    # 1. Ordinal numbers: 24ma -> 24-a
    num_ord_entry = ET.SubElement(section, 'e')
    ET.SubElement(num_ord_entry, 're').text = '[0-9]+\\-a'
    pair = ET.SubElement(num_ord_entry, 'p')
    left = ET.SubElement(pair, 'l')
    ET.SubElement(left, 's').set('n', 'num')
    ET.SubElement(left, 's').set('n', 'ord')
    
    right = ET.SubElement(pair, 'r')
    ET.SubElement(right, 's').set('n', 'num')
    ET.SubElement(right, 's').set('n', 'ord')
    entries_added += 1
    
    # 2. Plain numbers: 1907 -> 1907 (pass-through)
    num_entry = ET.SubElement(section, 'e')
    ET.SubElement(num_entry, 're').text = '[0-9]+'
    pair = ET.SubElement(num_entry, 'p')
    left = ET.SubElement(pair, 'l')
    ET.SubElement(left, 's').set('n', 'num')
    
    right = ET.SubElement(pair, 'r')
    ET.SubElement(right, 's').set('n', 'num')
    entries_added += 1

    entries_skipped_no_translation = 0
    entries_skipped_low_confidence = 0
    entries_skipped_no_lemma = 0
    entries_skipped_junk = 0
    
    for entry in entries:
        lemma = entry.get('lemma', '').strip()
        
        if not lemma:
            entries_skipped_no_lemma += 1
            continue

        translations = entry.get('translations', [])
        
        if not translations:
            entries_skipped_no_translation += 1
            continue
        
        pos = entry.get('pos')
        
        # Guess POS if missing
        if not pos:
            pos = guess_pos_ido(lemma)
        
        # FIX: Correct obviously wrong POS assignments and infer for common function words
        lemma_lower = lemma.lower()
        
        # Special case: 'la' is often mis-tagged as 'adj' but should be 'det' (article)
        if lemma_lower == 'la' and pos == 'adj':
            # Fix wrong POS: la is an article, not an adjective
            pos = 'det'
        
        # CRITICAL: Infer POS for common function words when pos is None
        # These are critical function words that must be recognized
        if pos is None:
            if lemma_lower == 'de':
                pos = 'prep'  # preposition
            elif lemma_lower in {'por', 'kun', 'sur', 'sub', 'per', 'pro', 'sen', 'dum'}:
                pos = 'prep'  # prepositions
            elif lemma_lower in {'ni', 'vi', 'ili', 'ili', 'oni'}:
                pos = 'prn'  # pronouns
            elif lemma_lower in {'kaj', 'sed', 'aŭ', 'nek'}:
                pos = 'cnjcoo'  # coordinating conjunctions
            elif lemma_lower in {'ke', 'se', 'kvankam'}:
                pos = 'cnjsub'  # subordinating conjunctions
            elif lemma_lower in {'ĉu', 'kiel', 'kie', 'kiam'}:
                pos = 'adv'  # question words/adverbs
            elif lemma_lower in {'jam', 'ankoraŭ', 'nun', 'tiam'}:
                pos = 'adv'  # adverbs
        
        # Normalize POS to standard form (conjunction → cnjcoo, etc.)
        pos_normalized = pos
        if pos:
            pos_lower = pos.lower()
            if pos_lower in {'conjunction', 'coordinating conjunction'}:
                pos_normalized = 'cnjcoo'
            elif pos_lower in {'subordinating conjunction'}:
                pos_normalized = 'cnjsub'
            elif pos_lower in {'preposition'}:
                pos_normalized = 'prep'
            elif pos_lower in {'determiner', 'article', 'art', 'det'}:
                pos_normalized = 'det'
            elif pos_lower in {'pronoun', 'prn'}:
                pos_normalized = 'prn'
            elif pos_lower in {'adverb', 'adv'}:
                pos_normalized = 'adv'
        
        # Extract stem for Ido
        paradigm = entry.get('morphology', {}).get('paradigm')
        ido_stem = extract_lemma_ido(lemma, pos_normalized)
        
        # Skip junk lemmas (numbers, units, etc.)
        if not is_valid_lemma(lemma, ido_stem):
            entries_skipped_junk += 1
            continue

        # Function words (conjunctions, prepositions, etc.) MUST have POS tags in bidix
        # because the monodix analyzer outputs them with tags (e.g., a<pr>)
        # and the bilingual lookup needs matching tags to work correctly.
        function_word_pos = {'cnjcoo', 'cnjsub', 'pr', 'prep', 'det', 'prn', 'adv'}
        is_function_word = pos_normalized in function_word_pos if pos_normalized else False
        # Add POS tags for ALL entries including function words
        should_add_pos = add_pos and pos_normalized and pos_normalized in POS_MAP
        
        # Filter and sort translations before processing
        # 1. Filter cognates (identical lemma == translation, case-insensitive)
        # 2. Sort by confidence (highest first)
        valid_translations = []
        
        # PRE-FILTER: For verbs, if we have an infinitive translation (ends in -i),
        # drop any conjugated translations (ends in -as, -is, -os, etc.)
        # This fixes "Tense Mismatch" where present tense forms pollute the bidix
        if pos_normalized in {'v', 'vblex', 'verb'}:
            has_infinitive = any(t.get('term', '').strip().endswith('i') 
                               for t in translations 
                               if t.get('lang') == 'eo' and t.get('term', '').strip())
            
            if has_infinitive:
                # Filter out non-infinitives from the source translations list first
                # (We create a new list to avoid modifying the original in place if used elsewhere)
                translations = [t for t in translations 
                              if t.get('lang') != 'eo' or t.get('term', '').strip().endswith('i')]

        for trans in translations:
            term = trans.get('term', '').strip()
            lang = trans.get('lang', '')
            confidence = trans.get('confidence', 0.0)
            
            # Skip if not Esperanto
            if lang != 'eo':
                continue
            
            # Skip if below confidence threshold
            if confidence < min_confidence:
                entries_skipped_low_confidence += 1
                continue
            
            if not term:
                continue
            
            # CRITICAL: Clean translation of Wiktionary metadata markers
            # Removes ↓, →, ←, parenthetical hints like (indikante aganton), etc.
            term = clean_translation(term)

            # If multiple alternatives separated by comma, take only the first.
            # e.g., "de, da" → "de"  (the autogen can't generate multi-word terms)
            if ',' in term:
                term = term.split(',')[0].strip()

            # Skip if term is empty after cleaning
            if not term:
                continue

            # Check if cognate (identical lemma == translation, case-insensitive)
            is_cognate = lemma_lower == term.lower()
            
            valid_translations.append({
                'term': term,
                'confidence': confidence,
                'is_cognate': is_cognate,
                'trans': trans  # Keep original for other fields
            })
        
        # Filter cognates: remove if other non-cognate translations exist
        # EXCEPTION 1: For function words, keep cognates
        # EXCEPTION 2: If a cognate has high confidence (>= 0.95), keep it!
        non_cognate_count = sum(1 for t in valid_translations if not t['is_cognate'])
        best_non_cognate_conf = max([t['confidence'] for t in valid_translations if not t['is_cognate']] + [0.0])
        best_overall_conf = max([t['confidence'] for t in valid_translations] + [0.0])
        
        if non_cognate_count > 0 and not is_function_word:
            # Only remove cognates if they have lower confidence than the best non-cognate
            # OR if they are low confidence in general.
            # But if we have a 1.0 confidence cognate, we should definitely keep it!
            valid_translations = [t for t in valid_translations 
                                if not t['is_cognate'] or t['confidence'] >= 0.95 or t['confidence'] >= best_non_cognate_conf]
        
        # CRITICAL: Filter out low-confidence translations if we have a high-confidence one
        if best_overall_conf >= 0.95:
            # If we have a very high confidence translation (like from Wiktionary/Seed),
            # drop any translations that have significantly lower confidence (like from BERT)
            # This prevents BERT junk from polluting common words
            valid_translations = [t for t in valid_translations if t['confidence'] >= 0.95 or t['confidence'] >= best_overall_conf - 0.01]
        
        # Sort by confidence (highest first)
        valid_translations.sort(key=lambda t: t['confidence'], reverse=True)
        
        # Process sorted translations
        for trans_data in valid_translations:
            term = trans_data['term']
            confidence = trans_data['confidence']
            
            # Use already extracted stems
            ido_lemma = ido_stem
            epo_lemma = EPO_PRONOUN_FORMS.get(ido_lemma, term) if pos_normalized == 'prn' else term

            # For determiners: strip any embedded XML tags from translation term.
            # The transfer rule for det already adds <def><sp>, so the bidix must
            # supply only the bare lemma+det tag (e.g., la<det>), not la<det><def><sp>.
            if pos_normalized == 'det' and '<' in epo_lemma:
                epo_lemma = epo_lemma.split('<')[0]


            # Skip if either lemma is empty
            if not ido_lemma or not epo_lemma:
                continue

            # Create entry (use should_add_pos instead of add_pos for function words)
            # Use normalized POS for bidix entry
            entry_elem = create_bidix_entry(ido_lemma, epo_lemma, confidence, pos_normalized, should_add_pos)
            section.append(entry_elem)
            entries_added += 1
    
    # Second pass: Generate -ebl adjective bidix entries from verbs
    # For each verb with Esperanto translation, generate corresponding -ebl adjective
    ebl_bidix_generated = 0
    processed_bidix_lemmas = set()
    
    # Collect all lemmas we've already added to avoid duplicates
    for entry in entries:
        processed_bidix_lemmas.add(entry.get('lemma', '').lower())
    
    # Generate -ebl bidix entries from verbs
    for entry in entries:
        lemma = entry.get('lemma', '').strip()
        if not lemma:
            continue
        
        pos = entry.get('pos')
        if not pos:
            pos = guess_pos_ido(lemma)
        pos_normalized = pos
        if pos:
            pos_lower = pos.lower()
            if pos_lower in {'conjunction', 'coordinating conjunction'}:
                pos_normalized = 'cnjcoo'
            elif pos_lower in {'subordinating conjunction'}:
                pos_normalized = 'cnjsub'
            elif pos_lower in {'preposition'}:
                pos_normalized = 'prep'
        
        # Check if this is a verb with Esperanto translation
        if pos_normalized in {'v', 'vblex', 'verb'} and lemma.endswith('ar') and len(lemma) > 3:
            translations = entry.get('translations', [])
            eo_translations = [t for t in translations if t.get('lang') == 'eo' and t.get('confidence', 0) >= min_confidence]
            
            if eo_translations:
                verb_stem = lemma[:-2]  # Remove -ar
                ebl_lemma = verb_stem + 'ebla'
                
                # Skip if already exists
                if ebl_lemma.lower() in processed_bidix_lemmas:
                    continue
                
                # Generate Esperanto -ebla form from verb translation
                # Map Ido verb stem to full Esperanto -ebla adjective form
                # Pattern: Ido stem "lern" → Esperanto full form "lernebla"
                # Search all translations for an infinitive (-i) to derive from
                eo_infinitive = None
                # Sort translations by confidence to get the best one
                eo_translations.sort(key=lambda t: t.get('confidence', 0), reverse=True)
                
                for eo_trans in eo_translations:
                    term = eo_trans.get('term', '').strip()
                    if term and term.endswith('i'):
                        eo_infinitive = term
                        break
                
                if eo_infinitive:
                    verb_stem = lemma[:-2]  # Remove -ar
                    eo_verb_stem = eo_infinitive[:-1]  # Remove -i
                    eo_ebla_full = eo_verb_stem + 'ebla'  # Full form: stem + ebla
                    
                    # Create bidix entry: Ido verb stem → Esperanto full -ebla form
                    # Example: lern → lernebla
                    ido_lemma_stem = verb_stem
                    entry_elem = create_bidix_entry(ido_lemma_stem, eo_ebla_full, 0.95, 'adj', add_pos and True)
                    section.append(entry_elem)
                    entries_added += 1
                    ebl_bidix_generated += 1
                    processed_bidix_lemmas.add(ebl_lemma.lower())
    
    # Write output
    print(f"\nWriting bidix to {output_file}...")
    print(f"  Entries added: {entries_added}")
    print(f"  Entries skipped (no translation): {entries_skipped_no_translation}")
    print(f"  Entries skipped (low confidence): {entries_skipped_low_confidence}")
    print(f"  Entries skipped (no lemma): {entries_skipped_no_lemma}")
    print(f"  Entries skipped (junk lemma): {entries_skipped_junk}")
    if ebl_bidix_generated > 0:
        print(f"  -ebl adjective bidix entries generated from verbs: {ebl_bidix_generated}")
    
    # Format XML with proper indentation
    indent_xml(root)
    
    tree = ET.ElementTree(root)
    tree.write(output_file, encoding='UTF-8', xml_declaration=True)
    
    print(f"✅ Successfully generated bidix: {output_file}")


def indent_xml(elem, level=0):
    """
    Add proper indentation to XML for readability.
    
    CRITICAL: Do NOT add whitespace inside <r> or <l> tags in bidix because 
    it breaks morphological analysis! Tags must stay on one line.
    """
    indent = "\n" + "  " * level
    
    # Skip formatting inside <r> and <l> tags - they must stay on one line
    if elem.tag in ('r', 'l'):
        # Just fix the tail (what comes after this element)
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = indent
        return
    
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = indent + "  "
        if not elem.tail or not elem.tail.strip():
            elem.tail = indent
        for child in elem:
            indent_xml(child, level + 1)
        if not child.tail or not child.tail.strip():
            child.tail = indent
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = indent


def main():
    parser = argparse.ArgumentParser(
        description='Generate Apertium bidix from merged JSON'
    )
    parser.add_argument(
        '--input',
        type=Path,
        default=Path(__file__).parent.parent / 'merged' / 'merged_bidix.json',
        help='Input merged_bidix.json file'
    )
    parser.add_argument(
        '--output',
        type=Path,
        default=Path(__file__).parent.parent / 'generated' / 'ido-epo.ido-epo.dix',
        help='Output .dix file'
    )
    parser.add_argument(
        '--min-confidence',
        type=float,
        default=0.0,
        help='Minimum confidence threshold for including translations'
    )
    parser.add_argument(
        '--no-pos',
        action='store_true',
        help='Do not add POS tags to entries'
    )
    
    args = parser.parse_args()
    
    # Create output directory if needed
    args.output.parent.mkdir(parents=True, exist_ok=True)
    
    generate_bidix(args.input, args.output, args.min_confidence, add_pos=not args.no_pos)


if __name__ == '__main__':
    main()
