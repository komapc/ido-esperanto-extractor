#!/usr/bin/env python3
"""Simple dump parser for io.wiktionary pages-articles XML.

This script downloads the bz2 dump (if not present), streams page elements, and
uses mwparserfromhell to extract Ido sections and translations. It writes a JSON
output similar to the API-based extractor.

This is intentionally simple and meant for moderate-size dumps. For very large
or production runs, consider using the 'mwxml' library or a dedicated streaming
XML parser tuned for Wikimedia dumps.
"""

import argparse
import bz2
import json
import os
import re
import sys
import tempfile
import urllib.request
from datetime import datetime
from typing import Optional

try:
    import mwparserfromhell as mwp
except Exception:
    mwp = None

DUMP_URL = 'https://dumps.wikimedia.org/iowiktionary/latest/iowiktionary-latest-pages-articles.xml.bz2'
DUMP_FILE = 'iowiktionary-latest-pages-articles.xml.bz2'

ID_SECTION_RE = re.compile(r"==\s*(?:\{\{io\}\}|Ido)\s*==", re.IGNORECASE)


def download_dump(path: str) -> None:
    if os.path.exists(path):
        print(f"Dump already exists: {path}")
        return
    print(f"Downloading dump to {path} (this may take a while)...")
    urllib.request.urlretrieve(DUMP_URL, path)
    print("Download complete")


def stream_pages_from_dump(path: str):
    """Yield (title, wikitext) for each page in the dump.

    This is a simple implementation that looks for <page> ... </page> blocks and
    extracts the <title> and <text> content. It will use streaming reads to avoid
    loading the whole file in memory.
    """
    open_fn = bz2.open if path.endswith('.bz2') else open
    with open_fn(path, 'rt', encoding='utf-8', errors='ignore') as f:
        buf = []
        in_page = False
        for line in f:
            if '<page>' in line:
                in_page = True
                buf = [line]
            elif '</page>' in line and in_page:
                buf.append(line)
                page_xml = ''.join(buf)
                # extract title
                title_m = re.search(r'<title>(.*?)</title>', page_xml, re.DOTALL)
                text_m = re.search(r'<text[^>]*>([\s\S]*?)</text>', page_xml, re.DOTALL)
                title = title_m.group(1) if title_m else None
                text = text_m.group(1) if text_m else None
                if title and text:
                    # unescape common XML entities
                    text = text.replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&')
                    yield title, text
                in_page = False
                buf = []
            elif in_page:
                buf.append(line)


def extract_from_wikitext(title: str, wikitext: str) -> Optional[dict]:
    # Find Ido section
    sec_match = re.search(r'(==\s*(?:\{\{io\}\}|Ido)\s*==[\s\S]*?)(?=^==|\Z)', wikitext, re.MULTILINE | re.IGNORECASE)
    if not sec_match:
        return None
    ido_section = sec_match.group(1)
    # Extract categories from the whole page wikitext (support English and local 'Kategorio')
    cats = re.findall(r'\[\[(?:Category|Kategorio):([^\]|]+)', wikitext, re.IGNORECASE)
    # conservative suffix/compound indicators to filter out non-base forms
    suffix_indicators = ('suf', 'sufix', 'sufixo', 'radik', 'radiko', 'komp', 'kompon', 'affix', 'suffix')
    for c in cats:
        low = c.lower()
        for ind in suffix_indicators:
            if ind in low:
                # skip pages whose categories indicate suffixes/roots/compounds
                return None
    # try to extract Esperanto translations within that section
    if mwp:
        try:
            wc = mwp.parse(ido_section)
        except Exception:
            return None
        translations = []
        for templ in wc.filter_templates(recursive=True):
            name = str(templ.name).strip().lower()
            if name.startswith('t') or name == 'l' or name.startswith('t+'):
                try:
                    lang = str(templ.params[0].value).strip().lower() if len(templ.params) > 0 else ''
                except Exception:
                    lang = ''
                if lang in ('eo', 'esperanto'):
                    for idx in range(1, len(templ.params)):
                        try:
                            val = str(templ.params[idx].value).strip()
                            if val:
                                translations.append(val)
                        except Exception:
                            continue
        # fallback: look for '* Esperanto: ...'
        if not translations:
            for line in ido_section.splitlines():
                m = re.match(r'\*\s*(?:Esperanto|eo)[:\-\s]+(.+)', line, re.IGNORECASE)
                if m:
                    translations.append(m.group(1).strip())
        if not translations:
            return None
        # keep only base word forms: also skip titles that look like affix/suffix forms (rudimentary)
        t_low = title.lower()
        for ind in suffix_indicators:
            if ind in t_low:
                return None
        return {
            'ido_word': title,
            'esperanto_translations': translations,
        }
    else:
        # Without mwparserfromhell, do a simpler regex extraction
        translations = re.findall(r"\*\s*(?:Esperanto|eo)[:\-\s]+([^\n]+)", ido_section, re.IGNORECASE)
        if not translations:
            return None
        return {
            'ido_word': title,
            'esperanto_translations': translations,
            'definitions': []
        }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dump', default=DUMP_FILE)
    parser.add_argument('--download', action='store_true')
    parser.add_argument('--out', default='ido_from_dump.json')
    parser.add_argument('--limit', type=int)
    args = parser.parse_args()

    if args.download:
        download_dump(args.dump)

    if not os.path.exists(args.dump):
        print('Dump not found. Use --download or provide dump path.')
        sys.exit(1)

    out = []
    count = 0
    candidates = 0
    parsed = 0
    for title, text in stream_pages_from_dump(args.dump):
        if args.limit and count >= args.limit:
            break
        res = extract_from_wikitext(title, text)
        if res:
            candidates += 1
            out.append(res)
            parsed += 1
        count += 1
        if count % 1000 == 0:
            print(f'Processed {count} pages, collected {len(out)} entries')

    result = {
        'metadata': {
            'extraction_date': datetime.now().isoformat(),
            'source': 'iowiktionary dump',
            'total_words': len(out),
            'script_version': 'dump-parser-0.1',
            'pages_processed': count,
            'candidates_examined': candidates,
            'parsed_entries': parsed,
            'parsed_pct': (parsed / candidates * 100) if candidates else 0.0
        },
        'words': out
    }

    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f'Dump parse complete: {len(out)} entries written to {args.out}')
