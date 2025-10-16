#!/usr/bin/env python3
"""
Extract vocabulary from Ido Wikipedia using langlinks SQL dump.

This script:
1. Downloads Ido Wikipedia langlinks SQL dump (~1-5 MB)
2. Parses it to extract Ido->Esperanto interlanguage links
3. Matches against article titles from the main dump
4. Outputs CSV of vocabulary

This is MUCH faster than querying Wikidata API!

Usage:
    python3 extract_ido_wiki_via_langlinks.py
"""

import argparse
import bz2
import csv
import gzip
import json
import os
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Dict, Set, Optional


# Configuration
DUMP_FILE = 'iowiki-latest-pages-articles.xml.bz2'
LANGLINKS_URL = 'https://dumps.wikimedia.org/iowiki/latest/iowiki-latest-langlinks.sql.gz'
LANGLINKS_FILE = 'iowiki-latest-langlinks.sql.gz'
OUTPUT_CSV = 'ido_wiki_vocabulary_langlinks.csv'
DICTIONARY_FILE = 'dictionary_merged.json'


class LanglinksVocabularyExtractor:
    """Extract vocabulary using Wikipedia langlinks SQL dump."""
    
    def __init__(self, dictionary_file: str = DICTIONARY_FILE):
        """Initialize extractor."""
        self.dictionary_file = dictionary_file
        self.existing_dict = self.load_dictionary()
        self.langlinks = {}  # Maps Ido title -> Esperanto title
        
        self.stats = {
            'pages_processed': 0,
            'articles_found': 0,
            'valid_word_titles': 0,
            'langlinks_total': 0,
            'langlinks_to_esperanto': 0,
            'matched_articles': 0,
            'in_dictionary': 0,
            'new_words': 0,
        }
        self.vocabulary = []
    
    def load_dictionary(self) -> Dict:
        """Load existing merged dictionary."""
        try:
            with open(self.dictionary_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                print(f"✓ Loaded existing dictionary: {len(data.get('words', []))} entries")
                return data
        except FileNotFoundError:
            print(f"⚠ Dictionary file not found: {self.dictionary_file}")
            return {'words': []}
    
    def is_in_dictionary(self, ido_word: str) -> bool:
        """Check if word exists in current dictionary."""
        ido_lower = ido_word.lower().strip()
        for entry in self.existing_dict.get('words', []):
            entry_word = entry.get('ido_word', '').lower().strip()
            if entry_word == ido_lower:
                return True
        return False
    
    def is_valid_word_title(self, title: str) -> bool:
        """Check if title is a valid word (single word or compound)."""
        title = title.strip()
        
        if not title or len(title) < 2:
            return False
        
        # Skip parenthetical disambiguation
        if '(' in title or ')' in title:
            return False
        
        # Skip special characters
        if any(char in title for char in ['/', '\\', '&', '+', '=', '[', ']', '{', '}', '|', '<', '>']):
            return False
        
        # Allow single words or compounds (with space or hyphen)
        words = title.split()
        if len(words) == 1 or len(words) == 2:
            return True
        
        return False
    
    def download_langlinks(self, force: bool = False):
        """Download langlinks SQL dump."""
        if os.path.exists(LANGLINKS_FILE) and not force:
            file_size_mb = os.path.getsize(LANGLINKS_FILE) / (1024 * 1024)
            print(f"✓ Langlinks file already exists: {LANGLINKS_FILE} ({file_size_mb:.1f} MB)")
            return
        
        print(f"Downloading langlinks dump from {LANGLINKS_URL}...")
        
        try:
            def progress_callback(block_num, block_size, total_size):
                downloaded = block_num * block_size
                percent = min(100, downloaded * 100 / total_size) if total_size > 0 else 0
                mb_downloaded = downloaded / (1024 * 1024)
                mb_total = total_size / (1024 * 1024)
                print(f"\rDownloading: {percent:.1f}% ({mb_downloaded:.1f}/{mb_total:.1f} MB)", end='')
            
            urllib.request.urlretrieve(LANGLINKS_URL, LANGLINKS_FILE, progress_callback)
            print(f"\n✓ Download complete: {LANGLINKS_FILE}")
        except Exception as e:
            print(f"\n✗ Error downloading langlinks: {e}")
            raise
    
    def parse_langlinks(self):
        """Parse langlinks SQL dump to extract Ido->Esperanto links."""
        print(f"\nParsing langlinks from {LANGLINKS_FILE}...")
        
        with gzip.open(LANGLINKS_FILE, 'rt', encoding='utf-8', errors='ignore') as f:
            # Pattern to match INSERT statements
            # Format: INSERT INTO `langlinks` VALUES (page_id,'lang_code','target_title'),...;
            insert_pattern = re.compile(r"INSERT INTO `langlinks` VALUES (.+);")
            # Pattern to match individual entries
            # Format: (123,'eo','Article Title')
            entry_pattern = re.compile(r"\((\d+),'([^']+)','([^']+)'\)")
            
            for line in f:
                line = line.strip()
                
                # Skip non-INSERT lines
                if not line.startswith('INSERT INTO'):
                    continue
                
                # Extract the VALUES portion
                match = insert_pattern.search(line)
                if not match:
                    continue
                
                values_str = match.group(1)
                
                # Parse all entries in this INSERT statement
                for entry_match in entry_pattern.finditer(values_str):
                    page_id = entry_match.group(1)
                    lang_code = entry_match.group(2)
                    target_title = entry_match.group(3)
                    
                    self.stats['langlinks_total'] += 1
                    
                    # Only keep Esperanto links
                    if lang_code == 'eo':
                        # Decode SQL escaping
                        target_title = target_title.replace("\\'", "'")
                        target_title = target_title.replace("\\\\", "\\")
                        
                        # Store with page_id as key (we'll map to title later)
                        self.langlinks[page_id] = target_title
                        self.stats['langlinks_to_esperanto'] += 1
                    
                    if self.stats['langlinks_total'] % 10000 == 0:
                        print(f"\r  Parsed {self.stats['langlinks_total']:,} langlinks, "
                              f"found {self.stats['langlinks_to_esperanto']:,} to Esperanto...", end='')
        
        print(f"\n✓ Parsed {self.stats['langlinks_to_esperanto']:,} Ido->Esperanto links")
    
    def extract_page_id_mapping(self):
        """
        Extract page_id -> title mapping from the main Wikipedia dump.
        We need this because langlinks uses page_id, not titles.
        """
        print(f"\nExtracting page IDs from {DUMP_FILE}...")
        
        if not os.path.exists(DUMP_FILE):
            raise FileNotFoundError(f"Wikipedia dump not found: {DUMP_FILE}")
        
        page_id_to_title = {}
        
        file_obj = bz2.open(DUMP_FILE, 'rt', encoding='utf-8', errors='ignore')
        
        try:
            page_buffer = []
            in_page = False
            
            for line in file_obj:
                line = line.strip()
                
                if '<page>' in line:
                    in_page = True
                    page_buffer = [line]
                elif '</page>' in line and in_page:
                    page_buffer.append(line)
                    page_xml = '\n'.join(page_buffer)
                    
                    try:
                        page_elem = ET.fromstring(page_xml)
                        
                        # Extract page ID
                        id_elem = page_elem.find('id')
                        page_id = id_elem.text if id_elem is not None else None
                        
                        # Extract title
                        title_elem = page_elem.find('title')
                        title = title_elem.text if title_elem is not None else None
                        
                        # Extract namespace
                        ns_elem = page_elem.find('ns')
                        namespace = int(ns_elem.text) if ns_elem is not None else 0
                        
                        # Check for redirect
                        redirect_elem = page_elem.find('redirect')
                        is_redirect = redirect_elem is not None
                        
                        # Only keep main namespace, non-redirect pages
                        if page_id and title and namespace == 0 and not is_redirect:
                            page_id_to_title[page_id] = title
                            self.stats['articles_found'] += 1
                    
                    except ET.ParseError:
                        pass
                    
                    in_page = False
                    page_buffer = []
                    
                    self.stats['pages_processed'] += 1
                    if self.stats['pages_processed'] % 1000 == 0:
                        print(f"\r  Processed {self.stats['pages_processed']:,} pages, "
                              f"found {self.stats['articles_found']:,} articles...", end='')
                
                elif in_page:
                    page_buffer.append(line)
        
        finally:
            file_obj.close()
        
        print(f"\n✓ Extracted {len(page_id_to_title):,} page ID mappings")
        return page_id_to_title
    
    def build_vocabulary(self, page_id_to_title: Dict[str, str]):
        """Build vocabulary by matching langlinks with article titles."""
        print(f"\nBuilding vocabulary...")
        
        for page_id, esperanto_title in self.langlinks.items():
            # Get Ido title from page_id
            ido_title = page_id_to_title.get(page_id)
            
            if not ido_title:
                continue
            
            # Check if valid word title
            if not self.is_valid_word_title(ido_title):
                continue
            
            self.stats['valid_word_titles'] += 1
            self.stats['matched_articles'] += 1
            
            # Check if in dictionary
            in_dict = self.is_in_dictionary(ido_title)
            
            if in_dict:
                self.stats['in_dictionary'] += 1
            else:
                self.stats['new_words'] += 1
            
            # Add to vocabulary
            self.vocabulary.append({
                'ido_word': ido_title,
                'esperanto_word': esperanto_title,
                'in_current_dict': in_dict
            })
            
            # Print first few and periodic updates
            if len(self.vocabulary) <= 20 or len(self.vocabulary) % 100 == 0:
                status = "✓ IN DICT" if in_dict else "✗ NEW"
                print(f"  {status}: {ido_title:30} → {esperanto_title}")
        
        print(f"\n✓ Built vocabulary with {len(self.vocabulary):,} entries")
    
    def save_csv(self, output_file: str = OUTPUT_CSV):
        """Save vocabulary to CSV file."""
        print(f"\nSaving to {output_file}...")
        
        # Sort by: new words first, then alphabetically
        self.vocabulary.sort(key=lambda x: (x['in_current_dict'], x['ido_word'].lower()))
        
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['ido_word', 'esperanto_word', 'in_current_dict'])
            writer.writeheader()
            writer.writerows(self.vocabulary)
        
        print(f"✓ Saved {len(self.vocabulary)} entries to {output_file}")
    
    def print_stats(self):
        """Print extraction statistics."""
        print("\n" + "="*70)
        print("STATISTICS")
        print("="*70)
        print(f"Pages processed:              {self.stats['pages_processed']:6,}")
        print(f"Articles found (ns=0):        {self.stats['articles_found']:6,}")
        print(f"\nLanglinks parsed:             {self.stats['langlinks_total']:6,}")
        print(f"  - To Esperanto:             {self.stats['langlinks_to_esperanto']:6,}")
        print(f"  - Matched to articles:      {self.stats['matched_articles']:6,}")
        print(f"  - Valid word titles:        {self.stats['valid_word_titles']:6,}")
        print(f"\nVocabulary extracted:         {len(self.vocabulary):6,}")
        print(f"  - Already in dictionary:    {self.stats['in_dictionary']:6,}")
        print(f"  - NEW words:                {self.stats['new_words']:6,}")
        print("="*70)


def main():
    """Main execution."""
    parser = argparse.ArgumentParser(
        description='Extract vocabulary from Ido Wikipedia via langlinks SQL dump'
    )
    parser.add_argument('--download', action='store_true',
                       help='Force download of langlinks dump')
    parser.add_argument('--output', '-o', default=OUTPUT_CSV,
                       help=f'Output CSV file (default: {OUTPUT_CSV})')
    parser.add_argument('--dictionary', default=DICTIONARY_FILE,
                       help=f'Dictionary file for comparison (default: {DICTIONARY_FILE})')
    
    args = parser.parse_args()
    
    print("="*70)
    print("IDO WIKIPEDIA VOCABULARY EXTRACTION VIA LANGLINKS")
    print("="*70)
    print()
    
    try:
        # Initialize extractor
        extractor = LanglinksVocabularyExtractor(dictionary_file=args.dictionary)
        
        # Download langlinks dump
        extractor.download_langlinks(force=args.download)
        
        # Parse langlinks
        extractor.parse_langlinks()
        
        # Extract page ID mapping
        page_id_to_title = extractor.extract_page_id_mapping()
        
        # Build vocabulary
        extractor.build_vocabulary(page_id_to_title)
        
        # Save results
        extractor.save_csv(args.output)
        
        # Print statistics
        extractor.print_stats()
        
        print(f"\n✅ Complete! Review {args.output} for vocabulary candidates.")
        return 0
    
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())

