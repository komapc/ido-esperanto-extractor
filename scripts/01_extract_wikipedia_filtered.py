#!/usr/bin/env python3
"""
Stage 1: Wikipedia XML → Filtered JSON
Convert zipped XML dump to filtered JSON with categories and relevance filtering.
"""
import argparse
import logging
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Tuple

from _common import open_maybe_compressed, write_json, ensure_dir, configure_logging

# Precompiled regex patterns for performance
EXCLUDE_TITLE_RE = [
    re.compile(r"^:|^Talk:|^User:|^File:|^Image:|^Template:|^Category:|^Help:|^Portal:|^Wikipedia:", re.IGNORECASE),
    re.compile(r"^[A-Za-z]$"),
]

# Categories that indicate relevant articles
RELEVANT_CATEGORIES = [
    re.compile(r"kategorio:.*geografio", re.IGNORECASE),
    re.compile(r"kategorio:.*historio", re.IGNORECASE),
    re.compile(r"kategorio:.*scienco", re.IGNORECASE),
    re.compile(r"kategorio:.*teknologio", re.IGNORECASE),
    re.compile(r"kategorio:.*kulturo", re.IGNORECASE),
    re.compile(r"kategorio:.*persono", re.IGNORECASE),
    re.compile(r"kategorio:.*urbo", re.IGNORECASE),
    re.compile(r"kategorio:.*lando", re.IGNORECASE),
    re.compile(r"kategorio:.*rivero", re.IGNORECASE),
    re.compile(r"kategorio:.*monto", re.IGNORECASE),
]


def _child(elem: ET.Element, local: str):
    """Find child element by local name."""
    for ch in list(elem):
        if isinstance(ch.tag, str) and ch.tag.endswith(local):
            return ch
    return None


def is_article_title(title: str) -> bool:
    """Check if title represents a valid article (not meta pages)."""
    if not title:
        return False
    for pat in EXCLUDE_TITLE_RE:
        if pat.search(title):
            return False
    return True


def has_relevant_content(text: str) -> bool:
    """Check if article has relevant content (not just stubs or redirects)."""
    if not text:
        return False
    
    # Skip very short articles (likely stubs)
    if len(text) < 100:
        return False
    
    # Skip redirects
    if text.strip().startswith('#REDIRECT') or text.strip().startswith('#redirect'):
        return False
    
    # Skip disambiguation pages
    if 'disambiguation' in text.lower() or 'disambig' in text.lower():
        return False
    
    # Look for category links in the text
    category_pattern = r"\[\[kategorio:([^\]]+)\]\]"
    categories = re.findall(category_pattern, text, re.IGNORECASE)
    
    # If it has categories, it's likely a real article
    if categories:
        return True
    
    # If no categories but substantial content, include it
    if len(text) > 500:
        return True
    
    return False


def iter_pages(xml_path: Path) -> Iterator[Tuple[str, str, str]]:
    """Iterate over Wikipedia pages from XML dump."""
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


def extract_filtered_titles(xml_path: Path, out_json: Path) -> None:
    """Extract and filter Wikipedia titles with category-based relevance."""
    logging.info("Stage 1: Extracting filtered Ido Wikipedia titles from %s", xml_path)
    ensure_dir(out_json.parent)
    
    items: List[Dict[str, str]] = []
    count = 0
    filtered_count = 0
    
    for title, ns, text in iter_pages(xml_path):
        if ns != "0":  # Only main namespace articles
            continue
        if not is_article_title(title):
            continue
        
        # Check if article has relevant content
        if has_relevant_content(text):
            items.append({
                "lemma": title, 
                "pos": "propn", 
                "language": "io", 
                "provenance": [{"source": "io_wikipedia", "page": title}],
                "categories": extract_categories(text),
                "text_length": len(text)
            })
            filtered_count += 1
        
        count += 1
        if count % 5000 == 0:
            logging.info("Processed %d pages, filtered %d relevant articles...", count, filtered_count)
    
    write_json(out_json, items)
    logging.info("Stage 1 complete: Wrote %s (%d filtered items from %d total pages)", 
                out_json, len(items), count)


def extract_categories(text: str) -> List[str]:
    """Extract category names from article text."""
    category_pattern = r"\[\[kategorio:([^\]]+)\]\]"
    categories = re.findall(category_pattern, text, re.IGNORECASE)
    return [cat.strip() for cat in categories]


def main(argv: Iterable[str]) -> int:
    ap = argparse.ArgumentParser(description="Stage 1: Extract filtered Ido Wikipedia titles")
    ap.add_argument(
        "--input",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data/raw/iowiki-latest-pages-articles.xml.bz2",
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "work/io_wikipedia_filtered.json",
    )
    ap.add_argument("-v", "--verbose", action="count", default=0)
    args = ap.parse_args(list(argv))

    configure_logging(args.verbose)
    
    # Check if output already exists (resumability)
    if args.out.exists():
        logging.info("Output file %s already exists, skipping Stage 1", args.out)
        return 0
    
    extract_filtered_titles(args.input, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
