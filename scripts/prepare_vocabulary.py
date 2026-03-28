#!/usr/bin/env python3
"""prepare_vocabulary.py — single-pass vocabulary preparation.

Replaces the three-script sequence:
  normalize_entries.py → infer_morphology.py → filter_and_validate.py

Reads:  work/bilingual_raw.json
Writes: work/final_vocabulary.json
"""
import argparse
import logging
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from _common import read_json, write_json, configure_logging, clean_lemma, is_valid_lemma, save_text


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ALLOWED_EO_CHARS_RE = re.compile(r"^[A-Za-zĈĜĤĴŜŬĉĝĥĵŝŭ\-]+$")

DEMONYM_NOUN_SUFFIXES = ("ano", "iano")
DEMONYM_ADJ_SUFFIXES = ("ana", "iana")

_FUNC_POS = frozenset({'cnjcoo', 'cnjsub', 'pr', 'det', 'prn'})

_SHORT_POS: Dict[str, str] = {
    "noun": "n", "adjective": "adj", "adverb": "adv", "verb": "vblex",
    "preposition": "pr", "conjunction": "cnjcoo",
    "subordinating conjunction": "cnjsub", "determiner": "det", "pronoun": "prn",
    "interjection": "ij", "numeral": "num",
}


# ---------------------------------------------------------------------------
# Step 1: Normalize  (was normalize_entries.py)
# ---------------------------------------------------------------------------

def _is_valid_eo_term(term: str) -> bool:
    if not term:
        return False
    if ',' in term:
        return False
    return bool(ALLOWED_EO_CHARS_RE.match(term))


def _clean_eo_term(raw: str) -> str:
    term = (raw or '').strip()
    if any(x in term for x in ['|', '{', '}', 'bgcolor']):
        return ''
    term = re.sub(r"\s*Kategorio:[^\s]+.*$", "", term)
    if '*' in term:
        return ''
    term = re.sub(r"\s+", " ", term).strip()
    return term


def _normalize(entries: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    stats = {'input': len(entries), 'cleaned': 0, 'invalid': 0, 'duplicates': 0, 'output': 0}
    # Pass 1: clean lemmas and translation terms
    for e in entries:
        orig = e.get("lemma") or ""
        cleaned = clean_lemma(orig)
        if cleaned != orig:
            stats['cleaned'] += 1
        e["lemma"] = cleaned
        cleaned_senses = []
        for sense in e.get("senses", []):
            cleaned_tr = []
            for tr in sense.get("translations", []):
                if "term" in tr:
                    t = clean_lemma(str(tr["term"]))
                    if is_valid_lemma(t):
                        tr["term"] = t
                        cleaned_tr.append(tr)
            if cleaned_tr:
                sense["translations"] = cleaned_tr
                cleaned_senses.append(sense)
        e["senses"] = cleaned_senses

    # Pass 2: filter invalid
    valid = []
    for e in entries:
        if not is_valid_lemma(e.get("lemma", "")) or not e.get("senses"):
            stats['invalid'] += 1
            continue
        valid.append(e)

    # Pass 3: deduplicate
    seen: set = set()
    out: List[Dict[str, Any]] = []
    for e in valid:
        lemma = (e.get("lemma") or "").strip()
        pos = (e.get("pos") or "").strip()
        lang = (e.get("language") or "").strip()
        trans = tuple(sorted({
            (tr.get("lang"), (tr.get("term") or "").strip())
            for s in e.get("senses", [])
            for tr in s.get("translations", [])
            if tr.get("lang") == "eo"
        }))
        key = (lemma.lower(), pos.lower(), lang.lower(), trans)
        if key in seen:
            stats['duplicates'] += 1
            continue
        seen.add(key)
        out.append(e)

    out.sort(key=lambda x: (str(x.get("lemma", "")), str(x.get("pos", ""))))
    stats['output'] = len(out)
    return out, stats


# ---------------------------------------------------------------------------
# Step 2: Infer morphology  (was infer_morphology.py)
# ---------------------------------------------------------------------------

def _load_function_words(fw_path: Path) -> Dict[str, str]:
    fw: Dict[str, str] = {
        'dil': 'prep_art', 'dal': 'prep_art', 'del': 'prep_art',
        'el': 'prep_art', 'sil': 'prep_art',
        # NOTE: 'al' excluded — also a standalone preposition, avoid double articles
    }
    try:
        data = read_json(fw_path)
        for entry in data:
            lemma = str(entry.get('lemma') or '').lower()
            pos = str(entry.get('pos') or '')
            if lemma and pos:
                fw[lemma] = pos
    except Exception as exc:
        logging.warning("Could not load function_words_io.json: %s", exc)
    return fw


def _has_wikipedia_provenance(entry: Dict[str, Any]) -> bool:
    for p in entry.get("provenance", []) or []:
        src = str(p.get("source") or "")
        if "wikipedia" in src:
            return True
    return False


def _infer_paradigm(entry: Dict[str, Any], function_words: Dict[str, str]) -> Optional[str]:
    lemma = str(entry.get("lemma") or "")
    pos = entry.get("pos")
    if not lemma:
        return None
    lower = lemma.lower()

    if lower in function_words:
        return function_words[lower]

    basic_numbers = {"un", "du", "tri", "kvar", "kin", "sis", "sep", "ok", "non", "dek"}
    if lower in basic_numbers:
        return "num"
    if re.match(r'^\d+(\.\d+)?$', lemma):
        return "num"
    if " " in lemma or "-" in lemma:
        return "o__n"
    if lower.endswith(DEMONYM_NOUN_SUFFIXES):
        return "o__n"
    if lower.endswith(DEMONYM_ADJ_SUFFIXES):
        return "a__adj"
    if lower.endswith("ia") and len(lemma) > 3:
        return "o__n"
    # Ido verb endings are definitive — override noisy POS tags from fr_wikt etc.
    if (lower.endswith("ar") or lower.endswith("ir")) and not lemma[:1].isupper():
        return "ar__vblex"
    if pos in ("noun", "n"):
        return "o__n"
    if pos in ("adjective", "adj"):
        return "a__adj"
    if pos in ("adverb", "adv"):
        return "e__adv"
    if pos in ("verb", "vblex"):
        return "ar__vblex"
    if pos in ("preposition", "pr"):
        return "__pr"
    if pos in ("conjunction", "cnjcoo"):
        return "__cnjcoo"
    if pos in ("subordinating conjunction", "cnjsub"):
        return "__cnjsub"
    if pos in ("determiner", "det"):
        return "__det"
    if pos in ("pronoun", "prn"):
        return "__prn"
    if pos in ("interjection", "ij", "numeral", "num"):
        return "o__n"
    if lower.endswith("a"):
        return "a__adj"
    if lower.endswith("e"):
        return "e__adv"
    if lower.endswith("o"):
        return "o__n"
    if lower.endswith("ar") or lower.endswith("ir"):
        return "ar__vblex"
    if _has_wikipedia_provenance(entry):
        if lemma[:1].isupper() or lower.endswith("i"):
            return "o__n"
    if lemma[:1].isupper() and len(lemma) > 2:
        return "o__n"
    return None


def _maybe_add_demonym_twin(
    base: Dict[str, Any],
    existing: set,
    out: List[Dict[str, Any]],
) -> None:
    lemma = str(base.get("lemma") or "")
    lower = lemma.lower()
    par = (base.get("morphology") or {}).get("paradigm")

    pairs = [
        ("iano", "o__n", "iana", "a__adj", "adjective"),
        ("ano", "o__n", "ana", "a__adj", "adjective"),
        ("iana", "a__adj", "iano", "o__n", "noun"),
        ("ana", "a__adj", "ano", "o__n", "noun"),
    ]
    for sfx, req_par, twin_sfx, twin_par, twin_pos in pairs:
        if lower.endswith(sfx) and par == req_par:
            twin = lemma[:-len(sfx)] + twin_sfx
            if twin not in existing:
                existing.add(twin)
                out.append({**base, "lemma": twin, "pos": twin_pos,
                             "morphology": {"paradigm": twin_par, "features": {}}})
            break


def _infer_morphology(entries: List[Dict[str, Any]], function_words: Dict[str, str]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    existing: set = set()

    def add(e: Dict[str, Any]) -> None:
        lk = str(e.get("lemma") or "")
        if lk:
            existing.add(lk)
        out.append(e)

    for e in entries:
        par = _infer_paradigm(e, function_words)
        morph = {"paradigm": par, "features": {}}
        raw_pos = e.get("pos")
        norm_pos = _SHORT_POS.get(str(raw_pos or ''), raw_pos)
        e2 = {**e, "morphology": morph, "pos": norm_pos}
        add(e2)
        _maybe_add_demonym_twin(e2, existing, out)

        lemma = str(e2.get("lemma") or "")
        par2 = (e2.get("morphology") or {}).get("paradigm")
        # Toponym -ia → -iana
        if lemma and lemma.lower().endswith("ia") and par2 == "o__n":
            twin = lemma + "na"
            if twin not in existing:
                existing.add(twin)
                out.append({**e2, "lemma": twin, "pos": "adjective",
                             "morphology": {"paradigm": "a__adj", "features": {}}})
        # Wikipedia proper noun ending -a → +na adjective
        if lemma and _has_wikipedia_provenance(e2) and lemma.lower().endswith("a") and par2 == "o__n" and len(lemma) > 3:
            twin = lemma + "na"
            if twin not in existing:
                existing.add(twin)
                out.append({**e2, "lemma": twin, "pos": "adjective",
                             "morphology": {"paradigm": "a__adj", "features": {}}})
        # -iana → -ia noun twin
        if lemma and lemma.lower().endswith("iana") and par2 == "a__adj":
            twin = lemma[:-2]
            if twin not in existing:
                existing.add(twin)
                out.append({**e2, "lemma": twin, "pos": "noun",
                             "morphology": {"paradigm": "o__n", "features": {}}})
        # -ana → -a noun twin
        if lemma and lemma.lower().endswith("ana") and par2 == "a__adj":
            twin = lemma[:-2]
            if twin not in existing:
                existing.add(twin)
                out.append({**e2, "lemma": twin, "pos": "noun",
                             "morphology": {"paradigm": "o__n", "features": {}}})
    return out


# ---------------------------------------------------------------------------
# Step 3: Filter and validate  (was filter_and_validate.py)
# ---------------------------------------------------------------------------

def _load_frequency_ranks(freq_path: Path) -> Dict[str, int]:
    try:
        data = read_json(freq_path)
        return {str(it.get('token') or '').lower(): int(it.get('rank') or 0)
                for it in data.get('items', [])
                if it.get('token') and it.get('rank')}
    except Exception:
        return {}


def _is_wikipedia_only(entry: Dict[str, Any]) -> bool:
    prov = entry.get('provenance') or []
    has_wiki = any((p.get('source') or '').endswith('wikipedia') for p in prov if isinstance(p, dict))
    has_wikt = any((p.get('source') or '').endswith('wiktionary') for p in prov if isinstance(p, dict))
    return has_wiki and not has_wikt


def _allow_by_frequency(lemma: str, ranks: Dict[str, int], top_n: int) -> bool:
    for t in (lemma.split() or [lemma]):
        r = ranks.get(t.lower())
        if r is not None and r <= top_n:
            return True
    return False


def _is_demonym(lemma: str) -> bool:
    base = (lemma.replace('-', ' ').split() or [''])[-1]
    return len(base) >= 3 and base.lower().endswith(("ano", "iano", "iana", "ana"))


def _schema_ok(entry: Dict[str, Any]) -> bool:
    return bool(entry.get("lemma") and entry.get("language") and isinstance(entry.get("senses"), list))


def _apply_filters(
    entries: List[Dict[str, Any]],
    wiki_top_n: int,
    freq_path: Path,
) -> Tuple[List[Dict[str, Any]], Dict[str, int], List[str]]:
    ranks = _load_frequency_ranks(freq_path)
    stats = {k: 0 for k in ('bad_schema', 'bad_lemma', 'wiki_low_freq', 'all_tr_removed', 'tr_removed')}
    suspicious: List[str] = []
    out: List[Dict[str, Any]] = []

    for e in entries:
        if not _schema_ok(e):
            stats['bad_schema'] += 1
            continue
        lemma = str(e.get('lemma') or '')
        if not is_valid_lemma(lemma):
            stats['bad_lemma'] += 1
            continue
        if _is_wikipedia_only(e) and not (_is_demonym(lemma) or _allow_by_frequency(lemma, ranks, wiki_top_n)):
            stats['wiki_low_freq'] += 1
            suspicious.append(f"wiki_low_freq: {lemma}")
            continue

        senses = []
        for s in e.get("senses", []) or []:
            cleaned_tr = []
            for t in s.get("translations", []) or []:
                term = _clean_eo_term(t.get('term') or '')
                lang = t.get('lang')
                if not term:
                    continue
                if lang == 'eo' and not _is_valid_eo_term(term):
                    stats['tr_removed'] += 1
                    suspicious.append(f"bad_tr_eo: {lemma} -> {term}")
                    continue
                if ',' in term:
                    stats['tr_removed'] += 1
                    suspicious.append(f"comma_tr: {lemma} -> {term}")
                    continue
                cleaned_tr.append({**t, 'term': term})
            if cleaned_tr:
                senses.append({**s, 'translations': cleaned_tr})

        if not senses:
            stats['all_tr_removed'] += 1
            if str(e.get('language')) == 'io':
                out.append({**e, "senses": []})
            continue
        out.append({**e, "senses": senses})

    return out, stats, suspicious


def _merge_function_words(entries: List[Dict[str, Any]], fw_path: Path) -> List[Dict[str, Any]]:
    try:
        fws = read_json(fw_path)
    except Exception as exc:
        logging.warning("Could not load function words: %s", exc)
        return entries

    by_lemma = {str(e.get('lemma') or ''): e for e in entries}
    added = 0
    for fw in fws:
        lemma = str(fw.get('lemma') or '')
        pos = str(fw.get('pos') or '')
        if not lemma or not pos:
            continue
        paradigm = pos if pos in _FUNC_POS else None
        morph = {'paradigm': paradigm, 'features': {}}
        if lemma in by_lemma:
            by_lemma[lemma]['pos'] = pos
            by_lemma[lemma]['morphology'] = morph
        else:
            by_lemma[lemma] = {
                'id': f'io:{lemma}:{pos}',
                'lemma': lemma,
                'pos': pos,
                'language': 'io',
                'senses': [],
                'morphology': morph,
                'provenance': [{'source': 'whitelist'}],
            }
            added += 1
    if added:
        logging.info("Added %d function words absent from bilingual data", added)
    merged = list(by_lemma.values())
    merged.sort(key=lambda x: (str(x.get('lemma', '')), str(x.get('pos', ''))))
    return merged


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def prepare(
    input_path: Path,
    output_path: Path,
    fw_path: Path,
    freq_path: Path,
    wiki_top_n: int,
) -> int:
    entries = read_json(input_path)
    if not isinstance(entries, list):
        entries = entries.get('entries', [])
    logging.info("Loaded %d entries from %s", len(entries), input_path)

    # Step 1: normalize
    entries, norm_stats = _normalize(entries)
    logging.info("Normalize: %d → %d (cleaned=%d invalid=%d dup=%d)",
                 norm_stats['input'], norm_stats['output'],
                 norm_stats['cleaned'], norm_stats['invalid'], norm_stats['duplicates'])

    # Step 2: infer morphology
    function_words = _load_function_words(fw_path)
    entries = _infer_morphology(entries, function_words)
    logging.info("Morphology inference: %d entries (incl. demonym/toponym twins)", len(entries))

    # Step 3: filter and validate
    entries, filt_stats, suspicious = _apply_filters(entries, wiki_top_n, freq_path)
    logging.info("Filter: bad_schema=%d bad_lemma=%d wiki_low_freq=%d tr_removed=%d",
                 filt_stats['bad_schema'], filt_stats['bad_lemma'],
                 filt_stats['wiki_low_freq'], filt_stats['tr_removed'])

    # Step 4: merge function words whitelist
    entries = _merge_function_words(entries, fw_path)

    write_json(output_path, entries)
    logging.info("Wrote %s (%d entries)", output_path, len(entries))

    # Write suspicious report
    lines = ['# Suspicious Items Report\n', '## Stats']
    for k, v in filt_stats.items():
        lines.append(f'- {k}: {v}')
    lines.append('\n## Examples')
    lines.extend(f'- {l}' for l in suspicious[:2000])
    report_path = output_path.parent.parent / 'reports/suspicious_items.md'
    try:
        save_text(report_path, '\n'.join(lines) + '\n')
    except Exception:
        pass
    return 0


def main(argv: Iterable[str]) -> int:
    base = Path(__file__).resolve().parents[1]
    ap = argparse.ArgumentParser(description="Single-pass vocabulary preparation: normalize + morph + filter")
    ap.add_argument("--input", type=Path, default=base / "work/bilingual_raw.json")
    ap.add_argument("--out", type=Path, default=base / "work/final_vocabulary.json")
    ap.add_argument("--function-words", type=Path, default=base / "data/function_words_io.json")
    ap.add_argument("--freq", type=Path, default=base / "work/io_wiki_frequency.json")
    ap.add_argument("--wiki-top-n", type=int, default=500)
    ap.add_argument("-v", "--verbose", action="count", default=0)
    args = ap.parse_args(list(argv))

    configure_logging(args.verbose)
    return prepare(args.input, args.out, args.function_words, args.freq, args.wiki_top_n)


if __name__ == "__main__":
    import sys
    raise SystemExit(main(sys.argv[1:]))
