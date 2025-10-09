#!/usr/bin/env python3
"""
Convert Ido-Esperanto JSON dictionaries to Apertium .dix format
"""

import json
import xml.etree.ElementTree as ET
from xml.dom import minidom
from collections import defaultdict
from datetime import datetime


class DixConverter:
    """Convert JSON dictionaries to Apertium .dix XML format"""
    
    # Ido morphology suffix mapping to POS tags
    SUFFIX_TO_POS = {
        '.o': ('n', 'noun'),           # noun
        '.a': ('adj', 'adjective'),    # adjective
        '.e': ('adv', 'adverb'),       # adverb
        '.ar': ('vblex', 'verb'),      # infinitive verb
        '.ir': ('vblex', 'verb'),      # infinitive verb (passive)
    }
    
    def __init__(self, json_file):
        """Load the merged JSON dictionary"""
        with open(json_file, 'r', encoding='utf-8') as f:
            self.data = json.load(f)
        
        self.stats = {
            'total_entries': len(self.data['words']),
            'by_pos': defaultdict(int),
            'with_morfologio': 0,
            'without_morfologio': 0,
        }
    
    def analyze_morfologio(self, morfologio):
        """
        Analyze morfologio field to extract root and determine POS
        Returns: (root, pos_tag, full_morphology)
        """
        if not morfologio or len(morfologio) < 2:
            return None, None, None
        
        root = morfologio[0]
        suffixes = ''.join(morfologio[1:])
        
        # Determine POS from suffix
        pos_tag = None
        for suffix_pattern, (tag, _) in self.SUFFIX_TO_POS.items():
            if suffixes.endswith(suffix_pattern):
                pos_tag = tag
                break
        
        return root, pos_tag, suffixes
    
    def guess_pos_from_word(self, word, esperanto_translation):
        """
        Guess POS from word ending when morfologio is unavailable.
        Returns: pos_tag (or None if cannot determine)
        """
        if not word:
            return None
        
        # Common Ido word endings
        if word.endswith('o'):
            return 'n'  # noun
        elif word.endswith('a'):
            return 'adj'  # adjective
        elif word.endswith('e'):
            return 'adv'  # adverb
        elif word.endswith('ar') or word.endswith('ir'):
            return 'vblex'  # verb
        elif word.endswith('as') or word.endswith('is') or word.endswith('os'):
            return 'vblex'  # conjugated verb
        
        # Check common function words
        function_words = {
            # Conjunctions
            'e': 'cnjcoo', 'o': 'cnjcoo', 'ma': 'cnjcoo', 'sed': 'cnjcoo', 
            'nam': 'cnjcoo', 'ka': 'cnjcoo',
            'se': 'cnjsub', 'kande': 'cnjsub', 'dum': 'cnjsub', 'quale': 'cnjsub', 
            'quankam': 'cnjsub', 'pro': 'cnjsub',
            # Prepositions  
            'de': 'pr', 'da': 'pr', 'en': 'pr', 'ad': 'pr', 'sur': 'pr', 
            'sub': 'pr', 'ante': 'pr', 'pos': 'pr', 'inter': 'pr', 
            'kontre': 'pr', 'til': 'pr', 'tra': 'pr', 'ultra': 'pr', 
            'cis': 'pr', 'per': 'pr', 'por': 'pr',
            # Adverbs
            'anke': 'adv', 'tre': 'adv', 'nur': 'adv', 'yes': 'adv', 'no': 'adv', 
            'forsan': 'adv', 'anche': 'adv', 'ja': 'adv', 'ne': 'adv',
            'hike': 'adv', 'ibe': 'adv', 'ube': 'adv', 'ulaloke': 'adv',
            # Pronouns
            'me': 'prn', 'tu': 'prn', 'il': 'prn', 'ela': 'prn', 'ol': 'prn', 
            'lu': 'prn', 'ni': 'prn', 'vi': 'prn', 'li': 'prn', 'eli': 'prn',
            'olu': 'prn', 'elu': 'prn', 'nia': 'prn', 'via': 'prn', 'lia': 'prn',
        }
        
        if word.lower() in function_words:
            return function_words[word.lower()]
        
        # If Esperanto translation is provided, check its ending
        if esperanto_translation:
            epo = esperanto_translation.lower()
            if epo.endswith('o'):
                return 'n'
            elif epo.endswith('a'):
                return 'adj'
            elif epo.endswith('e'):
                return 'adv'
            elif epo.endswith('i'):
                return 'vblex'
        
        # Default to adverb for unrecognized words (many function words are adverbs)
        return 'adv'
    
    def _extract_esperanto_root(self, word, pos_tag):
        """
        Extract the root from an Esperanto word based on POS.
        Returns: root (stem without grammatical ending)
        """
        if not word:
            return word
        
        # For nouns, remove -o
        if pos_tag == 'n' and word.endswith('o'):
            return word[:-1]
        
        # For adjectives, remove -a
        if pos_tag == 'adj' and word.endswith('a'):
            return word[:-1]
        
        # For adverbs, remove -e
        if pos_tag == 'adv' and word.endswith('e'):
            return word[:-1]
        
        # For verbs, remove -i
        if pos_tag == 'vblex' and word.endswith('i'):
            return word[:-1]
        
        # For function words and others, return as-is
        return word
    
    def create_ido_monolingual_dix(self, output_file):
        """Create Ido monolingual morphological dictionary"""
        
        # Create XML structure
        dictionary = ET.Element('dictionary')
        
        # Add alphabet
        alphabet = ET.SubElement(dictionary, 'alphabet')
        alphabet.text = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
        
        # Add symbol definitions
        sdefs = ET.SubElement(dictionary, 'sdefs')
        symbols = [
            'n', 'adj', 'adv', 'vblex', 'pr', 'prn', 'det', 
            'num', 'cnjcoo', 'cnjsub', 'ij',
            'sg', 'pl', 'sp',
            'nom', 'acc',
            'inf', 'pri', 'pii', 'fti', 'cni', 'imp',
            'p1', 'p2', 'p3',
            'm', 'f', 'mf', 'nt',
            'np', 'ant', 'cog', 'top', 'al',
        ]
        for symbol in symbols:
            ET.SubElement(sdefs, 'sdef', n=symbol)
        
        # Add paradigms
        pardefs = ET.SubElement(dictionary, 'pardefs')
        self._add_ido_paradigms(pardefs)
        
        # Add main section with entries
        section = ET.SubElement(dictionary, 'section', id='main', type='standard')
        
        # Process each entry
        entries_by_pos = defaultdict(list)
        fixed_entries_by_pos = defaultdict(list)  # For words without paradigms
        
        for word_entry in self.data['words']:
            ido_word = word_entry.get('ido_word', '')
            morfologio = word_entry.get('morfologio', [])
            esperanto_words = word_entry.get('esperanto_words', [])
            
            if not ido_word:
                continue
            
            if morfologio and len(morfologio) >= 2:
                root, pos_tag, suffixes = self.analyze_morfologio(morfologio)
                
                if root and pos_tag:
                    self.stats['with_morfologio'] += 1
                    self.stats['by_pos'][pos_tag] += 1
                    
                    # Determine paradigm name
                    paradigm = self._get_paradigm_name(suffixes, pos_tag)
                    
                    entries_by_pos[pos_tag].append({
                        'lemma': ido_word,
                        'root': root,
                        'paradigm': paradigm
                    })
                else:
                    self.stats['without_morfologio'] += 1
                    # Try fallback for words without standard morfologio
                    epo_word = esperanto_words[0] if esperanto_words else ''
                    pos_tag = self.guess_pos_from_word(ido_word, epo_word)
                    if pos_tag:
                        self.stats['by_pos'][pos_tag] += 1
                        fixed_entries_by_pos[pos_tag].append({
                            'lemma': ido_word,
                            'pos': pos_tag
                        })
            else:
                self.stats['without_morfologio'] += 1
                # Try fallback for words without morfologio
                epo_word = esperanto_words[0] if esperanto_words else ''
                pos_tag = self.guess_pos_from_word(ido_word, epo_word)
                if pos_tag:
                    self.stats['by_pos'][pos_tag] += 1
                    fixed_entries_by_pos[pos_tag].append({
                        'lemma': ido_word,
                        'pos': pos_tag
                    })
        
        # Add entries with paradigms grouped by POS
        for pos_tag, entries in sorted(entries_by_pos.items()):
            # Add comment
            comment = ET.Comment(f' {pos_tag} entries with paradigms ({len(entries)}) ')
            section.append(comment)
            
            for entry in sorted(entries, key=lambda x: x['lemma']):
                e = ET.SubElement(section, 'e', lm=entry['lemma'])
                i = ET.SubElement(e, 'i')
                i.text = entry['root']
                ET.SubElement(e, 'par', n=entry['paradigm'])
        
        # Add fixed entries (invariable words) grouped by POS
        for pos_tag, entries in sorted(fixed_entries_by_pos.items()):
            # Add comment
            comment = ET.Comment(f' {pos_tag} invariable entries ({len(entries)}) ')
            section.append(comment)
            
            for entry in sorted(entries, key=lambda x: x['lemma']):
                e = ET.SubElement(section, 'e', lm=entry['lemma'])
                i = ET.SubElement(e, 'i')
                i.text = entry['lemma']
                # Use invariable paradigm
                ET.SubElement(e, 'par', n=f"__{pos_tag}")
        
        # Write to file
        self._write_pretty_xml(dictionary, output_file)
        return self.stats
    
    def create_bilingual_dix(self, output_file):
        """Create Ido-Esperanto bilingual dictionary"""
        
        dictionary = ET.Element('dictionary')
        
        # Add alphabet
        alphabet = ET.SubElement(dictionary, 'alphabet')
        alphabet.text = 'abcdefghijklmnopqrstuvwxyzĉĝĥĵŝŭABCDEFGHIJKLMNOPQRSTUVWXYZĈĜĤĴŜŬ'
        
        # Add symbol definitions (same as monolingual)
        sdefs = ET.SubElement(dictionary, 'sdefs')
        symbols = ['n', 'adj', 'adv', 'vblex', 'pr', 'prn', 'det', 'num', 
                   'cnjcoo', 'cnjsub', 'ij', 'sg', 'pl', 'sp', 'nom', 'acc',
                   'inf', 'pri', 'pii', 'fti', 'cni', 'imp', 'p1', 'p2', 'p3']
        for symbol in symbols:
            ET.SubElement(sdefs, 'sdef', n=symbol)
        
        # Add main section
        section = ET.SubElement(dictionary, 'section', id='main', type='standard')
        
        bilingual_count = 0
        skipped_count = 0
        fallback_count = 0
        
        for word_entry in self.data['words']:
            ido_word = word_entry.get('ido_word', '')
            esperanto_words = word_entry.get('esperanto_words', [])
            morfologio = word_entry.get('morfologio', [])
            
            if not ido_word or not esperanto_words:
                continue
            
            # Get first Esperanto translation
            epo_word = esperanto_words[0] if esperanto_words else ''
            
            # Clean up any formatting artifacts
            if '|' in epo_word or '{' in epo_word:
                skipped_count += 1
                continue
            
            if not epo_word:
                skipped_count += 1
                continue
            
            # Analyze morphology to get POS
            root, pos_tag, suffixes = self.analyze_morfologio(morfologio)
            
            # If no POS from morfologio, try to guess it
            if not pos_tag:
                pos_tag = self.guess_pos_from_word(ido_word, epo_word)
                if pos_tag:
                    fallback_count += 1
            
            if pos_tag:
                # Create bilingual entry
                e = ET.SubElement(section, 'e')
                p = ET.SubElement(e, 'p')
                
                # Left side (Ido) - use lemma (full form), not root
                l = ET.SubElement(p, 'l')
                l.text = ido_word
                ET.SubElement(l, 's', n=pos_tag)
                
                # Right side (Esperanto) - use lemma (full form), not root  
                r = ET.SubElement(p, 'r')
                r.text = epo_word
                ET.SubElement(r, 's', n=pos_tag)
                
                bilingual_count += 1
            else:
                skipped_count += 1
        
        # Write to file
        self._write_pretty_xml(dictionary, output_file)
        
        return {
            'bilingual_entries': bilingual_count,
            'fallback_guessed': fallback_count,
            'skipped': skipped_count,
            'source': 'Ido',
            'target': 'Esperanto'
        }
    
    def _add_ido_paradigms(self, pardefs):
        """Add Ido inflection paradigms"""
        
        # Noun paradigm (o__n)
        pardef = ET.SubElement(pardefs, 'pardef', n='o__n')
        # Singular nominative
        e = ET.SubElement(pardef, 'e')
        p = ET.SubElement(e, 'p')
        l = ET.SubElement(p, 'l')
        l.text = 'o'
        r = ET.SubElement(p, 'r')
        r.text = 'o'
        ET.SubElement(r, 's', n='n')
        ET.SubElement(r, 's', n='sg')
        ET.SubElement(r, 's', n='nom')
        
        # Plural nominative  
        e = ET.SubElement(pardef, 'e')
        p = ET.SubElement(e, 'p')
        l = ET.SubElement(p, 'l')
        l.text = 'i'
        r = ET.SubElement(p, 'r')
        r.text = 'o'
        ET.SubElement(r, 's', n='n')
        ET.SubElement(r, 's', n='pl')
        ET.SubElement(r, 's', n='nom')
        
        # Singular accusative
        e = ET.SubElement(pardef, 'e')
        p = ET.SubElement(e, 'p')
        l = ET.SubElement(p, 'l')
        l.text = 'on'
        r = ET.SubElement(p, 'r')
        r.text = 'o'
        ET.SubElement(r, 's', n='n')
        ET.SubElement(r, 's', n='sg')
        ET.SubElement(r, 's', n='acc')
        
        # Plural accusative
        e = ET.SubElement(pardef, 'e')
        p = ET.SubElement(e, 'p')
        l = ET.SubElement(p, 'l')
        l.text = 'in'
        r = ET.SubElement(p, 'r')
        r.text = 'o'
        ET.SubElement(r, 's', n='n')
        ET.SubElement(r, 's', n='pl')
        ET.SubElement(r, 's', n='acc')
        
        # Adjective paradigm (a__adj)
        pardef = ET.SubElement(pardefs, 'pardef', n='a__adj')
        # Singular
        e = ET.SubElement(pardef, 'e')
        p = ET.SubElement(e, 'p')
        l = ET.SubElement(p, 'l')
        l.text = 'a'
        r = ET.SubElement(p, 'r')
        r.text = 'a'
        ET.SubElement(r, 's', n='adj')
        ET.SubElement(r, 's', n='sg')
        
        # Plural
        e = ET.SubElement(pardef, 'e')
        p = ET.SubElement(e, 'p')
        l = ET.SubElement(p, 'l')
        l.text = 'i'
        r = ET.SubElement(p, 'r')
        r.text = 'a'
        ET.SubElement(r, 's', n='adj')
        ET.SubElement(r, 's', n='pl')
        
        # Adverb paradigm (e__adv)
        pardef = ET.SubElement(pardefs, 'pardef', n='e__adv')
        e = ET.SubElement(pardef, 'e')
        p = ET.SubElement(e, 'p')
        ET.SubElement(p, 'l').text = 'e'
        r = ET.SubElement(p, 'r')
        r.text = 'e'
        ET.SubElement(r, 's', n='adv')
        
        # Verb paradigm (ar__vblex)
        pardef = ET.SubElement(pardefs, 'pardef', n='ar__vblex')
        # Infinitive
        e = ET.SubElement(pardef, 'e')
        p = ET.SubElement(e, 'p')
        ET.SubElement(p, 'l').text = 'ar'
        r = ET.SubElement(p, 'r')
        r.text = 'ar'
        ET.SubElement(r, 's', n='vblex')
        ET.SubElement(r, 's', n='inf')
        
        # Present tense (-as)
        e = ET.SubElement(pardef, 'e')
        p = ET.SubElement(e, 'p')
        ET.SubElement(p, 'l').text = 'as'
        r = ET.SubElement(p, 'r')
        r.text = 'ar'
        ET.SubElement(r, 's', n='vblex')
        ET.SubElement(r, 's', n='pri')
        
        # Past tense (-is)
        e = ET.SubElement(pardef, 'e')
        p = ET.SubElement(e, 'p')
        ET.SubElement(p, 'l').text = 'is'
        r = ET.SubElement(p, 'r')
        r.text = 'ar'
        ET.SubElement(r, 's', n='vblex')
        ET.SubElement(r, 's', n='pii')
        
        # Future tense (-os)
        e = ET.SubElement(pardef, 'e')
        p = ET.SubElement(e, 'p')
        ET.SubElement(p, 'l').text = 'os'
        r = ET.SubElement(p, 'r')
        r.text = 'ar'
        ET.SubElement(r, 's', n='vblex')
        ET.SubElement(r, 's', n='fti')
        
        # Conditional (-us)
        e = ET.SubElement(pardef, 'e')
        p = ET.SubElement(e, 'p')
        ET.SubElement(p, 'l').text = 'us'
        r = ET.SubElement(p, 'r')
        r.text = 'ar'
        ET.SubElement(r, 's', n='vblex')
        ET.SubElement(r, 's', n='cni')
        
        # Imperative (-ez)
        e = ET.SubElement(pardef, 'e')
        p = ET.SubElement(e, 'p')
        ET.SubElement(p, 'l').text = 'ez'
        r = ET.SubElement(p, 'r')
        r.text = 'ar'
        ET.SubElement(r, 's', n='vblex')
        ET.SubElement(r, 's', n='imp')
        
        # Invariable paradigms for function words
        # Invariable adverb
        pardef = ET.SubElement(pardefs, 'pardef', n='__adv')
        e = ET.SubElement(pardef, 'e')
        p = ET.SubElement(e, 'p')
        ET.SubElement(p, 'l').text = ''
        r = ET.SubElement(p, 'r')
        ET.SubElement(r, 's', n='adv')
        
        # Invariable preposition
        pardef = ET.SubElement(pardefs, 'pardef', n='__pr')
        e = ET.SubElement(pardef, 'e')
        p = ET.SubElement(e, 'p')
        ET.SubElement(p, 'l').text = ''
        r = ET.SubElement(p, 'r')
        ET.SubElement(r, 's', n='pr')
        
        # Invariable coordinating conjunction
        pardef = ET.SubElement(pardefs, 'pardef', n='__cnjcoo')
        e = ET.SubElement(pardef, 'e')
        p = ET.SubElement(e, 'p')
        ET.SubElement(p, 'l').text = ''
        r = ET.SubElement(p, 'r')
        ET.SubElement(r, 's', n='cnjcoo')
        
        # Invariable subordinating conjunction
        pardef = ET.SubElement(pardefs, 'pardef', n='__cnjsub')
        e = ET.SubElement(pardef, 'e')
        p = ET.SubElement(e, 'p')
        ET.SubElement(p, 'l').text = ''
        r = ET.SubElement(p, 'r')
        ET.SubElement(r, 's', n='cnjsub')
        
        # Invariable pronoun
        pardef = ET.SubElement(pardefs, 'pardef', n='__prn')
        e = ET.SubElement(pardef, 'e')
        p = ET.SubElement(e, 'p')
        ET.SubElement(p, 'l').text = ''
        r = ET.SubElement(p, 'r')
        ET.SubElement(r, 's', n='prn')
        
        # Invariable noun
        pardef = ET.SubElement(pardefs, 'pardef', n='__n')
        e = ET.SubElement(pardef, 'e')
        p = ET.SubElement(e, 'p')
        ET.SubElement(p, 'l').text = ''
        r = ET.SubElement(p, 'r')
        ET.SubElement(r, 's', n='n')
        
        # Invariable adjective
        pardef = ET.SubElement(pardefs, 'pardef', n='__adj')
        e = ET.SubElement(pardef, 'e')
        p = ET.SubElement(e, 'p')
        ET.SubElement(p, 'l').text = ''
        r = ET.SubElement(p, 'r')
        ET.SubElement(r, 's', n='adj')
        
        # Invariable verb
        pardef = ET.SubElement(pardefs, 'pardef', n='__vblex')
        e = ET.SubElement(pardef, 'e')
        p = ET.SubElement(e, 'p')
        ET.SubElement(p, 'l').text = ''
        r = ET.SubElement(p, 'r')
        ET.SubElement(r, 's', n='vblex')
    
    def _get_paradigm_name(self, suffixes, pos_tag):
        """Determine appropriate paradigm based on suffix and POS"""
        if pos_tag == 'n':
            return 'o__n'
        elif pos_tag == 'adj':
            return 'a__adj'
        elif pos_tag == 'adv':
            return 'e__adv'
        elif pos_tag == 'vblex':
            return 'ar__vblex'
        else:
            return 'o__n'  # default
    
    def _write_pretty_xml(self, element, filename):
        """Write XML with pretty formatting"""
        # Convert to string without pretty printing
        # Apertium tools are sensitive to whitespace in certain contexts
        rough_string = ET.tostring(element, encoding='utf-8')
        
        with open(filename, 'wb') as f:
            # Add XML declaration
            f.write(b'<?xml version="1.0" encoding="UTF-8"?>\n')
            f.write(rough_string)
            f.write(b'\n')
        
        print(f"✅ Written to: {filename}")


def main():
    """Main conversion function"""
    print("🔄 Ido-Esperanto Dictionary Converter")
    print("=" * 60)
    
    converter = DixConverter('dictionary_merged.json')
    
    print(f"\n📊 Total entries in JSON: {converter.stats['total_entries']}")
    
    # Create Ido monolingual dictionary
    print("\n🔨 Creating Ido monolingual dictionary...")
    ido_stats = converter.create_ido_monolingual_dix('apertium-ido.ido.dix')
    
    print(f"\n✅ Ido Dictionary Statistics:")
    print(f"   - Entries with morphology: {ido_stats['with_morfologio']}")
    print(f"   - Entries without morphology: {ido_stats['without_morfologio']}")
    print(f"   - By POS:")
    for pos, count in sorted(ido_stats['by_pos'].items()):
        print(f"     * {pos}: {count}")
    
    # Create bilingual dictionary
    print("\n🔨 Creating Ido-Esperanto bilingual dictionary...")
    bil_stats = converter.create_bilingual_dix('apertium-ido-epo.ido-epo.dix')
    
    print(f"\n✅ Bilingual Dictionary Statistics:")
    print(f"   - Bilingual entries: {bil_stats['bilingual_entries']}")
    print(f"   - POS guessed (fallback): {bil_stats['fallback_guessed']}")
    print(f"   - Skipped entries: {bil_stats['skipped']}")
    print(f"   - Direction: {bil_stats['source']} → {bil_stats['target']}")
    
    print("\n✨ Conversion complete!")
    print("\n📁 Generated files:")
    print("   - apertium-ido.ido.dix (Ido monolingual)")
    print("   - apertium-ido-epo.ido-epo.dix (Ido-Esperanto bilingual)")


if __name__ == '__main__':
    main()

