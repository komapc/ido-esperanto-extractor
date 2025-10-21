"""
JSON utility functions for reading/writing standardized dictionary files.
"""
import json
from pathlib import Path
from datetime import datetime


def load_json(file_path):
    """Load JSON file and return data."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_json(data, file_path, indent=2):
    """Save data to JSON file with proper formatting."""
    file_path = Path(file_path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=indent)
    
    return file_path


def load_source_json(source_name, sources_dir='sources'):
    """Load a standardized source JSON file."""
    file_path = Path(sources_dir) / f'source_{source_name}.json'
    return load_json(file_path)


def save_source_json(data, source_name, sources_dir='sources'):
    """Save a standardized source JSON file."""
    file_path = Path(sources_dir) / f'source_{source_name}.json'
    return save_json(data, file_path)


def validate_source_json(data):
    """Validate that a source JSON has the required structure."""
    required_fields = ['metadata', 'entries']
    for field in required_fields:
        if field not in data:
            raise ValueError(f"Missing required field: {field}")
    
    required_metadata = ['source_name', 'file_type', 'origin', 'extraction', 'statistics']
    for field in required_metadata:
        if field not in data['metadata']:
            raise ValueError(f"Missing required metadata field: {field}")
    
    return True


def get_file_size_mb(file_path):
    """Get file size in megabytes."""
    size_bytes = Path(file_path).stat().st_size
    return size_bytes / (1024 * 1024)


def get_file_mtime(file_path):
    """Get file modification time as datetime."""
    mtime = Path(file_path).stat().st_mtime
    return datetime.fromtimestamp(mtime)

