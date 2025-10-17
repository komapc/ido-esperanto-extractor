#!/usr/bin/env python3
import argparse
import html
import json
import logging
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Tuple

from _common import open_maybe_compressed, write_json, ensure_dir, configure_logging

try:
    import mwparserfromhell  # type: ignore
except Exception:  # pragma: no cover
    mwparserfromhell = None  # type: ignore


def _child(elem: ET.Element, local: str) -> Optional[ET.Element]:
    for ch in list(elem):
        if isinstance(ch.tag, str) and ch.tag.endswith(local):
            return ch
    return None


LANG_SECTION_PATTERNS = {
    "io": [r"==\s*\{\{io\}\}\s*==", r"==\s*Ido\s*==", r"\{\{-ido-\}\}"],
    "eo": [r"==\s*\{\{eo\}\}\s*==", r"==\s*Esperanto\s*==", r"===\s*Esperanto\s*===", r"\{\{-eo-\}\}"],
}

TARGET_TRANSLATION_PATTERNS = {
    # Patterns try to capture list forms (bullets with language label) and template forms
    "io": [
        r"\*\s*\{\{io\}\}\s*[:\.-]\s*(.+?)(?=\n\*|\n\|\}|\Z)",
        r"\*\s*(?:Ido|ido|IO)\s*[:\.-]\s*(.+?)(?=\n\*|\n\|\}|\Z)",
        r"\{\{t\+?\|io\|([^}|]+)",
        r"\{\{trad\+?\|io\|([^}|]+)",
        r"\{\{l\|io\|([^}|]+)",
        r"\{\{link\|io\|([^}|]+)",
        r"\{\{m\|io\|([^}|]+)",
    ],
    "eo": [
        r"\*\s*\{\{eo\}\}\s*[:\.-]\s*(.+?)(?=\n\*|\n\|\}|\Z)",
        r"\*\s*(?:Esperanto|esperanto|EO)\s*[:\.-]\s*(.+?)(?=\n\*|\n\|\}|\Z)",
        r"\{\{t\+?\|eo\|([^}|]+)",
        r"\{\{trad\+?\|eo\|([^}|]+)",
        r"\{\{l\|eo\|([^}|]+)",
        r"\{\{link\|eo\|([^}|]+)",
        r"\{\{m\|eo\|([^}|]+)",
    ],
}

POS_PATTERN = re.compile(r"===\s*(Noun|Verb|Adjective|Adverb|Pronoun|Preposition|Conjunction|Interjection|Substantivo|Verbo|Adjektivo|Adverbo)\s*===", re.IGNORECASE)


def is_valid_title(title: str) -> bool:
    if not title:
        return False
    t = title.strip()
    if len(t) < 2:
        return False
    skip = {"MediaWiki", "Help", "Category", "Template", "User", "Talk", "File", "Image", "Special", "Main", "Wikipedia", "Wiktionary"}
    if t in skip:
        return False
    return True


def extract_language_section(wikitext: str, lang_code: str) -> Optional[str]:
    for pat in LANG_SECTION_PATTERNS.get(lang_code, []):
        m = re.search(pat, wikitext, flags=re.IGNORECASE)
        if not m:
            continue
        start = m.start()
        section = wikitext[start:]
        nxt = re.search(r"\n==[^=]", section)
        if nxt:
            section = section[:nxt.start()]
        return section
    return None


def extract_pos(section: str) -> Optional[str]:
    m = POS_PATTERN.search(section or "")
    if not m:
        return None
    pos = m.group(1).lower()
    return {"substantivo": "noun", "verbo": "verb", "adjektivo": "adjective", "adverbo": "adverb"}.get(pos, pos)


def clean_translation_text(text: str) -> str:
    if not text:
        return ""
    text = html.unescape(text)
    text = re.sub(r"\{\{[^}]*\}}", "", text)  # templates
    text = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]+)\]\]", r"\1", text)  # links
    text = re.sub(r"\[\[(?:Category|Kategorio):[^\]]*\]\]", "", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\|\s*\}.*$", "", text)
    text = re.sub(r"\s+", " ", text).strip(" \t\n\r\f\v:;,.–-|")
    return text


def parse_meanings(blob: str) -> List[List[str]]:
    if not blob:
        return []
    t = clean_translation_text(blob)
    if not t:
        return []
    # number-separated meanings like (1) x; (2) y
    numbered = re.findall(r"\((\d+)\)\s*([^;()]+)", t)
    if numbered:
        out: List[List[str]] = []
        for _, meaning in numbered:
            syns = [s.strip() for s in meaning.split(',') if s.strip()]
            if syns:
                out.append(syns)
        return out
    # semicolon meanings
    if ';' in t:
        out = []
        for part in t.split(';'):
            syns = [s.strip() for s in part.split(',') if s.strip()]
            if syns:
                out.append(syns)
        return out
    # comma list
    parts = [p.strip() for p in t.split(',')]
    if 1 < len(parts) <= 8 and all(len(p) < 20 for p in parts):
        return [parts]
    return [[t]]


def extract_translations(section: str, target_code: str) -> List[List[str]]:
    out: List[List[str]] = []
    for pat in TARGET_TRANSLATION_PATTERNS.get(target_code, []):
        for match in re.findall(pat, section or "", flags=re.IGNORECASE | re.DOTALL):
            blob = match[0] if isinstance(match, tuple) else match
            meanings = parse_meanings(blob)
            out.extend(meanings)
    # dedupe meaning lists
    seen = set()
    uniq: List[List[str]] = []
    for mlist in out:
        key = tuple(sorted(mlist))
        if key in seen:
            continue
        seen.add(key)
        uniq.append(mlist)
    return uniq


def extract_translations_anywhere(wikitext: str, target_code: str) -> List[List[str]]:
    """Fallback: scan the entire page text for target language translations.
    Useful for EO pages where translation lists/templates are outside the immediate section block.
    """
    return extract_translations(wikitext or "", target_code)


TRADUKOJ_HDR_RE = re.compile(r"^===+\s*Tradukoj\s*===+\s*$", re.IGNORECASE | re.MULTILINE)


def extract_tradukoj_io(section_or_page: str) -> List[List[str]]:
    text = section_or_page or ""
    # Find Tradukoj subsection (level 3 or 4)
    m = TRADUKOJ_HDR_RE.search(text)
    if not m:
        return []
    start = m.end()
    # Capture until next heading of same or higher level (=== or ==)
    tail = text[start:]
    end_m = re.search(r"^==[^=].*?$|^===+\s*[^=].*?$", tail, flags=re.MULTILINE)
    block = tail[: end_m.start()] if end_m else tail

    # Collect Ido lines/templates within block
    patterns = [
        r"\*\s*\{\{io\}\}\s*[:\.-]\s*(.+)$",
        r"\*\s*io\s*[:\.-]\s*(.+)$",
        r"\{\{t\+?\|io\|([^}|]+)",
        r"\{\{trad\+?\|io\|([^}|]+)",
        r"\{\{l\|io\|([^}|]+)",
        r"\{\{link\|io\|([^}|]+)",
        r"\{\{m\|io\|([^}|]+)",
    ]
    out: List[List[str]] = []
    for pat in patterns:
        for match in re.findall(pat, block, flags=re.IGNORECASE | re.MULTILINE):
            blob = match[0] if isinstance(match, tuple) else match
            meanings = parse_meanings(blob)
            out.extend(meanings)

    # Dedupe
    seen = set()
    uniq: List[List[str]] = []
    for mlist in out:
        key = tuple(sorted(mlist))
        if key in seen:
            continue
        seen.add(key)
        uniq.append(mlist)
    return uniq


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


@dataclass
class ParserConfig:
    source_code: str  # 'io' or 'eo'
    target_code: str  # 'eo' or 'io'


def parse_wiktionary(xml_path: Path, cfg: ParserConfig, out_json: Path, limit: Optional[int] = None) -> None:
    logging.info("Parsing %s → %s from %s", cfg.source_code, cfg.target_code, xml_path)
    ensure_dir(out_json.parent)
    entries: List[Dict[str, Any]] = []
    processed = 0

    for title, ns, text in iter_pages(xml_path):
        if limit and processed >= limit:
            break
        if ns != "0":
            continue
        processed += 1
        if not is_valid_title(title):
            continue
        section = extract_language_section(text, cfg.source_code)
        pos = extract_pos(section or "") if section else None
        translations = extract_translations(section or "", cfg.target_code) if section else []
        # Fallback heuristics for EO→IO: scan whole page if section yielded nothing
        if cfg.source_code == "eo" and not translations:
            # 1) Tradukoj block
            translations = extract_tradukoj_io(section or text)
        if cfg.source_code == "eo" and not translations:
            # 2) Scan anywhere on the page for IO targets
            translations = extract_translations_anywhere(text, cfg.target_code)
        if not translations:
            continue
        entry: Dict[str, Any] = {
            "id": f"{cfg.source_code}:{title}:{pos or 'x'}",
            "lemma": title,
            "pos": pos,
            "language": cfg.source_code,
            "senses": [
                {"senseId": None, "gloss": None, "translations": [{"lang": cfg.target_code, "term": t, "confidence": 0.6, "source": f"{cfg.source_code}_wiktionary"} for t in syns]}
                for syns in translations
            ],
            "provenance": [{"source": f"{cfg.source_code}_wiktionary", "page": title, "rev": None}],
        }
        entries.append(entry)
        if processed % 1000 == 0:
            logging.info("Processed %d pages...", processed)

    write_json(out_json, entries)
    logging.info("Wrote %s (%d entries)", out_json, len(entries))


def main(argv: Iterable[str]) -> int:
    ap = argparse.ArgumentParser(description="Shared Wiktionary parser")
    ap.add_argument("--input", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--source", choices=["io", "eo"], required=True)
    ap.add_argument("--target", choices=["eo", "io"], required=True)
    ap.add_argument("--limit", type=int)
    ap.add_argument("-v", "--verbose", action="count", default=0)
    args = ap.parse_args(list(argv))

    configure_logging(args.verbose)
    cfg = ParserConfig(source_code=args.source, target_code=args.target)
    parse_wiktionary(args.input, cfg, args.out, args.limit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))


