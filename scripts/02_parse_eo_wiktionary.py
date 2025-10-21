#!/usr/bin/env python3
"""
Orthogonal Parser: Esperanto Wiktionary

Parses Esperanto Wiktionary dump and produces standardized source JSON.

Input:  dumps/eowiktionary-latest-pages-articles.xml.bz2
Output: sources/source_eo_wiktionary.json
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from _common import configure_logging
from wiktionary_parser import ParserConfig
from utils.parser_base import parse_wiktionary_wrapper, find_dump_file


def main(argv):
    ap = argparse.ArgumentParser(description="Parse Esperanto Wiktionary (Orthogonal)")
    ap.add_argument("--dump", type=Path, help="Path to Wiktionary dump file")
    ap.add_argument("--output", type=Path, default=Path("sources/source_eo_wiktionary.json"))
    ap.add_argument("--limit", type=int, help="Limit number of pages to parse (for testing)")
    ap.add_argument("--progress-every", type=int, default=1000)
    ap.add_argument("-v", "--verbose", action="count", default=0)
    args = ap.parse_args(list(argv))
    
    configure_logging(args.verbose)
    
    # Find dump file
    if not args.dump:
        base_dir = Path(__file__).parent.parent
        args.dump = find_dump_file(
            "eowiktionary-*.xml.bz2",
            base_dir / "dumps",
            [
                base_dir / "eowiktionary-latest-pages-articles.xml.bz2",
                base_dir / "data" / "raw" / "eowiktionary-latest-pages-articles.xml.bz2"
            ]
        )
    
    if not args.dump or not args.dump.exists():
        print(f"❌ Error: Dump file not found")
        print(f"   Run: ./scripts/00_download_dumps.sh")
        return 1
    
    # Parse and convert
    cfg = ParserConfig(source_code="eo", target_code="io")
    return parse_wiktionary_wrapper(
        args.dump, cfg, args.output, args,
        source_name="eo_wiktionary",
        url_base="https://eo.wiktionary.org/wiki/",
        script_path=Path(__file__)
    )


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

