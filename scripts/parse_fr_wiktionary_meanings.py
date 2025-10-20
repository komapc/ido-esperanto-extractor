#!/usr/bin/env python3
import argparse
import json
import logging
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from _common import configure_logging, read_json, write_json

# Pre-compile regex patterns for performance
TRAD_SECTION_RE = re.compile(r'\{\{trad-début\|([^}]+)\}\}(.*?)\{\{trad-fin\}\}', re.DOTALL)
IO_TRANS_RE = re.compile(r'\{\{T\|io\}\}\s*:\s*\{\{trad\+?\|io\|([^}|]+)')
EO_TRANS_RE = re.compile(r'\{\{T\|eo\}\}\s*:\s*\{\{trad\+?\|eo\|([^}|]+)')


def extract_numbered_meanings(text: str) -> List[Dict[str, Any]]:
    """Extract numbered meanings from French Wiktionary text."""
    meanings = []
    
    # Look for numbered list items in French section
    # Pattern: # definition text (using # instead of 1.)
    meaning_pattern = r'^#\s+(.+?)(?=^#|^===|^==|\Z)'
    
    meaning_num = 1
    for match in re.finditer(meaning_pattern, text, re.MULTILINE | re.DOTALL):
        definition = match.group(1).strip()
        
        # Clean up definition (remove examples, citations, etc.)
        definition = re.sub(r'{{exemple[^}]*}}', '', definition)  # Remove examples
        definition = re.sub(r'{{[^}]*}}', '', definition)  # Remove templates
        definition = re.sub(r'\[\[[^]]*\]\]', '', definition)  # Remove links
        definition = re.sub(r'[#*]', '', definition)  # Remove bullets
        definition = re.sub(r'\s+', ' ', definition).strip()
        
        if definition and len(definition) > 10:  # Filter out very short definitions
            meanings.append({
                'number': meaning_num,
                'definition': definition
            })
            meaning_num += 1
    
    return meanings


def extract_translations_for_meaning(text: str, meaning_num: int) -> Dict[str, List[str]]:
    """Extract Ido and Esperanto translations for a specific meaning."""
    translations = {'io': [], 'eo': []}
    
    # Look for trad-début sections that might contain this meaning
    # Pattern: {{trad-début|meaning description}}
    trad_sections = re.findall(r'\{\{trad-début\|([^}]+)\}\}(.*?)\{\{trad-fin\}\}', text, re.DOTALL)
    
    for meaning_desc, section_text in trad_sections:
        # Look for Ido and Esperanto translations in this section
        io_matches = re.findall(r'\{\{T\|io\}\}\s*:\s*\{\{trad\+?\|io\|([^}|]+)', section_text)
        eo_matches = re.findall(r'\{\{T\|eo\}\}\s*:\s*\{\{trad\+?\|eo\|([^}|]+)', section_text)
        
        for match in io_matches:
            translation = match.strip()
            if translation and len(translation) > 1:
                translations['io'].append(translation)
        
        for match in eo_matches:
            translation = match.strip()
            if translation and len(translation) > 1:
                translations['eo'].append(translation)
    
    return translations


def parse_fr_wiktionary_page(title: str, text: str) -> List[Dict[str, Any]]:
    """Parse a single French Wiktionary page for meaning-specific translations.
    
    Returns IO-centered dictionary entries ready to write.
    """
    results = []
    
    # Extract all translation sections with IO and EO translations (using pre-compiled regex)
    trad_sections = TRAD_SECTION_RE.findall(text)
    
    for meaning_desc, section_text in trad_sections:
        # Look for Ido and Esperanto translations in this section (using pre-compiled regex)
        io_matches = IO_TRANS_RE.findall(section_text)
        eo_matches = EO_TRANS_RE.findall(section_text)
        
        # Only include if we have both IO and EO translations
        if io_matches and eo_matches:
            for io_term in io_matches:
                for eo_term in eo_matches:
                    # Convert to IO-centered format immediately
                    results.append({
                        'lemma': io_term.strip(),
                        'pos': 'adjective',  # Default, could be improved
                        'language': 'io',
                        'senses': [{
                            'senseId': f"fr_{title}",
                            'gloss': meaning_desc.strip(),
                            'translations': [{
                                'lang': 'eo',
                                'term': eo_term.strip(),
                                'source': 'fr_wiktionary_meaning',
                                'sources': ['fr_wiktionary_meaning'],
                                'confidence': 0.7
                            }]
                        }],
                        'provenance': [{
                            'source': 'fr_wiktionary_meaning',
                            'page': title,
                            'meaning': meaning_desc.strip()
                        }]
                    })
    
    return results


def parse_fr_wiktionary_dump(dump_path: Path, output_path: Path, progress_every: int = 1000) -> None:
    """Parse French Wiktionary dump for meaning-specific IO/EO translations.
    
    Optimized version:
    - Pre-compiled regex patterns
    - Early filtering to skip irrelevant pages
    - Incremental writing to avoid memory accumulation
    """
    import xml.etree.ElementTree as ET
    import bz2
    
    logging.info("Parsing French Wiktionary dump for meaning-specific translations")
    
    processed = 0
    french_pages = 0
    pages_with_translations = 0
    total_pairs = 0
    
    # Open output file for incremental writing
    with bz2.open(dump_path, 'rt', encoding='utf-8') as f, \
         open(output_path, 'w', encoding='utf-8') as out_f:
        
        # Write JSON array opening
        out_f.write('[\n')
        first_entry = True
        
        for event, elem in ET.iterparse(f, events=('start', 'end')):
            if event == 'end' and elem.tag.endswith('page'):
                title_elem = elem.find('.//{http://www.mediawiki.org/xml/export-0.11/}title')
                text_elem = elem.find('.//{http://www.mediawiki.org/xml/export-0.11/}text')
                
                if title_elem is not None and text_elem is not None:
                    title = title_elem.text
                    text = text_elem.text or ''
                    
                    if title and text:
                        # Early filtering: Quick reject non-French pages
                        if '{{langue|fr}}' not in text and 'Français' not in text:
                            processed += 1
                            if processed % progress_every == 0:
                                logging.info("Processed %d pages, %d French pages, %d with translations, found %d meaning pairs", 
                                           processed, french_pages, pages_with_translations, total_pairs)
                            elem.clear()
                            continue
                        
                        french_pages += 1
                        
                        # Early filtering: Quick reject pages without both IO and EO
                        if '{{T|io}}' not in text or '{{T|eo}}' not in text:
                            processed += 1
                            if processed % progress_every == 0:
                                logging.info("Processed %d pages, %d French pages, %d with translations, found %d meaning pairs", 
                                           processed, french_pages, pages_with_translations, total_pairs)
                            elem.clear()
                            continue
                        
                        pages_with_translations += 1
                        
                        # Now do expensive parsing
                        page_results = parse_fr_wiktionary_page(title, text)
                        
                        # Write results incrementally
                        if page_results:
                            for result in page_results:
                                if not first_entry:
                                    out_f.write(',\n')
                                json.dump(result, out_f, ensure_ascii=False)
                                first_entry = False
                                total_pairs += 1
                            
                            logging.info("Found %d pairs in page: %s (total: %d)", 
                                       len(page_results), title, total_pairs)
                    
                    processed += 1
                    if processed % progress_every == 0:
                        logging.info("Processed %d pages, %d French pages, %d with translations, found %d meaning pairs", 
                                   processed, french_pages, pages_with_translations, total_pairs)
                
                elem.clear()
        
        # Write JSON array closing
        out_f.write('\n]\n')
    
    logging.info("Wrote %s (%d meaning-specific pairs)", output_path, total_pairs)


def main(argv) -> int:
    ap = argparse.ArgumentParser(description="Parse French Wiktionary for meaning-specific IO/EO translations")
    ap.add_argument("--input", type=Path, default=Path(__file__).resolve().parents[1] / "data/raw/frwiktionary-latest-pages-articles.xml.bz2")
    ap.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] / "work/fr_wikt_meanings.json")
    ap.add_argument("--progress-every", type=int, default=1000, help="Log progress every N pages")
    ap.add_argument("-v", "--verbose", action="count", default=0)
    args = ap.parse_args(argv)

    configure_logging(args.verbose)
    parse_fr_wiktionary_dump(args.input, args.output, args.progress_every)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
