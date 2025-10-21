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
    "en": [r"==\s*English\s*==", r"==\s*\{\{en\}\}\s*=="],
}

TARGET_TRANSLATION_PATTERNS = {
    # Patterns try to capture list forms (bullets with language label) and template forms
    # Note: Use [ \t]* instead of \s* to prevent matching newlines and jumping to next line
    # Note: Use [^\n]+ to prevent capturing content from next line
    "io": [
        r"\*[ \t]*\{\{io\}\}[ \t]*[:\.-][ \t]*([^\n]+?)(?=\n|\|\}|\Z)",
        r"\*[ \t]*(?:Ido|ido|IO)[ \t]*[:\.-][ \t]*([^\n]+?)(?=\n|\|\}|\Z)",
        r"\{\{t\+?\|io\|([^}|]+)",
        r"\{\{trad\+?\|io\|([^}|]+)",
        r"\{\{l\|io\|([^}|]+)",
        r"\{\{link\|io\|([^}|]+)",
        r"\{\{m\|io\|([^}|]+)",
    ],
    "eo": [
        r"\*[ \t]*\{\{eo\}\}[ \t]*[:\.-][ \t]*([^\n]+?)(?=\n|\|\}|\Z)",
        r"\*[ \t]*(?:Esperanto|esperanto|EO)[ \t]*[:\.-][ \t]*([^\n]+?)(?=\n|\|\}|\Z)",
        r"(?m)^.*?Esperanto[ \t]*[:\-][ \t]*([^\n|]+)",
        r"\{\{t\+?\|eo\|([^}|]+)",
        r"\{\{trad\+?\|eo\|([^}|]+)",
        r"\{\{l\|eo\|([^}|]+)",
        r"\{\{link\|eo\|([^}|]+)",
        r"\{\{m\|eo\|([^}|]+)",
    ],
    "en": [
        r"\*[ \t]*\{\{en\}\}[ \t]*[:\.-][ \t]*([^\n]+?)(?=\n|\|\}|\Z)",
        r"\*[ \t]*(?:Angliana|English|EN|en)[ \t]*[:\.-][ \t]*([^\n]+?)(?=\n|\|\}|\Z)",
        r"(?m)^.*?(?:Angliana|English)[ \t]*[:\-][ \t]*([^\n|]+)",
        r"\{\{t\+?\|en\|([^}|]+)",
        r"\{\{trad\+?\|en\|([^}|]+)",
        r"\{\{l\|en\|([^}|]+)",
        r"\{\{link\|en\|([^}|]+)",
        r"\{\{m\|en\|([^}|]+)",
    ],
    "fr": [
        r"\*[ \t]*\{\{fr\}\}[ \t]*[:\.-][ \t]*([^\n]+?)(?=\n|\|\}|\Z)",
        r"\*[ \t]*(?:Franciana|French|FR|fr)[ \t]*[:\.-][ \t]*([^\n]+?)(?=\n|\|\}|\Z)",
        r"(?m)^.*?(?:Franciana|French)[ \t]*[:\-][ \t]*([^\n|]+)",
        r"\{\{t\+?\|fr\|([^}|]+)",
        r"\{\{trad\+?\|fr\|([^}|]+)",
        r"\{\{l\|fr\|([^}|]+)",
        r"\{\{link\|fr\|([^}|]+)",
        r"\{\{m\|fr\|([^}|]+)",
    ],
}

# Match POS headings at level 3 or higher (===, ====, ...), English or Ido labels
POS_HEADER_RE = re.compile(
    r"^==+\s*(Noun|Verb|Adjective|Adverb|Pronoun|Preposition|Conjunction|Interjection|Substantivo|Verbo|Adjektivo|Adverbo)\s*==+\s*$",
    re.IGNORECASE | re.MULTILINE,
)


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
    text = section or ""
    # 1) Heading-based detection
    m = POS_HEADER_RE.search(text)
    if m:
        pos = m.group(1).lower()
        pos = {"substantivo": "noun", "verbo": "verb", "adjektivo": "adjective", "adverbo": "adverb"}.get(pos, pos)
        return pos

    # 2) Template-based detection (e.g., {{head|io|verb}})
    if mwparserfromhell is not None:
        try:
            wt = mwparserfromhell.parse(text)
            for tpl in wt.filter_templates():
                name = tpl.name.strip().lower()
                # Generic head template
                if name == "head" and tpl.has_param(0) and tpl.has_param(1):
                    lang = str(tpl.get(0).value).strip().lower()
                    p = str(tpl.get(1).value).strip().lower()
                    if lang in {"io", "ido"}:
                        if p in {"noun", "verb", "adjective", "adverb", "pronoun", "preposition", "conjunction", "interjection"}:
                            return p
                # Language-specific short templates (best-effort)
                if name.startswith("io-"):
                    p = name.split("io-", 1)[-1]
                    mapping = {
                        "noun": "noun",
                        "verb": "verb",
                        "adj": "adjective",
                        "adjective": "adjective",
                        "adv": "adverb",
                        "adverb": "adverb",
                        "pron": "pronoun",
                        "prep": "preposition",
                        "conj": "conjunction",
                        "int": "interjection",
                    }
                    if p in mapping:
                        return mapping[p]
        except Exception:
            pass

    # 3) Category-based hints (English or Esperanto labels)
    cat_text = text.lower()
    cat_hints = [
        ("[[category:ido nouns", "noun"),
        ("[[category:ido verbs", "verb"),
        ("[[category:ido adjectives", "adjective"),
        ("[[category:ido adverbs", "adverb"),
        ("[[kategorio:ido substantivo", "noun"),
        ("[[kategorio:ido verbo", "verb"),
        ("[[kategorio:ido adjektivo", "adjective"),
        ("[[kategorio:ido adverbo", "adverb"),
    ]
    for needle, p in cat_hints:
        if needle in cat_text:
            return p

    # 4) Fallback: use lemma ending heuristics where POS headings are absent
    # This is handled later by morphology inference too, but giving POS helps downstream.
    # We cannot access the title here, so skip to let morphology handle.
    return None


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
            # Filter out empty meaning lists (e.g., when "Esperanto:" has no content)
            meanings = [m for m in meanings if m and all(t.strip() for t in m)]
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
            # Filter out empty meaning lists
            meanings = [m for m in meanings if m and all(t.strip() for t in m)]
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


def parse_wiktionary(
    xml_path: Path,
    cfg: ParserConfig,
    out_json: Path,
    limit: Optional[int] = None,
    progress_every: Optional[int] = None,
) -> None:
    logging.info("Parsing %s → %s from %s", cfg.source_code, cfg.target_code, xml_path)
    ensure_dir(out_json.parent)
    entries: List[Dict[str, Any]] = []
    processed = 0

    prog_n = max(1, int(progress_every or 1000))
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
        # Also collect English/French translations for IO/EO pages; and for EN pages collect IO and EO
        en_trans_lists: List[List[str]] = []
        fr_trans_lists: List[List[str]] = []
        if section and cfg.source_code in {"io", "eo"}:
            en_trans_lists = extract_translations(section, "en")
            fr_trans_lists = extract_translations(section, "fr")
        io_from_en: List[List[str]] = []
        eo_from_en: List[List[str]] = []
        if section and cfg.source_code == "en":
            io_from_en = extract_translations(section, "io")
            eo_from_en = extract_translations(section, "eo")
        # Fallback heuristics for EO→IO: scan whole page if section yielded nothing
        if cfg.source_code == "eo" and not translations:
            # 1) Tradukoj block
            translations = extract_tradukoj_io(section or text)
        if cfg.source_code == "eo" and not translations:
            # 2) Scan anywhere on the page for IO targets
            translations = extract_translations_anywhere(text, cfg.target_code)
        # Allow entries that have EN/FR (or IO/EO on EN pages) even if no direct target translations
        has_extras = bool(en_trans_lists or fr_trans_lists or io_from_en or eo_from_en)
        if not translations and not has_extras:
            continue
        entry: Dict[str, Any] = {
            "id": f"{cfg.source_code}:{title}:{pos or 'x'}",
            "lemma": title,
            "pos": pos,
            "language": cfg.source_code,
            "senses": [],
            "provenance": [{"source": f"{cfg.source_code}_wiktionary", "page": title, "rev": None}],
        }
        # Add EO target translations as one sense per meaning list
        for syns in translations:
            entry["senses"].append({
                "senseId": None,
                "gloss": None,
                "translations": [{"lang": cfg.target_code, "term": t, "confidence": 0.6, "source": f"{cfg.source_code}_wiktionary"} for t in syns]
            })
        # Add EN/FR translations as separate sense lists to preserve language
        if en_trans_lists:
            for syns in en_trans_lists:
                entry["senses"].append({
                    "senseId": None,
                    "gloss": None,
                    "translations": [{"lang": "en", "term": t, "confidence": 0.5, "source": f"{cfg.source_code}_wiktionary"} for t in syns]
                })
        if fr_trans_lists:
            for syns in fr_trans_lists:
                entry["senses"].append({
                    "senseId": None,
                    "gloss": None,
                    "translations": [{"lang": "fr", "term": t, "confidence": 0.5, "source": f"{cfg.source_code}_wiktionary"} for t in syns]
                })
        # Add IO/EO captured on English pages
        if io_from_en:
            for syns in io_from_en:
                entry["senses"].append({
                    "senseId": None,
                    "gloss": None,
                    "translations": [{"lang": "io", "term": t, "confidence": 0.6, "source": f"{cfg.source_code}_wiktionary"} for t in syns]
                })
        if eo_from_en:
            for syns in eo_from_en:
                entry["senses"].append({
                    "senseId": None,
                    "gloss": None,
                    "translations": [{"lang": "eo", "term": t, "confidence": 0.6, "source": f"{cfg.source_code}_wiktionary"} for t in syns]
                })
        entries.append(entry)
        if processed % prog_n == 0:
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
    ap.add_argument("--progress-every", type=int, default=1000)
    ap.add_argument("-v", "--verbose", action="count", default=0)
    args = ap.parse_args(list(argv))

    configure_logging(args.verbose)
    cfg = ParserConfig(source_code=args.source, target_code=args.target)
    parse_wiktionary(args.input, cfg, args.out, args.limit, progress_every=args.progress_every)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))


