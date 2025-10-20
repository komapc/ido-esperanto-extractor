#!/usr/bin/env python3
import argparse
import sys
import logging
from pathlib import Path

from _common import configure_logging
from wiktionary_parser import parse_wiktionary


def main(argv) -> int:
    ap = argparse.ArgumentParser(description="Parse French Wiktionary dump for IO/EO translations")
    ap.add_argument("--input", type=Path, default=Path(__file__).resolve().parents[1] / "data/raw/frwiktionary-latest-pages-articles.xml.bz2")
    ap.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] / "work/fr_wikt_fr_xx.json")
    ap.add_argument("--progress-every", type=int, default=1000, help="Log progress every N pages")
    ap.add_argument("-v", "--verbose", action="count", default=0)
    args = ap.parse_args(argv)

    configure_logging(args.verbose)
    
    from wiktionary_parser import ParserConfig
    cfg = ParserConfig(
        source_code="fr",
        target_code="io,eo"
    )
    
    logging.info("Parsing fr → io/eo from %s", args.input)
    parse_wiktionary(
        xml_path=args.input,
        cfg=cfg,
        out_json=args.output,
        progress_every=args.progress_every
    )
    
    from _common import read_json
    entries = read_json(args.output)
    logging.info("Wrote %s (%d entries)", args.output, len(entries))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
