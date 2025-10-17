#!/usr/bin/env python3
import argparse
import logging
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Tuple

from _common import open_maybe_compressed, write_json, ensure_dir, configure_logging


def _child(elem: ET.Element, local: str):
    for ch in list(elem):
        if isinstance(ch.tag, str) and ch.tag.endswith(local):
            return ch
    return None


EXCLUDE_TITLE_RE = [
    re.compile(r"^:|^Talk:|^User:|^File:|^Image:|^Template:|^Category:|^Help:|^Portal:|^Wikipedia:", re.IGNORECASE),
    re.compile(r"^[A-Za-z]$"),
]


def is_article_title(title: str) -> bool:
    if not title:
        return False
    for pat in EXCLUDE_TITLE_RE:
        if pat.search(title):
            return False
    return True


def iter_pages(xml_path: Path) -> Iterator[Tuple[str, str, str]]:
    with open_maybe_compressed(xml_path, mode="rt", encoding="utf-8") as fh:
        context = ET.iterparse(fh, events=("end",))
        for event, elem in context:
            if isinstance(elem.tag, str) and elem.tag.endswith("page"):
                title_el = _child(elem, "title")
                ns_el = _child(elem, "ns")
                rev_el = _child(elem, "revision")
                text_el = _child(rev_el, "text") if rev_el is not None else None
                title = title_el.text if title_el is not None else ""
                text = text_el.text if text_el is not None else ""
                ns = ns_el.text if ns_el is not None else ""
                yield title or "", ns or "", text or ""
                elem.clear()


def extract_titles(xml_path: Path, out_json: Path) -> None:
    logging.info("Extracting Ido Wikipedia titles from %s", xml_path)
    ensure_dir(out_json.parent)
    items: List[Dict[str, str]] = []
    count = 0
    for title, ns, text in iter_pages(xml_path):
        if ns != "0":
            continue
        if not is_article_title(title):
            continue
        items.append({"lemma": title, "pos": "propn", "language": "io", "provenance": [{"source": "io_wikipedia", "page": title}]})
        count += 1
        if count % 2000 == 0:
            logging.info("Processed %d titles...", count)
    write_json(out_json, items)
    logging.info("Wrote %s (%d items)", out_json, len(items))


def main(argv: Iterable[str]) -> int:
    ap = argparse.ArgumentParser(description="Extract Ido Wikipedia article titles as vocabulary candidates")
    ap.add_argument(
        "--input",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data/raw/iowiki-latest-pages-articles.xml.bz2",
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "work/io_wiki_vocab.json",
    )
    ap.add_argument("-v", "--verbose", action="count", default=0)
    args = ap.parse_args(list(argv))

    configure_logging(args.verbose)
    extract_titles(args.input, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))


