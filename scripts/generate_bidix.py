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
    'numeral': 'num',     # numeral (full name)
    'ord': 'num',         # ordinals are based on num
    'ordinal': 'num',     # ordinals (full name)
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
        elif pos_lower in {'numeral', 'num'}:
            pos = 'num'
        elif pos_lower in {'ordinal', 'ord'}:
            pos = 'ord'

    # Invariable words (function words) should not have stems extracted
    invariable_pos = {'pr', 'prep', 'cnjcoo', 'cnjsub', 'det', 'prn', 'ij', 'num', 'np'}
    if pos in invariable_pos:
        if pos == 'np':
            return word.strip()
        return word.lower()
    
    # Ordinals
    if pos == 'ord':
        # Standard stemming for Ido ordinals: unesma -> un, duesma -> du
        if word.lower().endswith('esma'):
            return word[:-4].lower()
        elif word.lower().endswith('ma'):
            return word[:-2].lower()
        return word.lower()

    # CRITICAL FIX: If POS is None, don't guess for short words (likely function words)
    if not pos:
        if len(word) <= 3:
            return word.lower()
        pos = guess_pos_ido(word)
    
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
    """
    if not word:
        return word
    
    word = word.strip()
    
    # If POS not provided, guess it
    if not pos:
        pos = guess_pos_esperanto(word)
    
    if pos == 'ord' or (pos == 'adj' and word.endswith('a')):
        # For Esperanto ordinals like unua, dua, the lemma is the same as the cardinal stem
        # except for 'unua' which can be 'unu'.
        if word.lower() == 'unua':
            return 'unu'
        if word.endswith('a'):
            return word[:-1]
    
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
                if default_pos in ('ord', 'ordinal'):
                    # Add ord tag for ordinals
                    ET.SubElement(elem, 's').set('n', 'ord')

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
    
    # Load Esperanto lemmas for fallback (if the root is identical in both languages)
    epo_lemmas = set()
    epo_dix_path = Path(__file__).resolve().parents[3] / "apertium-epo/apertium-epo.epo.dix"
    if epo_dix_path.exists():
        try:
            epo_tree = ET.parse(epo_dix_path)
            for e in epo_tree.findall(".//e"):
                lm = e.get('lm')
                if lm:
                    epo_lemmas.add(lm.lower())
            print(f"  ✅ Loaded {len(epo_lemmas)} lemmas from Esperanto dictionary for fallback")
        except Exception as e:
            print(f"  ⚠️ Warning: Failed to parse Esperanto dictionary: {e}")
    else:
        print(f"  ⚠️ Warning: Esperanto dictionary not found at {epo_dix_path}")

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
                 'pri', 'pii', 'fti', 'cni', 'imp', 'inf',
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
    
    # Store root translations for productive suffix derivation
    # Map of Ido_stem -> [Epo_stems]
    root_translations = {} 
    
    # Pre-process entries to build root translation map
    for entry in entries:
        lemma = entry.get('lemma', '').strip()
        pos = entry.get('pos')
        if not lemma or not entry.get('translations'): continue
        
        # We only care about base roots (not already derived words)
        lemma_lower = lemma.lower()
        if not any(lemma_lower.endswith(s) for s in ('isto', 'uro', 'ala', 'eyo', 'ino', 'ana', 'ebla')):
            for trans in entry.get('translations', []):
                if trans.get('lang') == 'eo' and trans.get('confidence', 0) >= 0.9:
                    term = clean_translation(trans.get('term', ''))
                    if term:
                        ido_stem = extract_lemma_ido(lemma, pos)
                        # Guess pos if needed for esperanto stemming
                        epo_pos = pos if pos else guess_pos_esperanto(term)
                        epo_stem = extract_lemma_esperanto(term, epo_pos)
                        if ido_stem and epo_stem:
                            if ido_stem not in root_translations:
                                root_translations[ido_stem] = []
                            if epo_stem not in root_translations[ido_stem]:
                                root_translations[ido_stem].append(epo_stem)

    processed_bidix_lemmas = set()
    for entry in entries:
        lemma = entry.get('lemma', '').strip()
        
        if not lemma:
            entries_skipped_no_lemma += 1
            continue

        translations = entry.get('translations', [])
        pos = entry.get('pos')
        lemma_lower = lemma.lower()
        
        if not translations:
            # FALLBACK: If no translation but lemma exists in Esperanto, assume identical root
            if lemma_lower in epo_lemmas:
                # Create a synthetic translation
                translations = [{
                    'term': lemma, # Use same word
                    'lang': 'eo',
                    'confidence': 0.8,
                    'source': 'root_fallback'
                }]
            else:
                entries_skipped_no_translation += 1
                continue
        
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
            elif pos_lower in {'numeral', 'num'}:
                pos_normalized = 'num'
            elif pos_lower in {'ordinal', 'ord'}:
                pos_normalized = 'ord'
        
        # Extract stem for Ido
        paradigm = entry.get('morphology', {}).get('paradigm')
        ido_lemma = extract_lemma_ido(lemma, pos_normalized)
        
        # Skip junk lemmas (numbers, units, etc.)
        if not is_valid_lemma(lemma, ido_lemma):
            entries_skipped_junk += 1
            continue

        # Function words (conjunctions, prepositions, etc.) MUST have POS tags in bidix
        function_word_pos = {'cnjcoo', 'cnjsub', 'pr', 'prep', 'det', 'prn', 'adv', 'num', 'ord'}
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
                'trans': trans
            })
        
        # Filter cognates
        non_cognate_count = sum(1 for t in valid_translations if not t['is_cognate'])
        best_non_cognate_conf = max([t['confidence'] for t in valid_translations if not t['is_cognate']] + [0.0])
        best_overall_conf = max([t['confidence'] for t in valid_translations] + [0.0])
        
        if non_cognate_count > 0 and not is_function_word:
            valid_translations = [t for t in valid_translations 
                                if not t['is_cognate'] or t['confidence'] >= 0.95 or t['confidence'] >= best_non_cognate_conf]
        
        # CRITICAL: Filter out low-confidence translations if we have a high-confidence one
        if best_overall_conf >= 0.95:
            valid_translations = [t for t in valid_translations if t['confidence'] >= 0.95 or t['confidence'] >= best_overall_conf - 0.01]
        
        # Sort by confidence (highest first)
        valid_translations.sort(key=lambda t: t['confidence'], reverse=True)
        
        # Process sorted translations
        for trans_data in valid_translations:
            term = trans_data['term']
            confidence = trans_data['confidence']
            
            # Use already extracted stems
            ido_lemma_entry = ido_lemma
            epo_lemma_entry = term

            if pos_normalized == 'prn':
                epo_lemma_entry = EPO_PRONOUN_FORMS.get(ido_lemma_entry, term)
            elif pos_normalized == 'ord':
                # Map Ido ordinal stem to Esperanto ordinal stem + <ord>
                # Example: un (from unesma) -> unu<ord>
                epo_stem = extract_lemma_esperanto(term, 'ord')
                epo_lemma_entry = f"{epo_stem}<ord>"
            elif pos_normalized == 'num':
                epo_lemma_entry = term  # Keep as-is for now

            # For determiners: strip any embedded XML tags from translation term.
            if pos_normalized == 'det' and '<' in epo_lemma_entry:
                epo_lemma_entry = epo_lemma_entry.split('<')[0]

            # Skip if either lemma is empty
            if not ido_lemma_entry or not epo_lemma_entry:
                continue

            # Create entry (use should_add_pos instead of add_pos for function words)
            # Use normalized POS for bidix entry
            entry_elem = create_bidix_entry(ido_lemma_entry, epo_lemma_entry, confidence, pos_normalized, should_add_pos)
            section.append(entry_elem)
            entries_added += 1
            processed_bidix_lemmas.add(lemma.lower())

    # Third pass: Productive Suffix Mapping (Ido -> Esperanto)
    # Rules:
    # -isto -> -isto (person)
    # -uro  -> -aĵo (result)
    # -eyo  -> -ejo (place)
    # -ino  -> -ino (feminine)
    # -ala  -> -a   (adjective)
    # -ana  -> -ano (member/citizen)
    
    SUFFIX_MAP = [
        ('isto', 'isto', 'n'),
        ('uro', 'aĵo', 'n'),
        ('eyo', 'ejo', 'n'),
        ('ino', 'ino', 'n'),
        ('ala', 'a', 'adj'),
        ('ana', 'ano', 'n'),
    ]
    
    # Do not apply suffix mapping to these words (avoid wrong guesses)
    SUFFIX_BLACKLIST = {'ala', 'balo', 'pino', 'panino'}
    
    productive_entries_added = 0
    for entry in entries:
        lemma = entry.get('lemma', '').strip().lower()
        if not lemma or lemma in processed_bidix_lemmas or lemma in SUFFIX_BLACKLIST:
            continue
            
        for ido_suffix, epo_suffix, pos_tag in SUFFIX_MAP:
            if lemma.endswith(ido_suffix) and len(lemma) > len(ido_suffix) + 2:
                # Potential root
                ido_root = lemma[:-len(ido_suffix)]
                
                # Check root translations (check various root endings)
                best_epo_root = None
                for root_ending in ['o', 'ar', 'a', 'e', '']:
                    test_root = ido_root + root_ending
                    if test_root in root_translations:
                        # Use first translation for now
                        best_epo_root = root_translations[test_root][0]
                        break
                
                if best_epo_root:
                    # Construct Esperanto translation
                    # If epo_suffix is 'a' (adjective), we replace the 'o' ending of root if it exists
                    if epo_suffix == 'a' and best_epo_root.endswith('o'):
                        epo_trans = best_epo_root[:-1] + 'a'
                    else:
                        epo_trans = best_epo_root + epo_suffix
                    
                    # Add to bidix - MUST use the full Ido derived lemma
                    # Example: muzikist (stem of muzikisto) -> muzikisto (Epo)
                    ido_derived_stem = extract_lemma_ido(lemma, pos_tag)
                    entry_elem = create_bidix_entry(ido_derived_stem, epo_trans, 0.85, pos_tag, add_pos)
                    section.append(entry_elem)
                    entries_added += 1
                    productive_entries_added += 1
                    processed_bidix_lemmas.add(lemma)
                    break # Only one suffix per word
    
    if productive_entries_added > 0:
        print(f"  Productive suffix translations generated: {productive_entries_added}")
    
    # Generate -ebl adjective bidix entries from verbs
    ebl_bidix_generated = 0
    
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
