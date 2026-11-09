#!/usr/bin/env python3
"""Ido translations from Spanish Wiktionary, for vortaro's Spanish words.

es.wiktionary lists translations as ``{{t|io|a1=1|t1=hundo|t2=…}}`` under the
Spanish entry (``== {{lengua|es}} ==``). Each ``tN`` value is an Ido word for
the page title (a Spanish word). Output (work/es_wiktionary_io.json):

    {"pairs": {"hundo": ["perro"], ...}, "pages": N, "skipped": [...]}

Values that are not a single clean word (``urso/ursino``, ``x (y)``) are
skipped and listed, so they can be fixed on the wiki. The dump is brought up
to date by its overlay (fetch_wiktionary_overlay.py --lang es), like io.

Usage:
  python3 scripts/parse_es_wiktionary_io.py [--dump FILE] [--out FILE]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
from wiktionary_parser import iter_pages  # noqa: E402
from utils.parser_base import find_dump_file  # noqa: E402

_LANG_HEADING_RE = re.compile(r"^==\s*\{\{lengua\|([^}|]+)[^}]*\}\}\s*==\s*$", re.MULTILINE)
_T_IO_RE = re.compile(r"\{\{t\|io\|([^{}]*)\}\}")
_T_VALUE_RE = re.compile(r"(?:^|\|)t\d+=([^|]*)")
_BAD_CHARS = set("/()[]{}<>=,;")


def spanish_section(text: str) -> str:
    """Text of the ``{{lengua|es}}`` section ("" when the page has none)."""
    heads = list(_LANG_HEADING_RE.finditer(text))
    for i, m in enumerate(heads):
        if m.group(1).strip() == "es":
            end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
            return text[m.end():end]
    return ""


def ido_terms(section: str) -> Tuple[List[str], List[str]]:
    """(clean Ido words, rejected values) from the ``{{t|io|…}}`` templates."""
    good: List[str] = []
    bad: List[str] = []
    for tm in _T_IO_RE.finditer(section):
        for raw in _T_VALUE_RE.findall(tm.group(1)):
            w = raw.strip()
            if not w:
                continue
            if any(c in _BAD_CHARS for c in w):
                bad.append(w)
            elif w not in good:
                good.append(w)
    return good, bad


def extract(pages) -> Dict:
    pairs: Dict[str, List[str]] = {}
    skipped = []
    n = 0
    for title, ns, text in pages:
        if str(ns) != "0" or "{{t|io|" not in text:
            continue
        good, bad = ido_terms(spanish_section(text))
        if good or bad:
            n += 1
        for w in good:
            lst = pairs.setdefault(w, [])
            if title not in lst:
                lst.append(title)
        skipped += [{"page": title, "value": b} for b in bad]
    return {"pairs": dict(sorted(pairs.items())), "pages": n, "skipped": skipped}


def main(argv=None) -> int:
    base = Path(__file__).resolve().parents[1]
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dump", type=Path)
    ap.add_argument("--out", type=Path, default=base / "work" / "es_wiktionary_io.json")
    args = ap.parse_args(argv)
    dump = args.dump or find_dump_file("eswiktionary-*.xml.bz2", base / "dumps", [base / "data" / "raw"])
    if dump is None:
        raise SystemExit("No eswiktionary dump found (scripts/download_dumps.sh)")
    result = extract(iter_pages(dump))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{args.out}: {len(result['pairs'])} Ido words from {result['pages']} pages, "
          f"{len(result['skipped'])} values skipped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
