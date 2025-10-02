"""Clean and normalize translations in ido_esperanto_simple.json.

Features:
- Back up the original file to ido_esperanto_simple.json.bak
- Normalize translation strings (remove leading markers, bullets, excessive spaces)
- Remove empty translation entries and deduplicate keeping order
- Write output atomically (write to temp then rename)

Usage:
    python3 clean_simple_json.py [--in file] [--out file]
"""

import argparse
import json
import os
import re
import shutil
import tempfile
from typing import List, Dict, Any


DEFAULT_PATH = 'ido_esperanto_simple.json'


def normalize_translation(s: str) -> str:
    if not s:
        return ''
    s = s.strip()
    # Remove leading list markers like '*:', '*', '-', etc.
    s = re.sub(r'^[\*\-\s:]+', '', s)
    # Remove stray bullets or punctuation at ends
    s = s.strip(' \t\n\r\f\v:;,.')
    # Replace multiple whitespace with single space
    s = re.sub(r'\s+', ' ', s)
    return s


def clean_entries(words: List[Dict[str, Any]]) -> int:
    changed = 0
    for w in words:
        orig = w.get('esperanto_translations', []) or []
        cleaned: List[str] = []
        for t in orig:
            n = normalize_translation(t)
            if n:
                cleaned.append(n)

        # deduplicate preserving order
        seen = set()
        out = []
        for t in cleaned:
            if t not in seen:
                seen.add(t)
                out.append(t)

        if out != orig:
            w['esperanto_translations'] = out
            changed += 1

    return changed


def atomic_write(path: str, data: Any) -> None:
    dirn = os.path.dirname(path) or '.'
    fd, tmp = tempfile.mkstemp(dir=dirn, prefix='.tmp_', suffix='.json')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        shutil.move(tmp, path)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except Exception:
                pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--in', dest='infile', default=DEFAULT_PATH,
                        help='Input JSON file (default: ido_esperanto_simple.json)')
    parser.add_argument('--out', dest='outfile', default=DEFAULT_PATH,
                        help='Output JSON file (by default overwrites input)')
    parser.add_argument('--backup', dest='backup', action='store_true',
                        help='Create a .bak backup of the input file')
    args = parser.parse_args()

    if not os.path.exists(args.infile):
        print(f'Input file not found: {args.infile}')
        return

    with open(args.infile, 'r', encoding='utf-8') as f:
        data = json.load(f)

    words = data.get('words', [])
    changed = clean_entries(words)

    if args.backup:
        bak = args.infile + '.bak'
        shutil.copyfile(args.infile, bak)
        print(f'Created backup: {bak}')

    atomic_write(args.outfile, data)
    print(f'Cleaned translations for {changed} entries, wrote {args.outfile}')


if __name__ == '__main__':
    main()
