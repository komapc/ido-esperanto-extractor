#!/usr/bin/env python3
"""Sort Apertium .dix files alphabetically by lemma attribute."""

import argparse
import logging
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Iterable, List, Tuple

from _common import configure_logging


def sort_dix_file(dix_path: Path) -> None:
    """Sort entries in an Apertium .dix file alphabetically by lm attribute."""
    logging.info("Sorting %s", dix_path)
    
    tree = ET.parse(dix_path)
    root = tree.getroot()
    
    # Find <section id="main">
    main = None
    for sec in root.iter("section"):
        if sec.get("id") == "main":
            main = sec
            break
    
    if main is None:
        logging.warning("No main section found in %s", dix_path)
        return
    
    # Collect all entries with their preceding comments/whitespace
    groups: List[Tuple[str, List]] = []
    current_group = []
    
    for node in list(main):
        tag = node.tag if isinstance(node.tag, str) else None
        
        if tag == 'e':
            # This is an entry - finalize current group
            lm = node.get('lm', '')
            current_group.append(node)
            groups.append((lm.lower(), current_group))
            current_group = []
        else:
            # Comments, whitespace, etc. - attach to next entry
            current_group.append(node)
    
    # Handle any trailing non-entry nodes
    if current_group:
        groups.append(("zzz", current_group))  # Sort to end
    
    # Sort by lemma (case-insensitive)
    groups.sort(key=lambda x: x[0])
    
    # Rebuild main section
    main.clear()
    for _, group in groups:
        for node in group:
            main.append(node)
    
    # Write sorted XML
    tree.write(dix_path, encoding='UTF-8', xml_declaration=True)
    logging.info("Sorted and saved %s", dix_path)


def main(argv: Iterable[str]) -> int:
    ap = argparse.ArgumentParser(description="Sort Apertium .dix files alphabetically")
    ap.add_argument("files", type=Path, nargs="+", help="DIX files to sort")
    ap.add_argument("-v", "--verbose", action="count", default=0)
    args = ap.parse_args(list(argv))
    
    configure_logging(args.verbose)
    
    for dix_file in args.files:
        if not dix_file.exists():
            logging.error("File not found: %s", dix_file)
            continue
        sort_dix_file(dix_file)
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

