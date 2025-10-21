"""
Metadata generation and management utilities.
"""
from datetime import datetime
from pathlib import Path


def create_metadata(source_name, dump_file, dump_date=None, script_path=None, version="2.0"):
    """
    Create standardized metadata block for source JSON.
    
    Args:
        source_name: Name of the source (e.g., 'io_wiktionary')
        dump_file: Path to the dump file
        dump_date: Date of the dump (YYYY-MM-DD) or None to extract from filename
        script_path: Path to the parser script
        version: Version of the parser
    
    Returns:
        dict: Standardized metadata block
    """
    dump_path = Path(dump_file)
    
    # Extract dump date from filename if not provided
    if dump_date is None:
        # Try to extract from filename like "iowiktionary-20251021-..."
        filename = dump_path.name
        if 'latest' in filename:
            # Use file modification time
            mtime = dump_path.stat().st_mtime
            dump_date = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d')
        else:
            # Try to parse date from filename
            import re
            match = re.search(r'(\d{8})', filename)
            if match:
                date_str = match.group(1)
                dump_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
            else:
                dump_date = datetime.now().strftime('%Y-%m-%d')
    
    metadata = {
        "source_name": source_name,
        "file_type": "source_json",
        "origin": {
            "dump_file": dump_path.name,
            "dump_date": dump_date,
            "dump_size_mb": round(dump_path.stat().st_size / (1024 * 1024), 2)
        },
        "extraction": {
            "date": datetime.now().isoformat(),
            "script": str(script_path) if script_path else "unknown",
            "version": version
        },
        "statistics": {
            "total_entries": 0,
            "with_translations": 0,
            "with_morphology": 0
        }
    }
    
    return metadata


def update_statistics(metadata, total_entries, with_translations=0, with_morphology=0):
    """Update the statistics section of metadata."""
    metadata['statistics'] = {
        "total_entries": total_entries,
        "with_translations": with_translations,
        "with_morphology": with_morphology
    }
    return metadata


def create_merge_metadata(source_files, total_words, source_stats):
    """
    Create metadata for merged output files.
    
    Args:
        source_files: List of source JSON files that were merged
        total_words: Total unique words in merged output
        source_stats: Dict of source_name → entry count
    
    Returns:
        dict: Metadata for merged output
    """
    metadata = {
        "file_type": "merged_output",
        "creation_date": datetime.now().isoformat(),
        "version": "2.0",
        "sources": source_files,
        "statistics": {
            "total_unique_words": total_words,
            "source_breakdown": source_stats
        }
    }
    
    return metadata

