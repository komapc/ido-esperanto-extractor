#!/usr/bin/env python3
"""
Create Ido-Esperanto Bilingual Apertium Dictionary

This script:
1. Reads the Ido-Esperanto dictionary_merged.json
2. Converts it to a proper Apertium bilingual dictionary format
3. Maps Ido roots to Esperanto lemmas with correct POS tags
"""

import json
import xml.etree.ElementTree as ET
from xml.dom import minidom
from collections import defaultdict
from datetime import datetime


class IdoEsperantoBilingualConverter:
    """Convert Ido-Esperanto dictionary to Apertium bilingual .dix format"""
    
    # Function word mappings (Ido → Esperanto)
    FUNCTION_WORD_TRANSLATIONS = {
        # Pronouns
        ('me', 'prn'): ('mi', 'prn'),
        ('tu', 'prn'): ('vi', 'prn'),
        ('il', 'prn'): ('li', 'prn'),
        ('el', 'prn'): ('ŝi', 'prn'),
        ('ol', 'prn'): ('ĝi', 'prn'),
        ('lu', 'prn'): ('li', 'prn'),  # or ŝi
        ('ni', 'prn'): ('ni', 'prn'),
        ('vi', 'prn'): ('vi', 'prn'),
        ('li', 'prn'): ('ili', 'prn'),
        ('qua', 'prn'): ('kiu', 'prn'),  # relative pronoun
        # Determiners
        ('la', 'det'): ('la', 'det'),
        # Adverbs
        ('ne', 'adv'): ('ne', 'adv'),
        ('yes', 'adv'): ('jes', 'adv'),
        # Conjunctions  
        ('ka', 'cnjsub'): ('ke', 'cnjsub'),
        ('ke', 'cnjsub'): ('ke', 'cnjsub'),
        ('e', 'cnjcoo'): ('kaj', 'cnjcoo'),
        ('ed', 'cnjcoo'): ('kaj', 'cnjcoo'),  # alternative form of "and"
        ('ma', 'cnjcoo'): ('sed', 'cnjcoo'),
        ('o', 'cnjcoo'): ('aŭ', 'cnjcoo'),
        # Prepositions
        ('en', 'pr'): ('en', 'pr'),
        ('da', 'pr'): ('de', 'pr'),
        ('di', 'pr'): ('de', 'pr'),
        ('a', 'pr'): ('al', 'pr'),
        ('de', 'pr'): ('de', 'pr'),
        ('por', 'pr'): ('por', 'pr'),
        ('inter', 'pr'): ('inter', 'pr'),
        ('pro', 'pr'): ('pro', 'pr'),
        ('malgre', 'pr'): ('malgraŭ', 'pr'),
    }
    
    # Ido suffix to POS mapping
    SUFFIX_TO_POS = {
        '.o': 'n',
        '.a': 'adj',
        '.e': 'adv',
        '.ar': 'vblex',
        '.ir': 'vblex',
        '.or': 'vblex',
        '.as': 'vblex',
        '.is': 'vblex',
        '.os': 'vblex',
        '.us': 'vblex',
        '.ez': 'vblex',
    }
    
    def __init__(self, json_file):
        """Load the merged JSON dictionary"""
        print(f"Loading {json_file}...")
        with open(json_file, 'r', encoding='utf-8') as f:
            self.data = json.load(f)
        
        self.stats = {
            'total_entries': len(self.data['words']),
            'valid_translations': 0,
            'by_pos': defaultdict(int),
            'skipped_no_translation': 0,
            'skipped_invalid': 0,
        }
    
    def analyze_morfologio(self, morfologio):
        """
        Analyze morfologio field to extract root and determine POS
        
        Returns: (root, pos)
        """
        if not morfologio or len(morfologio) < 2:
            return None, None
        
        root = morfologio[0]
        suffixes = ''.join(morfologio[1:])
        
        # Determine POS from suffix
        # Sort by length descending to match longer patterns first (e.g., .ar before .a)
        pos = None
        sorted_patterns = sorted(self.SUFFIX_TO_POS.items(), key=lambda x: -len(x[0]))
        for suffix_pattern, pos_tag in sorted_patterns:
            if suffixes.startswith(suffix_pattern):
                pos = pos_tag
                break
        
        # If not found, try to infer from ending
        if not pos:
            if suffixes.startswith('.'):
                first_suffix = suffixes.split('.')[1] if '.' in suffixes[1:] else suffixes[1:]
                if first_suffix in ['o', 'i', 'on', 'in']:
                    pos = 'n'
                elif first_suffix == 'a':
                    pos = 'adj'
                elif first_suffix == 'e':
                    pos = 'adv'
        
        return root, pos
    
    def get_esperanto_root(self, esperanto_word, pos):
        """
        Extract Esperanto root from full word based on POS
        
        Examples:
        - abako (n) → abak
        - bona (adj) → bon
        - bone (adv) → bon
        - vidi (vblex) → vid
        """
        if not esperanto_word:
            return None
        
        word = esperanto_word.strip()
        
        # Remove common Esperanto endings based on POS
        if pos == 'n':
            # Nouns end in -o
            if word.endswith('o'):
                return word[:-1]
        elif pos == 'adj':
            # Adjectives end in -a
            if word.endswith('a'):
                return word[:-1]
        elif pos == 'adv':
            # Adverbs end in -e
            if word.endswith('e'):
                return word[:-1]
        elif pos == 'vblex':
            # Verbs end in -i (infinitive)
            if word.endswith('i'):
                return word[:-1]
        
        # If no ending matched, return the whole word
        return word
    
    def clean_esperanto_translation(self, translation):
        """
        Clean Esperanto translation from artifacts
        
        Returns: cleaned translation or None if invalid
        """
        if not translation:
            return None
        
        translation = translation.strip()
        
        # Skip invalid translations
        if not translation:
            return None
        if translation.startswith('|'):
            return None
        if translation.startswith('{'):
            return None
        if translation.startswith('['):
            return None
        if len(translation) < 2:
            return None
        if not translation[0].isalpha():
            return None
        
        # Remove wiki markup
        translation = translation.replace('[[', '').replace(']]', '')
        translation = translation.split('|')[0]  # Take first part of pipe
        
        return translation.strip()
    
    def create_bilingual_dix(self, output_file):
        """Create Apertium bilingual dictionary"""
        
        print("\n🔨 Creating Apertium bilingual dictionary...")
        
        # Create XML structure
        dictionary = ET.Element('dictionary')
        
        # Add comment
        comment = ET.Comment(f'''
        Ido-Esperanto Bilingual Dictionary for Apertium
        Auto-generated from Ido Wiktionary data
        Generated: {datetime.now().isoformat()}
        Source entries: {self.stats['total_entries']}
        ''')
        dictionary.append(comment)
        
        # Add alphabet (include Esperanto special characters)
        alphabet = ET.SubElement(dictionary, 'alphabet')
        alphabet.text = 'abcdefghijklmnopqrstuvwxyzĉĝĥĵŝŭABCDEFGHIJKLMNOPQRSTUVWXYZĈĜĤĴŜŬ'
        
        # Add symbol definitions
        sdefs = ET.SubElement(dictionary, 'sdefs')
        symbols = [
            ('n', 'Noun'),
            ('adj', 'Adjective'),
            ('adv', 'Adverb'),
            ('vblex', 'Verb'),
            ('pr', 'Preposition'),
            ('prn', 'Pronoun'),
            ('det', 'Determiner'),
            ('num', 'Numeral'),
            ('cnjcoo', 'Coordinating conjunction'),
            ('cnjsub', 'Subordinating conjunction'),
            ('ij', 'Interjection'),
        ]
        for symbol, comment_text in symbols:
            ET.SubElement(sdefs, 'sdef', n=symbol, c=comment_text)
        
        # Add main section with entries
        section = ET.SubElement(dictionary, 'section', id='main', type='standard')
        
        # Process each entry
        entries_by_pos = defaultdict(list)
        
        for word_entry in self.data['words']:
            ido_word = word_entry.get('ido_word', '')
            esperanto_words = word_entry.get('esperanto_words', [])
            morfologio = word_entry.get('morfologio', [])
            
            if not ido_word or not esperanto_words:
                self.stats['skipped_no_translation'] += 1
                continue
            
            # Get Ido root and POS
            ido_root, pos = self.analyze_morfologio(morfologio)
            
            if not ido_root or not pos:
                self.stats['skipped_invalid'] += 1
                continue
            
            # Get first Esperanto translation
            epo_word = esperanto_words[0] if esperanto_words else ''
            epo_word = self.clean_esperanto_translation(epo_word)
            
            if not epo_word:
                self.stats['skipped_invalid'] += 1
                continue
            
            # For Esperanto, use the full lemma (with grammatical ending)
            # The generator needs the full form: kato, bona, bone, vidi
            epo_lemma = epo_word.strip()
            
            if not epo_lemma:
                self.stats['skipped_invalid'] += 1
                continue
            
            # Add to entries
            self.stats['valid_translations'] += 1
            self.stats['by_pos'][pos] += 1
            
            entries_by_pos[pos].append({
                'ido_root': ido_root,
                'epo_root': epo_lemma,  # Use full lemma, not root
                'pos': pos
            })
        
        # Add function words first
        if self.FUNCTION_WORD_TRANSLATIONS:
            function_words_by_pos = defaultdict(list)
            for (ido_word, ido_pos), (epo_word, epo_pos) in self.FUNCTION_WORD_TRANSLATIONS.items():
                function_words_by_pos[ido_pos].append({
                    'ido_word': ido_word,
                    'epo_word': epo_word,
                    'pos': ido_pos
                })
            
            comment = ET.Comment(f' Function Words ({len(self.FUNCTION_WORD_TRANSLATIONS)} entries) ')
            section.append(comment)
            
            for pos_tag in sorted(function_words_by_pos.keys()):
                for entry in sorted(function_words_by_pos[pos_tag], key=lambda x: x['ido_word']):
                    e = ET.SubElement(section, 'e')
                    p = ET.SubElement(e, 'p')
                    
                    # Left side (Ido)
                    l = ET.SubElement(p, 'l')
                    l.text = entry['ido_word']
                    ET.SubElement(l, 's', n=entry['pos'])
                    
                    # Right side (Esperanto)
                    r = ET.SubElement(p, 'r')
                    r.text = entry['epo_word']
                    ET.SubElement(r, 's', n=entry['pos'])
        
        # Add entries grouped by POS
        pos_names = {
            'n': 'Nouns',
            'adj': 'Adjectives',
            'adv': 'Adverbs',
            'vblex': 'Verbs'
        }
        
        for pos_tag in ['n', 'adj', 'adv', 'vblex']:
            if pos_tag in entries_by_pos:
                entries = entries_by_pos[pos_tag]
                pos_name = pos_names.get(pos_tag, pos_tag)
                
                comment = ET.Comment(f' {pos_name} ({len(entries)} entries) ')
                section.append(comment)
                
                # Remove duplicates (same ido_root + epo_root + pos)
                seen = set()
                unique_entries = []
                for entry in entries:
                    key = (entry['ido_root'], entry['epo_root'], entry['pos'])
                    if key not in seen:
                        seen.add(key)
                        unique_entries.append(entry)
                
                for entry in sorted(unique_entries, key=lambda x: x['ido_root']):
                    e = ET.SubElement(section, 'e')
                    p = ET.SubElement(e, 'p')
                    
                    # Left side (Ido) - format: <l>root<s n="pos"/></l>
                    l_text = f"{entry['ido_root']}<s n=\"{entry['pos']}\"/>"
                    l = ET.SubElement(p, 'l')
                    # Parse the text as XML fragment
                    l_elem = ET.fromstring(f"<l>{l_text}</l>")
                    l.text = l_elem.text
                    for child in l_elem:
                        l.append(child)
                    
                    # Right side (Esperanto) - format: <r>root<s n="pos"/></r>
                    r_text = f"{entry['epo_root']}<s n=\"{entry['pos']}\"/>"
                    r = ET.SubElement(p, 'r')
                    # Parse the text as XML fragment
                    r_elem = ET.fromstring(f"<r>{r_text}</r>")
                    r.text = r_elem.text
                    for child in r_elem:
                        r.append(child)
        
        # Write to file
        self._write_pretty_xml(dictionary, output_file)
        return self.stats
    
    def _write_pretty_xml(self, element, filename):
        """Write XML with custom formatting to preserve inline tags"""
        
        def write_element(elem, f, indent=0):
            """Recursively write XML elements with proper formatting"""
            ind = '  ' * indent
            
            # Start tag
            if elem.tag == 'dictionary':
                f.write(f'{ind}<{elem.tag}>\n')
            elif elem.tag in ['l', 'r']:
                # Inline format for l and r elements: <l>text<s n="..."/></l>
                f.write(f'{ind}<{elem.tag}>')
                if elem.text:
                    f.write(elem.text)
                for child in elem:
                    if child.tag == 's':
                        n_val = child.get('n', '')
                        f.write(f'<s n="{n_val}"/>')
                f.write(f'</{elem.tag}>\n')
                return  # Don't process children again
            else:
                # Regular tags with attributes
                attrs = ' '.join([f'{k}="{v}"' for k, v in elem.attrib.items()])
                if attrs:
                    f.write(f'{ind}<{elem.tag} {attrs}')
                else:
                    f.write(f'{ind}<{elem.tag}')
                
                # Check if has children or text
                if len(elem) == 0 and not elem.text:
                    f.write('/>\n')
                    return
                else:
                    f.write('>')
                    if elem.text and elem.text.strip():
                        f.write(elem.text)
                    if len(elem) > 0:
                        f.write('\n')
            
            # Children
            for child in elem:
                if isinstance(child.tag, str):  # Skip comments for now
                    write_element(child, f, indent + 1)
            
            # End tag
            if elem.tag not in ['l', 'r']:
                if len(elem) > 0:
                    f.write(f'{ind}</{elem.tag}>\n')
                elif elem.text:
                    f.write(f'</{elem.tag}>\n')
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
            write_element(element, f)
        
        print(f"✅ Written to: {filename}")


def main():
    """Main function"""
    print("=" * 70)
    print("  Ido-Esperanto Bilingual Apertium Dictionary Generator")
    print("=" * 70)
    
    # Input and output files
    json_file = 'dictionary_merged.json'
    output_file = '../apertium-ido-epo/apertium-ido-epo.ido-epo.dix'
    
    if not os.path.exists(json_file):
        print(f"❌ Error: {json_file} not found!")
        print("   Please run the extractor first to generate the dictionary.")
        return 1
    
    # Create converter
    converter = IdoEsperantoBilingualConverter(json_file)
    
    print(f"\n📊 Input Statistics:")
    print(f"   Total entries: {converter.stats['total_entries']}")
    
    # Create Apertium dictionary
    stats = converter.create_bilingual_dix(output_file)
    
    print(f"\n✅ Conversion Complete!")
    print(f"\n📊 Output Statistics:")
    print(f"   Valid translations: {stats['valid_translations']}")
    print(f"   Skipped (no translation): {stats['skipped_no_translation']}")
    print(f"   Skipped (invalid): {stats['skipped_invalid']}")
    print(f"\n📈 By Part of Speech:")
    for pos, count in sorted(stats['by_pos'].items(), key=lambda x: x[1], reverse=True):
        print(f"   {pos:10} {count:5} entries")
    
    print(f"\n✨ Bilingual dictionary created successfully!")
    print(f"   Output: {output_file}")
    
    return 0


if __name__ == '__main__':
    import os
    import sys
    sys.exit(main())

