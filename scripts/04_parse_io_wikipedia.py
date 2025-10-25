#!/usr/bin/env python3
"""
Orthogonal Parser: Ido Wikipedia

Parses Ido Wikipedia langlinks dump and produces standardized source JSON.
Extracts Ido→Esperanto mappings from article interlanguage links.

Input:  dumps/iowiki-latest-langlinks.sql.gz
Output: sources/source_io_wikipedia.json

Structure:
{
  "metadata": {...},
  "entries": [
    {
      "lemma": "kavalo",
      "translations": {"eo": ["ĉevalo"]},
      "morphology": {"paradigm": "o__n"},
      "source_page": "https://io.wikipedia.org/wiki/Kavalo"
    }
  ]
}
"""

import argparse
import sys
import re
import gzip
from pathlib import Path
from datetime import datetime

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent))

from _common import configure_logging, open_maybe_compressed
from utils.json_utils import save_json, get_file_size_mb
from utils.metadata import create_metadata, update_statistics


def parse_langlinks_sql(sql_file, limit=None):
    """
    Parse langlinks SQL dump to extract IO→EO mappings.
    
    SQL format:
    INSERT INTO `langlinks` VALUES (123,'eo','Ĉevalo'),(...);
    
    Returns list of (io_title, eo_title) tuples.
    """
    print(f"📖 Parsing langlinks SQL dump...")
    
    langlinks = []
    line_count = 0
    insert_count = 0
    
    # Pattern to match INSERT INTO statements
    insert_pattern = re.compile(r"INSERT INTO `langlinks` VALUES (.+);")
    # Pattern to match individual tuples
    tuple_pattern = re.compile(r"\((\d+),'([^']+)','([^']+)'\)")
    
    with open_maybe_compressed(sql_file, mode='rt', encoding='utf-8', errors='replace') as f:
        for line in f:
            line_count += 1
            
            if line_count % 10000 == 0:
                print(f"   Processed {line_count:,} lines, found {len(langlinks):,} IO→EO links...", end='\r')
            
            # Look for INSERT INTO statements
            match = insert_pattern.search(line)
            if not match:
                continue
            
            insert_count += 1
            values_str = match.group(1)
            
            # Extract all tuples from this INSERT
            for tuple_match in tuple_pattern.finditer(values_str):
                page_id = tuple_match.group(1)
                lang_code = tuple_match.group(2)
                target_title = tuple_match.group(3)
                
                # Only keep Esperanto links
                if lang_code == 'eo':
                    # We don't have the source IO title in langlinks, need to join with page table
                    # For now, store page_id and will need to resolve later
                    # Or we can use the simpler approach of extracting from pages dump
                    langlinks.append((page_id, lang_code, target_title))
                    
                    if limit and len(langlinks) >= limit:
                        break
            
            if limit and len(langlinks) >= limit:
                break
    
    print(f"\n   Found {len(langlinks):,} IO→EO langlinks from {insert_count:,} INSERT statements")
    return langlinks


def extract_wikipedia_vocab(dump_file, limit=None):
    """
    Extract Ido Wikipedia vocabulary with Esperanto translations.
    
    Uses pre-processed vocabulary with category-based classification:
    - vocabulary/unknown → regular words (n/adj/vblex based on morphology)
    - geography/people/organization → proper nouns (np)
    """
    print(f"📖 Extracting Wikipedia vocabulary with category-based classification...")
    
    # Check for pre-processed vocabulary and classifications
    parent_dir = Path(__file__).parent.parent
    processed_file = parent_dir / "wikipedia_vocabulary_merge_ready.json"
    classifications_file = parent_dir / "wikipedia_classifications.json"
    
    if not processed_file.exists():
        print(f"   ⚠️  Pre-processed vocabulary not found: {processed_file.name}")
        print(f"   Run: python3 scripts/extract_wikipedia_langlinks.py first")
        return []
    
    # Load vocabulary
    print(f"   Loading vocabulary: {processed_file.name}")
    import json
    with open(processed_file, 'r', encoding='utf-8') as f:
        vocab_data = json.load(f)
    
    # Load classifications if available
    classifications = {}
    if classifications_file.exists():
        print(f"   Loading classifications: {classifications_file.name}")
        with open(classifications_file, 'r', encoding='utf-8') as f:
            class_data = json.load(f)
        
        # Build word→classification mapping
        for classification, words_list in class_data.get('classifications', {}).items():
            for word_info in words_list:
                word = word_info.get('word')
                if word:
                    classifications[word] = classification
        
        print(f"   ✅ Loaded classifications for {len(classifications):,} words")
    else:
        print(f"   ⚠️  Classifications not found: {classifications_file.name}")
        print(f"   Run: python3 analyze_wikipedia_categories.py first")
        print(f"   Continuing without classifications (will use morphology only)")
    
    # Convert to entries list with proper POS tagging
    entries = []
    stats = {
        'vocabulary': 0,
        'unknown': 0,
        'geography': 0,
        'people': 0,
        'organization': 0,
        'temporal': 0,
        'no_classification': 0
    }
    
    words_list = vocab_data.get('words', [])
    print(f"   Processing {len(words_list):,} words...")
    
    for word_entry in words_list:
        ido_word = word_entry.get('ido_word', '')
        if not ido_word:
            continue
        
        eo_words = word_entry.get('esperanto_words', [])
        original_pos = word_entry.get('part_of_speech', '')
        
        # Get classification
        classification = classifications.get(ido_word, 'no_classification')
        
        # Determine POS based on classification (Option C)
        if classification in ['vocabulary', 'unknown']:
            # For vocabulary/unknown words, infer POS from morphology (NOT from original_pos)
            # The original_pos might have been 'np' from capitalization, but categories say it's regular vocab
            if original_pos in ['n', 'adj', 'vblex', 'adv']:
                # If original POS was a regular word type, keep it
                pos = original_pos
            else:
                # Otherwise, infer from word ending (Ido grammar rules)
                word_lower = ido_word.lower()
                if word_lower.endswith('ar') or word_lower.endswith('ir') or word_lower.endswith('or'):
                    pos = 'vblex'  # verb infinitive
                elif word_lower.endswith('a'):
                    pos = 'adj'  # adjective
                elif word_lower.endswith('e'):
                    pos = 'adv'  # adverb
                else:
                    pos = 'n'  # default to noun (most common for -o ending and others)
            stats[classification] += 1
        elif classification in ['geography', 'people', 'organization', 'temporal']:
            # Tag as proper noun
            pos = 'np'
            stats[classification] += 1
        else:
            # No classification - use original
            pos = original_pos if original_pos else 'n'
            stats['no_classification'] += 1
        
        entry = {
            'lemma': ido_word,
            'esperanto': eo_words,
            'pos': pos,
            'classification': classification,
            'original_pos': original_pos
        }
        entries.append(entry)
    
    # Print statistics
    print(f"\n   📊 Classification statistics:")
    print(f"      Regular words:")
    print(f"        • vocabulary: {stats['vocabulary']:,}")
    print(f"        • unknown: {stats['unknown']:,}")
    print(f"      Proper nouns (np):")
    print(f"        • geography: {stats['geography']:,}")
    print(f"        • people: {stats['people']:,}")
    print(f"        • organization: {stats['organization']:,}")
    print(f"        • temporal: {stats['temporal']:,}")
    if stats['no_classification'] > 0:
        print(f"      No classification: {stats['no_classification']:,}")
    
    total_regular = stats['vocabulary'] + stats['unknown']
    total_proper = stats['geography'] + stats['people'] + stats['organization'] + stats['temporal']
    print(f"\n   ✅ Total: {total_regular:,} regular + {total_proper:,} proper nouns = {len(entries):,} entries")
    
    return entries


def convert_to_standardized_format(entries_data, dump_file, script_path):
    """
    Convert extracted Wikipedia data to standardized format.
    """
    # Create metadata
    metadata = create_metadata(
        source_name="io_wikipedia",
        dump_file=dump_file,
        script_path=script_path,
        version="2.0"
    )
    
    # Convert entries to standardized format
    entries = []
    total_entries = 0
    with_translations = 0
    with_morphology = 0
    
    for entry_data in entries_data:
        lemma = entry_data.get('lemma', '').strip()
        if not lemma:
            continue
        
        total_entries += 1
        
        # Extract translations
        translations = {}
        eo_words = entry_data.get('esperanto', [])
        if eo_words:
            translations['eo'] = eo_words if isinstance(eo_words, list) else [eo_words]
            with_translations += 1
        
        # Extract POS (from classification-based tagging)
        pos = entry_data.get('pos')
        classification = entry_data.get('classification', 'unknown')
        
        # Extract morphology
        morphology = {}
        morph = entry_data.get('morphology')
        if morph:
            # Morphology might be a POS tag or paradigm
            if isinstance(morph, str):
                morphology = {"paradigm": morph}
            elif isinstance(morph, dict):
                morphology = morph
            with_morphology += 1
        
        # Create standardized entry
        entry = {
            "lemma": lemma,
            "pos": pos,
            "translations": translations,
            "morphology": morphology,
            "source_page": f"https://io.wikipedia.org/wiki/{lemma.replace(' ', '_')}",
            "classification": classification
        }
        
        # Remove empty fields
        if not entry['pos']:
            del entry['pos']
        if not entry['translations']:
            del entry['translations']
        if not entry['morphology']:
            del entry['morphology']
        if not entry.get('classification'):
            del entry['classification']
        
        entries.append(entry)
    
    # Update metadata statistics
    update_statistics(metadata, total_entries, with_translations, with_morphology)
    
    return {
        "metadata": metadata,
        "entries": entries
    }


def main(argv):
    ap = argparse.ArgumentParser(description="Parse Ido Wikipedia (Orthogonal)")
    ap.add_argument(
        "--dump",
        type=Path,
        help="Path to langlinks SQL dump file"
    )
    ap.add_argument(
        "--output",
        type=Path,
        default=Path("sources/source_io_wikipedia.json"),
        help="Output path for standardized JSON"
    )
    ap.add_argument("--limit", type=int, help="Limit number of entries (for testing)")
    ap.add_argument("-v", "--verbose", action="count", default=0)
    args = ap.parse_args(list(argv))
    
    configure_logging(args.verbose)
    
    # Find dump file
    if args.dump:
        dump_file = args.dump
    else:
        # Look in dumps/ directory
        dumps_dir = Path(__file__).parent.parent / "dumps"
        candidates = list(dumps_dir.glob("iowiki-*.sql.gz"))
        if not candidates:
            # Fallback to old location
            dump_file = Path(__file__).parent.parent / "iowiki-latest-langlinks.sql.gz"
        else:
            # Use most recent
            dump_file = max(candidates, key=lambda p: p.stat().st_mtime)
    
    if not dump_file.exists():
        print(f"❌ Error: Dump file not found: {dump_file}")
        print(f"   Run: ./scripts/download_dumps.sh")
        print(f"   Note: Wikipedia is OPTIONAL and can be skipped")
        return 1
    
    print(f"📖 Parsing Ido Wikipedia")
    print(f"   Input: {dump_file}")
    print(f"   Size: {get_file_size_mb(dump_file):.1f} MB")
    print(f"   Output: {args.output}")
    
    try:
        # Extract Wikipedia vocabulary
        entries_data = extract_wikipedia_vocab(dump_file, limit=args.limit)
        
        # Convert to standardized format
        print(f"\n📦 Converting to standardized format...")
        standardized_data = convert_to_standardized_format(
            entries_data,
            dump_file,
            Path(__file__)
        )
        
        # Save standardized output
        save_json(standardized_data, args.output)
        
        # Print statistics
        stats = standardized_data['metadata']['statistics']
        print(f"\n✅ Parsing complete!")
        print(f"   Total entries: {stats['total_entries']:,}")
        print(f"   With EO translations: {stats['with_translations']:,}")
        print(f"   With morphology: {stats['with_morphology']:,}")
        print(f"   Output size: {get_file_size_mb(args.output):.1f} MB")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

