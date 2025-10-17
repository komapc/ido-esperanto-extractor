#!/usr/bin/env python3
import argparse
import collections
import logging
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Counter, Dict, Iterable, Tuple

from _common import ensure_dir, write_json, configure_logging, open_maybe_compressed

try:
    import mwparserfromhell  # type: ignore
except Exception:  # pragma: no cover
    mwparserfromhell = None  # type: ignore


TITLE_TAG = "{http://www.mediawiki.org/xml/export-0.10/}title"
NS_TAG = "{http://www.mediawiki.org/xml/export-0.10/}ns"
REV_TAG = "{http://www.mediawiki.org/xml/export-0.10/}revision"
TEXT_TAG = "{http://www.mediawiki.org/xml/export-0.10/}text"


WIKITEXT_LINK_RE = re.compile(r"\[\[(?:[^\]|]*\|)?([^\]]+)\]\]")
HTML_TAG_RE = re.compile(r"<[^>]+>")
TEMPLATE_RE = re.compile(r"\{\{[^\}]*\}\}")
REF_RE = re.compile(r"<ref[^>]*>.*?</ref>", re.DOTALL)
FILE_RE = re.compile(r"\[\[(?:File|Fajlo|Dosiero|Datei|Archivo):[^\]]*\]\]", re.IGNORECASE)
# Avoid using Unicode property classes (\p{L}) not supported by Python's re.


def strip_wikitext(text: str) -> str:
    if not text:
        return ""
    if mwparserfromhell is not None:
        try:
            return mwparserfromhell.parse(text).strip_code(normalize=True, collapse=True)
        except Exception:
            pass
    text = REF_RE.sub(" ", text)
    text = TEMPLATE_RE.sub(" ", text)
    text = FILE_RE.sub(" ", text)
    # Keep display text of links
    text = WIKITEXT_LINK_RE.sub(r"\1", text)
    text = HTML_TAG_RE.sub(" ", text)
    return text


def tokenize(text: str) -> Iterable[str]:
    # Normalize and split on non-letters; keep Unicode letters
    text = text.lower()
    # Python's default regex lacks \p{L}, but many letters are matched by \w; fallback split
    # Replace non-letter characters with space
    text = re.sub(r"[^\w]+", " ", text, flags=re.UNICODE)
    for tok in text.split():
        if len(tok) < 2:
            continue
        yield tok


def iter_wiki_pages(xml_path: Path) -> Iterable[Tuple[str, str, str]]:
    # Yields (title, ns, text)
    with open_maybe_compressed(xml_path, mode="rt", encoding="utf-8") as fh:
        context = ET.iterparse(fh, events=("end",))
        for event, elem in context:
            if elem.tag.endswith("page"):
                # Extract child nodes
                title_elem = elem.find(TITLE_TAG)
                ns_elem = elem.find(NS_TAG)
                rev_elem = elem.find(REV_TAG)
                text_elem = rev_elem.find(TEXT_TAG) if rev_elem is not None else None
                title = title_elem.text if title_elem is not None else ""
                ns = ns_elem.text if ns_elem is not None else ""
                content = text_elem.text if text_elem is not None else ""
                yield title or "", ns or "", content or ""
                elem.clear()


def build_frequency(xml_path: Path, out_json: Path) -> None:
    logging.info("Building frequency from %s", xml_path)
    ensure_dir(out_json.parent)
    counts: Counter[str] = collections.Counter()
    num_pages = 0
    for title, ns, text in iter_wiki_pages(xml_path):
        if ns != "0":  # main/article namespace only
            continue
        num_pages += 1
        plain = strip_wikitext(text)
        counts.update(tokenize(plain))
        if num_pages % 500 == 0:
            logging.info("Processed %d pages...", num_pages)

    logging.info("Finished pages: %d, unique tokens: %d", num_pages, len(counts))
    # Build ranked list
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    out = [
        {"token": tok, "count": int(cnt), "rank": idx + 1}
        for idx, (tok, cnt) in enumerate(ranked)
    ]
    write_json(out_json, {"source": str(xml_path), "items": out})
    logging.info("Wrote %s", out_json)


def main(argv: Iterable[str]) -> int:
    ap = argparse.ArgumentParser(description="Build frequency list from Ido Wikipedia dump")
    ap.add_argument(
        "--input",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data/raw/iowiki-latest-pages-articles.xml.bz2",
        help="Path to iowiki pages-articles XML (.bz2)",
    )
    ap.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "work/io_wiki_frequency.json",
        help="Output JSON path",
    )
    ap.add_argument("-v", "--verbose", action="count", default=0)
    args = ap.parse_args(list(argv))

    configure_logging(args.verbose)
    build_frequency(args.input, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))


