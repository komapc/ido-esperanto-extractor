#!/usr/bin/env python3
import argparse
import logging
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from _common import write_json, configure_logging


def parse_monodix(path: Path) -> List[Dict[str, Any]]:
    tree = ET.parse(path)
    root = tree.getroot()
    entries: List[Dict[str, Any]] = []

    # Find main section
    for section in root.findall('.//section'):
        if section.get('id') == 'main':
            for e in section.findall('e'):
                lm = e.get('lm') or ''
                par = None
                par_el = e.find('par')
                if par_el is not None:
                    par = par_el.get('n')
                # POS may be encoded indirectly via paradigm; capture as-is
                entries.append({
                    'id': f'io:{lm}:x',
                    'lemma': lm,
                    'pos': None,
                    'language': 'io',
                    'senses': [],
                    'morphology': { 'paradigm': par, 'features': {} },
                    'provenance': [ { 'source': 'apertium_monodix', 'file': str(path) } ],
                })
    return entries


def main(argv: Iterable[str]) -> int:
    ap = argparse.ArgumentParser(description='Convert Apertium monodix to JSON entries')
    ap.add_argument('--input', type=Path, required=True, help='Path to apertium-ido.ido.dix')
    ap.add_argument('--out', type=Path, required=True, help='Output JSON path')
    ap.add_argument('-v', '--verbose', action='count', default=0)
    args = ap.parse_args(list(argv))

    configure_logging(args.verbose)
    entries = parse_monodix(args.input)
    write_json(args.out, entries)
    logging.info('Wrote %s (%d entries)', args.out, len(entries))
    return 0


if __name__ == '__main__':
    import sys
    raise SystemExit(main(sys.argv[1:]))


