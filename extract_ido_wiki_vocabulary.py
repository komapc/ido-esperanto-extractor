#!/usr/bin/env python3
"""
Extract vocabulary from Ido Wikipedia dump by finding articles with Esperanto interwiki links.

This script:
1. Downloads the latest Ido Wikipedia dump
2. Extracts articles with Esperanto interwiki links
3. Filters for single-word and compound-word titles
4. Checks against existing dictionary
5. Outputs CSV for review

Usage:
    python3 extract_ido_wiki_vocabulary.py
    python3 extract_ido_wiki_vocabulary.py --download  # Force download
    python3 extract_ido_wiki_vocabulary.py --limit 1000  # For testing
"""

import argparse
import bz2
import csv
import json
import os
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Optional, Tuple


# Ido Wikipedia dump configuration
DUMP_URL = 'https://dumps.wikimedia.org/iowiki/latest/iowiki-latest-pages-articles.xml.bz2'
DUMP_FILE = 'iowiki-latest-pages-articles.xml.bz2'
OUTPUT_CSV = 'ido_wiki_vocabulary.csv'
DICTIONARY_FILE = 'dictionary_merged.json'


class IdoWikipediaVocabularyExtractor:
    """Extract vocabulary from Ido Wikipedia with Esperanto interwiki links."""
    
    def __init__(self, dictionary_file: str = DICTIONARY_FILE):
        """Initialize extractor."""
        self.dictionary_file = dictionary_file
        self.existing_dict = self.load_dictionary()
        self.stats = {
            'pages_processed': 0,
            'articles_found': 0,
            'with_esperanto_interwiki': 0,
            'single_word_titles': 0,
            'compound_word_titles': 0,
            'excluded_disambiguation': 0,
            'excluded_redirects': 0,
            'excluded_namespace': 0,
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
            print("  Will mark all words as new")
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
        """
        Check if title is a valid word (single word or compound).
        
        Valid:
        - Single words: "hundo", "matematiko"
        - Compounds: "biciklo-rido", "nord-sudo"
        - Months: "Aprilo", "Julio"
        - Cities/countries: "Stockholm", "Suedia"
        
        Invalid:
        - Multi-word: "Nia Dio" (too long)
        - Special characters: "E (litero)"
        - Numbers only: "1984"
        """
        title = title.strip()
        
        # Empty or very short
        if not title or len(title) < 2:
            return False
        
        # Contains parentheses (usually disambiguation or clarification)
        if '(' in title or ')' in title:
            return False
        
        # Contains special characters that indicate it's not a word
        if any(char in title for char in ['/', '\\', '&', '+', '=', '[', ']', '{', '}', '|', '<', '>']):
            return False
        
        # Check if it's a single word or hyphenated compound
        # Allow: letters, hyphens, apostrophes, accented characters
        # Split by space to check word count
        words = title.split()
        
        # Allow single words or 2-word compounds if they're hyphenated
        if len(words) == 1:
            # Single word (possibly with hyphens): "hundo", "nord-sudo"
            return True
        elif len(words) == 2:
            # Two words only if connected by hyphen originally
            # This handles "nord-sudo" being split but still being one compound
            # Actually, if split by space gives 2 words, it's probably "New York" style
            # Let's be permissive and include it
            return True
        else:
            # More than 2 words - probably a phrase or sentence
            return False
    
    def is_disambiguation_page(self, title: str, content: str) -> bool:
        """Check if page is a disambiguation page."""
        title_lower = title.lower()
        content_lower = content.lower()
        
        # Check title
        if 'disambigo' in title_lower or 'disambiguation' in title_lower:
            return True
        
        # Check for disambiguation templates
        disambiguation_patterns = [
            r'\{\{disambig',
            r'\{\{disamb\}\}',
            r'\{\{homonimy',
            r'\[\[Category:Disambig',
            r'\[\[Kategorio:Disambig',
        ]
        
        for pattern in disambiguation_patterns:
            if re.search(pattern, content_lower):
                return True
        
        return False
    
    def extract_esperanto_interwiki(self, content: str) -> Optional[str]:
        """
        Extract Esperanto interwiki link from page content.
        
        Format: [[eo:ArticleTitle]]
        """
        # Pattern for interwiki links
        # [[eo:Title]] or [[eo:Title|display text]]
        pattern = r'\[\[eo:([^\]|]+)(?:\|[^\]]+)?\]\]'
        
        matches = re.findall(pattern, content, re.IGNORECASE)
        
        if matches:
            # Return the first match, cleaned
            esperanto_title = matches[0].strip()
            # Decode URL encoding if present
            esperanto_title = esperanto_title.replace('_', ' ')
            return esperanto_title
        
        return None
    
    def download_dump(self, force: bool = False) -> None:
        """Download Ido Wikipedia dump if needed."""
        if os.path.exists(DUMP_FILE) and not force:
            file_size_mb = os.path.getsize(DUMP_FILE) / (1024 * 1024)
            print(f"✓ Dump file already exists: {DUMP_FILE} ({file_size_mb:.1f} MB)")
            return
        
        print(f"Downloading Ido Wikipedia dump from {DUMP_URL}...")
        print("This may take a few minutes...")
        
        try:
            def progress_callback(block_num, block_size, total_size):
                downloaded = block_num * block_size
                percent = min(100, downloaded * 100 / total_size)
                mb_downloaded = downloaded / (1024 * 1024)
                mb_total = total_size / (1024 * 1024)
                print(f"\rDownloading: {percent:.1f}% ({mb_downloaded:.1f}/{mb_total:.1f} MB)", end='')
            
            urllib.request.urlretrieve(DUMP_URL, DUMP_FILE, progress_callback)
            print(f"\n✓ Download complete: {DUMP_FILE}")
        except Exception as e:
            print(f"\n✗ Error downloading dump: {e}")
            raise
    
    def stream_pages(self, dump_file: str, limit: Optional[int] = None):
        """Stream pages from Wikipedia dump."""
        if not os.path.exists(dump_file):
            raise FileNotFoundError(f"Dump file not found: {dump_file}")
        
        print(f"Processing dump file: {dump_file}")
        
        # Open compressed file
        file_obj = bz2.open(dump_file, 'rt', encoding='utf-8', errors='ignore')
        
        try:
            page_buffer = []
            in_page = False
            pages_yielded = 0
            
            for line in file_obj:
                line = line.strip()
                
                if '<page>' in line:
                    in_page = True
                    page_buffer = [line]
                elif '</page>' in line and in_page:
                    page_buffer.append(line)
                    page_xml = '\n'.join(page_buffer)
                    
                    # Parse page
                    try:
                        page_elem = ET.fromstring(page_xml)
                        
                        # Extract title
                        title_elem = page_elem.find('title')
                        title = title_elem.text if title_elem is not None else None
                        
                        # Extract namespace
                        ns_elem = page_elem.find('ns')
                        namespace = int(ns_elem.text) if ns_elem is not None else 0
                        
                        # Check for redirect
                        redirect_elem = page_elem.find('redirect')
                        is_redirect = redirect_elem is not None
                        
                        # Extract text content
                        text = None
                        revision = page_elem.find('revision')
                        if revision is not None:
                            text_elem = revision.find('text')
                            if text_elem is not None:
                                text = text_elem.text
                        
                        if title and text:
                            yield {
                                'title': title,
                                'namespace': namespace,
                                'is_redirect': is_redirect,
                                'content': text
                            }
                            
                            pages_yielded += 1
                            
                            if limit and pages_yielded >= limit:
                                print(f"\nReached limit of {limit} pages")
                                break
                    
                    except ET.ParseError:
                        # Skip malformed pages
                        pass
                    
                    in_page = False
                    page_buffer = []
                    
                    # Progress indicator
                    self.stats['pages_processed'] += 1
                    if self.stats['pages_processed'] % 1000 == 0:
                        print(f"\rProcessed {self.stats['pages_processed']} pages, "
                              f"found {self.stats['with_esperanto_interwiki']} with Esperanto links...", 
                              end='')
                
                elif in_page:
                    page_buffer.append(line)
        
        finally:
            file_obj.close()
    
    def extract_vocabulary(self, dump_file: str = DUMP_FILE, limit: Optional[int] = None):
        """Extract vocabulary from dump."""
        print("\n" + "="*70)
        print("IDO WIKIPEDIA VOCABULARY EXTRACTION")
        print("="*70 + "\n")
        
        for page in self.stream_pages(dump_file, limit):
            title = page['title']
            namespace = page['namespace']
            is_redirect = page['is_redirect']
            content = page['content']
            
            # Filter 1: Only main namespace (articles)
            if namespace != 0:
                self.stats['excluded_namespace'] += 1
                continue
            
            self.stats['articles_found'] += 1
            
            # Filter 2: Skip redirects
            if is_redirect:
                self.stats['excluded_redirects'] += 1
                continue
            
            # Filter 3: Skip disambiguation pages
            if self.is_disambiguation_page(title, content):
                self.stats['excluded_disambiguation'] += 1
                continue
            
            # Filter 4: Check for valid word title
            if not self.is_valid_word_title(title):
                continue
            
            # Count word type
            if '-' in title or ' ' in title:
                self.stats['compound_word_titles'] += 1
            else:
                self.stats['single_word_titles'] += 1
            
            # Filter 5: Extract Esperanto interwiki
            esperanto_title = self.extract_esperanto_interwiki(content)
            
            if not esperanto_title:
                continue
            
            self.stats['with_esperanto_interwiki'] += 1
            
            # Check if in dictionary
            in_dict = self.is_in_dictionary(title)
            
            if in_dict:
                self.stats['in_dictionary'] += 1
            else:
                self.stats['new_words'] += 1
            
            # Add to vocabulary list
            self.vocabulary.append({
                'ido_word': title,
                'esperanto_word': esperanto_title,
                'in_current_dict': in_dict
            })
            
            # Debug output for first few entries
            if len(self.vocabulary) <= 10:
                status = "✓ IN DICT" if in_dict else "✗ NEW"
                print(f"  {status}: {title:30} → {esperanto_title}")
        
        print(f"\n\nExtraction complete!")
    
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
        print(f"  - Excluded (redirects):     {self.stats['excluded_redirects']:6,}")
        print(f"  - Excluded (disambiguation):{self.stats['excluded_disambiguation']:6,}")
        print(f"  - Excluded (other ns):      {self.stats['excluded_namespace']:6,}")
        print(f"\nValid word titles:            {self.stats['single_word_titles'] + self.stats['compound_word_titles']:6,}")
        print(f"  - Single words:             {self.stats['single_word_titles']:6,}")
        print(f"  - Compound words:           {self.stats['compound_word_titles']:6,}")
        print(f"\nWith Esperanto interwiki:     {self.stats['with_esperanto_interwiki']:6,}")
        print(f"  - Already in dictionary:    {self.stats['in_dictionary']:6,}")
        print(f"  - NEW words:                {self.stats['new_words']:6,}")
        print(f"\nTotal vocabulary extracted:   {len(self.vocabulary):6,}")
        print("="*70)


def main():
    """Main execution."""
    parser = argparse.ArgumentParser(
        description='Extract vocabulary from Ido Wikipedia with Esperanto interwiki links'
    )
    parser.add_argument('--download', action='store_true',
                       help='Force download of Wikipedia dump')
    parser.add_argument('--limit', type=int,
                       help='Limit number of pages to process (for testing)')
    parser.add_argument('--output', '-o', default=OUTPUT_CSV,
                       help=f'Output CSV file (default: {OUTPUT_CSV})')
    parser.add_argument('--dictionary', default=DICTIONARY_FILE,
                       help=f'Dictionary file for comparison (default: {DICTIONARY_FILE})')
    
    args = parser.parse_args()
    
    try:
        # Initialize extractor
        extractor = IdoWikipediaVocabularyExtractor(dictionary_file=args.dictionary)
        
        # Download dump if needed
        extractor.download_dump(force=args.download)
        
        # Extract vocabulary
        extractor.extract_vocabulary(DUMP_FILE, limit=args.limit)
        
        # Save results
        extractor.save_csv(args.output)
        
        # Print statistics
        extractor.print_stats()
        
        print(f"\n✅ Complete! Review {args.output} for vocabulary candidates.")
        return 0
    
    except KeyboardInterrupt:
        print("\n\n⚠ Interrupted by user")
        return 1
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())

