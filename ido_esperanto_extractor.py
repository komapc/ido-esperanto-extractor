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

        # If mwparserfromhell is available, parse wikitext and use mwp-based extractors;
        # otherwise treat content_to_parse as rendered HTML and use HTML fallbacks.
        if HAVE_MWP:
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
        else:
            # HTML fallback: when the API returns rendered HTML for the Ido section
            # we should extract translations from that HTML, but definitions are
            # often present only in the full page wikitext. Use both sources:
            # - ido_section_wikitext (HTML) for translations
            # - content (full wikitext) for definitions/etymology/examples
            # This makes the HTML fallback more likely to produce non-empty
            # definitions for filtering downstream.
            if ido_section_wikitext and isinstance(ido_section_wikitext, str) and ido_section_wikitext.lstrip().startswith('<'):
                esperanto_translations = self.extract_esperanto_translations(ido_section_wikitext)
                if not esperanto_translations:
                    return None

                # prefer definitions/metadata from the full wikitext page when available
                part_of_speech = self.extract_part_of_speech(content) or self.extract_part_of_speech(ido_section_wikitext)
                definitions = self.extract_definitions(content) or self.extract_definitions(ido_section_wikitext)
                etymology = self.extract_etymology(content) or self.extract_etymology(ido_section_wikitext)
                examples = self.extract_examples(content) or self.extract_examples(ido_section_wikitext)
            else:
                # No HTML section available; fall back to parsing whatever we have
                esperanto_translations = self.extract_esperanto_translations(content_to_parse)
                if not esperanto_translations:
                    return None

                part_of_speech = self.extract_part_of_speech(content_to_parse)
                definitions = self.extract_definitions(content_to_parse)
                etymology = self.extract_etymology(content_to_parse)
                examples = self.extract_examples(content_to_parse)

        return {
            'ido_word': title,
            'esperanto_translations': esperanto_translations,
            'part_of_speech': part_of_speech,
            'definitions': definitions,
            'source_url': f'https://io.wiktionary.org/wiki/{quote(title)}',
        }
    
    def extract_esperanto_translations(self, text: str) -> List[str]:
        """Extract Esperanto translations.

        Accepts either a mwparserfromhell Wikicode object or a string (wikitext or HTML).
        Tries mwparserfromhell templates first (if available), falls back to regex on
        wikitext, and finally extracts from HTML <li> items when necessary.
        """
        def _from_wikicode(wc) -> List[str]:
            translations: Set[str] = set()
            # templates like {{t|eo|...}} or {{l|eo|...}}
            try:
                for templ in wc.filter_templates(recursive=True):
                    name = str(templ.name).strip().lower()
                    if name.startswith('t') or name == 'l' or name.startswith('t+'):
                        # common pattern: first param is language code
                        try:
                            lang = str(templ.params[0].value).strip().lower() if len(templ.params) > 0 else ''
                        except Exception:
                            lang = ''
                        if lang in ('eo', 'esperanto'):
                            # translation typically in param 1 or 2
                            for idx in range(1, len(templ.params)):
                                try:
                                    val = str(templ.params[idx].value).strip()
                                    if val:
                                        translations.add(self._clean_extracted_text(val))
                                except Exception:
                                    continue
            except Exception:
                pass

            # also look for bullet lines like '* Esperanto: translation'
            for line in str(wc).splitlines():
                line = line.strip()
                if not line.startswith('*'):
                    continue
                body = line.lstrip('*').strip()
                m = re.match(r'^(?:\(?\s*(?:Esperanto|esperanto|eo)\s*\)?[:\-\s]+)(.+)$', body)
                if m:
                    translations.add(self._clean_extracted_text(m.group(1)))

            return list(dict.fromkeys([t for t in translations if t]))

        def _from_wikitext(textstr: str) -> List[str]:
            translations: List[str] = []
            patterns = [
                r'\*\s*(?:Esperanto|esperanto|eo):\s*([^\n\*]+)',
                r'\|\s*(?:Esperanto|esperanto|eo)\s*=\s*([^\n\|]+)',
                r'{{t\+?\|eo\|([^}]+)}}',
                r'{{l\|eo\|([^}]+)}}'
            ]
            for pattern in patterns:
                for m in re.findall(pattern, textstr, re.IGNORECASE):
                    val = re.sub(r'{{[^}]*}}', '', m)
                    val = re.sub(r'\[\[([^\]|]*)\|?[^\]]*\]\]', r'\1', val)
                    val = val.strip(' ,;')
                    if val:
                        translations.append(val)
            # de-dup while preserving order
            seen = set()
            out = []
            for t in translations:
                if t not in seen:
                    seen.add(t)
                    out.append(t)
            return out

        def _from_html(htmlstr: str) -> List[str]:
            parser = _SimpleHtmlListParser()
            try:
                parser.feed(htmlstr)
            except Exception:
                pass
            translations: Set[str] = set()
            for item in parser.items:
                m = re.match(r'^(?:\s*(?:Esperanto|esperanto|eo)[:\-\s]+)(.+)$', item, re.IGNORECASE)
                if m:
                    translations.add(self._clean_extracted_text(m.group(1)))
                else:
                    # look for templates inside item
                    for tm in re.findall(r'{{t\+?\|eo\|([^}]+)}}', item, re.IGNORECASE):
                        translations.add(self._clean_extracted_text(tm))
            return list(dict.fromkeys([t for t in translations if t]))

        # Now dispatch based on types/availability
        # If passed a mwparserfromhell object
        if HAVE_MWP and not isinstance(text, str):
            return _from_wikicode(text)

        # If string input
        if isinstance(text, str):
            s = text.strip()
            # HTML content
            if s.startswith('<'):
                return _from_html(text)
            # else treat as wikitext
            return _from_wikitext(text)

        return []

    def _batch_fetch_pages(self, titles: List[str]) -> Dict[str, Optional[str]]:
        """Batch fetch wikitext for up to 50 titles per API call. Returns mapping title->content."""
        out: Dict[str, Optional[str]] = {}
        if not titles:
            return out
        base = self.base_url
        # chunk titles into groups of 50
        for i in range(0, len(titles), 50):
            chunk = titles[i:i+50]
            params = {
                'action': 'query',
                'titles': '|'.join(chunk),
                'prop': 'revisions',
                'rvprop': 'content',
                'format': 'json'
            }
            try:
                resp = self.session.get(base, params=params)
                resp.raise_for_status()
                data = resp.json()
                pages = data.get('query', {}).get('pages', {})
                for pid, pinfo in pages.items():
                    title = pinfo.get('title')
                    if not title:
                        continue
                    revs = pinfo.get('revisions', [])
                    if revs:
                        rev = revs[0]
                        # Support both legacy '*' key and the slots.main['*'] pattern
                        if 'slots' in rev and isinstance(rev['slots'], dict) and 'main' in rev['slots']:
                            out[title] = rev['slots']['main'].get('*', '')
                        else:
                            out[title] = rev.get('*', '')
                    else:
                        out[title] = None
            except requests.RequestException as e:
                print(f"Batch fetch error: {e}")
                for t in chunk:
                    out[t] = None
            time.sleep(0.1)
        return out

    def search_candidates(self, query: str = '"=={{io}}=="|"==Ido=="', limit: Optional[int] = None) -> List[str]:
        """Use the search API to find candidate pages likely to have Ido sections.

        The default query searches for both literal '=={{io}}==' and '==Ido==' headings.
        """
        titles: List[str] = []
        scontinue = None
        count = 0
        while True:
            params = {
                'action': 'query',
                'list': 'search',
                'srsearch': query,
                'srlimit': 500,
                'format': 'json'
            }
            if scontinue:
                params['sroffset'] = scontinue
            try:
                resp = self.session.get(self.base_url, params=params)
                resp.raise_for_status()
                data = resp.json()
                results = data.get('query', {}).get('search', [])
                batch = [r.get('title') for r in results if r.get('title')]
                titles.extend(batch)
                count += len(batch)
                if limit and count >= limit:
                    return titles[:limit]
                # pagination via 'continue' uses 'sroffset' or 'continue' token
                if 'continue' in data:
                    scontinue = data['continue'].get('sroffset') or None
                else:
                    break
            except requests.RequestException as e:
                print(f"Search error: {e}")
                break
            time.sleep(0.1)
        return titles

    def extract_via_search(self, limit: Optional[int] = None, output_file: str = 'ido_esperanto_dict.json') -> None:
        """Prototype: find candidate pages via search, batch-fetch content, and extract entries."""
        print("Searching for candidate pages containing Ido sections...")
        candidates = self.search_candidates(limit=limit)
        print(f"Found {len(candidates)} candidate pages")

        contents = self._batch_fetch_pages(candidates)

        extracted = []
        for title, content in contents.items():
            if not content:
                continue
            # Skip dot-prefixed
            if title.startswith('.') or not re.match(r'^[A-Za-z0-9]', title):
                continue
            entry = self.parse_ido_entry(title, content)
            if not entry:
                continue
            defs = entry.get('definitions') or []
            defs = self._filter_and_clean_definitions(defs)
            if not defs:
                # try to accept translation-only entries for search mode
                translations = entry.get('esperanto_translations') or []
                if not translations:
                    continue
                entry['definitions'] = []
            else:
                entry['definitions'] = defs
            entry.pop('source_url', None)
            entry.pop('raw_content', None)
            extracted.append(entry)

        result = {
            'metadata': {
                'extraction_date': datetime.now().isoformat(),
                'source': 'io.wiktionary.org',
                'total_words': len(extracted),
                'script_version': '1.0',
                'pages_processed': len(candidates)
            },
            'words': extracted
        }

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        print(f"Search extraction complete: {len(extracted)} entries saved to {output_file}")

    def _clean_extracted_text(self, text: str) -> str:
        """Sanitize extracted wikitext/HTML fragments into readable strings."""
        if not text:
            return ''
        # Remove templates
        text = re.sub(r'{{[^}]*}}', '', text)
        # Convert wiki links [[x|y]] -> y or [[x]] -> x
        text = re.sub(r'\[\[([^\]|]*\|)?([^\]]+)\]\]', r'\2', text)
        # Decode basic HTML entities
        text = text.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
        # Remove pipes left and collapse whitespace
        text = text.replace('|', ' ')
        text = re.sub(r'\s+', ' ', text)
        return text.strip(' \t\n\r\f\v:;,-')

    def _filter_and_clean_definitions(self, defs: List[str]) -> List[str]:
        """Clean and filter a list of definition strings, removing HTML artifacts.

        Keeps only strings that contain alphabetic characters and do not look like
        HTML/table fragments (heuristics: no '<', no 'valign', no 'width=', no 'f9f9f9').
        """
        cleaned: List[str] = []
        for d in defs:
            if not d:
                continue
            s = self._clean_extracted_text(d)
            if not s:
                continue
            # Reject obvious HTML/table fragments
            low = s.lower()
            if '<' in s or '>' in s or 'valign' in low or 'width=' in low or 'f9f9f9' in low:
                continue
            # Require at least one alphabetic character
            if not any(ch.isalpha() for ch in s):
                continue
            cleaned.append(s)
            if len(cleaned) >= 3:
                break
        return cleaned
    
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
        definitions: List[str] = []

        if not text:
            return []

        # 1) Prefer explicit Esperanto-language markers in wikitext, e.g. '*{{eo}}: [[Obadja]]'
        eo_template_pattern = r"\*\s*{{\s*eo(?:\|[^}]*)?\s*}}\s*[:\-]?\s*([^\n\|]+)"
        for m in re.findall(eo_template_pattern, text, flags=re.IGNORECASE):
            val = m.strip()
            val = re.sub(r'\[\[([^\]|]*\|)?([^\]]+)\]\]', r'\2', val)
            val = re.sub(r'{{[^}]*}}', '', val)
            val = val.strip(' \t\n\r\f\v:;,')
            if val:
                definitions.append(val)

        # 2) Look for lines like '* Esperanto: translation' as a fallback
        for m in re.findall(r"\*\s*(?:Esperanto|eo)[:\-\s]+([^\n\|]+)", text, flags=re.IGNORECASE):
            val = m.strip()
            val = re.sub(r'\[\[([^\]|]*\|)?([^\]]+)\]\]', r'\2', val)
            val = re.sub(r'{{[^}]*}}', '', val)
            val = val.strip(' \t\n\r\f\v:;,')
            if val:
                definitions.append(val)

        # 3) Generic fallback: numbered or bulleted definitions after cleaning table attributes
        if not definitions:
            cleaned = text
            # remove common table cell attributes that leak into lines
            cleaned = re.sub(r'bgcolor=\"[^\"]*\"', '', cleaned)
            cleaned = re.sub(r'valign=[^\s|]+', '', cleaned)
            cleaned = re.sub(r'width=[^\s|]+', '', cleaned)
            def_patterns = [r'#\s*([^\n#]+)', r'\*\s*([^\n\*]+)']
            for pattern in def_patterns:
                for match in re.findall(pattern, cleaned):
                    definition = re.sub(r'{{[^}]*}}', '', match)
                    definition = re.sub(r'\[\[([^\]|]*)\|?[^\]]*\]\]', r'\1', definition)
                    definition = definition.strip()
                    if definition and not definition.lower().startswith(('esperanto', 'see also')):
                        definitions.append(definition)

        # Deduplicate while preserving order
        seen = set()
        out = []
        for d in definitions:
            if d and d not in seen:
                seen.add(d)
                out.append(d)
                if len(out) >= 3:
                    break

        return out
    
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
            
            # Skip titles that are not word-like (start with non-alphanumeric)
            # and specifically skip dot-prefixed titles (user requested)
            if not re.match(r'^[A-Za-z0-9]', title) or title.startswith('.'):
                continue
            
            # Get page content
            content = self.get_page_content(title)
            if not content:
                continue
            
            # Parse Ido entry
            entry = self.parse_ido_entry(title, content)
            if entry:
                # Clean and filter definitions
                defs = entry.get('definitions') or []
                defs = self._filter_and_clean_definitions(defs)
                if not defs:
                    continue
                entry['definitions'] = defs
                # Remove unwanted fields if present
                entry.pop('raw_content', None)
                entry.pop('examples', None)
                entry.pop('etymology', None)
                # Remove source_url per user request
                entry.pop('source_url', None)
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
    parser.add_argument('--mode', choices=['all', 'search', 'dump'], default='all',
                        help='Extraction mode: all (iterate all pages), search (API search+batch fetch), dump (use local dump parser)')
    
    args = parser.parse_args()
    
    extractor = IdoEsperantoExtractor()
    try:
        if args.mode == 'search':
            extractor.extract_via_search(limit=args.limit, output_file=args.output)
        else:
            extractor.extract_all_words(limit=args.limit, output_file=args.output)
    except KeyboardInterrupt:
        print("\nExtraction interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"Error during extraction: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
