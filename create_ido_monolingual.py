#!/usr/bin/env python3
"""
Create Ido Monolingual Apertium Dictionary

This script:
1. Reads the Ido-Esperanto dictionary_merged.json (which has morfologio data)
2. Converts it to a proper Apertium monolingual dictionary format
3. Handles Ido morphology (roots + suffixes) properly
"""

import json
import xml.etree.ElementTree as ET
from xml.dom import minidom
from collections import defaultdict
from datetime import datetime


class IdoMonolingualConverter:
    """Convert Ido dictionary with morphology to Apertium .dix format"""
    
    # Ido suffix to Apertium paradigm mapping
    SUFFIX_PARADIGMS = {
        '.o': 'o__n',           # noun
        '.a': 'a__adj',         # adjective  
        '.e': 'e__adv',         # adverb
        '.ar': 'ar__vblex',     # verb infinitive
        '.ir': 'ir__vblex',     # verb infinitive (passive)
        '.or': 'or__vblex',     # verb infinitive (future)
    }
    
    # Determine POS from suffix
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
            'by_pos': defaultdict(int),
            'with_morfologio': 0,
            'without_morfologio': 0,
            'paradigm_usage': defaultdict(int),
        }
    
    def analyze_morfologio(self, morfologio):
        """
        Analyze morfologio field to extract root and determine POS
        
        Example:
        - ['abak', '.o'] → root='abak', paradigm='o__n', pos='n'
        - ['bon', '.a'] → root='bon', paradigm='a__adj', pos='adj'
        - ['vid', '.ar'] → root='vid', paradigm='ar__vblex', pos='vblex'
        """
        if not morfologio or len(morfologio) < 2:
            return None, None, None
        
        root = morfologio[0]
        suffixes = ''.join(morfologio[1:])
        
        # Determine paradigm and POS from suffix
        paradigm = None
        pos = None
        
        for suffix_pattern, paradigm_name in self.SUFFIX_PARADIGMS.items():
            if suffixes.startswith(suffix_pattern):
                paradigm = paradigm_name
                pos = self.SUFFIX_TO_POS.get(suffix_pattern)
                break
        
        # If not found, try to infer from ending
        if not paradigm:
            if suffixes.startswith('.'):
                first_suffix = suffixes.split('.')[1] if '.' in suffixes[1:] else suffixes[1:]
                if first_suffix in ['o', 'i', 'on', 'in']:
                    paradigm = 'o__n'
                    pos = 'n'
                elif first_suffix == 'a':
                    paradigm = 'a__adj'
                    pos = 'adj'
                elif first_suffix == 'e':
                    paradigm = 'e__adv'
                    pos = 'adv'
        
        return root, paradigm, pos
    
    def create_paradigms(self, pardefs):
        """Add Ido inflection paradigms to pardefs element"""
        
        # Noun paradigm (o__n)
        pardef = ET.SubElement(pardefs, 'pardef', n='o__n')
        # Singular nominative
        e = ET.SubElement(pardef, 'e')
        p = ET.SubElement(e, 'p')
        ET.SubElement(p, 'l').text = 'o'
        r = ET.SubElement(p, 'r')
        ET.SubElement(r, 's', n='n')
        ET.SubElement(r, 's', n='sg')
        ET.SubElement(r, 's', n='nom')
        
        # Plural nominative
        e = ET.SubElement(pardef, 'e')
        p = ET.SubElement(e, 'p')
        ET.SubElement(p, 'l').text = 'i'
        r = ET.SubElement(p, 'r')
        ET.SubElement(r, 's', n='n')
        ET.SubElement(r, 's', n='pl')
        ET.SubElement(r, 's', n='nom')
        
        # Singular accusative
        e = ET.SubElement(pardef, 'e')
        p = ET.SubElement(e, 'p')
        ET.SubElement(p, 'l').text = 'on'
        r = ET.SubElement(p, 'r')
        ET.SubElement(r, 's', n='n')
        ET.SubElement(r, 's', n='sg')
        ET.SubElement(r, 's', n='acc')
        
        # Plural accusative
        e = ET.SubElement(pardef, 'e')
        p = ET.SubElement(e, 'p')
        ET.SubElement(p, 'l').text = 'in'
        r = ET.SubElement(p, 'r')
        ET.SubElement(r, 's', n='n')
        ET.SubElement(r, 's', n='pl')
        ET.SubElement(r, 's', n='acc')
        
        # Adjective paradigm (a__adj)
        pardef = ET.SubElement(pardefs, 'pardef', n='a__adj')
        # Base form
        e = ET.SubElement(pardef, 'e')
        p = ET.SubElement(e, 'p')
        ET.SubElement(p, 'l').text = 'a'
        r = ET.SubElement(p, 'r')
        ET.SubElement(r, 's', n='adj')
        
        # Adverbial form
        e = ET.SubElement(pardef, 'e')
        p = ET.SubElement(e, 'p')
        ET.SubElement(p, 'l').text = 'e'
        r = ET.SubElement(p, 'r')
        ET.SubElement(r, 's', n='adv')
        
        # Adverb paradigm (e__adv)
        pardef = ET.SubElement(pardefs, 'pardef', n='e__adv')
        e = ET.SubElement(pardef, 'e')
        p = ET.SubElement(e, 'p')
        ET.SubElement(p, 'l').text = 'e'
        r = ET.SubElement(p, 'r')
        ET.SubElement(r, 's', n='adv')
        
        # Verb paradigm (ar__vblex)
        pardef = ET.SubElement(pardefs, 'pardef', n='ar__vblex')
        # Infinitive
        e = ET.SubElement(pardef, 'e')
        p = ET.SubElement(e, 'p')
        ET.SubElement(p, 'l').text = 'ar'
        r = ET.SubElement(p, 'r')
        ET.SubElement(r, 's', n='vblex')
        ET.SubElement(r, 's', n='inf')
        
        # Present
        e = ET.SubElement(pardef, 'e')
        p = ET.SubElement(e, 'p')
        ET.SubElement(p, 'l').text = 'as'
        r = ET.SubElement(p, 'r')
        ET.SubElement(r, 's', n='vblex')
        ET.SubElement(r, 's', n='pri')
        
        # Past
        e = ET.SubElement(pardef, 'e')
        p = ET.SubElement(e, 'p')
        ET.SubElement(p, 'l').text = 'is'
        r = ET.SubElement(p, 'r')
        ET.SubElement(r, 's', n='vblex')
        ET.SubElement(r, 's', n='pii')
        
        # Future
        e = ET.SubElement(pardef, 'e')
        p = ET.SubElement(e, 'p')
        ET.SubElement(p, 'l').text = 'os'
        r = ET.SubElement(p, 'r')
        ET.SubElement(r, 's', n='vblex')
        ET.SubElement(r, 's', n='fti')
        
        # Imperative
        e = ET.SubElement(pardef, 'e')
        p = ET.SubElement(e, 'p')
        ET.SubElement(p, 'l').text = 'ez'
        r = ET.SubElement(p, 'r')
        ET.SubElement(r, 's', n='vblex')
        ET.SubElement(r, 's', n='imp')
        
        # Conditional
        e = ET.SubElement(pardef, 'e')
        p = ET.SubElement(e, 'p')
        ET.SubElement(p, 'l').text = 'us'
        r = ET.SubElement(p, 'r')
        ET.SubElement(r, 's', n='vblex')
        ET.SubElement(r, 's', n='cni')
    
    def create_apertium_dix(self, output_file):
        """Create Apertium monolingual dictionary"""
        
        print("\n🔨 Creating Apertium monolingual dictionary...")
        
        # Create XML structure
        dictionary = ET.Element('dictionary')
        
        # Add comment
        comment = ET.Comment(f'''
        Ido Monolingual Dictionary for Apertium
        Auto-generated from Ido Wiktionary data
        Generated: {datetime.now().isoformat()}
        Entries: {self.stats['total_entries']}
        ''')
        dictionary.append(comment)
        
        # Add alphabet
        alphabet = ET.SubElement(dictionary, 'alphabet')
        alphabet.text = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
        
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
            ('sg', 'Singular'),
            ('pl', 'Plural'),
            ('sp', 'Singular/Plural'),
            ('nom', 'Nominative'),
            ('acc', 'Accusative'),
            ('inf', 'Infinitive'),
            ('pri', 'Present indicative'),
            ('pii', 'Past indicative'),
            ('fti', 'Future indicative'),
            ('cni', 'Conditional'),
            ('imp', 'Imperative'),
            ('np', 'Proper noun'),
            ('ant', 'Anthroponym'),
            ('cog', 'Cognomen'),
            ('top', 'Toponym'),
        ]
        for symbol, comment in symbols:
            ET.SubElement(sdefs, 'sdef', n=symbol, c=comment)
        
        # Add paradigms
        pardefs = ET.SubElement(dictionary, 'pardefs')
        self.create_paradigms(pardefs)
        
        # Add main section with entries
        section = ET.SubElement(dictionary, 'section', id='main', type='standard')
        
        # Process each entry
        entries_by_pos = defaultdict(list)
        
        for word_entry in self.data['words']:
            ido_word = word_entry.get('ido_word', '')
            morfologio = word_entry.get('morfologio', [])
            
            if not ido_word:
                continue
            
            if morfologio and len(morfologio) >= 2:
                root, paradigm, pos = self.analyze_morfologio(morfologio)
                
                if root and paradigm and pos:
                    self.stats['with_morfologio'] += 1
                    self.stats['by_pos'][pos] += 1
                    self.stats['paradigm_usage'][paradigm] += 1
                    
                    entries_by_pos[pos].append({
                        'lemma': ido_word,
                        'root': root,
                        'paradigm': paradigm
                    })
                else:
                    self.stats['without_morfologio'] += 1
            else:
                self.stats['without_morfologio'] += 1
        
        # Add entries grouped by POS
        pos_names = {'n': 'Nouns', 'adj': 'Adjectives', 'adv': 'Adverbs', 'vblex': 'Verbs'}
        
        for pos_tag in ['n', 'adj', 'adv', 'vblex']:
            if pos_tag in entries_by_pos:
                entries = entries_by_pos[pos_tag]
                pos_name = pos_names.get(pos_tag, pos_tag)
                
                comment = ET.Comment(f' {pos_name} ({len(entries)} entries) ')
                section.append(comment)
                
                for entry in sorted(entries, key=lambda x: x['lemma']):
                    e = ET.SubElement(section, 'e', lm=entry['lemma'])
                    i = ET.SubElement(e, 'i')
                    i.text = entry['root']
                    ET.SubElement(e, 'par', n=entry['paradigm'])
        
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
    print("  Ido Monolingual Apertium Dictionary Generator")
    print("=" * 70)
    
    # Input and output files
    json_file = 'dictionary_merged.json'
    output_file = '../apertium-ido-epo/apertium-ido.ido.dix'
    
    if not os.path.exists(json_file):
        print(f"❌ Error: {json_file} not found!")
        print("   Please run the extractor first to generate the dictionary.")
        return 1
    
    # Create converter
    converter = IdoMonolingualConverter(json_file)
    
    print(f"\n📊 Input Statistics:")
    print(f"   Total entries: {converter.stats['total_entries']}")
    
    # Create Apertium dictionary
    stats = converter.create_apertium_dix(output_file)
    
    print(f"\n✅ Conversion Complete!")
    print(f"\n📊 Output Statistics:")
    print(f"   Entries with morphology: {stats['with_morfologio']}")
    print(f"   Entries without morphology: {stats['without_morfologio']}")
    print(f"\n📈 By Part of Speech:")
    for pos, count in sorted(stats['by_pos'].items(), key=lambda x: x[1], reverse=True):
        print(f"   {pos:10} {count:5} entries")
    
    print(f"\n📋 Paradigm Usage:")
    for paradigm, count in sorted(stats['paradigm_usage'].items(), key=lambda x: x[1], reverse=True):
        print(f"   {paradigm:15} {count:5} entries")
    
    print(f"\n✨ Dictionary created successfully!")
    print(f"   Output: {output_file}")
    
    return 0


if __name__ == '__main__':
    import os
    import sys
    sys.exit(main())

