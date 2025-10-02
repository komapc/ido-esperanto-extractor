#!/usr/bin/env python3
"""
Improved Ido-Esperanto Dictionary Extractor v2

This version includes:
- Part of speech extraction
- Proper parsing of multiple meanings
- Cleaner output format
- Better translation cleaning
"""

import argparse
import bz2
import json
import os
import re
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

# Configuration
DUMP_URL = 'https://dumps.wikimedia.org/iowiktionary/latest/iowiktionary-latest-pages-articles.xml.bz2'
DUMP_FILE = 'iowiktionary-latest-pages-articles.xml.bz2'

# Patterns for filtering
IDO_SECTION_PATTERNS = [
    re.compile(r'==\s*\{\{io\}\}\s*==', re.IGNORECASE),
    re.compile(r'==\s*Ido\s*==', re.IGNORECASE)
]

# Translation patterns
TRANSLATION_PATTERNS = [
    re.compile(r'\*\s*\{\{eo\}\}\s*:\s*([^\n\|]+)', re.IGNORECASE),
    re.compile(r'\*\s*(?:Esperanto|esperanto|eo)\s*[:\-]\s*([^\n\|]+)', re.IGNORECASE),
    re.compile(r'{{t\+?\|eo\|([^}|]+)}}', re.IGNORECASE),
    re.compile(r'{{l\|eo\|([^}|]+)}}', re.IGNORECASE),
    re.compile(r'{{ux\|io\|([^}|]+)\|([^}]+)}}', re.IGNORECASE),
]

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


class ImprovedDumpParserV2:
    """Improved dump parser with part of speech and better translation parsing."""
    
    def __init__(self, dump_file: str = DUMP_FILE):
        self.dump_file = dump_file
        self.stats = {
            'pages_processed': 0,
            'pages_with_ido_section': 0,
            'valid_entries_found': 0,
            'skipped_by_category': 0,
            'skipped_by_title': 0,
            'skipped_no_translations': 0,
            'entries_with_pos': 0,
            'entries_with_multiple_meanings': 0,
        }
    
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
    
    def extract_ido_section(self, wikitext: str) -> Optional[str]:
        """Extract the Ido section from wikitext."""
        for pattern in IDO_SECTION_PATTERNS:
            match = re.search(pattern, wikitext)
            if match:
                # Find the end of the Ido section (next == header or end of text)
                start_pos = match.start()
                section_content = wikitext[start_pos:]
                
                # Find the end of the section
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
    
    def parse_multiple_translations(self, translation_text: str) -> List[str]:
        """Parse a translation string that may contain multiple meanings."""
        if not translation_text:
            return []
        
        translations = []
        
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
                    translations.append(clean_meaning)
            return translations
        
        # Handle semicolon-separated meanings like "kanti; ĉirpi"
        if ';' in text:
            parts = text.split(';')
            for part in parts:
                clean_part = part.strip()
                if clean_part and len(clean_part) > 1:
                    translations.append(clean_part)
            return translations
        
        # Handle comma-separated meanings (but be careful with commas in definitions)
        if ',' in text and len(text) > 10:  # Only split if it's a longer text
            # Look for patterns like "word1, word2, word3" vs "word, definition"
            # If it looks like a list of short words, split on commas
            parts = [p.strip() for p in text.split(',')]
            if all(len(p) < 20 for p in parts):  # All parts are reasonably short
                translations.extend(parts)
                return translations
        
        # Single translation
        if text and len(text) > 1:
            translations.append(text)
        
        return translations
    
    def extract_translations(self, ido_section: str) -> List[str]:
        """Extract Esperanto translations from Ido section."""
        translations = []
        
        if not ido_section:
            return translations
        
        # Extract using patterns
        for pattern in TRANSLATION_PATTERNS:
            matches = pattern.findall(ido_section)
            for match in matches:
                if isinstance(match, tuple):
                    # Handle templates with multiple parameters
                    translation = match[0].strip()
                else:
                    translation = match.strip()
                
                if translation:
                    # Parse multiple meanings
                    parsed_translations = self.parse_multiple_translations(translation)
                    translations.extend(parsed_translations)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_translations = []
        for trans in translations:
            if trans not in seen and len(trans) > 1:
                seen.add(trans)
                unique_translations.append(trans)
        
        return unique_translations
    
    def clean_translation(self, translation: str) -> str:
        """Clean and normalize a translation string."""
        if not translation:
            return ""
        
        # Remove templates
        translation = re.sub(r'{{[^}]*}}', '', translation)
        
        # Remove wiki links but keep the text
        translation = re.sub(r'\[\[([^\]|]*\|)?([^\]]+)\]\]', r'\2', translation)
        
        # Remove category links completely
        translation = re.sub(r'\[\[(?:Category|Kategorio):[^\]]*\]\]', '', translation)
        
        # Remove category references like "Kategorio:Eo BA" or just "BA"
        translation = re.sub(r'\s*Kategorio:[^\s]*', '', translation)
        translation = re.sub(r'\s+[A-Z]{1,3}\s*$', '', translation)
        
        # Remove HTML tags
        translation = re.sub(r'<[^>]+>', '', translation)
        
        # Decode HTML entities
        translation = translation.replace('&nbsp;', ' ')
        translation = translation.replace('&amp;', '&')
        translation = translation.replace('&lt;', '<')
        translation = translation.replace('&gt;', '>')
        
        # Remove common artifacts
        translation = re.sub(r'\*', '', translation)  # Remove asterisks
        translation = re.sub(r'#.*$', '', translation)  # Remove everything after #
        
        # Clean whitespace and punctuation
        translation = re.sub(r'\s+', ' ', translation)
        translation = translation.strip(' \t\n\r\f\v:;,.-')
        
        return translation
    
    def extract_from_wikitext(self, title: str, wikitext: str) -> Optional[Dict]:
        """Extract Ido-Esperanto entry from wikitext."""
        # Check if title is valid
        if not self.is_valid_title(title):
            self.stats['skipped_by_title'] += 1
            return None
        
        # Check for excluded categories
        if self.has_excluded_categories(wikitext):
            self.stats['skipped_by_category'] += 1
            return None
        
        # Extract Ido section
        ido_section = self.extract_ido_section(wikitext)
        if not ido_section:
            return None
        
        self.stats['pages_with_ido_section'] += 1
        
        # Extract part of speech
        pos = self.extract_part_of_speech(ido_section)
        if pos:
            self.stats['entries_with_pos'] += 1
        
        # Extract translations
        translations = self.extract_translations(ido_section)
        if not translations:
            self.stats['skipped_no_translations'] += 1
            return None
        
        self.stats['valid_entries_found'] += 1
        
        # Check if we have multiple meanings
        if len(translations) > 1:
            self.stats['entries_with_multiple_meanings'] += 1
        
        return {
            'ido_word': title,
            'esperanto_translations': translations,
            'part_of_speech': pos
        }
    
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
                if self.stats['pages_processed'] > 10000:  # Reasonable limit
                    break
        
        finally:
            file_obj.close()
    
    def download_dump(self, force: bool = False) -> None:
        """Download the dump file if it doesn't exist or force is True."""
        if os.path.exists(self.dump_file) and not force:
            print(f"Dump file already exists: {self.dump_file}")
            return
        
        print(f"Downloading dump from {DUMP_URL}...")
        print("This may take several minutes...")
        
        try:
            urllib.request.urlretrieve(DUMP_URL, self.dump_file)
            print(f"Download complete: {self.dump_file}")
        except Exception as e:
            print(f"Error downloading dump: {e}")
            raise
    
    def extract_dictionary(self, limit: Optional[int] = None, output_file: str = 'ido_esperanto_v2.json') -> None:
        """Extract Ido-Esperanto dictionary from dump."""
        print("Starting improved Ido-Esperanto dictionary extraction v2...")
        
        entries = []
        processed = 0
        
        try:
            for title, wikitext in self.stream_pages_from_dump():
                if limit and processed >= limit:
                    break
                
                entry = self.extract_from_wikitext(title, wikitext)
                if entry:
                    entries.append(entry)
                    translations_str = ', '.join(entry['esperanto_translations'][:2])
                    pos_info = f" ({entry['part_of_speech']})" if entry['part_of_speech'] else ""
                    print(f"✓ Found: {entry['ido_word']}{pos_info} -> [{translations_str}]")
                
                processed += 1
            
        except KeyboardInterrupt:
            print("\nExtraction interrupted by user.")
        except Exception as e:
            print(f"Error during extraction: {e}")
            raise
        
        # Create result
        result = {
            'metadata': {
                'extraction_date': datetime.now().isoformat(),
                'total_words': len(entries),
                'script_version': 'v2.0',
                'stats': self.stats.copy()
            },
            'words': entries
        }
        
        # Save to file
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        print(f"\nExtraction complete!")
        print(f"Total pages processed: {self.stats['pages_processed']}")
        print(f"Pages with Ido sections: {self.stats['pages_with_ido_section']}")
        print(f"Valid entries found: {self.stats['valid_entries_found']}")
        print(f"Entries with part of speech: {self.stats['entries_with_pos']}")
        print(f"Entries with multiple meanings: {self.stats['entries_with_multiple_meanings']}")
        print(f"Skipped by category: {self.stats['skipped_by_category']}")
        print(f"Skipped by title: {self.stats['skipped_by_title']}")
        print(f"Skipped no translations: {self.stats['skipped_no_translations']}")
        print(f"Results saved to: {output_file}")


def main():
    parser = argparse.ArgumentParser(description='Improved Ido-Esperanto dictionary extractor v2')
    parser.add_argument('--dump', default=DUMP_FILE, help='Path to dump file')
    parser.add_argument('--download', action='store_true', help='Download dump file')
    parser.add_argument('--force-download', action='store_true', help='Force re-download of dump file')
    parser.add_argument('--output', '-o', default='ido_esperanto_v2.json', help='Output JSON file')
    parser.add_argument('--limit', type=int, help='Limit number of pages to process (for testing)')
    
    args = parser.parse_args()
    
    extractor = ImprovedDumpParserV2(args.dump)
    
    try:
        if args.download or args.force_download:
            extractor.download_dump(force=args.force_download)
        
        extractor.extract_dictionary(limit=args.limit, output_file=args.output)
    
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
