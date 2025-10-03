#!/usr/bin/env python3
"""
Bidirectional Dictionary Extractor v3

Supports extraction between Ido and Esperanto in both directions:
- Ido → Esperanto (from io.wiktionary.org)
- Esperanto → Ido (from eo.wiktionary.org)

Features:
- Part of speech extraction
- Proper parsing of multiple meanings
- Cleaner output format
- Better translation cleaning
- Bidirectional language support
"""

import argparse
import bz2
import json
import os
import re
import stat
import sys
import tempfile
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Optional, List, Dict, Iterator, Tuple
from urllib.parse import urljoin

try:
    import mwparserfromhell as mwp
    HAVE_MWP = True
except ImportError:
    mwp = None
    HAVE_MWP = False

# Configuration for different language pairs
DUMP_CONFIGS = {
    'ido-esperanto': {
        'dump_url': 'https://dumps.wikimedia.org/iowiktionary/latest/iowiktionary-latest-pages-articles.xml.bz2',
        'dump_file': 'iowiktionary-latest-pages-articles.xml.bz2',
        'source_lang': 'ido',
        'target_lang': 'esperanto',
        'source_code': 'io',
        'target_code': 'eo',
        'wiktionary_domain': 'io.wiktionary.org'
    },
    'esperanto-ido': {
        'dump_url': 'https://dumps.wikimedia.org/eowiktionary/latest/eowiktionary-latest-pages-articles.xml.bz2',
        'dump_file': 'eowiktionary-latest-pages-articles.xml.bz2',
        'source_lang': 'esperanto',
        'target_lang': 'ido',
        'source_code': 'eo',
        'target_code': 'io',
        'wiktionary_domain': 'eo.wiktionary.org'
    }
}

# Patterns for different language sections
SECTION_PATTERNS = {
    'ido': [
        re.compile(r'==\s*\{\{io\}\}\s*==', re.IGNORECASE),
        re.compile(r'==\s*Ido\s*==', re.IGNORECASE),
        re.compile(r'\{\{-ido-\}\}', re.IGNORECASE),
        re.compile(r'\{\{-adj-\}\}', re.IGNORECASE)
    ],
    'esperanto': [
        re.compile(r'==\s*\{\{eo\}\}\s*==', re.IGNORECASE),
        re.compile(r'==\s*Esperanto\s*==', re.IGNORECASE),
        re.compile(r'\{\{-eo-\}\}', re.IGNORECASE),
        re.compile(r'\{\{-adj-\}\}', re.IGNORECASE)
    ]
}

# Translation patterns for different target languages
TRANSLATION_PATTERNS = {
    'esperanto': [
        # Pattern 1: *{{eo}}: translation
        re.compile(r'\*\s*\{\{eo\}\}\s*:\s*(.+?)(?=\s*\n\s*\*|\s*\n\s*\|}|\s*$)', re.IGNORECASE | re.DOTALL),
        # Pattern 2: *Esperanto: translation
        re.compile(r'\*\s*(?:Esperanto|esperanto|eo)\s*[:\-]\s*(.+?)(?=\s*\n\s*\*|\s*\n\s*\|}|\s*$)', re.IGNORECASE | re.DOTALL),
        # Pattern 3: Template patterns
        re.compile(r'{{t\+?\|eo\|([^}|]+)}}', re.IGNORECASE),
        re.compile(r'{{l\|eo\|([^}|]+)}}', re.IGNORECASE),
        re.compile(r'{{ux\|io\|([^}|]+)\|([^}]+)}}', re.IGNORECASE),
    ],
    'ido': [
        # Pattern 1: *{{io}}: translation
        re.compile(r'\*\s*\{\{io\}\}\s*:\s*(.+?)(?=\s*\n\s*\*|\s*\n\s*\|}|\s*$)', re.IGNORECASE | re.DOTALL),
        # Pattern 2: *Ido: translation
        re.compile(r'\*\s*(?:Ido|ido|io)\s*[:\-]\s*(.+?)(?=\s*\n\s*\*|\s*\n\s*\|}|\s*$)', re.IGNORECASE | re.DOTALL),
        # Pattern 3: Template patterns
        re.compile(r'{{t\+?\|io\|([^}|]+)}}', re.IGNORECASE),
        re.compile(r'{{l\|io\|([^}|]+)}}', re.IGNORECASE),
        re.compile(r'{{ux\|eo\|([^}|]+)\|([^}]+)}}', re.IGNORECASE),
    ]
}

# Part of speech patterns
POS_PATTERNS = [
    re.compile(r'===\s*(Noun|Verb|Adjective|Adverb|Pronoun|Preposition|Conjunction|Interjection|Substantivo|Verbo|Adjektivo|Adverbo)\s*===', re.IGNORECASE),
]

# Category patterns to exclude
EXCLUDE_CATEGORY_PATTERNS = [
    re.compile(r'sufix', re.IGNORECASE),
    re.compile(r'sufixo', re.IGNORECASE),
    re.compile(r'radik', re.IGNORECASE),
    re.compile(r'radiko', re.IGNORECASE),
    re.compile(r'kompon', re.IGNORECASE),
    re.compile(r'affix', re.IGNORECASE),
    re.compile(r'suffix', re.IGNORECASE),
    re.compile(r'prefix', re.IGNORECASE),
    re.compile(r'io-rad', re.IGNORECASE),
]

# Word validation patterns
INVALID_TITLE_PATTERNS = [
    re.compile(r'^[^A-Za-z]'),  # Doesn't start with letter
    re.compile(r'^[A-Za-z]$'),  # Single letter
    re.compile(r'^[0-9]+'),     # Starts with numbers
    re.compile(r'[=\/\&\+\-\(\)\[\]\{\}\|]'),  # Contains special chars
    re.compile(r'^\s*$'),       # Empty or whitespace only
]


class BidirectionalDictionaryExtractor:
    """Bidirectional dictionary extractor supporting Ido↔Esperanto extraction."""
    
    def __init__(self, language_pair: str = 'ido-esperanto', dump_file: str = None):
        """
        Initialize the extractor for a specific language pair.
        
        Args:
            language_pair: Either 'ido-esperanto' or 'esperanto-ido'
            dump_file: Override the default dump file path
        """
        if language_pair not in DUMP_CONFIGS:
            raise ValueError(f"Unsupported language pair: {language_pair}. Supported pairs: {list(DUMP_CONFIGS.keys())}")
        
        self.config = DUMP_CONFIGS[language_pair]
        self.language_pair = language_pair
        self.dump_file = dump_file or self.config['dump_file']
        
        # Get language-specific patterns
        self.source_section_patterns = SECTION_PATTERNS[self.config['source_lang']]
        self.target_translation_patterns = TRANSLATION_PATTERNS[self.config['target_lang']]
        
        self.stats = {
            'pages_processed': 0,
            f'pages_with_{self.config["source_lang"]}_section': 0,
            'valid_entries_found': 0,
            'skipped_by_category': 0,
            'skipped_by_title': 0,
            'skipped_no_translations': 0,
            'entries_with_pos': 0,
            'entries_with_multiple_meanings': 0,
            'entries_with_metadata': 0,
        }
        self.failed_links = []  # Track links that failed to parse
    
    def is_valid_title(self, title: str) -> bool:
        """Check if title represents a valid word entry."""
        if not title or len(title.strip()) == 0:
            return False
        
        title = title.strip()
        
        # Check against invalid patterns
        for pattern in INVALID_TITLE_PATTERNS:
            if pattern.search(title):
                return False
        
        # Additional checks
        if len(title) < 2:
            return False
        
        # Skip common non-words
        skip_words = {
            'MediaWiki', 'Help', 'Category', 'Template', 'User', 'Talk',
            'File', 'Image', 'Special', 'Main', 'Wikipedia', 'Wiktionary'
        }
        if title in skip_words:
            return False
        
        return True
    
    def has_excluded_categories(self, wikitext: str) -> bool:
        """Check if page has categories that should be excluded."""
        categories = re.findall(r'\[\[(?:Category|Kategorio):\s*([^\]|]+)', wikitext, re.IGNORECASE)
        category_text = ' '.join(categories).lower()
        
        for pattern in EXCLUDE_CATEGORY_PATTERNS:
            if pattern.search(category_text):
                return True
        return False
    
    def extract_source_section(self, wikitext: str) -> Optional[str]:
        """Extract the source language section from wikitext."""
        for pattern in self.source_section_patterns:
            match = re.search(pattern, wikitext)
            if match:
                # Find the end of the Ido section
                start_pos = match.start()
                section_content = wikitext[start_pos:]
                
                # For template-based sections ({{-ido-}}, {{-adj-}}), look for next section differently
                if pattern.pattern in [r'\{\{-ido-\}\}', r'\{\{-adj-\}\}']:
                    # Look for next major section (## or == headers)
                    next_section = re.search(r'\n##|\n==[^=]', section_content)
                    if next_section:
                        section_content = section_content[:next_section.start()]
                else:
                    # For traditional sections, look for next == header
                    next_section = re.search(r'\n==[^=]', section_content)
                    if next_section:
                        section_content = section_content[:next_section.start()]
                
                return section_content
                return None
                
    def extract_part_of_speech(self, ido_section: str) -> Optional[str]:
        """Extract part of speech from Ido section."""
        if not ido_section:
                return None
                
        for pattern in POS_PATTERNS:
            match = pattern.search(ido_section)
            if match:
                pos = match.group(1).lower()
                # Map to standard English terms
                pos_map = {
                    'substantivo': 'noun',
                    'verbo': 'verb', 
                    'adjektivo': 'adjective',
                    'adverbo': 'adverb'
                }
                return pos_map.get(pos, pos)
        
            return None

    def extract_metadata(self, ido_section: str) -> Dict[str, any]:
        """Extract additional metadata from Ido section like Morfologio."""
        metadata = {}
        
        if not ido_section:
            return metadata
        
        # Extract Morfologio (morphology) and parse into meaningful list
        morfologio_patterns = [
            r'Morfologio:\s*([^\n]+)',
            r'Morfologio\s*:\s*([^\n]+)',
            r'Morfologio\s+([^\n]+)'
        ]
        for pattern in morfologio_patterns:
            match = re.search(pattern, ido_section, re.IGNORECASE)
            if match:
                morfologio_text = match.group(1).strip()
                # Clean up common artifacts
                morfologio_text = re.sub(r'^\s*[:\-]\s*', '', morfologio_text)
                if morfologio_text and len(morfologio_text) > 1:
                    # Parse morfologio into meaningful components
                    parsed_morfologio = self.parse_morfologio(morfologio_text)
                    if parsed_morfologio:
                        metadata['morfologio'] = parsed_morfologio
                break

        return metadata
    
    def parse_morfologio(self, morfologio_text: str) -> List[str]:
        """Parse morfologio text into meaningful components.
        Example: "[[fac]][[.ar]] [[Kategorio:Io FA]]" -> ["fac", ".ar"]"""
        if not morfologio_text:
            return []
        
        components = []
        
        # Remove category references (Kategorio:)
        text = re.sub(r'\s*\[\[Kategorio:[^\]]+\]\]', '', morfologio_text)
        
        # Extract components from [[word]] patterns
        # Pattern matches: [[fac]], [[.ar]], [[word]], etc.
        matches = re.findall(r'\[\[([^\]]+)\]\]', text)
        
        for match in matches:
            # Skip empty matches
            if not match.strip():
                continue
            
            # Clean up the match
            clean_match = match.strip()
            
            # Skip category codes that might still be there
            if re.match(r'^[A-Z]{1,3}$', clean_match):
                continue
            
            components.append(clean_match)
        
        return components
    
    def parse_multiple_translations(self, translation_text: str) -> List[List[str]]:
        """Parse a translation string that may contain multiple meanings.
        Returns a list of lists, where each inner list represents one meaning with its synonyms."""
        if not translation_text:
            return []
        
        meanings = []
        
        # Special handling for [[#Esperanto|translation]] pattern
        esperanto_link_match = re.search(r'\[\[#Esperanto\|([^\]]+)\]\]', translation_text)
        if esperanto_link_match:
            translation = esperanto_link_match.group(1).strip()
            # Clean up any trailing symbols like ↓
            translation = re.sub(r'\s+↓\s*$', '', translation)
            if translation and len(translation) > 1:
                meanings.append([translation])
                return meanings
        
        # Clean the text first
        text = self.clean_translation(translation_text)
        if not text:
            return []
        
        # Skip malformed entries
        if text in ['[['] or text.startswith('[['):
            return []
        
        # Handle numbered meanings like "(1) finiĝi; (2) fini"
        numbered_pattern = r'\((\d+)\)\s*([^;()]+)'
        numbered_matches = re.findall(numbered_pattern, text)
        if numbered_matches:
            for num, meaning in numbered_matches:
                clean_meaning = meaning.strip()
                if clean_meaning and len(clean_meaning) > 1:
                    # Split by commas for synonyms within each meaning
                    synonyms = [s.strip() for s in clean_meaning.split(',') if s.strip()]
                    if synonyms:
                        meanings.append(synonyms)
            return meanings
        
        # Handle semicolon-separated meanings like "kanti; ĉirpi" or "malkaŝi; riveli, revelacii"
        if ';' in text:
            parts = text.split(';')
            for part in parts:
                clean_part = part.strip()
                if clean_part and len(clean_part) > 1:
                    # Split by commas for synonyms within each meaning
                    synonyms = [s.strip() for s in clean_part.split(',') if s.strip()]
                    if synonyms:
                        meanings.append(synonyms)
            return meanings
        
        # Handle comma-separated meanings (but be careful with commas in definitions)
        if ',' in text and len(text) > 10:  # Only split if it's a longer text
            # Look for patterns like "word1, word2, word3" vs "word, definition"
            # If it looks like a list of short words, split on commas
            parts = [p.strip() for p in text.split(',')]
            if all(len(p) < 20 for p in parts):  # All parts are reasonably short
                meanings.append(parts)
                return meanings
        
        # Single translation
        if text and len(text) > 1:
            meanings.append([text])
        
        return meanings
    
    def extract_translations(self, source_section: str) -> List[List[str]]:
        """Extract target language translations from source language section."""
        all_meanings = []
        
        if not source_section:
            return all_meanings
        
        # Extract using patterns
        for pattern in self.target_translation_patterns:
            matches = pattern.findall(source_section)
            for match in matches:
                if isinstance(match, tuple):
                    # Handle templates with multiple parameters
                    translation = match[0].strip()
                else:
                    translation = match.strip()
                
                # Check if translation is truly empty or contains only whitespace/newlines
                if translation and translation.strip() and len(translation.strip()) > 1:
                    # Skip translations that are just template markers or malformed
                    if (translation.strip() in ['}}', '{{', '}', '{'] or 
                        translation.strip().startswith('}}') or
                        translation.strip().endswith('{{') or
                        '{{' in translation.strip() or
                        translation.strip().startswith('*{{')):
                        continue
                    
                    # Parse multiple meanings
                    parsed_meanings = self.parse_multiple_translations(translation)
                    
                    # Filter out malformed meanings
                    valid_meanings = []
                    for meaning_list in parsed_meanings:
                        valid_translations = []
                        for trans in meaning_list:
                            # Skip empty, too short, or malformed translations
                            if (trans and len(trans) > 1 and 
                                not trans.startswith('[[') and 
                                not trans.endswith(']]') and
                                trans != '[[' and trans != ']]' and
                                not trans.strip().startswith('{{') and  # Skip template markers
                                not trans.strip().startswith('*{{') and  # Skip next language markers
                                trans.strip() not in ['}}', '{{', '}', '{'] and  # Skip template fragments
                                not trans.strip().startswith('}}') and
                                not trans.strip().endswith('{{')):
                                valid_translations.append(trans)
                        
                        if valid_translations:  # Only add if we have valid translations
                            valid_meanings.append(valid_translations)
                    
                    all_meanings.extend(valid_meanings)
        
        # Remove duplicate meanings while preserving order
        seen_meanings = set()
        unique_meanings = []
        for meaning_list in all_meanings:
            # Create a key from the sorted synonyms to detect duplicates
            meaning_key = tuple(sorted(meaning_list))
            if meaning_key not in seen_meanings:
                seen_meanings.add(meaning_key)
                unique_meanings.append(meaning_list)
        
        return unique_meanings
    
    def extract_target_language_section_translations(self, wikitext: str, title: str) -> List[List[str]]:
        """Extract translations from standalone Esperanto sections (fallback method)."""
        all_meanings = []
        
        if not wikitext or not title:
            return all_meanings
        
        # Look for Esperanto translations in language sections (A-lingui, B-lingui, etc.)
        language_section_patterns = [
            r'{{A-lingui}}.*?(?={{B-lingui}}|{{C-lingui}}|{{D-lingui}}|{{E-lingui}}|{{F-lingui}}|{{G-lingui}}|{{H-lingui}}|{{I-lingui}}|{{J-lingui}}|{{K-lingui}}|{{L-lingui}}|{{M-lingui}}|{{N-lingui}}|{{O-lingui}}|{{P-lingui}}|{{Q-lingui}}|{{R-lingui}}|{{S-lingui}}|{{T-lingui}}|{{U-lingui}}|{{V-lingui}}|{{W-lingui}}|{{X-lingui}}|{{Y-lingui}}|{{Z-lingui}}|\Z)',
            r'{{B-lingui}}.*?(?={{C-lingui}}|{{D-lingui}}|{{E-lingui}}|{{F-lingui}}|{{G-lingui}}|{{H-lingui}}|{{I-lingui}}|{{J-lingui}}|{{K-lingui}}|{{L-lingui}}|{{M-lingui}}|{{N-lingui}}|{{O-lingui}}|{{P-lingui}}|{{Q-lingui}}|{{R-lingui}}|{{S-lingui}}|{{T-lingui}}|{{U-lingui}}|{{V-lingui}}|{{W-lingui}}|{{X-lingui}}|{{Y-lingui}}|{{Z-lingui}}|\Z)',
            r'{{C-lingui}}.*?(?={{D-lingui}}|{{E-lingui}}|{{F-lingui}}|{{G-lingui}}|{{H-lingui}}|{{I-lingui}}|{{J-lingui}}|{{K-lingui}}|{{L-lingui}}|{{M-lingui}}|{{N-lingui}}|{{O-lingui}}|{{P-lingui}}|{{Q-lingui}}|{{R-lingui}}|{{S-lingui}}|{{T-lingui}}|{{U-lingui}}|{{V-lingui}}|{{W-lingui}}|{{X-lingui}}|{{Y-lingui}}|{{Z-lingui}}|\Z)',
            r'{{D-lingui}}.*?(?={{E-lingui}}|{{F-lingui}}|{{G-lingui}}|{{H-lingui}}|{{I-lingui}}|{{J-lingui}}|{{K-lingui}}|{{L-lingui}}|{{M-lingui}}|{{N-lingui}}|{{O-lingui}}|{{P-lingui}}|{{Q-lingui}}|{{R-lingui}}|{{S-lingui}}|{{T-lingui}}|{{U-lingui}}|{{V-lingui}}|{{W-lingui}}|{{X-lingui}}|{{Y-lingui}}|{{Z-lingui}}|\Z)',
            r'{{E-lingui}}.*?(?={{F-lingui}}|{{G-lingui}}|{{H-lingui}}|{{I-lingui}}|{{J-lingui}}|{{K-lingui}}|{{L-lingui}}|{{M-lingui}}|{{N-lingui}}|{{O-lingui}}|{{P-lingui}}|{{Q-lingui}}|{{R-lingui}}|{{S-lingui}}|{{T-lingui}}|{{U-lingui}}|{{V-lingui}}|{{W-lingui}}|{{X-lingui}}|{{Y-lingui}}|{{Z-lingui}}|\Z)',
            r'{{F-lingui}}.*?(?={{G-lingui}}|{{H-lingui}}|{{I-lingui}}|{{J-lingui}}|{{K-lingui}}|{{L-lingui}}|{{M-lingui}}|{{N-lingui}}|{{O-lingui}}|{{P-lingui}}|{{Q-lingui}}|{{R-lingui}}|{{S-lingui}}|{{T-lingui}}|{{U-lingui}}|{{V-lingui}}|{{W-lingui}}|{{X-lingui}}|{{Y-lingui}}|{{Z-lingui}}|\Z)',
            r'{{G-lingui}}.*?(?={{H-lingui}}|{{I-lingui}}|{{J-lingui}}|{{K-lingui}}|{{L-lingui}}|{{M-lingui}}|{{N-lingui}}|{{O-lingui}}|{{P-lingui}}|{{Q-lingui}}|{{R-lingui}}|{{S-lingui}}|{{T-lingui}}|{{U-lingui}}|{{V-lingui}}|{{W-lingui}}|{{X-lingui}}|{{Y-lingui}}|{{Z-lingui}}|\Z)',
            r'{{H-lingui}}.*?(?={{I-lingui}}|{{J-lingui}}|{{K-lingui}}|{{L-lingui}}|{{M-lingui}}|{{N-lingui}}|{{O-lingui}}|{{P-lingui}}|{{Q-lingui}}|{{R-lingui}}|{{S-lingui}}|{{T-lingui}}|{{U-lingui}}|{{V-lingui}}|{{W-lingui}}|{{X-lingui}}|{{Y-lingui}}|{{Z-lingui}}|\Z)',
            r'{{I-lingui}}.*?(?={{J-lingui}}|{{K-lingui}}|{{L-lingui}}|{{M-lingui}}|{{N-lingui}}|{{O-lingui}}|{{P-lingui}}|{{Q-lingui}}|{{R-lingui}}|{{S-lingui}}|{{T-lingui}}|{{U-lingui}}|{{V-lingui}}|{{W-lingui}}|{{X-lingui}}|{{Y-lingui}}|{{Z-lingui}}|\Z)',
            r'{{J-lingui}}.*?(?={{K-lingui}}|{{L-lingui}}|{{M-lingui}}|{{N-lingui}}|{{O-lingui}}|{{P-lingui}}|{{Q-lingui}}|{{R-lingui}}|{{S-lingui}}|{{T-lingui}}|{{U-lingui}}|{{V-lingui}}|{{W-lingui}}|{{X-lingui}}|{{Y-lingui}}|{{Z-lingui}}|\Z)',
            r'{{K-lingui}}.*?(?={{L-lingui}}|{{M-lingui}}|{{N-lingui}}|{{O-lingui}}|{{P-lingui}}|{{Q-lingui}}|{{R-lingui}}|{{S-lingui}}|{{T-lingui}}|{{U-lingui}}|{{V-lingui}}|{{W-lingui}}|{{X-lingui}}|{{Y-lingui}}|{{Z-lingui}}|\Z)',
            r'{{L-lingui}}.*?(?={{M-lingui}}|{{N-lingui}}|{{O-lingui}}|{{P-lingui}}|{{Q-lingui}}|{{R-lingui}}|{{S-lingui}}|{{T-lingui}}|{{U-lingui}}|{{V-lingui}}|{{W-lingui}}|{{X-lingui}}|{{Y-lingui}}|{{Z-lingui}}|\Z)',
            r'{{M-lingui}}.*?(?={{N-lingui}}|{{O-lingui}}|{{P-lingui}}|{{Q-lingui}}|{{R-lingui}}|{{S-lingui}}|{{T-lingui}}|{{U-lingui}}|{{V-lingui}}|{{W-lingui}}|{{X-lingui}}|{{Y-lingui}}|{{Z-lingui}}|\Z)',
            r'{{N-lingui}}.*?(?={{O-lingui}}|{{P-lingui}}|{{Q-lingui}}|{{R-lingui}}|{{S-lingui}}|{{T-lingui}}|{{U-lingui}}|{{V-lingui}}|{{W-lingui}}|{{X-lingui}}|{{Y-lingui}}|{{Z-lingui}}|\Z)',
            r'{{O-lingui}}.*?(?={{P-lingui}}|{{Q-lingui}}|{{R-lingui}}|{{S-lingui}}|{{T-lingui}}|{{U-lingui}}|{{V-lingui}}|{{W-lingui}}|{{X-lingui}}|{{Y-lingui}}|{{Z-lingui}}|\Z)',
            r'{{P-lingui}}.*?(?={{Q-lingui}}|{{R-lingui}}|{{S-lingui}}|{{T-lingui}}|{{U-lingui}}|{{V-lingui}}|{{W-lingui}}|{{X-lingui}}|{{Y-lingui}}|{{Z-lingui}}|\Z)',
            r'{{Q-lingui}}.*?(?={{R-lingui}}|{{S-lingui}}|{{T-lingui}}|{{U-lingui}}|{{V-lingui}}|{{W-lingui}}|{{X-lingui}}|{{Y-lingui}}|{{Z-lingui}}|\Z)',
            r'{{R-lingui}}.*?(?={{S-lingui}}|{{T-lingui}}|{{U-lingui}}|{{V-lingui}}|{{W-lingui}}|{{X-lingui}}|{{Y-lingui}}|{{Z-lingui}}|\Z)',
            r'{{S-lingui}}.*?(?={{T-lingui}}|{{U-lingui}}|{{V-lingui}}|{{W-lingui}}|{{X-lingui}}|{{Y-lingui}}|{{Z-lingui}}|\Z)',
            r'{{T-lingui}}.*?(?={{U-lingui}}|{{V-lingui}}|{{W-lingui}}|{{X-lingui}}|{{Y-lingui}}|{{Z-lingui}}|\Z)',
            r'{{U-lingui}}.*?(?={{V-lingui}}|{{W-lingui}}|{{X-lingui}}|{{Y-lingui}}|{{Z-lingui}}|\Z)',
            r'{{V-lingui}}.*?(?={{W-lingui}}|{{X-lingui}}|{{Y-lingui}}|{{Z-lingui}}|\Z)',
            r'{{W-lingui}}.*?(?={{X-lingui}}|{{Y-lingui}}|{{Z-lingui}}|\Z)',
            r'{{X-lingui}}.*?(?={{Y-lingui}}|{{Z-lingui}}|\Z)',
            r'{{Y-lingui}}.*?(?={{Z-lingui}}|\Z)',
            r'{{Z-lingui}}.*?(?=\Z)'
        ]
        
        for pattern in language_section_patterns:
            matches = re.findall(pattern, wikitext, re.DOTALL | re.IGNORECASE)
            for match in matches:
                # Look for Esperanto translations in this language section
                esperanto_patterns = [
                    r'\*\{\{eo\}\}\.\s*\[\[([^\]]+)\]\]',  # *{{eo}}. [[word]]
                    r'\*\{\{eo\}\}:\s*\[\[([^\]]+)\]\]',   # *{{eo}}: [[word]]
                    r'\*\{\{eo\}\}\.\s*([^|\n\*]+)',       # *{{eo}}. word
                    r'\*\{\{eo\}\}:\s*([^|\n\*]+)'         # *{{eo}}: word
                ]
                
                for eo_pattern in esperanto_patterns:
                    eo_matches = re.findall(eo_pattern, match, re.IGNORECASE)
                    for eo_match in eo_matches:
                        translation = eo_match.strip()
                        if translation and len(translation) > 1:
                            parsed_meanings = self.parse_multiple_translations(translation)
                            all_meanings.extend(parsed_meanings)
        
        # Also look for traditional Esperanto sections with various patterns
        esperanto_section_patterns = [
            r'## Esperanto\s*\n(.*?)(?=\n##|\Z)',
            r'=== Esperanto ===\s*\n(.*?)(?=\n===|\Z)',
            r'== Esperanto ==\s*\n(.*?)(?=\n==|\Z)'
        ]
        
        for pattern in esperanto_section_patterns:
            matches = re.findall(pattern, wikitext, re.DOTALL | re.IGNORECASE)
            for match in matches:
                esperanto_section = match.strip()
                
                # Look for translation patterns in Esperanto section
                # Pattern: * word - translation
                translation_patterns = [
                    # Direct translation: * word - translation
                    rf'\*\s*{re.escape(title)}\s*[-–]\s*([^-\n]+)',
                    # Handle cases where the word appears without explicit translation (same word)
                    rf'\*\s*{re.escape(title)}\s+kaj[^-]*[-–]\s*([^-\n]+)',
                    # Direct translation with period
                    rf'\*\s*{re.escape(title)}\s*[-–]\s*([^-\n]*?)\s*\.',
                    # Fallback pattern
                    rf'\*\s*{re.escape(title)}\s*[-–]\s*([^-\n]+)'
                ]
                
                # Special case: if the line just contains the word itself, it's self-translating
                if re.search(rf'\*\s*{re.escape(title)}\s*$', esperanto_section, re.IGNORECASE):
                    all_meanings.append([title])
                    continue
                
                # Special case: if the word appears in a compound phrase, treat as self-translating
                # Example: "* dika kaj longa - grosa." -> dika translates to dika
                if re.search(rf'\*\s*{re.escape(title)}\s+kaj', esperanto_section, re.IGNORECASE):
                    all_meanings.append([title])
                continue
                
                for trans_pattern in translation_patterns:
                    trans_matches = re.findall(trans_pattern, esperanto_section, re.IGNORECASE)
                    for trans_match in trans_matches:
                        translation = trans_match.strip()
                        if translation and len(translation) > 1:
                            # Check if the translation is just the same word (like dika -> dika)
                            if translation.lower() == title.lower():
                                all_meanings.append([title])
                        else:
                                parsed_meanings = self.parse_multiple_translations(translation)
                                all_meanings.extend(parsed_meanings)
        
        # Remove duplicate meanings while preserving order
        seen_meanings = set()
        unique_meanings = []
        for meaning_list in all_meanings:
            meaning_key = tuple(sorted(meaning_list))
            if meaning_key not in seen_meanings:
                seen_meanings.add(meaning_key)
                unique_meanings.append(meaning_list)
        
        return unique_meanings
    
    def clean_translation(self, translation: str) -> str:
        """Clean and normalize a translation string."""
        if not translation:
            return ""
        
        # Decode HTML entities first (including numeric entities like &#265; for ĉ)
        import html
        translation = html.unescape(translation)
        
        # Remove templates
        translation = re.sub(r'{{[^}]*}}', '', translation)
        
        # Remove wiki links but keep the text (handle piped links like [[ĉarmo|ĉeko]])
        translation = re.sub(r'\[\[([^\]|]*\|)?([^\]]+)\]\]', r'\2', translation)
        
        # Remove category links completely
        translation = re.sub(r'\[\[(?:Category|Kategorio):[^\]]*\]\]', '', translation)
        
        # Remove category references like "Kategorio:Eo BA" or just "BA"
        translation = re.sub(r'\s*Kategorio:[^\s]*', '', translation)
        translation = re.sub(r'\s+[A-Z]{1,3}\s*$', '', translation)
        translation = re.sub(r'\s*\[\[Kategorio:[^\]]+\]\]', '', translation)  # Remove [[Kategorio:...]]
        
        # Remove HTML tags and table fragments
        translation = re.sub(r'<[^>]+>', '', translation)
        translation = re.sub(r'\|\s*\}.*$', '', translation)  # Remove table fragments like "|} |bgcolor=..."
        
        # Remove common artifacts
        translation = re.sub(r'\*', '', translation)  # Remove asterisks
        translation = re.sub(r'#.*$', '', translation)  # Remove everything after #
        
        # Remove incomplete wiki links (like "[[")
        translation = re.sub(r'\[\[[^\]]*$', '', translation)  # Remove incomplete [[ at end
        translation = re.sub(r'^[^\[]*\]\]', '', translation)  # Remove incomplete ]] at start
        
        # Remove standalone incomplete brackets
        translation = re.sub(r'^\[\[$', '', translation)  # Remove just "[["
        translation = re.sub(r'^\]\]$', '', translation)  # Remove just "]]"
        
        # Remove arrow symbols and other Unicode symbols that aren't words
        translation = re.sub(r'[↓↑→←]', '', translation)
        
        # Remove standalone symbols that aren't words
        if len(translation.strip()) == 1 and translation.strip() in '↓↑→←':
            return ""
        
        # Clean whitespace and punctuation
        translation = re.sub(r'\s+', ' ', translation)
        translation = translation.strip(' \t\n\r\f\v:;,.-')
        
        return translation
    
    def extract_from_wikitext(self, title: str, wikitext: str) -> Optional[Dict]:
        """Extract dictionary entry from wikitext."""
        # Check if title is valid
        if not self.is_valid_title(title):
            self.stats['skipped_by_title'] += 1
            return None
    
        # Check for excluded categories
        if self.has_excluded_categories(wikitext):
            self.stats['skipped_by_category'] += 1
            return None
        
        # Extract source language section
        source_section = self.extract_source_section(wikitext)
        if not source_section:
            # Track failed parsing - pages that have source language sections but failed to extract
            if any(pattern.search(wikitext) for pattern in self.source_section_patterns):
                self.failed_links.append({
                    'title': title,
                    'url': f'https://{self.config["wiktionary_domain"]}/wiki/{title.replace(" ", "_")}'
                })
            return None
        
        self.stats[f'pages_with_{self.config["source_lang"]}_section'] += 1
        
        # Extract part of speech
        pos = self.extract_part_of_speech(source_section)
        if pos:
            self.stats['entries_with_pos'] += 1
        
        # Extract translations
        translations = self.extract_translations(source_section)
        
        # If no translations found in source section, try standalone target language sections as fallback
        if not translations:
            translations = self.extract_target_language_section_translations(wikitext, title)
        
        if not translations:
            self.stats['skipped_no_translations'] += 1
            
            # Track failed parsing - pages with source language sections but no valid translations
            self.failed_links.append({
                'title': title,
                'url': f'https://{self.config["wiktionary_domain"]}/wiki/{title.replace(" ", "_")}'
            })
            return None
    
        self.stats['valid_entries_found'] += 1
        
        # Count multiple meanings
        if len(translations) > 1:
            self.stats['entries_with_multiple_meanings'] += 1
        
        # Extract additional metadata
        metadata = self.extract_metadata(source_section)
        
        # Build entry dictionary
        entry = {
            f'{self.config["source_lang"]}_word': title,
            f'{self.config["target_lang"]}_translations': translations
        }
        
        # Only add part_of_speech if it's not empty
        if pos:
            entry['part_of_speech'] = pos
        
        # Add metadata if available
        if metadata:
            entry.update(metadata)
            self.stats['entries_with_metadata'] += 1
        
        return entry
    
    def stream_pages_from_dump(self) -> Iterator[Tuple[str, str]]:
        """Stream pages from the dump file using robust line-by-line parsing."""
        if not os.path.exists(self.dump_file):
            raise FileNotFoundError(f"Dump file not found: {self.dump_file}")
        
        # Use appropriate decompression
        if self.dump_file.endswith('.bz2'):
            file_obj = bz2.open(self.dump_file, 'rt', encoding='utf-8', errors='ignore')
        else:
            file_obj = open(self.dump_file, 'r', encoding='utf-8', errors='ignore')
        
        try:
            current_page = {}
            in_page = False
            in_text = False
            page_buffer = []
            
            for line_num, line in enumerate(file_obj):
                line = line.strip()
                
                if '<page>' in line:
                    in_page = True
                    current_page = {}
                    page_buffer = [line]
                elif '</page>' in line and in_page:
                    page_buffer.append(line)
                    page_xml = '\n'.join(page_buffer)
                    
                    # Parse the page XML
                    try:
                        page_elem = ET.fromstring(page_xml)
                        
                        # Extract title
                        title_elem = page_elem.find('title')
                        if title_elem is not None:
                            title = title_elem.text
                        else:
                            title = None
                        
                        # Extract text from revision
                        text = None
                        revision = page_elem.find('revision')
                        if revision is not None:
                            text_elem = revision.find('text')
                            if text_elem is not None:
                                text = text_elem.text
                        
                        if title and text:
                            # Unescape XML entities
                            text = text.replace('&lt;', '<')
                            text = text.replace('&gt;', '>')
                            text = text.replace('&amp;', '&')
                            
                            yield title, text
                            
                            self.stats['pages_processed'] += 1
                            
                            if self.stats['pages_processed'] % 1000 == 0:
                                print(f"Processed {self.stats['pages_processed']} pages...")
                    
                    except ET.ParseError:
                        # Skip malformed pages
                        pass
                    
                    in_page = False
                    current_page = {}
                    page_buffer = []
                
                elif in_page:
                    page_buffer.append(line)
                
                # Stop after processing enough pages for testing
                if self.stats['pages_processed'] > 500000:  # High limit for large dumps
                    break

        finally:
            file_obj.close()
    
    def download_dump(self, force: bool = False) -> None:
        """Download the dump file if it doesn't exist or force is True."""
        if os.path.exists(self.dump_file) and not force:
            print(f"Dump file already exists: {self.dump_file}")
            return
        
        dump_url = self.config['dump_url']
        print(f"Downloading {self.config['source_lang']} dump from {dump_url}...")
        print("This may take several minutes...")
        
        try:
            urllib.request.urlretrieve(dump_url, self.dump_file)
            print(f"Download complete: {self.dump_file}")
        except Exception as e:
            print(f"Error downloading dump: {e}")
            raise
    
    def get_dump_metadata(self) -> Dict[str, any]:
        """Get metadata about the dump file."""
        dump_metadata = {}
        
        if hasattr(self, 'dump_file') and self.dump_file and os.path.exists(self.dump_file):
            try:
                stat_info = os.stat(self.dump_file)
                dump_metadata = {
                    'dump_filename': os.path.basename(self.dump_file),
                    'dump_path': os.path.abspath(self.dump_file),
                    'dump_size_bytes': stat_info.st_size,
                    'dump_size_mb': round(stat_info.st_size / (1024 * 1024), 2),
                    'dump_modified': datetime.fromtimestamp(stat_info.st_mtime).isoformat(),
                    'dump_created': datetime.fromtimestamp(stat_info.st_ctime).isoformat()
                }
                
                # Try to extract version info from filename
                filename = os.path.basename(self.dump_file)
                if 'latest' in filename:
                    dump_metadata['dump_version'] = 'latest'
                else:
                    # Try to extract date from filename
                    date_match = re.search(r'(\d{8})', filename)
                    if date_match:
                        dump_metadata['dump_date'] = date_match.group(1)
                
            except Exception as e:
                dump_metadata['dump_error'] = str(e)
        
        return dump_metadata

    def extract_dictionary(self, limit: Optional[int] = None, base_output_name: str = 'ido_esperanto_v2') -> None:
        """Extract Ido-Esperanto dictionary from dump."""
        print(f"Starting bidirectional dictionary extraction v3 ({self.config['source_lang']} → {self.config['target_lang']})...")
        
        entries = []
        processed = 0
        
        try:
            for title, wikitext in self.stream_pages_from_dump():
                if limit and processed >= limit:
                    break
                
                entry = self.extract_from_wikitext(title, wikitext)
                if entry:
                    entries.append(entry)
                    # Format translations for display
                    target_translations_key = f'{self.config["target_lang"]}_translations'
                    source_word_key = f'{self.config["source_lang"]}_word'
                    
                    if entry[target_translations_key]:
                        first_meaning = entry[target_translations_key][0]
                        if isinstance(first_meaning, list):
                            translations_str = ', '.join(first_meaning[:2])
                        else:
                            translations_str = first_meaning
                        if len(entry[target_translations_key]) > 1:
                            translations_str += f" (+{len(entry[target_translations_key])-1} more)"
                    else:
                        translations_str = ""
                    pos_info = f" ({entry['part_of_speech']})" if entry.get('part_of_speech') else ""
                    print(f"✓ Found: {entry[source_word_key]}{pos_info} -> [{translations_str}]")
                
                processed += 1
            
        except KeyboardInterrupt:
            print("\nExtraction interrupted by user.")
        except Exception as e:
            print(f"Error during extraction: {e}")
            raise
        
        # Get dump metadata
        dump_metadata = self.get_dump_metadata()
        
        # Create successful entries result
        successful_result = {
            'metadata': {
                'extraction_date': datetime.now().isoformat(),
                'total_words': len(entries),
                'script_version': 'v2.0',
                'stats': self.stats.copy(),
                'source_dump': dump_metadata
            },
            'words': entries
        }
        
        # Create failed entries result
        failed_result = {
            'metadata': {
                'extraction_date': datetime.now().isoformat(),
                'total_failed': len(self.failed_links),
                'script_version': 'v2.0',
                'stats': self.stats.copy(),
                'source_dump': dump_metadata
            },
            'failed_links': self.failed_links
        }
        
        # Generate output filenames - simplified names
        successful_file = "dictionary.json"
        failed_file = "failed_items.json"
        
        # Save successful entries
        with open(successful_file, 'w', encoding='utf-8') as f:
            json.dump(successful_result, f, ensure_ascii=False, indent=2)
        
        # Save failed entries
        with open(failed_file, 'w', encoding='utf-8') as f:
            json.dump(failed_result, f, ensure_ascii=False, indent=2)
        
        print(f"\nExtraction complete!")
        print(f"Total pages processed: {self.stats['pages_processed']}")
        print(f"Pages with {self.config['source_lang']} sections: {self.stats[f'pages_with_{self.config['source_lang']}_section']}")
        print(f"Valid entries found: {self.stats['valid_entries_found']}")
        print(f"Entries with part of speech: {self.stats['entries_with_pos']}")
        print(f"Entries with multiple meanings: {self.stats['entries_with_multiple_meanings']}")
        print(f"Entries with metadata: {self.stats['entries_with_metadata']}")
        print(f"Skipped by category: {self.stats['skipped_by_category']}")
        print(f"Skipped by title: {self.stats['skipped_by_title']}")
        print(f"Skipped no translations: {self.stats['skipped_no_translations']}")
        print(f"Failed parsing links: {len(self.failed_links)}")
        print(f"Dictionary saved to: {successful_file}")
        print(f"Failed items saved to: {failed_file}")


def main():
    parser = argparse.ArgumentParser(description='Bidirectional Dictionary Extractor v3 - Ido↔Esperanto')
    parser.add_argument('--language-pair', choices=['ido-esperanto', 'esperanto-ido'], 
                       default='ido-esperanto', help='Language pair to extract (default: ido-esperanto)')
    parser.add_argument('--dump', help='Path to dump file (overrides default for language pair)')
    parser.add_argument('--download', action='store_true', help='Download dump file')
    parser.add_argument('--force-download', action='store_true', help='Force re-download of dump file')
    parser.add_argument('--output', '-o', help='Base name for output files (default: based on language pair)')
    parser.add_argument('--limit', type=int, help='Limit number of pages to process (for testing)')
    
    args = parser.parse_args()
    
    # Set default output name based on language pair
    if not args.output:
        args.output = args.language_pair
    
    # Get dump file path
    dump_file = args.dump or DUMP_CONFIGS[args.language_pair]['dump_file']
    
    extractor = BidirectionalDictionaryExtractor(args.language_pair, dump_file)
    
    try:
        if args.download or args.force_download:
            extractor.download_dump(force=args.force_download)
        
        extractor.extract_dictionary(limit=args.limit, base_output_name=args.output)
    
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
