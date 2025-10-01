#!/usr/bin/env python3
"""
Simple Ido-Esperanto Dictionary Extractor

This script downloads Ido words with Esperanto translations from io.wiktionary.org
using only standard library modules (no external dependencies).

Usage:
    python3 ido_simple.py [limit]
"""

import json
import re
import sys
import time
import urllib.request
import urllib.parse
from datetime import datetime


def fetch_url(url):
    """Fetch content from URL with error handling"""
    try:
        req = urllib.request.Request(url)
        req.add_header('User-Agent', 'IdoEsperantoExtractor/1.0 (Educational/Research Purpose)')
        with urllib.request.urlopen(req) as response:
            return response.read().decode('utf-8')
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None


def get_all_pages(limit=None):
    """Get page titles from io.wiktionary.org"""
    base_url = "https://io.wiktionary.org/w/api.php"
    pages = []
    continue_param = None
    
    print("Fetching page titles from io.wiktionary.org...")
    
    while True:
        params = {
            'action': 'query',
            'list': 'allpages',
            'aplimit': '500',
            'format': 'json',
            'apnamespace': '0'
        }
        
        if continue_param:
            params['apcontinue'] = continue_param
            
        url = base_url + '?' + urllib.parse.urlencode(params)
        data = fetch_url(url)
        
        if not data:
            break
            
        try:
            json_data = json.loads(data)
            batch_pages = [page['title'] for page in json_data.get('query', {}).get('allpages', [])]
            pages.extend(batch_pages)
            
            print(f"Fetched {len(pages)} page titles...")
            
            if limit and len(pages) >= limit:
                pages = pages[:limit]
                break
                
            continue_param = json_data.get('continue', {}).get('apcontinue')
            if not continue_param:
                break
                
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON: {e}")
            break
            
        time.sleep(0.1)  # Be respectful
    
    return pages


def get_page_content(title):
    """Get wikitext content of a page"""
    base_url = "https://io.wiktionary.org/w/api.php"
    params = {
        'action': 'query',
        'titles': title,
        'prop': 'revisions',
        'rvprop': 'content',
        'format': 'json'
    }
    
    url = base_url + '?' + urllib.parse.urlencode(params)
    data = fetch_url(url)
    
    if not data:
        return None
        
    try:
        json_data = json.loads(data)
        pages = json_data.get('query', {}).get('pages', {})
        
        for page_id, page_data in pages.items():
            if page_id != '-1':  # Page exists
                revisions = page_data.get('revisions', [])
                if revisions:
                    return revisions[0].get('*', '')
    except json.JSONDecodeError:
        pass
    
    return None


def extract_esperanto_translations(content):
    """Extract Esperanto translations from wikitext content"""
    if not content:
        return []
        
    # Look for Ido section (format: =={{io}}==)
    ido_match = re.search(r'==\s*{{io}}\s*==(.*)', content, re.MULTILINE | re.DOTALL | re.IGNORECASE)
    if not ido_match:
        # Also try standard format
        ido_match = re.search(r'==\s*Ido\s*==(.*)', content, re.MULTILINE | re.DOTALL | re.IGNORECASE)
        if not ido_match:
            return []
    
    ido_section = ido_match.group(1)
    translations = []
    
    # Pattern 1: *{{eo}}: translation (most common in io.wiktionary.org)
    pattern1 = re.findall(r'\*\s*{{eo}}\s*:\s*([^\n]+)', ido_section, re.IGNORECASE)
    translations.extend(pattern1)
    
    # Pattern 2: * Esperanto: translation
    pattern2 = re.findall(r'^\*\s*(?:Esperanto|esperanto|eo):\s*([^\n\*]+)', ido_section, re.MULTILINE | re.IGNORECASE)
    translations.extend(pattern2)
    
    # Pattern 3: {{t|eo|translation}}
    pattern3 = re.findall(r'{{t\+?\|eo\|([^}|]+)}}', ido_section, re.IGNORECASE)
    translations.extend(pattern3)
    
    # Pattern 4: {{l|eo|translation}}
    pattern4 = re.findall(r'{{l\|eo\|([^}|]+)}}', ido_section, re.IGNORECASE)
    translations.extend(pattern4)
    
    # Clean up translations
    cleaned = []
    for trans in translations:
        # Remove templates and links
        clean = re.sub(r'{{[^}]*}}', '', trans)
        # Remove category links completely
        clean = re.sub(r'\[\[Kategorio:[^\]]*\]\]', '', clean)
        # Remove other links but keep the text
        clean = re.sub(r'\[\[([^\]|]*)\|?[^\]]*\]\]', r'\1', clean)
        clean = clean.strip(' ,;')
        if clean:
            cleaned.append(clean)
    
    return list(set(cleaned))  # Remove duplicates


def extract_part_of_speech(content):
    """Extract part of speech from Ido section"""
    if not content:
        return None
        
    ido_match = re.search(r'==\s*Ido\s*==(.*?)(?=^==|\Z)', content, re.MULTILINE | re.DOTALL | re.IGNORECASE)
    if not ido_match:
        return None
    
    ido_section = ido_match.group(1)
    
    pos_match = re.search(r'===\s*(Noun|Verb|Adjective|Adverb|Pronoun|Preposition|Conjunction|Interjection)\s*===', 
                         ido_section, re.IGNORECASE)
    if pos_match:
        return pos_match.group(1).lower()
    
    return None


def extract_definitions(content):
    """Extract definitions from Ido section"""
    if not content:
        return []
        
    ido_match = re.search(r'==\s*Ido\s*==(.*?)(?=^==|\Z)', content, re.MULTILINE | re.DOTALL | re.IGNORECASE)
    if not ido_match:
        return []
    
    ido_section = ido_match.group(1)
    
    # Look for numbered definitions
    definitions = re.findall(r'^#\s*([^\n#]+)', ido_section, re.MULTILINE)
    
    # Clean up definitions
    cleaned = []
    for defn in definitions[:3]:  # Limit to 3
        clean = re.sub(r'{{[^}]*}}', '', defn)
        clean = re.sub(r'\[\[([^\]|]*)\|?[^\]]*\]\]', r'\1', clean)
        clean = clean.strip()
        if clean and not clean.lower().startswith(('esperanto', 'see also')):
            cleaned.append(clean)
    
    return cleaned


def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    output_file = 'ido_esperanto_simple.json'
    
    print("Starting Ido-Esperanto dictionary extraction...")
    
    # Get all pages
    pages = get_all_pages(limit)
    if not pages:
        print("No pages found!")
        return
    
    print(f"Processing {len(pages)} pages...")
    
    extracted_words = []
    
    for i, title in enumerate(pages):
        if i % 10 == 0:
            print(f"Processing page {i+1}/{len(pages)}: {title}")
        
        # Get page content
        content = get_page_content(title)
        if not content:
            continue
        
        # Extract Esperanto translations
        translations = extract_esperanto_translations(content)
        if not translations:
            continue
        
        # Extract additional metadata
        pos = extract_part_of_speech(content)
        definitions = extract_definitions(content)
        
        entry = {
            'ido_word': title,
            'esperanto_translations': translations,
            'part_of_speech': pos,
            'definitions': definitions,
            'source_url': f'https://io.wiktionary.org/wiki/{urllib.parse.quote(title)}'
        }
        # Skip entries with empty definitions
        if not definitions:
            continue

        extracted_words.append(entry)
        print(f"  ✓ Found Ido word with Esperanto translation: {title}")
        
        time.sleep(0.1)  # Be respectful
    
    # Create final output
    result = {
        'metadata': {
            'extraction_date': datetime.now().isoformat(),
            'source': 'io.wiktionary.org',
            'total_words': len(extracted_words),
            'script_version': '1.0 (simple)',
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


if __name__ == '__main__':
    main()
