#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

from _common import configure_logging
from wiktionary_parser import ParserConfig, parse_wiktionary


def main(argv):
    ap = argparse.ArgumentParser(description="Parse English Wiktionary for EN→(IO/EO) hints")
    ap.add_argument(
        "--input",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data/raw/enwiktionary-latest-pages-articles.xml.bz2",
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "work/en_wikt_en_xx.json",
    )
    ap.add_argument("--target", choices=["io", "eo", "both"], default="io",
                   help="Target language(s) to extract")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--progress-every", type=int, default=1000)
    ap.add_argument("-v", "--verbose", action="count", default=0)
    args = ap.parse_args(list(argv))

    configure_logging(args.verbose)
    
    # Parse once if targeting both languages
    if args.target == "both":
        cfg = ParserConfig(source_code="en", target_code="io")
        parse_wiktionary(args.input, cfg, args.out, args.limit, progress_every=args.progress_every)
    else:
        cfg = ParserConfig(source_code="en", target_code=args.target)
        parse_wiktionary(args.input, cfg, args.out, args.limit, progress_every=args.progress_every)
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))


