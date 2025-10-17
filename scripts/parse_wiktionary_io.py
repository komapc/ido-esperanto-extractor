#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

from _common import configure_logging
from wiktionary_parser import ParserConfig, parse_wiktionary


def main(argv):
    ap = argparse.ArgumentParser(description="Parse Ido Wiktionary for IO→EO pairs")
    ap.add_argument(
        "--input",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data/raw/iowiktionary-latest-pages-articles.xml.bz2",
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "work/io_wikt_io_eo.json",
    )
    ap.add_argument("--limit", type=int)
    ap.add_argument("-v", "--verbose", action="count", default=0)
    args = ap.parse_args(list(argv))

    configure_logging(args.verbose)
    cfg = ParserConfig(source_code="io", target_code="eo")
    parse_wiktionary(args.input, cfg, args.out, args.limit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))


