"""
Shared base functions for all Wiktionary parsers.

Provides common conversion logic to reduce duplication across parsers.
"""

import re
import tempfile
from pathlib import Path
from utils.json_utils import save_json, get_file_size_mb
from utils.metadata import create_metadata, update_statistics


def convert_wiktionary_to_unified(old_format_data, source_name, url_base, dump_file, script_path, confidence=1.0):
    """
    Convert wiktionary_parser output to unified JSON format.
    
    Unified format specification:
    - Each entry has "source" field
    - Translations are array of objects with "term", "lang", "confidence", "source"
    - Metadata fields go in "metadata" object
    - Confidence: 1.0 for wiktionary, 0.9 for wikipedia
    
    Args:
        old_format_data: Output from wiktionary_parser
        source_name: e.g., "io_wiktionary", "eo_wiktionary"
        url_base: e.g., "https://io.wiktionary.org/wiki/"
        dump_file: Path to dump file
        script_path: Path to parser script
        confidence: Confidence score for translations (default 1.0)
    
    Returns:
        dict: {"metadata": {...}, "entries": [...]} in unified format
    """
    # Create metadata
    metadata = create_metadata(
        source_name=source_name,
        dump_file=dump_file,
        script_path=script_path,
        version="3.0"  # Unified format version
    )
    
    # Handle both list and dict formats
    if isinstance(old_format_data, dict):
        entries_list = old_format_data.get('words', old_format_data.get('entries', []))
    else:
        entries_list = old_format_data
    
    # Convert entries to unified format
    entries = []
    total_entries = 0
    with_translations = 0
    with_morphology = 0
    
    for entry_data in entries_list:
        lemma = entry_data.get('lemma', '').strip()
        if not lemma:
            continue
        
        total_entries += 1
        
        # Extract translations from senses - convert to unified format
        translations_unified = []
        seen_translations = set()  # Track (term, lang) to avoid duplicates
        
        if 'senses' in entry_data:
            for sense in entry_data['senses']:
                if 'translations' in sense:
                    for trans in sense['translations']:
                        lang = trans.get('lang', '')
                        term = trans.get('term', '').strip()
                        
                        # Clean up term (extract from markup)
                        if term:
                            term = re.sub(r'\s*Kategorio:.*', '', term)
                            # Extract content from [[link]] or [[link|display]] - keep the term, not remove it
                            term = re.sub(r'\[\[([^\]|]+)(?:\|[^\]]+)?\]\]', r'\1', term)
                            term = term.strip()
                        
                        if lang and term:
                            trans_key = (term, lang)
                            if trans_key not in seen_translations:
                                seen_translations.add(trans_key)
                                translations_unified.append({
                                    "term": term,
                                    "lang": lang,
                                    "confidence": confidence,
                                    "source": source_name
                                })
        
        if translations_unified:
            with_translations += 1
        
        # Extract morphology
        morphology = {}
        if 'morphology' in entry_data and entry_data['morphology']:
            morph_data = entry_data['morphology']
            if isinstance(morph_data, dict) and morph_data.get('paradigm'):
                morphology = {"paradigm": morph_data['paradigm']}
                with_morphology += 1
        
        # Create unified entry
        entry = {
            "lemma": lemma,
            "source": source_name,
            "translations": translations_unified,
        }
        
        # Add optional fields
        if entry_data.get('pos'):
            entry['pos'] = entry_data['pos']
        
        if morphology:
            entry['morphology'] = morphology
        
        # Add metadata (source_page, etc.)
        entry['metadata'] = {
            "source_page": f"{url_base}{lemma}"
        }
        
        entries.append(entry)
    
    # Update metadata statistics
    update_statistics(metadata, total_entries, with_translations, with_morphology)
    
    return {
        "metadata": metadata,
        "entries": entries
    }


# Keep old function name for backward compatibility
def convert_wiktionary_to_standardized(old_format_data, source_name, url_base, dump_file, script_path):
    """Legacy wrapper - calls convert_wiktionary_to_unified."""
    return convert_wiktionary_to_unified(old_format_data, source_name, url_base, dump_file, script_path, confidence=1.0)


def find_dump_file(dump_pattern, dumps_dir, fallback_paths):
    """
    Find dump file in standard locations.
    
    Args:
        dump_pattern: Glob pattern (e.g., "iowiktionary-*.xml.bz2")
        dumps_dir: Path to dumps/ directory
        fallback_paths: List of fallback paths to try
    
    Returns:
        Path: Path to dump file or None if not found
    """
    # Look in dumps/ directory first
    candidates = list(dumps_dir.glob(dump_pattern))
    if candidates:
        # Use most recent
        return max(candidates, key=lambda p: p.stat().st_mtime)
    
    # Try fallback paths
    for fallback in fallback_paths:
        if fallback.exists():
            candidates = list(fallback.glob(dump_pattern))
            if candidates:
                # Use most recent
                return max(candidates, key=lambda p: p.stat().st_mtime)
    
    return None


def parse_wiktionary_wrapper(dump_file, parser_config, output_file, args, 
                            source_name, url_base, script_path, confidence=1.0):
    """
    Wrapper for parse_wiktionary that handles temp files and conversion.
    
    Args:
        dump_file: Path to Wiktionary dump
        parser_config: ParserConfig object
        output_file: Path to output source JSON
        args: Command-line arguments
        source_name: Source name for metadata
        url_base: Base URL for source_page links
        script_path: Path to parser script for metadata
        confidence: Confidence score for translations (default 1.0)
    
    Returns:
        int: 0 on success, 1 on error
    """
    from wiktionary_parser import parse_wiktionary
    
    print(f"📖 Parsing {source_name}")
    print(f"   Input: {dump_file}")
    print(f"   Size: {get_file_size_mb(dump_file):.1f} MB")
    print(f"   Output: {output_file}")
    
    # Use temp file for wiktionary_parser output
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp:
        temp_output = Path(tmp.name)
    
    try:
        # Parse using existing logic
        parse_wiktionary(dump_file, parser_config, temp_output, args.limit, 
                        progress_every=args.progress_every, skip_pivot=True)
        
        # Load old format
        import json
        with open(temp_output, 'r', encoding='utf-8') as f:
            old_data = json.load(f)
        
        # Convert to unified format
        print(f"\n📦 Converting to unified format...")
        unified_data = convert_wiktionary_to_unified(
            old_data, source_name, url_base, dump_file, script_path, confidence
        )
        
        # Save unified output
        save_json(unified_data, output_file)
        
        # Print statistics
        stats = unified_data['metadata']['statistics']
        print(f"\n✅ Parsing complete!")
        print(f"   Total entries: {stats['total_entries']:,}")
        print(f"   With translations: {stats['with_translations']:,}")
        print(f"   With morphology: {stats['with_morphology']:,}")
        print(f"   Output size: {get_file_size_mb(output_file):.1f} MB")
        
        return 0
        
    finally:
        # Clean up temp file
        if temp_output.exists():
            temp_output.unlink()
