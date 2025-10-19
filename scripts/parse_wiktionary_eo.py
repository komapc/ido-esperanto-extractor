#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

from _common import configure_logging
from wiktionary_parser import ParserConfig, parse_wiktionary


def main(argv):
    ap = argparse.ArgumentParser(description="Parse Esperanto Wiktionary for EO→IO pairs")
    ap.add_argument(
        "--input",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data/raw/eowiktionary-latest-pages-articles.xml.bz2",
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "work/eo_wikt_eo_io.json",
    )
    ap.add_argument("--limit", type=int)
    ap.add_argument("--progress-every", type=int, default=1000)
    ap.add_argument("-v", "--verbose", action="count", default=0)
    args = ap.parse_args(list(argv))

    configure_logging(args.verbose)
    cfg = ParserConfig(source_code="eo", target_code="io")
    parse_wiktionary(args.input, cfg, args.out, args.limit, progress_every=args.progress_every)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))




