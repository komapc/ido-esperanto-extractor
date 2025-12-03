#!/usr/bin/env python3
"""
Validate JSON files against the unified schema.

Fails hard on any validation error - no silent errors.
"""

import json
import sys
from pathlib import Path
from typing import Dict, Any, List, Tuple

try:
    import jsonschema
except ImportError:
    print("ERROR: jsonschema not installed. Install with: pip install jsonschema")
    sys.exit(1)


def load_schema(schema_path: Path) -> Dict[str, Any]:
    """Load JSON schema."""
    with open(schema_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def validate_file(file_path: Path, schema: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Validate a JSON file against the schema.
    
    Returns:
        (is_valid, list_of_errors)
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return False, [f"Invalid JSON: {e}"]
    
    validator = jsonschema.Draft7Validator(schema)
    errors = list(validator.iter_errors(data))
    
    if errors:
        error_messages = []
        for error in errors:
            path = '.'.join(str(p) for p in error.path)
            error_messages.append(f"  {path}: {error.message}")
        return False, error_messages
    
    return True, []


def main():
    script_dir = Path(__file__).parent
    data_dir = script_dir.parent
    schema_path = data_dir / 'schema.json'
    
    if not schema_path.exists():
        print(f"ERROR: Schema not found: {schema_path}")
        sys.exit(1)
    
    schema = load_schema(schema_path)
    
    if len(sys.argv) < 2:
        print("Usage: validate_schema.py <json_file> [json_file2 ...]")
        print("       validate_schema.py --all  # Validate all source_*.json files")
        sys.exit(1)
    
    if sys.argv[1] == '--all':
        sources_dir = data_dir / 'sources'
        if not sources_dir.exists():
            print(f"ERROR: Sources directory not found: {sources_dir}")
            sys.exit(1)
        
        json_files = list(sources_dir.glob('source_*.json'))
        if not json_files:
            print(f"WARNING: No source_*.json files found in {sources_dir}")
            sys.exit(0)
    else:
        json_files = [Path(f) for f in sys.argv[1:]]
    
    all_valid = True
    
    for json_file in json_files:
        if not json_file.exists():
            print(f"ERROR: File not found: {json_file}")
            all_valid = False
            continue
        
        is_valid, errors = validate_file(json_file, schema)
        
        if is_valid:
            print(f"✅ {json_file.name}: Valid")
        else:
            print(f"❌ {json_file.name}: INVALID")
            for error in errors:
                print(error)
            all_valid = False
    
    if not all_valid:
        sys.exit(1)
    
    print("\n✅ All files valid!")


if __name__ == '__main__':
    main()

