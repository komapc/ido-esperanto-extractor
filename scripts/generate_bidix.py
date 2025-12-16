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


# POS mapping from JSON to Apertium symbol definitions
POS_MAP = {
    'n': 'n',           # noun
    'v': 'vblex',       # verb
    'vblex': 'vblex',   # verb (already mapped)
    'adj': 'adj',       # adjective
    'adv': 'adv',       # adverb
    'pr': 'prep',       # preposition -> prep in bidix
    'prep': 'prep',     # preposition
    'prn': 'prn',       # pronoun
    'det': 'det',       # determiner
    'num': 'num',       # numeral
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
    
    # Invariable words (function words) should not have stems extracted
    invariable_pos = {'pr', 'prep', 'cnjcoo', 'cnjsub', 'det', 'prn', 'ij', 'num'}
    if pos in invariable_pos:
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
    
    Format without POS:
    <e>
      <p>
        <l>ido_lemma</l>
        <r>epo_lemma</r>
      </p>
    </e>
    
    Format with POS:
    <e>
      <!-- confidence: 1.0000 -->
      <p>
        <l>ido_lemma<s n="pos"/></l>
        <r>epo_lemma<s n="pos"/></r>
      </p>
    </e>
    """
    entry = ET.Element('e')
    
    # Add confidence comment
    comment = ET.Comment(f' confidence: {confidence:.4f} ')
    entry.append(comment)
    
    pair = ET.SubElement(entry, 'p')
    left = ET.SubElement(pair, 'l')
    right = ET.SubElement(pair, 'r')
    
    # Decide whether to add POS tags
    if add_pos and pos and pos in POS_MAP:
        # With POS tags
        left.text = ido_lemma
        s_left = ET.SubElement(left, 's')
        s_left.set('n', POS_MAP[pos])
        
        right.text = epo_lemma
        s_right = ET.SubElement(right, 's')
        s_right.set('n', POS_MAP[pos])
    else:
        # Without POS tags
        left.text = ido_lemma
        right.text = epo_lemma
    
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
    
    # Standard symbol definitions for bidix
    sdef_list = ['n', 'vblex', 'adj', 'adv', 'prn', 'det', 'prep', 
                 'cnjcoo', 'cnjsub', 'num', 'np']
    
    for sdef_name in sdef_list:
        sdef = ET.SubElement(sdefs, 'sdef')
        sdef.set('n', sdef_name)
    
    # Add section with entries
    section = ET.SubElement(root, 'section')
    section.set('id', 'main')
    section.set('type', 'standard')
    
    # Track statistics
    entries_added = 0
    entries_skipped_no_translation = 0
    entries_skipped_low_confidence = 0
    entries_skipped_no_lemma = 0
    
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
        
        # For function words (conjunctions, prepositions), don't add POS tags in bidix
        # They need to match without POS tags for proper lookup
        # Use POS from source (Wiktionary, etc.) instead of hardcoding
        # Function word POS types that should not have tags in bidix:
        function_word_pos = {'cnjcoo', 'cnjsub', 'pr', 'prep', 'det', 'prn', 'adv'}
        is_function_word = pos_normalized in function_word_pos if pos_normalized else False
        should_add_pos = add_pos and pos_normalized and pos_normalized in POS_MAP and not is_function_word
        
        # Filter and sort translations before processing
        # 1. Filter cognates (identical lemma == translation, case-insensitive)
        # 2. Sort by confidence (highest first)
        valid_translations = []
        lemma_lower = lemma.lower()
        
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
            
            # Check if cognate (identical lemma == translation, case-insensitive)
            is_cognate = lemma_lower == term.lower()
            
            valid_translations.append({
                'term': term,
                'confidence': confidence,
                'is_cognate': is_cognate,
                'trans': trans  # Keep original for other fields
            })
        
        # Filter cognates: remove if other non-cognate translations exist
        # EXCEPTION: For function words (prepositions, conjunctions, etc.), keep cognates
        # because they're often the correct translation (e.g., de → de, kaj → kaj)
        non_cognate_count = sum(1 for t in valid_translations if not t['is_cognate'])
        if non_cognate_count > 0 and not is_function_word:
            # Remove cognates when alternatives exist (but not for function words)
            valid_translations = [t for t in valid_translations if not t['is_cognate']]
        
        # Sort by confidence (highest first)
        valid_translations.sort(key=lambda t: t['confidence'], reverse=True)
        
        # Process sorted translations
        for trans_data in valid_translations:
            term = trans_data['term']
            confidence = trans_data['confidence']
            trans = trans_data['trans']
            
            # Extract lemmas (stems)
            # For Ido: extract stem (homo → hom)
            # For Esperanto: keep full lemma (homo → homo) because Esperanto generator expects full lemmas
            # Use normalized POS for lemma extraction (this is the corrected POS)
            ido_lemma = extract_lemma_ido(lemma, pos_normalized)
            epo_lemma = term  # Keep full Esperanto lemma, don't extract stem
            
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
                # Since Esperanto doesn't have morphological generation for -ebl,
                # we map directly to the full form
                for eo_trans in eo_translations[:1]:  # Use first translation
                    eo_verb = eo_trans.get('term', '').strip()
                    if eo_verb and eo_verb.endswith('i'):
                        eo_verb_stem = eo_verb[:-1]  # Remove -i
                        eo_ebla_full = eo_verb_stem + 'ebla'  # Full form: stem + ebla
                        
                        # Create bidix entry: Ido verb stem → Esperanto full -ebla form
                        # Example: lern → lernebla
                        # The Ido side uses stem "lern" + ebl__adj paradigm to generate "lernebla"
                        # The Esperanto side is the full form "lernebla" ready to use
                        ido_lemma_stem = verb_stem
                        entry_elem = create_bidix_entry(ido_lemma_stem, eo_ebla_full, 0.95, 'adj', add_pos and True)
                        section.append(entry_elem)
                        entries_added += 1
                        ebl_bidix_generated += 1
                        processed_bidix_lemmas.add(ebl_lemma.lower())
                        break  # Only generate one entry per verb
    
    # Write output
    print(f"\nWriting bidix to {output_file}...")
    print(f"  Entries added: {entries_added}")
    print(f"  Entries skipped (no translation): {entries_skipped_no_translation}")
    print(f"  Entries skipped (low confidence): {entries_skipped_low_confidence}")
    print(f"  Entries skipped (no lemma): {entries_skipped_no_lemma}")
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


