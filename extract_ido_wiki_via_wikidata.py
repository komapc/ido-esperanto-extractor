#!/usr/bin/env python3
"""
Extract vocabulary from Ido Wikipedia using Wikidata to find Esperanto equivalents.

This script:
1. Extracts article titles from Ido Wikipedia dump
2. Queries Wikidata API to find corresponding Wikidata items
3. Gets Esperanto Wikipedia titles from Wikidata
4. Outputs CSV of Ido-Esperanto word pairs

Usage:
    python3 extract_ido_wiki_via_wikidata.py
    python3 extract_ido_wiki_via_wikidata.py --limit 100  # For testing
"""

import argparse
import bz2
import csv
import json
import os
import sys
import time
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Optional, Tuple


# Configuration
DUMP_FILE = 'iowiki-latest-pages-articles.xml.bz2'
OUTPUT_CSV = 'ido_wiki_vocabulary_wikidata.csv'
DICTIONARY_FILE = 'dictionary_merged.json'
WIKIDATA_API = 'https://www.wikidata.org/w/api.php'
CACHE_FILE = 'wikidata_cache.json'

# Rate limiting
REQUESTS_PER_SECOND = 5  # Be nice to Wikidata servers
REQUEST_DELAY = 1.0 / REQUESTS_PER_SECOND


class WikidataVocabularyExtractor:
    """Extract vocabulary using Wikidata as the bridge between Ido and Esperanto Wikipedia."""
    
    def __init__(self, dictionary_file: str = DICTIONARY_FILE):
        """Initialize extractor."""
        self.dictionary_file = dictionary_file
        self.existing_dict = self.load_dictionary()
        self.wikidata_cache = self.load_cache()
        self.last_request_time = 0
        
        self.stats = {
            'pages_processed': 0,
            'articles_found': 0,
            'valid_word_titles': 0,
            'wikidata_queries': 0,
            'wikidata_found': 0,
            'esperanto_found': 0,
            'cache_hits': 0,
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
    
    def load_cache(self) -> Dict:
        """Load Wikidata query cache."""
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                cache = json.load(f)
                print(f"✓ Loaded Wikidata cache: {len(cache)} entries")
                return cache
        except FileNotFoundError:
            print("✓ Starting fresh Wikidata cache")
            return {}
    
    def save_cache(self):
        """Save Wikidata query cache."""
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.wikidata_cache, f, ensure_ascii=False, indent=2)
        print(f"✓ Saved Wikidata cache: {len(self.wikidata_cache)} entries")
    
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
        
        if '(' in title or ')' in title:
            return False
        
        if any(char in title for char in ['/', '\\', '&', '+', '=', '[', ']', '{', '}', '|', '<', '>']):
            return False
        
        words = title.split()
        if len(words) == 1 or len(words) == 2:
            return True
        
        return False
    
    def rate_limit(self):
        """Ensure we don't exceed rate limits."""
        elapsed = time.time() - self.last_request_time
        if elapsed < REQUEST_DELAY:
            time.sleep(REQUEST_DELAY - elapsed)
        self.last_request_time = time.time()
    
    def query_wikidata(self, ido_title: str) -> Optional[str]:
        """
        Query Wikidata to find Esperanto Wikipedia title for an Ido Wikipedia article.
        
        Returns: Esperanto Wikipedia title or None
        """
        # Check cache first
        if ido_title in self.wikidata_cache:
            self.stats['cache_hits'] += 1
            return self.wikidata_cache[ido_title]
        
        # Rate limit
        self.rate_limit()
        
        self.stats['wikidata_queries'] += 1
        
        try:
            # Step 1: Get Wikidata ID from Ido Wikipedia title
            params = {
                'action': 'wbgetentities',
                'sites': 'iowiki',
                'titles': ido_title,
                'props': 'sitelinks',
                'format': 'json'
            }
            
            url = WIKIDATA_API + '?' + urllib.parse.urlencode(params)
            
            # Create request with proper User-Agent
            req = urllib.request.Request(
                url,
                headers={
                    'User-Agent': 'IdoEsperantoExtractor/1.0 (https://github.com/komapc/apertium-ido-epo) Python/urllib'
                }
            )
            
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))
            
            # Extract Wikidata entity
            entities = data.get('entities', {})
            
            if not entities or '-1' in entities:
                # No Wikidata item found
                self.wikidata_cache[ido_title] = None
                return None
            
            # Get the first entity (should be only one)
            entity = list(entities.values())[0]
            
            self.stats['wikidata_found'] += 1
            
            # Step 2: Get Esperanto Wikipedia title from sitelinks
            sitelinks = entity.get('sitelinks', {})
            
            if 'eowiki' in sitelinks:
                esperanto_title = sitelinks['eowiki'].get('title')
                self.stats['esperanto_found'] += 1
                
                # Cache the result
                self.wikidata_cache[ido_title] = esperanto_title
                
                return esperanto_title
            else:
                # Has Wikidata entry but no Esperanto article
                self.wikidata_cache[ido_title] = None
                return None
        
        except Exception as e:
            print(f"\n⚠ Error querying Wikidata for '{ido_title}': {e}")
            # Cache as None to avoid re-querying failed entries
            self.wikidata_cache[ido_title] = None
            return None
    
    def stream_pages(self, dump_file: str, limit: Optional[int] = None):
        """Stream article titles from Wikipedia dump."""
        if not os.path.exists(dump_file):
            raise FileNotFoundError(f"Dump file not found: {dump_file}")
        
        print(f"Processing dump file: {dump_file}")
        
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
                    
                    try:
                        page_elem = ET.fromstring(page_xml)
                        
                        title_elem = page_elem.find('title')
                        title = title_elem.text if title_elem is not None else None
                        
                        ns_elem = page_elem.find('ns')
                        namespace = int(ns_elem.text) if ns_elem is not None else 0
                        
                        redirect_elem = page_elem.find('redirect')
                        is_redirect = redirect_elem is not None
                        
                        if title and namespace == 0 and not is_redirect:
                            yield title
                            pages_yielded += 1
                            
                            if limit and pages_yielded >= limit:
                                break
                    
                    except ET.ParseError:
                        pass
                    
                    in_page = False
                    page_buffer = []
                    
                    self.stats['pages_processed'] += 1
                    if self.stats['pages_processed'] % 1000 == 0:
                        print(f"\rProcessed {self.stats['pages_processed']} pages, "
                              f"found {self.stats['esperanto_found']} with Esperanto equivalents "
                              f"(queried: {self.stats['wikidata_queries']}, cached: {self.stats['cache_hits']})...", 
                              end='')
                
                elif in_page:
                    page_buffer.append(line)
        
        finally:
            file_obj.close()
    
    def extract_vocabulary(self, dump_file: str = DUMP_FILE, limit: Optional[int] = None):
        """Extract vocabulary from dump using Wikidata."""
        print("\n" + "="*70)
        print("IDO WIKIPEDIA VOCABULARY EXTRACTION VIA WIKIDATA")
        print("="*70 + "\n")
        
        print("Note: This will query Wikidata API. Progress will be saved to cache.")
        print(f"Rate limit: {REQUESTS_PER_SECOND} requests/second\n")
        
        try:
            for title in self.stream_pages(dump_file, limit):
                self.stats['articles_found'] += 1
                
                # Filter for valid word titles
                if not self.is_valid_word_title(title):
                    continue
                
                self.stats['valid_word_titles'] += 1
                
                # Query Wikidata for Esperanto equivalent
                esperanto_title = self.query_wikidata(title)
                
                if not esperanto_title:
                    continue
                
                # Check if in dictionary
                in_dict = self.is_in_dictionary(title)
                
                if in_dict:
                    self.stats['in_dictionary'] += 1
                else:
                    self.stats['new_words'] += 1
                
                # Add to vocabulary
                self.vocabulary.append({
                    'ido_word': title,
                    'esperanto_word': esperanto_title,
                    'in_current_dict': in_dict
                })
                
                # Print first few entries and periodically after that
                if len(self.vocabulary) <= 20 or len(self.vocabulary) % 50 == 0:
                    status = "✓ IN DICT" if in_dict else "✗ NEW"
                    print(f"\n  {status}: {title:30} → {esperanto_title}")
                
                # Save cache periodically
                if self.stats['wikidata_queries'] % 100 == 0:
                    self.save_cache()
        
        except KeyboardInterrupt:
            print("\n\n⚠ Interrupted by user. Saving progress...")
            self.save_cache()
            raise
        
        print(f"\n\nExtraction complete!")
        
        # Final cache save
        self.save_cache()
    
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
        print(f"Valid word titles:            {self.stats['valid_word_titles']:6,}")
        print(f"\nWikidata API queries:         {self.stats['wikidata_queries']:6,}")
        print(f"  - Cache hits:               {self.stats['cache_hits']:6,}")
        print(f"  - Found in Wikidata:        {self.stats['wikidata_found']:6,}")
        print(f"  - Has Esperanto article:    {self.stats['esperanto_found']:6,}")
        print(f"\nVocabulary extracted:         {len(self.vocabulary):6,}")
        print(f"  - Already in dictionary:    {self.stats['in_dictionary']:6,}")
        print(f"  - NEW words:                {self.stats['new_words']:6,}")
        print("="*70)


def main():
    """Main execution."""
    parser = argparse.ArgumentParser(
        description='Extract vocabulary from Ido Wikipedia via Wikidata'
    )
    parser.add_argument('--limit', type=int,
                       help='Limit number of articles to process (for testing)')
    parser.add_argument('--output', '-o', default=OUTPUT_CSV,
                       help=f'Output CSV file (default: {OUTPUT_CSV})')
    parser.add_argument('--dictionary', default=DICTIONARY_FILE,
                       help=f'Dictionary file for comparison (default: {DICTIONARY_FILE})')
    parser.add_argument('--clear-cache', action='store_true',
                       help='Clear Wikidata cache and start fresh')
    
    args = parser.parse_args()
    
    # Clear cache if requested
    if args.clear_cache and os.path.exists(CACHE_FILE):
        os.remove(CACHE_FILE)
        print(f"✓ Cleared cache: {CACHE_FILE}\n")
    
    try:
        # Initialize extractor
        extractor = WikidataVocabularyExtractor(dictionary_file=args.dictionary)
        
        # Check if dump exists
        if not os.path.exists(DUMP_FILE):
            print(f"✗ Error: Dump file not found: {DUMP_FILE}")
            print("  Please run the previous script with --download first")
            return 1
        
        # Extract vocabulary
        extractor.extract_vocabulary(DUMP_FILE, limit=args.limit)
        
        # Save results
        extractor.save_csv(args.output)
        
        # Print statistics
        extractor.print_stats()
        
        print(f"\n✅ Complete! Review {args.output} for vocabulary candidates.")
        print(f"Cache saved to {CACHE_FILE} for future runs.")
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

