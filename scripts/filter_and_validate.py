#!/usr/bin/env python3
import argparse
import logging
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from _common import read_json, write_json, configure_logging, save_text


ALLOWED_EO_CHARS_RE = re.compile(r"^[A-Za-zĈĜĤĴŜŬĉĝĥĵŝŭ\-]+$")


def is_valid_lemma(lemma: str) -> bool:
    if not lemma:
        return False
    if lemma.startswith('.'):
        return False
    if ',' in lemma:
        return False
    if any(ch in lemma for ch in '[]{}|()'):
        return False
    if any(ch.isdigit() for ch in lemma):
        return False
    # Drop very long titles
    if len(lemma) > 40:
        return False
    # Drop 4+ token lemmas
    if len(lemma.split()) >= 4:
        return False
    # Remove spaces for validation; Wikipedia titles may include spaces, but we filter them out here per stricter rule
    test = lemma.replace(' ', '')
    return bool(ALLOWED_EO_CHARS_RE.match(test))


def is_valid_eo_term(term: str) -> bool:
    if not term:
        return False
    if ',' in term:
        return False
    return bool(ALLOWED_EO_CHARS_RE.match(term))


def clean_eo_term(raw: str) -> str:
    term = (raw or '').strip()
    # Drop if contains any table/template artifacts
    if any(x in term for x in ['|', '{', '}', 'bgcolor']):
        return ''
    # Accept categories by stripping trailing category annotation
    term = re.sub(r"\s*Kategorio:[^\s]+.*$", "", term)
    # Drop bullet-derived artifacts
    if '*' in term:
        return ''
    # Normalize whitespace
    term = re.sub(r"\s+", " ", term).strip()
    return term


def schema_ok(entry: Dict[str, Any]) -> bool:
    if not entry.get("lemma") or not entry.get("language"):
        return False
    if not isinstance(entry.get("senses"), list):
        return False
    return True


def load_frequency_ranks(freq_path: Path) -> Dict[str, int]:
    try:
        data = read_json(freq_path)
        ranks: Dict[str, int] = {}
        for it in data.get('items', []):
            tok = str(it.get('token') or '').lower()
            rank = int(it.get('rank') or 0)
            if tok and rank:
                ranks[tok] = rank
        return ranks
    except Exception:
        return {}


def is_wikipedia_only(entry: Dict[str, Any]) -> bool:
    prov = entry.get('provenance') or []
    has_wiki = any((p.get('source') or '').endswith('wikipedia') for p in prov if isinstance(p, dict))
    has_wikt = any((p.get('source') or '').endswith('wiktionary') for p in prov if isinstance(p, dict))
    return has_wiki and not has_wikt


def allow_wikipedia_by_frequency(lemma: str, ranks: Dict[str, int], top_n: int = 20) -> bool:
    tokens = [t.lower() for t in lemma.split() if t]
    for t in tokens or [lemma.lower()]:
        r = ranks.get(t)
        if r is not None and r <= top_n:
            return True
    return False


DEMONYM_SUFFIXES = (
    'ano', 'iano', 'iana', 'iana', 'iano', 'ana'
)


def is_demonym(lemma: str) -> bool:
    if not lemma:
        return False
    base = lemma.replace('-', ' ').split()[-1]
    if len(base) < 3:
        return False
    return base.lower().endswith(DEMONYM_SUFFIXES)


def apply_filters(entries: List[Dict[str, Any]], wiki_top_n: int) -> Tuple[List[Dict[str, Any]], Dict[str, int], List[str]]:
    out: List[Dict[str, Any]] = []
    stats = {
        'dropped_invalid_schema': 0,
        'dropped_bad_lemma': 0,
        'dropped_no_senses': 0,
        'dropped_all_translations_removed': 0,
        'translations_removed': 0,
        'dropped_wikipedia_low_freq': 0,
    }
    suspicious: List[str] = []

    # Load frequency ranks for Wikipedia gating
    freq_path = Path(__file__).resolve().parents[1] / 'work/io_wiki_frequency.json'
    ranks = load_frequency_ranks(freq_path)

    for e in entries:
        if not schema_ok(e):
            stats['dropped_invalid_schema'] += 1
            continue
        lemma = str(e.get('lemma') or '')
        if not is_valid_lemma(lemma):
            stats['dropped_bad_lemma'] += 1
            continue

        # Wikipedia-only gating by frequency
        if is_wikipedia_only(e) and not (is_demonym(lemma) or lemma.lower() == 'abel-manjero' or allow_wikipedia_by_frequency(lemma, ranks, top_n=wiki_top_n)):
            stats['dropped_wikipedia_low_freq'] += 1
            suspicious.append(f"wiki_low_freq: {lemma}")
            continue

        # Filter translations; for EO targets enforce Esperanto orthography and comma-free
        senses = []
        for s in e.get("senses", []) or []:
            cleaned_tr = []
            for t in s.get("translations", []) or []:
                term = clean_eo_term(t.get('term') or '')
                lang = t.get('lang')
                if not term:
                    # silently drop star/table/category noise without logging
                    continue
                if lang == 'eo' and not is_valid_eo_term(term):
                    stats['translations_removed'] += 1
                    # Do not log category/asterisk-derived cases; we've stripped those above
                    # Only log if it still fails after cleaning
                    suspicious.append(f"bad_tr_eo: {lemma} -> {term}")
                    continue
                if ',' in term:
                    stats['translations_removed'] += 1
                    suspicious.append(f"comma_tr: {lemma} -> {term}")
                    continue
                cleaned_tr.append(t)
            if cleaned_tr:
                senses.append({**s, 'translations': cleaned_tr})
        if not senses:
            stats['dropped_all_translations_removed'] += 1
            # Keep Ido entry for monolingual even if no EO translations remain
            if str(e.get('language')) == 'io':
                out.append({**e, "senses": []})
            continue
        out.append({**e, "senses": senses})

    if not out:
        stats['dropped_no_senses'] += 0  # placeholder to keep key present
    return out, stats, suspicious


def main(argv: Iterable[str]) -> int:
    ap = argparse.ArgumentParser(description="Filter and validate entries")
    ap.add_argument("--input", type=Path, default=Path(__file__).resolve().parents[1] / "work/bilingual_with_morph.json")
    ap.add_argument("--out", type=Path, default=Path(__file__).resolve().parents[1] / "work/final_vocabulary.json")
    ap.add_argument("--wiki-top-n", type=int, default=500, help="Top-N frequency rank threshold for Wikipedia-only keep")
    ap.add_argument("-v", "--verbose", action="count", default=0)
    args = ap.parse_args(list(argv))

    configure_logging(args.verbose)
    entries = read_json(args.input)
    result, stats, suspicious = apply_filters(entries, wiki_top_n=args.wiki_top_n)
    write_json(args.out, result)
    logging.info("Wrote %s (%d entries)", args.out, len(result))

    # Write suspicious report
    report_lines = []
    report_lines.append('# Suspicious Items Report\n')
    report_lines.append('## Stats')
    for k, v in stats.items():
        report_lines.append(f'- {k}: {v}')
    report_lines.append('\n## Examples')
    for line in suspicious[:2000]:
        report_lines.append(f'- {line}')
    save_text(Path(__file__).resolve().parents[1] / 'reports/suspicious_items.md', '\n'.join(report_lines) + '\n')
    return 0


if __name__ == "__main__":
    import sys
    raise SystemExit(main(sys.argv[1:]))


