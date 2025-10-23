#!/usr/bin/env python3
"""
Fixed English Wiktionary parser that properly extracts IO/EO translations from templates.

PROBLEM (OLD):
- Pattern stopped at | character: {{t|eo|hundo}} → captured only {{t
- Result: 95% truncated templates

SOLUTION (NEW):
- Capture full line without stopping at |
- Parse template arguments to extract words
- Filter qualifier/metadata templates
"""
import argparse
import json
import logging
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent))
from _common import configure_logging, write_json
from wiktionary_parser import iter_pages, is_valid_title, extract_language_section


def extract_translations_from_templates(line: str, target_lang: str) -> List[str]:
    """
    Extract translations from MediaWiki templates in a line.
    
    Templates we PARSE (extract word):
        {{t|eo|word}}        - unchecked translation
        {{t+|eo|word}}       - verified translation (best quality)
        {{tt|eo|word}}       - translation variant
        {{tt+|eo|word}}      - verified translation with transliteration
        {{l|eo|word}}        - link to word
        {{m|eo|word}}        - mention word
    
    Templates we SKIP (unverified):
        {{t-check|eo|word}}  - needs verification
        {{t-needed|eo}}      - translation missing
    
    Templates we IGNORE (metadata, removed entirely):
        {{qualifier|...}}    - context marker
        {{q|...}}            - short qualifier
        {{sense|...}}        - sense grouping
        {{lb|eo|...}}        - label/context
        {{m}}, {{f}}, {{n}}  - gender markers (not applicable to Esperanto)
        {{p}}, {{s}}         - number markers
    
    Args:
        line: Text line from English Wiktionary translation section
        target_lang: Language code ('io' or 'eo')
    
    Returns:
        List of translation words extracted from templates
    """
    translations = []
    
    # SKIP: Check for low-quality templates that indicate unreliable data
    if '{{t-check' in line or '{{t-needed' in line:
        return []
    
    # PARSE: Extract verified translations {{t+|lang|word}} (highest quality)
    # Format: {{t+|eo|hundo}}, {{t+|eo|hundo|m}}, {{t+|eo|hundo|alt=hundoj}}
    pattern_tplus = rf'\{{{{t\+\|{target_lang}\|([^|}}]+?)(?:\|[^}}]*)?\}}}}'
    for match in re.finditer(pattern_tplus, line, re.IGNORECASE):
        word = match.group(1).strip()
        if word and len(word) > 1:
            translations.append(word)
    
    # PARSE: Extract unchecked translations {{t|lang|word}}
    # Format: {{t|eo|hundo}}, {{t|eo|hundo|m}}, {{t|eo|hundo|alt=hundoj}}
    pattern_t = rf'\{{{{t\|{target_lang}\|([^|}}]+?)(?:\|[^}}]*)?\}}}}'
    for match in re.finditer(pattern_t, line, re.IGNORECASE):
        word = match.group(1).strip()
        if word and len(word) > 1:
            translations.append(word)
    
    # PARSE: Extract transliteration variants {{tt+|lang|word}}, {{tt|lang|word}}
    # Format: {{tt+|eo|hundo|tr=hun.do}}
    pattern_tt = rf'\{{{{tt\+?\|{target_lang}\|([^|}}]+?)(?:\|[^}}]*)?\}}}}'
    for match in re.finditer(pattern_tt, line, re.IGNORECASE):
        word = match.group(1).strip()
        if word and len(word) > 1:
            translations.append(word)
    
    # PARSE: Extract link templates {{l|lang|word}}, {{m|lang|word}}
    # Format: {{l|eo|hundo}}, {{m|eo|hundo|word}}
    pattern_link = rf'\{{{{[lm]\|{target_lang}\|([^|}}]+?)(?:\|[^}}]*)?\}}}}'
    for match in re.finditer(pattern_link, line, re.IGNORECASE):
        word = match.group(1).strip()
        if word and len(word) > 1:
            translations.append(word)
    
    return translations


def extract_bare_words(line: str, target_lang: str) -> List[str]:
    """
    Extract bare words (not in templates) from translation line.
    This handles cases where translations are listed without templates.
    
    Args:
        line: Translation line
        target_lang: Language code
    
    Returns:
        List of bare translation words
    """
    # First, remove all templates and metadata
    cleaned = line
    
    # Remove all templates (qualifier, sense, translations, etc.)
    cleaned = re.sub(r'\{\{[^}]*\}\}', '', cleaned)
    
    # Remove wikilinks [[word]] or [[word|display]]
    cleaned = re.sub(r'\[\[(?:[^\]|]*\|)?([^\]]+)\]\]', r'\1', cleaned)
    
    # Remove parenthetical notes
    cleaned = re.sub(r'\([^)]+\)', '', cleaned)
    
    # Extract words (letters + diacritics used in Ido/Esperanto)
    words = []
    # Allow: a-z, A-Z, ĉĝĥĵŝŭĈĜĤĴŜŬ (Esperanto), hyphen
    word_pattern = r'\b([a-zA-ZĉĝĥĵŝŭĈĜĤĴŜŬ]+-?[a-zA-ZĉĝĥĵŝŭĈĜĤĴŜŬ]+)\b'
    for match in re.finditer(word_pattern, cleaned):
        word = match.group(1).strip()
        # Filter out English words (very basic heuristic)
        if len(word) >= 3 and len(word) <= 30:
            words.append(word)
    
    return words


def clean_translation_line(line: str) -> str:
    """
    Clean translation line by removing metadata templates.
    
    IGNORE templates (remove entirely):
        {{qualifier|...}}, {{q|...}}, {{sense|...}}, {{lb|...}}
        Gender markers: {{m}}, {{f}}, {{n}}, {{c}}
        Number markers: {{p}}, {{s}}
    
    Args:
        line: Raw translation line
    
    Returns:
        Cleaned line with metadata removed
    """
    # Remove qualifier/context templates
    line = re.sub(r'\{\{(?:qualifier|q|sense|lb)\|[^}]*\}\}', '', line, flags=re.IGNORECASE)
    
    # Remove standalone gender/number markers
    line = re.sub(r'\{\{(?:[mfnpsc])\}\}', '', line, flags=re.IGNORECASE)
    
    # Remove gloss templates (English translations, not target language)
    line = re.sub(r'\{\{gloss\|[^}]*\}\}', '', line, flags=re.IGNORECASE)
    
    return line


def extract_english_translations(text: str, target_lang: str) -> List[Dict[str, Any]]:
    """
    Extract Ido or Esperanto translations from English Wiktionary page.
    
    Strategy:
    1. Find translation section (=== Translations ===)
    2. For each bullet line with target language
    3. Parse templates to extract words
    4. Clean metadata templates
    5. Extract bare words if present
    
    Args:
        text: Full English Wiktionary page text
        target_lang: 'io' or 'eo'
    
    Returns:
        List of sense dictionaries with translations
    """
    # Find Translations section
    # Pattern: === Translations === or ====Translations====
    trans_match = re.search(r'^===+\s*Translations\s*===+\s*$', text, re.MULTILINE | re.IGNORECASE)
    if not trans_match:
        return []
    
    # Extract section from Translations header to next header of same level
    section_start = trans_match.end()
    section_text = text[section_start:]
    
    # Find next section (=== or ==)
    next_section = re.search(r'^===?[^=]', section_text, re.MULTILINE)
    if next_section:
        section_text = section_text[:next_section.start()]
    
    # Find lines with target language
    # Format: * Esperanto: {{t|eo|word1}}, {{t+|eo|word2}}
    #     or: * {{sense|context}} Esperanto: {{t|eo|word}}
    
    lang_name = {
        'io': 'Ido',
        'eo': 'Esperanto'
    }.get(target_lang, target_lang)
    
    # Pattern: bullet line with language name
    # Captures everything after "Esperanto:" or "Ido:" until newline
    pattern = rf'^\*.*?{lang_name}\s*:\s*(.+?)$'
    
    senses = []
    for match in re.finditer(pattern, section_text, re.MULTILINE | re.IGNORECASE):
        line = match.group(1)
        
        # Clean metadata templates
        line = clean_translation_line(line)
        
        # Extract translations from templates
        template_words = extract_translations_from_templates(line, target_lang)
        
        # Extract bare words (if any)
        bare_words = extract_bare_words(line, target_lang)
        
        # Combine and deduplicate
        all_words = list(dict.fromkeys(template_words + bare_words))
        
        if all_words:
            sense = {
                'senseId': None,
                'gloss': None,  # English Wiktionary doesn't provide glosses in translation section
                'translations': [
                    {
                        'lang': target_lang,
                        'term': word,
                        'confidence': 0.8,  # Higher than old via-English (0.7) because we fixed parsing
                        'source': 'en_wiktionary'
                    }
                    for word in all_words
                ]
            }
            senses.append(sense)
    
    return senses


def parse_english_wiktionary(
    dump_path: Path,
    target_lang: str,
    out_json: Path,
    limit: Optional[int] = None,
    progress_every: int = 1000,
    verbose: bool = False
) -> None:
    """
    Parse English Wiktionary to extract IO or EO translations.
    
    Args:
        dump_path: Path to enwiktionary-*.xml.bz2
        target_lang: 'io' or 'eo'
        out_json: Output JSON file
        limit: Max pages to process (for testing)
        progress_every: Log progress every N pages
        verbose: Enable verbose logging
    """
    logging.info(f"Parsing English Wiktionary for {target_lang.upper()} translations")
    logging.info(f"Input: {dump_path}")
    logging.info(f"Output: {out_json}")
    if limit:
        logging.info(f"Limit: {limit} pages")
    
    entries = []
    pages_processed = 0
    pages_with_translations = 0
    
    for title, ns, text in iter_pages(dump_path):
        # Check limit
        if limit and pages_processed >= limit:
            logging.info(f"Reached limit of {limit} pages")
            break
        
        # Only main namespace (ns=0)
        if ns != "0":
            continue
        
        pages_processed += 1
        
        # Progress logging
        if pages_processed % progress_every == 0:
            logging.info(f"Processed {pages_processed:,} pages, found {pages_with_translations} with {target_lang.upper()} translations")
        
        # Skip invalid titles
        if not is_valid_title(title):
            continue
        
        # Extract English section (English word definitions)
        english_section = extract_language_section(text, 'en')
        if not english_section:
            continue
        
        # Extract translations
        senses = extract_english_translations(english_section, target_lang)
        
        if not senses:
            continue
        
        pages_with_translations += 1
        
        # Create entry
        entry = {
            'id': f'en:{title}:x',
            'lemma': title,  # English word
            'pos': None,  # POS not needed for via translations
            'language': 'en',
            'senses': senses,
            'provenance': [{
                'source': 'en_wiktionary',
                'page': title,
                'rev': None
            }]
        }
        
        entries.append(entry)
    
    # Save results
    out_json.parent.mkdir(parents=True, exist_ok=True)
    write_json(out_json, entries)
    
    logging.info(f"")
    logging.info(f"=" * 60)
    logging.info(f"PARSING COMPLETE")
    logging.info(f"=" * 60)
    logging.info(f"Total pages processed: {pages_processed:,}")
    logging.info(f"Pages with {target_lang.upper()} translations: {pages_with_translations}")
    logging.info(f"Entries extracted: {len(entries)}")
    logging.info(f"Output: {out_json}")


def main():
    parser = argparse.ArgumentParser(
        description='Parse English Wiktionary for IO/EO translations (FIXED template parser)'
    )
    parser.add_argument(
        '--input',
        type=Path,
        required=True,
        help='Path to enwiktionary-latest-pages-articles.xml.bz2'
    )
    parser.add_argument(
        '--target',
        choices=['io', 'eo'],
        required=True,
        help='Target language to extract (io or eo)'
    )
    parser.add_argument(
        '--out',
        type=Path,
        required=True,
        help='Output JSON file'
    )
    parser.add_argument(
        '--limit',
        type=int,
        help='Limit number of pages to process (for testing)'
    )
    parser.add_argument(
        '--progress-every',
        type=int,
        default=10000,
        help='Log progress every N pages (default: 10000)'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    # Configure logging
    configure_logging(2 if args.verbose else 1)
    
    # Parse
    parse_english_wiktionary(
        dump_path=args.input,
        target_lang=args.target,
        out_json=args.out,
        limit=args.limit,
        progress_every=args.progress_every,
        verbose=args.verbose
    )


if __name__ == '__main__':
    main()

