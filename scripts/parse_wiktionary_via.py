#!/usr/bin/env python3
"""
Unified script for parsing Wiktionary via translations (English and French).

This script handles both:
1. English Wiktionary: Parse EN→IO and EN→EO separately, then match by English word
2. French Wiktionary: Parse FR→IO/EO directly from same page

Strategy:
- For English: Two-pass approach (separate IO/EO parsing, then matching)
- For French: Single-pass approach (direct IO/EO extraction from same page)
- Both create IO↔EO pairs via intermediate language
- Source tag: "{lang}_wiktionary_via"
- Confidence: 0.8 (high quality)
"""
import argparse
import json
import logging
import re
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from _common import configure_logging, read_json, write_json
from wiktionary_parser import ParserConfig, parse_wiktionary

# Pre-compile regex patterns for French Wiktionary
TRAD_SECTION_RE = re.compile(r'\{\{trad-début\|([^}]+)\}\}(.*?)\{\{trad-fin\}\}', re.DOTALL)
IO_TRANS_RE = re.compile(r'\{\{T\|io\}\}\s*:\s*\{\{trad\+?\|io\|([^}|]+)')
EO_TRANS_RE = re.compile(r'\{\{T\|eo\}\}\s*:\s*\{\{trad\+?\|eo\|([^}|]+)')


def extract_french_via_translations(text: str) -> List[Dict[str, Any]]:
    """Extract via translations from French Wiktionary text."""
    via_translations = []
    
    # Look for numbered list items in French section
    meaning_pattern = r'^#\s+(.+?)(?=^#|^===|^==|\Z)'
    
    meaning_num = 1
    for match in re.finditer(meaning_pattern, text, re.MULTILINE | re.DOTALL):
        definition = match.group(1).strip()
        
        # Clean up definition (remove examples, citations, etc.)
        definition = re.sub(r'\([^)]*\)', '', definition).strip()
        if len(definition) < 3:
            continue
            
        # Extract translations for this meaning
        translations = extract_translations_for_meaning(text, meaning_num)
        
        if translations['io'] and translations['eo']:
            via_translations.append({
                'via_num': meaning_num,
                'definition': definition,
                'io_translations': translations['io'],
                'eo_translations': translations['eo']
            })
        meaning_num += 1
    
    return via_translations


def extract_translations_for_meaning(text: str, meaning_num: int) -> Dict[str, List[str]]:
    """Extract Ido and Esperanto translations for a specific meaning."""
    translations = {'io': [], 'eo': []}
    
    # Look for trad-début sections
    trad_sections = re.findall(r'\{\{trad-début\|([^}]+)\}\}(.*?)\{\{trad-fin\}\}', text, re.DOTALL)
    
    for via_desc, section_text in trad_sections:
        # Look for Ido and Esperanto translations in this section
        io_matches = IO_TRANS_RE.findall(section_text)
        eo_matches = EO_TRANS_RE.findall(section_text)
        
        for match in io_matches:
            translation = match.strip()
            if translation and len(translation) > 1:
                translations['io'].append(translation)
        
        for match in eo_matches:
            translation = match.strip()
            if translation and len(translation) > 1:
                translations['eo'].append(translation)
    
    return translations


def parse_french_wiktionary_via(dump_path: Path, output_path: Path, progress_every: int = 1) -> None:
    """Parse French Wiktionary for via-specific IO/EO translations."""
    logging.info("Parsing French Wiktionary for via translations")
    logging.info(f"Input: {dump_path}")
    logging.info(f"Output: {output_path}")
    
    results = []
    processed = 0
    french_pages = 0
    pages_with_translations = 0
    total_pairs = 0
    
    start_time = time.time()
    last_progress_time = start_time
    
    in_page = False  # Initialize before loop to avoid UnboundLocalError
    
    with open(dump_path, 'rb') as f:
        import bz2
        with bz2.open(f, 'rt', encoding='utf-8') as xml_file:
            for line in xml_file:
                if '<page>' in line:
                    page_content = line
                    in_page = True
                elif in_page and '</page>' in line:
                    page_content += line
                    in_page = False
                    
                    # Extract title and text
                    title_match = re.search(r'<title>(.*?)</title>', page_content)
                    text_match = re.search(r'<text[^>]*>(.*?)</text>', page_content, re.DOTALL)
                    
                    if title_match and text_match:
                        title = title_match.group(1)
                        text = text_match.group(1)
                        
                        # Skip non-French pages
                        if '{{langue|fr}}' not in text and 'Français' not in text:
                            processed += 1
                            continue
                        
                        french_pages += 1
                        
                        # Skip if no IO/EO translations
                        if '{{T|io}}' not in text or '{{T|eo}}' not in text:
                            processed += 1
                            continue
                        
                        pages_with_translations += 1
                        
                        # Extract via translations
                        via_translations = extract_french_via_translations(text)
                        
                        for via_data in via_translations:
                            for io_term in via_data['io_translations']:
                                for eo_term in via_data['eo_translations']:
                                    results.append({
                                        'id': f"fr_via:{title}:{via_data['via_num']}",
                                        'lemma_io': io_term,
                                        'lemma_eo': eo_term,
                                        'pos': None,
                                        'language_io': 'io',
                                        'language_eo': 'eo',
                                        'senses': [{
                                            'senseId': f"fr_via_{via_data['via_num']}",
                                            'gloss': via_data['definition'],
                                            'translations': [
                                                {'lang': 'eo', 'term': eo_term, 'confidence': 0.8, 'source': 'fr_wiktionary_via'}
                                            ]
                                        }],
                                        'provenance': [{
                                            'source': 'fr_wiktionary_via',
                                            'page': title,
                                            'via_definition': via_data['definition'],
                                            'via_num': via_data['via_num']
                                        }]
                                    })
                                    total_pairs += 1
                    
                    processed += 1
                    
                    # Progress logging
                    current_time = time.time()
                    time_since_last = current_time - last_progress_time
                    
                    if processed % progress_every == 0 or time_since_last >= 60:
                        elapsed = current_time - start_time
                        rate = processed / elapsed if elapsed > 0 else 0
                        logging.info("Processed %d pages, %d French pages, %d with translations, found %d meaning pairs (%.1f pages/sec, %.1f min elapsed)", 
                                   processed, french_pages, pages_with_translations, total_pairs, rate, elapsed/60)
                        last_progress_time = current_time
                elif in_page:
                    page_content += line
    
    write_json(output_path, results)
    logging.info("Wrote %s (%d via pairs)", output_path, len(results))


def build_english_via_pairs(io_file: Path, eo_file: Path, output_path: Path, progress_every: int = 1) -> None:
    """Build IO↔EO pairs by matching English words with both translations."""
    logging.info("Building IO↔EO pairs via English Wiktionary")
    logging.info(f"IO source: {io_file}")
    logging.info(f"EO source: {eo_file}")
    logging.info(f"Output: {output_path}")
    
    # Load data
    logging.info("Loading English→Ido translations...")
    io_entries = read_json(io_file)
    logging.info(f"Loaded {len(io_entries)} entries")
    
    logging.info("Loading English→Esperanto translations...")
    eo_entries = read_json(eo_file)
    logging.info(f"Loaded {len(eo_entries)} entries")
    
    # Build translation maps
    logging.info("Building translation maps...")
    io_map = defaultdict(list)  # English word -> [IO translations]
    eo_map = defaultdict(list)  # English word -> [EO translations]
    
    for entry in io_entries:
        lemma = entry.get('lemma', '')
        for sense in entry.get('senses', []):
            for trans in sense.get('translations', []):
                if trans.get('lang') == 'io':
                    io_map[lemma].append(trans['term'])
    
    for entry in eo_entries:
        lemma = entry.get('lemma', '')
        for sense in entry.get('senses', []):
            for trans in sense.get('translations', []):
                if trans.get('lang') == 'eo':
                    eo_map[lemma].append(trans['term'])
    
    # Find matches and create bilingual pairs
    logging.info("Finding matches...")
    results = []
    matches_found = 0
    
    start_time = time.time()
    last_progress_time = start_time
    
    for english_word in io_map:
        if english_word in eo_map:
            io_translations = list(set(io_map[english_word]))  # Remove duplicates
            eo_translations = list(set(eo_map[english_word]))  # Remove duplicates
            
            for io_term in io_translations:
                for eo_term in eo_translations:
                    results.append({
                        'id': f"en_via:{english_word}",
                        'lemma_io': io_term,
                        'lemma_eo': eo_term,
                        'pos': None,
                        'language_io': 'io',
                        'language_eo': 'eo',
                        'senses': [{
                            'senseId': 'en_via',
                            'gloss': f"via English '{english_word}'",
                            'translations': [
                                {'lang': 'eo', 'term': eo_term, 'confidence': 0.8, 'source': 'en_wiktionary_via'}
                            ]
                        }],
                        'provenance': [{
                            'source': 'en_wiktionary_via',
                            'page': english_word,
                            'via_language': 'en'
                        }]
                    })
                    matches_found += 1
            
            # Progress logging
            current_time = time.time()
            time_since_last = current_time - last_progress_time
            
            if matches_found % progress_every == 0 or time_since_last >= 60:
                elapsed = current_time - start_time
                rate = matches_found / elapsed if elapsed > 0 else 0
                logging.info("Found %d matches so far (%.1f matches/sec, %.1f min elapsed)", 
                           matches_found, rate, elapsed/60)
                last_progress_time = current_time
    
    write_json(output_path, results)
    logging.info("Wrote %s (%d via pairs)", output_path, len(results))


def main(argv) -> int:
    ap = argparse.ArgumentParser(description="Parse Wiktionary for via translations (English and French)")
    ap.add_argument("--source", choices=['en', 'fr'], required=True, help="Source language (en or fr)")
    ap.add_argument("--input", type=Path, help="Path to Wiktionary dump file")
    ap.add_argument("--io-input", type=Path, help="Path to IO translations JSON (for English)")
    ap.add_argument("--eo-input", type=Path, help="Path to EO translations JSON (for English)")
    ap.add_argument("--output", type=Path, help="Output path for via translations JSON")
    ap.add_argument("--progress-every", type=int, default=1, help="Log progress every N pages/matches")
    ap.add_argument("-v", "--verbose", action="count", default=0)
    args = ap.parse_args(argv)
    
    configure_logging(args.verbose)
    
    if args.source == 'fr':
        if not args.input:
            args.input = Path(__file__).resolve().parents[1] / "data/raw/frwiktionary-latest-pages-articles.xml.bz2"
        if not args.output:
            args.output = Path(__file__).resolve().parents[1] / "work/fr_wikt_via.json"
        
        parse_french_wiktionary_via(args.input, args.output, args.progress_every)
    
    elif args.source == 'en':
        if not args.io_input:
            args.io_input = Path(__file__).resolve().parents[1] / "work/en_wikt_en_io.json"
        if not args.eo_input:
            args.eo_input = Path(__file__).resolve().parents[1] / "work/en_wikt_en_eo.json"
        if not args.output:
            args.output = Path(__file__).resolve().parents[1] / "work/en_wikt_via.json"
        
        build_english_via_pairs(args.io_input, args.eo_input, args.output, args.progress_every)
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
