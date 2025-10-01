#!/usr/bin/env python3
"""
Ido-Esperanto Dictionary Extractor

This script downloads all Ido words with Esperanto translations from io.wiktionary.org
and saves them in a structured JSON format.

Usage:
    python3 ido_esperanto_extractor.py [--output output.json] [--limit N]

Requirements:
    pip install requests mwparserfromhell
"""

import json
import re
import sys
import time
import argparse
from datetime import datetime
from typing import Dict, List, Optional, Set
from urllib.parse import quote

import requests
try:
    import mwparserfromhell as mwp
    HAVE_MWP = True
except Exception:
    mwp = None
    HAVE_MWP = False
from html.parser import HTMLParser


class _SimpleHtmlListParser(HTMLParser):
    """Small HTML parser to extract text content from list items (<li>)."""
    def __init__(self):
        super().__init__()
        self.in_li = False
        self.current = []
        self.items = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == 'li':
            self.in_li = True
            self.current = []

    def handle_endtag(self, tag):
        if tag.lower() == 'li' and self.in_li:
            self.items.append(''.join(self.current).strip())
            self.in_li = False
            self.current = []

    def handle_data(self, data):
        if self.in_li:
            self.current.append(data)



class IdoEsperantoExtractor:
    def __init__(self, base_url: str = "https://io.wiktionary.org/w/api.php"):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'IdoEsperantoExtractor/1.0 (https://github.com/user/repo)'
        })
        
    def get_all_pages(self, limit: Optional[int] = None) -> List[str]:
        """Get all page titles from io.wiktionary.org"""
        print("Fetching all page titles from io.wiktionary.org...")
        
        pages = []
        apcontinue = None
        count = 0
        
        while True:
            params = {
                'action': 'query',
                'list': 'allpages',
                'aplimit': 500,
                'format': 'json',
                'apnamespace': 0  # Main namespace only
            }
            
            if apcontinue:
                params['apcontinue'] = apcontinue
                
            try:
                response = self.session.get(self.base_url, params=params)
                response.raise_for_status()
                data = response.json()
                
                if 'query' not in data or 'allpages' not in data['query']:
                    break
                    
                batch_pages = [page['title'] for page in data['query']['allpages']]
                pages.extend(batch_pages)
                count += len(batch_pages)
                
                print(f"Fetched {count} page titles...")
                
                if limit and count >= limit:
                    pages = pages[:limit]
                    break
                    
                if 'continue' not in data:
                    break
                    
                apcontinue = data['continue']['apcontinue']
                time.sleep(0.1)  # Be respectful to the server
                
            except requests.RequestException as e:
                print(f"Error fetching pages: {e}")
                break
                
        print(f"Total pages found: {len(pages)}")
        return pages
    
    def get_page_content(self, title: str) -> Optional[str]:
        """Get the wikitext content of a page"""
        params = {
            'action': 'query',
            'titles': title,
            'prop': 'revisions',
            'rvprop': 'content',
            'format': 'json'
        }
        
        try:
            response = self.session.get(self.base_url, params=params)
            response.raise_for_status()
            data = response.json()
            
            pages = data['query']['pages']
            page_id = next(iter(pages))
            
            if page_id == '-1':  # Page doesn't exist
                return None
                
            revisions = pages[page_id].get('revisions', [])
            if not revisions:
                return None
                
            return revisions[0].get('*', '')
            
        except requests.RequestException as e:
            print(f"Error fetching content for '{title}': {e}")
            return None

    def get_ido_section(self, title: str) -> Optional[str]:
        """Fetch only the Ido section wikitext for a page using the MediaWiki API.

        This first asks the API for the page sections (action=parse&prop=sections) to
        determine the section index for the Ido language section, then requests the
        wikitext for that particular section via revisions?rvsection to avoid downloading
        the entire page when possible.
        """
        # First ask for sections using action=parse to find the index of the Ido section
        params = {
            'action': 'parse',
            'page': title,
            'prop': 'sections',
            'format': 'json'
        }

        try:
            resp = self.session.get(self.base_url, params=params)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException:
            return None

        sections = data.get('parse', {}).get('sections', [])
        ido_index = None
        for sec in sections:
            sec_line = sec.get('line', '')
            if re.search(r'\bIdo\b', sec_line, re.IGNORECASE):
                ido_index = sec.get('index')
                break

        if not ido_index:
            return None

        # If mwparserfromhell is available, try to fetch raw wikitext for the section
        if HAVE_MWP:
            params = {
                'action': 'query',
                'titles': title,
                'prop': 'revisions',
                'rvprop': 'content',
                'rvsection': ido_index,
                'format': 'json'
            }

            try:
                resp = self.session.get(self.base_url, params=params)
                resp.raise_for_status()
                data = resp.json()
                pages = data.get('query', {}).get('pages', {})
                if not pages:
                    return None
                page_id = next(iter(pages))
                if page_id == '-1':
                    return None
                revisions = pages[page_id].get('revisions', [])
                if not revisions:
                    return None
                # Support both legacy '*' and slots.main['*'] patterns
                rev = revisions[0]
                if 'slots' in rev and 'main' in rev['slots']:
                    return rev['slots']['main'].get('*', '')
                return rev.get('*', '')
            except requests.RequestException:
                return None

        # If mwparserfromhell is not available, ask the API to return rendered HTML for the section
        params = {
            'action': 'parse',
            'page': title,
            'section': ido_index,
            'prop': 'text',
            'format': 'json'
        }

        try:
            resp = self.session.get(self.base_url, params=params)
            resp.raise_for_status()
            data = resp.json()
            return data.get('parse', {}).get('text', {}).get('*', None)
        except requests.RequestException:
            return None
    
    def parse_ido_entry(self, title: str, content: str) -> Optional[Dict]:
        """Parse wikitext content to extract Ido word with Esperanto translation"""
        # Prefer fetching only the Ido section via API (smaller payload)
        ido_section_wikitext = None
        try:
            ido_section_wikitext = self.get_ido_section(title)
        except Exception:
            ido_section_wikitext = None

        # Fall back to whole page content parse if section fetch failed
        content_to_parse = ido_section_wikitext if ido_section_wikitext else content

        if not content_to_parse:
            return None

        try:
            wikicode = mwp.parse(content_to_parse)
        except Exception as e:
            print(f"Error parsing wikitext for '{title}': {e}")
            return None

        # Extract Esperanto translations using mwparserfromhell
        esperanto_translations = self.extract_esperanto_translations(wikicode)
        if not esperanto_translations:
            return None

        # Extract additional metadata from the parsed section
        part_of_speech = self.extract_part_of_speech(wikicode)
        definitions = self.extract_definitions(wikicode)
        etymology = self.extract_etymology(wikicode)
        examples = self.extract_examples(wikicode)

        return {
            'ido_word': title,
            'esperanto_translations': esperanto_translations,
            'part_of_speech': part_of_speech,
            'definitions': definitions,
            'etymology': etymology,
            'examples': examples,
            'source_url': f'https://io.wiktionary.org/wiki/{quote(title)}',
            'raw_content': str(content_to_parse)[:500] + '...' if len(str(content_to_parse)) > 500 else str(content_to_parse)
        }
    
    def extract_esperanto_translations(self, text: str) -> List[str]:
        """Extract Esperanto translations from wikitext"""
        translations = []
        
        # Look for translation sections
        translation_patterns = [
            r'\*\s*(?:Esperanto|esperanto|eo):\s*([^\n\*]+)',
            r'\|\s*(?:Esperanto|esperanto|eo)\s*=\s*([^\n\|]+)',
            r'{{t\+?\|eo\|([^}]+)}}',
            r'{{l\|eo\|([^}]+)}}'
        ]
        
        for pattern in translation_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                # Clean up the translation
                translation = re.sub(r'{{[^}]*}}', '', match)  # Remove templates
                translation = re.sub(r'\[\[([^\]|]*)\|?[^\]]*\]\]', r'\1', translation)  # Remove links
                translation = translation.strip(' ,;')
                if translation:
                    translations.append(translation)
        
        return list(set(translations))  # Remove duplicates
        # If mwparserfromhell isn't available and we received HTML, extract from HTML
        if not HAVE_MWP and isinstance(wikicode, str) and wikicode.strip().lower().startswith('<'):
            parser = _SimpleHtmlListParser()
            parser.feed(wikicode)
            translations = set()
            for item in parser.items:
                m = re.match(r'^(?:\s*(?:Esperanto|esperanto|eo)[:\-\s]+)(.+)$', item)
                if m:
                    translations.add(self._clean_extracted_text(m.group(1)))
                else:
                    # fallback: include items that contain 'eo' markers
                    if 'eo' in item.lower() or 'esperanto' in item.lower():
                        translations.add(self._clean_extracted_text(item))
            cleaned = [t for t in translations if re.search(r'[A-Za-z\p{L}]', t)]
            return list(dict.fromkeys(cleaned))

        if isinstance(wikicode, str):
            try:
                wikicode = mwp.parse(wikicode)
            except Exception:
                return []
    
    def extract_part_of_speech(self, text: str) -> Optional[str]:
        """Extract part of speech from wikitext"""
        pos_patterns = [
            r'===\s*(Noun|Verb|Adjective|Adverb|Pronoun|Preposition|Conjunction|Interjection)\s*===',
            r'===\s*(Substantivo|Verbo|Adjektivo|Adverbo)\s*==='
        ]
        
        for pattern in pos_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).lower()
        
        return None
    
    def extract_definitions(self, text: str) -> List[str]:
        """Extract definitions from wikitext"""
        definitions = []
        
        # Look for numbered or bulleted definitions
        def_patterns = [
            r'#\s*([^\n#]+)',
            r'\*\s*([^\n\*]+)'
        ]
        
        for pattern in def_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                # Clean up definition
                definition = re.sub(r'{{[^}]*}}', '', match)
                definition = re.sub(r'\[\[([^\]|]*)\|?[^\]]*\]\]', r'\1', definition)
                definition = definition.strip()
                if definition and not definition.lower().startswith(('esperanto', 'see also')):
                    definitions.append(definition)
        
        return definitions[:3]  # Limit to first 3 definitions
    
    def extract_etymology(self, text: str) -> Optional[str]:
        """Extract etymology information"""
        etymology_match = re.search(r'===\s*Etymology\s*===\s*([^\n=]+)', text, re.IGNORECASE)
        if etymology_match:
            etymology = re.sub(r'{{[^}]*}}', '', etymology_match.group(1))
            etymology = re.sub(r'\[\[([^\]|]*)\|?[^\]]*\]\]', r'\1', etymology)
            return etymology.strip()
        return None
    
    def extract_examples(self, text: str) -> List[Dict[str, str]]:
        """Extract example sentences"""
        examples = []
        
        # Look for example patterns
        example_patterns = [
            r'{{example\|ido\|([^}|]+)\|([^}]+)}}',
            r'{{ux\|io\|([^}|]+)\|([^}]+)}}'
        ]
        
        for pattern in example_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                examples.append({
                    'ido': match[0].strip(),
                    'translation': match[1].strip()
                })
        
        return examples[:2]  # Limit to 2 examples
    
    def extract_all_words(self, limit: Optional[int] = None, output_file: str = 'ido_esperanto_dict.json') -> None:
        """Main extraction function"""
        print("Starting Ido-Esperanto dictionary extraction...")
        
        # Get all pages
        pages = self.get_all_pages(limit)
        
        if not pages:
            print("No pages found!")
            return
        
        extracted_words = []
        processed = 0
        
        for i, title in enumerate(pages):
            if i % 50 == 0:
                print(f"Processing page {i+1}/{len(pages)}: {title}")
            
            # Get page content
            content = self.get_page_content(title)
            if not content:
                continue
            
            # Parse Ido entry
            entry = self.parse_ido_entry(title, content)
            if entry:
                # Skip entries that have no definitions (empty list)
                defs = entry.get('definitions')
                if not defs:
                    # Skip this entity
                    continue
                extracted_words.append(entry)
                processed += 1
                print(f"✓ Found Ido word with Esperanto translation: {title}")
            
            # Be respectful to the server
            time.sleep(0.1)
        
        # Prepare final data structure
        result = {
            'metadata': {
                'extraction_date': datetime.now().isoformat(),
                'source': 'io.wiktionary.org',
                'total_words': len(extracted_words),
                'script_version': '1.0',
                'pages_processed': len(pages)
            },
            'words': extracted_words
        }
        
        # Save to file
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        print(f"\nExtraction complete!")
        print(f"Total pages processed: {len(pages)}")
        print(f"Ido words with Esperanto translations found: {len(extracted_words)}")
        print(f"Results saved to: {output_file}")


def main():
    parser = argparse.ArgumentParser(description='Extract Ido words with Esperanto translations from io.wiktionary.org')
    parser.add_argument('--output', '-o', default='ido_esperanto_dict.json', 
                       help='Output JSON file (default: ido_esperanto_dict.json)')
    parser.add_argument('--limit', '-l', type=int, 
                       help='Limit number of pages to process (for testing)')
    
    args = parser.parse_args()
    
    extractor = IdoEsperantoExtractor()
    
    try:
        extractor.extract_all_words(limit=args.limit, output_file=args.output)
    except KeyboardInterrupt:
        print("\nExtraction interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"Error during extraction: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
