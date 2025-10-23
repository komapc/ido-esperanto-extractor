#!/usr/bin/env python3
"""
Build IO↔EO bilingual pairs via English Wiktionary.

Strategy:
1. Parse English Wiktionary for IO translations → en_wikt_en_io.json
2. Parse English Wiktionary for EO translations → en_wikt_en_eo.json
3. Match by English word: if same English word has both IO and EO translations,
   create IO↔EO pairs
4. Source tag: "en_wiktionary_via"
5. Confidence: 0.8 (high quality now that templates are fixed)

Example:
  English "dictionary" has:
    - IO: vortolibro, dicionario, lexiko
    - EO: vortaro
  
  Creates pairs:
    vortolibro → vortaro [via "dictionary"]
    dicionario → vortaro [via "dictionary"]
    lexiko → vortaro [via "dictionary"]
"""
import argparse
import json
import logging
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Set

sys.path.insert(0, str(Path(__file__).parent))
from _common import configure_logging, read_json, write_json


def build_translation_map(entries: List[Dict[str, Any]], target_lang: str) -> Dict[str, Set[str]]:
    """
    Build map from English word → Set of translations in target language.
    
    Args:
        entries: Parsed English Wiktionary entries
        target_lang: 'io' or 'eo'
    
    Returns:
        Dict mapping English word to set of target language translations
    """
    translation_map = defaultdict(set)
    
    for entry in entries:
        english_word = entry.get('lemma')
        if not english_word:
            continue
        
        for sense in entry.get('senses', []):
            for trans in sense.get('translations', []):
                if trans.get('lang') == target_lang:
                    term = trans.get('term')
                    if term and len(term) > 1:
                        translation_map[english_word].add(term)
    
    return {k: v for k, v in translation_map.items()}


def build_bilingual_via_english(
    io_file: Path,
    eo_file: Path,
    out_file: Path,
    verbose: bool = False
) -> None:
    """
    Build IO↔EO bilingual pairs by matching English words with both translations.
    
    Args:
        io_file: JSON with English→Ido translations
        eo_file: JSON with English→Esperanto translations
        out_file: Output bilingual JSON
        verbose: Enable verbose logging
    """
    logging.info("Building IO↔EO pairs via English Wiktionary")
    logging.info(f"  IO source: {io_file}")
    logging.info(f"  EO source: {eo_file}")
    logging.info(f"  Output: {out_file}")
    
    # Load data
    logging.info("Loading English→Ido translations...")
    io_entries = read_json(io_file)
    logging.info(f"  Loaded {len(io_entries)} entries")
    
    logging.info("Loading English→Esperanto translations...")
    eo_entries = read_json(eo_file)
    logging.info(f"  Loaded {len(eo_entries)} entries")
    
    # Build translation maps
    logging.info("Building translation maps...")
    en_to_io = build_translation_map(io_entries, 'io')
    en_to_eo = build_translation_map(eo_entries, 'eo')
    
    logging.info(f"  English words with IO translations: {len(en_to_io)}")
    logging.info(f"  English words with EO translations: {len(en_to_eo)}")
    
    # Find English words that have BOTH IO and EO translations
    common_english = set(en_to_io.keys()) & set(en_to_eo.keys())
    logging.info(f"  English words with BOTH: {len(common_english)}")
    
    # Build bilingual pairs
    logging.info("Building IO↔EO pairs...")
    bilingual_pairs = []
    
    for english_word in sorted(common_english):
        io_words = en_to_io[english_word]
        eo_words = en_to_eo[english_word]
        
        # Create all combinations
        for io_word in io_words:
            for eo_word in eo_words:
                pair = {
                    'io': io_word,
                    'eo': eo_word,
                    'source': 'en_wiktionary_via',
                    'via': english_word,
                    'confidence': 0.8  # High quality (fixed parser)
                }
                bilingual_pairs.append(pair)
    
    # Save results
    out_file.parent.mkdir(parents=True, exist_ok=True)
    write_json(out_file, bilingual_pairs)
    
    logging.info("")
    logging.info("=" * 70)
    logging.info("BUILD COMPLETE")
    logging.info("=" * 70)
    logging.info(f"English words matched: {len(common_english)}")
    logging.info(f"IO↔EO pairs created: {len(bilingual_pairs)}")
    logging.info(f"Output: {out_file}")
    logging.info("")
    
    # Show samples
    logging.info("Sample pairs:")
    for pair in bilingual_pairs[:20]:
        io = pair['io']
        eo = pair['eo']
        via = pair['via']
        logging.info(f"  {io:20s} → {eo:20s} [via \"{via}\"]")


def main():
    parser = argparse.ArgumentParser(
        description='Build IO↔EO bilingual pairs via English Wiktionary'
    )
    parser.add_argument(
        '--io-input',
        type=Path,
        required=True,
        help='Input JSON with English→Ido translations'
    )
    parser.add_argument(
        '--eo-input',
        type=Path,
        required=True,
        help='Input JSON with English→Esperanto translations'
    )
    parser.add_argument(
        '--out',
        type=Path,
        required=True,
        help='Output bilingual JSON file'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    # Configure logging
    configure_logging(2 if args.verbose else 1)
    
    # Build
    build_bilingual_via_english(
        io_file=args.io_input,
        eo_file=args.eo_input,
        out_file=args.out,
        verbose=args.verbose
    )


if __name__ == '__main__':
    main()

