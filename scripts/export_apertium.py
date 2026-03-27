#!/usr/bin/env python3
import argparse
import logging
import re
from pathlib import Path
from typing import Iterable

from _common import read_json, ensure_dir, configure_logging, clean_lemma
import xml.etree.ElementTree as ET
from typing import Dict


def _load_function_words() -> Dict[str, str]:
    """Load Ido function words (lemma → paradigm) from function_words_io.json.

    Prepositional-article contractions (dil, dal, …) use the special
    ``prep_art`` paradigm and are kept hardcoded since that paradigm is not
    representable as a plain POS tag in the JSON file.
    """
    fw: Dict[str, str] = {
        'dil': 'prep_art', 'dal': 'prep_art', 'del': 'prep_art',
        'al': 'prep_art', 'el': 'prep_art', 'sil': 'prep_art',
    }
    fw_path = Path(__file__).resolve().parents[1] / 'data/function_words_io.json'
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


# Loaded once at import time.
_FUNCTION_WORDS: Dict[str, str] = _load_function_words()

_KATEGORIO_RE = re.compile(r'\s*Kategorio:[^\s]+.*$', re.IGNORECASE)


def _clean_translation_term(raw: str) -> str:
    """Strip arrow artifacts and Kategorio references from a translation term."""
    term = clean_lemma(raw).strip()
    term = _KATEGORIO_RE.sub('', term).strip()
    return term


# Map verbose Wiktionary POS names to short Apertium tags.
_VERBOSE_POS: Dict[str, str] = {
    "preposition": "pr", "conjunction": "cnjcoo",
    "subordinating conjunction": "cnjsub", "determiner": "det",
    "pronoun": "prn", "noun": "n", "adjective": "adj",
    "adverb": "adv", "verb": "vblex", "interjection": "ij", "numeral": "num",
}


def write_xml_file(elem: ET.Element, output_path: Path) -> None:
    """Write Apertium XML with declaration (no indentation to avoid breaking lt-proc)."""
    # Add XML declaration
    xml_declaration = b'<?xml version="1.0" encoding="UTF-8"?>\n'
    
    # Write to file
    with open(output_path, 'wb') as f:
        f.write(xml_declaration)
        f.write(ET.tostring(elem, encoding="utf-8"))
        f.write(b'\n')


def load_pardefs_from_file(pardefs_path: Path) -> ET.Element:
    """Load paradigm definitions from an XML file."""
    try:
        tree = ET.parse(pardefs_path)
        return tree.getroot()
    except Exception as e:
        logging.error(f"Failed to load pardefs from {pardefs_path}: {e}")
        # Return empty pardefs element if file load fails
        return ET.Element("pardefs")


def extract_stem(lemma: str, paradigm: str) -> str:
    """Extract stem from lemma based on paradigm. Used for both monolingual and bilingual dicts."""
    if not lemma:
        return ""
    if paradigm in {"__pr", "__det", "__prn", "__cnjcoo", "__cnjsub", "__prep_art"}:
        return lemma
    if paradigm == "ar__vblex":
        if lemma.endswith("ar"): return lemma[:-2]
        if lemma.endswith("ir"): return lemma[:-2]
        if lemma.endswith("or"): return lemma[:-2]
    if paradigm == "o__n" and lemma.endswith("o"):
        return lemma[:-1]
    if paradigm == "a__adj" and lemma.endswith("a"):
        return lemma[:-1]
    if paradigm == "e__adv" and lemma.endswith("e"):
        return lemma[:-1]
    return lemma


def build_monodix(entries):
    dictionary = ET.Element("dictionary")
    alphabet = ET.SubElement(dictionary, "alphabet")
    alphabet.text = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    # Define sdefs for monolingual dictionary
    sdefs = ET.SubElement(dictionary, "sdefs")
    for s in ["n", "adj", "adv", "vblex", "pr", "prn", "det", "num", "cnjcoo", "cnjsub", "ij", "sg", "pl", "sp", "nom", "acc", "inf", "pri", "pii", "fti", "cni", "imp", "pp", "p1", "p2", "p3", "m", "f", "mf", "nt", "np", "ant", "cog", "top", "al", "ciph", "able", "pasv", "act", "ord", "def", "der_pres", "der_act", "der_qual", "der_oz", "der_izar", "der_past", "der_ppa", "der_ppas", "der_pprs", "der_pfut", "der_ppra"]:
        ET.SubElement(sdefs, "sdef", n=s)
    # Load pardefs from external file instead of hardcoding
    pardefs_path = Path(__file__).resolve().parents[1] / "data/pardefs.xml"
    if pardefs_path.exists():
        logging.info(f"Loading pardefs from {pardefs_path}")
        external_pardefs = load_pardefs_from_file(pardefs_path)
        dictionary.append(external_pardefs)
    else:
        logging.warning(f"Pardefs file not found at {pardefs_path}, falling back to minimal defaults")
        pardefs = ET.SubElement(dictionary, "pardefs")
        # Basic paradigms (fallback only)
        def add_paradigm(name: str, l_text: str, r_s: list):
            pd = ET.SubElement(pardefs, "pardef", n=name)
            e = ET.SubElement(pd, "e")
            p = ET.SubElement(e, "p")
            ET.SubElement(p, "l").text = l_text
            r = ET.SubElement(p, "r")
            for s in r_s:
                ET.SubElement(r, "s", n=s)
        add_paradigm("o__n", "o", ["n", "sg", "nom"])
        add_paradigm("a__adj", "a", ["adj"])
        add_paradigm("e__adv", "e", ["adv"])
        add_paradigm("ar__vblex", "ar", ["vblex", "inf"])
        add_paradigm("num", "", ["num"])

    section = ET.SubElement(dictionary, "section", id="main", type="standard")
    def map_s_tag(par: str, pos: str | None) -> str | None:
        if par in ("o__n",):
            return "n"
        if par in ("a__adj",):
            return "adj"
        if par in ("e__adv",):
            return "adv"
        if par in ("ar__vblex",):
            return "vblex"
        if par in ("num",):
            return "num"
        if par in ("num_regex",):
            return "num"
        if par in ("__pr", "__det", "__prn", "__cnjcoo", "__cnjsub"):
            return par.replace("__", "")
        # Map raw pos for function words
        if pos in ("pr", "det", "prn", "cnjcoo", "cnjsub"):
            return pos
        return None

    # Sort entries alphabetically by lemma before adding to section
    # Handle None lemmas safely by using 'or ""' to convert None to empty string
    sorted_entries = sorted(entries, key=lambda e: ((e.get("lemma") or "").lower(), e.get("lemma") or ""))

    # Add a single regex entry to match all compound numbers (like 123, 4567, 12.34)
    # This will match any sequence of digits, with optional decimal point
    # No r attribute means bidirectional (both analysis and generation)
    en = ET.SubElement(section, "e")
    par = ET.SubElement(en, "par", n="num_regex")

    for e in sorted_entries:
        # New format doesn't have "language" field - all entries are Ido by default
        # Old format had language field, so check if present
        if e.get("language") and e.get("language") != "io":
            continue
        
        lm = e.get("lemma")
        if not lm:
            continue
        
        clean_lm = str(lm).strip()
        raw_par = (e.get("morphology") or {}).get("paradigm")
        pos = e.get("pos") if isinstance(e.get("pos"), str) else None
        # Normalize verbose POS names to short Apertium tags (entries that
        # bypassed infer_morphology.py may still carry verbose labels).
        if pos and pos in _VERBOSE_POS:
            pos = _VERBOSE_POS[pos]

        # Function words override stale paradigms from infer_morphology.py
        # (e.g. "ke" was assigned "e__adv" by ending heuristic but is cnjsub).
        if clean_lm.lower() in _FUNCTION_WORDS:
            raw_par = _FUNCTION_WORDS[clean_lm.lower()]

        # If no explicit paradigm, infer from POS (normalized upstream) with
        # ending heuristic fallback for entries that bypass infer_morphology.py.
        if not raw_par:
            if pos in {"vblex", "verb"}:
                raw_par = "ar__vblex"
            elif pos == "adj":
                raw_par = "a__adj"
            elif pos == "adv":
                raw_par = "e__adv"
            elif pos in {"pr", "det", "prn", "cnjcoo", "cnjsub"}:
                raw_par = "__" + pos
            else:
                lm_lower = clean_lm.lower()
                if lm_lower.endswith("ar") or lm_lower.endswith("ir"):
                    raw_par = "ar__vblex"
                elif lm_lower.endswith("a"):
                    raw_par = "a__adj"
                elif lm_lower.endswith("e"):
                    raw_par = "e__adv"
                else:
                    raw_par = "o__n"

        # Normalize function-word paradigms
        par = raw_par
        # Expand short POS tags from _FUNCTION_WORDS to full paradigm names
        if raw_par == "adv":
            par = "e__adv"
        elif raw_par == "adj":
            par = "a__adj"
        elif raw_par in {"n", "num", "ij"}:
            par = "o__n"
        elif raw_par == "vblex":
            par = "ar__vblex"
        # Special case for prepositional articles (dil, dal, etc.)
        elif raw_par == 'prep_art':
            par = "__prep_art"
        elif raw_par in {"pr", "det", "prn", "cnjcoo", "cnjsub", "prep", "conj", "article"}:
            if raw_par == "prep": par = "__pr"
            elif raw_par == "conj": par = "__cnjcoo"
            elif raw_par == "article": par = "__det"
            else: par = "__" + raw_par
        elif pos in {"pr", "det", "prn", "cnjcoo", "cnjsub"}:
            par = "__" + pos

        # Calculate stem based on paradigm
        stem = extract_stem(clean_lm, str(par))
        
        en = ET.SubElement(section, "e", lm=clean_lm)
        i = ET.SubElement(en, "i")
        i.text = stem
        par_elem = ET.SubElement(en, "par")
        par_elem.set("n", str(par))
        par_elem.tail = "" # No newlines
    return dictionary


def build_bidix(entries):

    dictionary = ET.Element("dictionary")
    alphabet = ET.SubElement(dictionary, "alphabet")
    alphabet.text = "abcdefghijklmnopqrstuvwxyzĉĝĥĵŝŭABCDEFGHIJKLMNOPQRSTUVWXYZĈĜĤĴŜŬ"
    sdefs = ET.SubElement(dictionary, "sdefs")
    for s in ["n", "adj", "adv", "vblex", "vbtr", "pr", "prn", "det", "num", "cnjcoo", "cnjsub", "ij", "sg", "pl", "sp", "nom", "acc", "inf", "pri", "pii", "fti", "cni", "imp", "pp", "pp3", "ppres", "p1", "p2", "p3", "ciph", "np", "def", "der_pres", "der_act", "der_qual", "der_oz", "der_izar", "der_past", "der_ppa", "der_ppas", "der_pprs", "der_pfut", "der_ppra"]:
        ET.SubElement(sdefs, "sdef", n=s)
    section = ET.SubElement(dictionary, "section", id="main", type="standard")
    def map_s_tag(par: str, pos: str | None) -> str | None:
        if par in ("o__n",):
            return "n"
        if par in ("a__adj",):
            return "adj"
        if par in ("e__adv",):
            return "adv"
        if par in ("ar__vblex",):
            return "vblex"
        if par in ("num",):
            return "num"
        if par in ("num_regex",):
            return "num"
        # Check if par is a function word POS directly (from FUNCTION_WORDS dict)
        if par in ("pr", "det", "prn", "cnjcoo", "cnjsub", "prep_art"):
            return par if par != "prep_art" else None
        if pos in ("pr", "det", "prn", "cnjcoo", "cnjsub"):
            return pos
        return None

    sorted_entries = sorted(entries, key=lambda e: (
        (e.get("lemma") or "").lower(), e.get("lemma") or ""))

    for e in sorted_entries:
        # New format doesn't have "language" field - all entries are Ido by default
        if e.get("language") and e.get("language") != "io":
            continue
        
        lm = e.get("lemma")
        if not lm:
            continue
        
        clean_lm = str(lm).strip()
        raw_par = (e.get("morphology") or {}).get("paradigm") or None
        pos = e.get("pos") if isinstance(e.get("pos"), str) else None

        # Collect EO translations - check both old and new formats
        eo_terms = []

        # New format: direct eo_translations field (BIG BIDIX format)
        if "eo_translations" in e and isinstance(e["eo_translations"], list):
            for raw_term in e["eo_translations"]:
                term = _clean_translation_term(str(raw_term))
                if term and term not in eo_terms:
                    eo_terms.append(term)

        # Old format: senses with translations
        for s in e.get("senses", []) or []:
            for tr in s.get("translations", []) or []:
                if tr.get("lang") == "eo":
                    raw_term = tr.get("term")
                    if raw_term:
                        term = _clean_translation_term(str(raw_term))
                        if term and term not in eo_terms:
                            eo_terms.append(term)
        if not eo_terms:
            continue
        # Use first translation as primary
        epo = eo_terms[0]
        en = ET.SubElement(section, "e")
        p = ET.SubElement(en, "p")

        # Determine Ido paradigm FIRST (needed for stem extraction)
        raw_par = (e.get("morphology") or {}).get("paradigm") or None
        pos = e.get("pos") if isinstance(e.get("pos"), str) else None
        # Normalize verbose POS names to short Apertium tags.
        if pos and pos in _VERBOSE_POS:
            pos = _VERBOSE_POS[pos]

        # Try function words first
        if not raw_par and clean_lm.lower() in _FUNCTION_WORDS:
            raw_par = _FUNCTION_WORDS[clean_lm.lower()]

        # Infer paradigm from POS (normalized upstream) or lemma ending as fallback.
        if not raw_par:
            if pos in {"vblex", "verb"}:
                raw_par = "ar__vblex"
            elif pos == "adj":
                raw_par = "a__adj"
            elif pos == "adv":
                raw_par = "e__adv"
            elif pos in {"pr", "det", "prn", "cnjcoo", "cnjsub"}:
                raw_par = "__" + pos
            else:
                # Ending heuristic for un-normalized entries (e.g. fr_wiktionary)
                lm_lower = clean_lm.lower()
                if lm_lower.endswith("ar") or lm_lower.endswith("ir"):
                    raw_par = "ar__vblex"
                elif lm_lower.endswith("a"):
                    raw_par = "a__adj"
                elif lm_lower.endswith("e"):
                    raw_par = "e__adv"
                else:
                    raw_par = "o__n"

        ido_tag = map_s_tag(raw_par, pos)

        # Extract stem from lemma for bilingual dictionary
        stem = extract_stem(clean_lm, str(raw_par))

        # Left (Ido) - use STEM, not full lemma
        l = ET.SubElement(p, "l")
        l.text = stem
        
        # Determine tags for Left (Ido)
        l_tags = []
        if raw_par == 'prep_art':
            l_tags = ["pr", "def"]
        elif ido_tag:
            l_tags = [ido_tag]
        
        for t in l_tags:
            s_elem = ET.SubElement(l, "s")
            s_elem.set("n", t)
            s_elem.tail = ""
        
        # Right (Esperanto)
        r = ET.SubElement(p, "r")
        
        # If multi-word (e.g. "de la"), split into multiple tags/blocks
        if " " in epo:
            words = epo.split()
            for i, word in enumerate(words):
                if i == 0:
                    r.text = word
                else:
                    # Add blank between words
                    b = ET.SubElement(r, "b")
                    b.tail = word
                
                # Guess tag for the word (simplified)
                # 'de' -> pr, 'la' -> det
                tag = "pr" if word == 'de' else ("det" if word == 'la' else (ido_tag or "n"))
                
                s_elem = ET.SubElement(r, "s")
                s_elem.set("n", tag)
                s_elem.tail = ""
        else:
            r.text = epo
            # Use the same tags as left side for single-word translations
            for t in l_tags:
                s_elem = ET.SubElement(r, "s")
                s_elem.set("n", t)
                s_elem.tail = ""

        # Productive derivational morphology: generate bilingual entries for
        # derived forms of known stems so any stem in the dict gets derivations free.
        # Include <n> on both sides so inflection tags pass through cleanly (no double tags).
        # Left: stem<vblex><der_X><n> — consumes all derivation symbols including noun tag.
        # Right: epo_form<n> — remaining <sg><nom> etc. pass through from input.
        if raw_par == 'ar__vblex' and epo and epo.endswith('i') and ' ' not in epo:
            epo_stem = epo[:-1]  # 'krei' → 'kre'
            # Noun-form derivations: -anto, -ado, -into (der tag + n)
            for der_tag, epo_suffix in [('der_pres', 'anto'), ('der_act', 'ado'), ('der_past', 'into')]:
                e_der = ET.SubElement(section, "e")
                p_der = ET.SubElement(e_der, "p")
                l_der = ET.SubElement(p_der, "l")
                l_der.text = stem
                ET.SubElement(l_der, "s", n="vblex").tail = ""
                ET.SubElement(l_der, "s", n=der_tag).tail = ""
                ET.SubElement(l_der, "s", n="n").tail = ""
                r_der = ET.SubElement(p_der, "r")
                r_der.text = epo_stem + epo_suffix
                ET.SubElement(r_der, "s", n="n").tail = ""
            # Participle adjectives: map to Epo verb paradigm tags for correct generation.
            # der_ppas(-ita): krei<vblex><pp>+<sg><nom> → kreita
            # der_ppa(-inta):  krei<vblex><pp3>+<sg>    → kreinta  (no <nom> in pardefs)
            # der_pprs(-ata):  krei<vbtr><ppres>+<sg><nom> → kreata
            # der_ppra(-anta) and der_pfut(-ota): apertium-epo cannot generate these.
            # Output surface form + <adj> so autobil blocks verb-fallback and shows
            # #kreanta/#kreota rather than the confusing #krei fallback.
            for der_tag, epo_suffix in [('der_ppra', 'anta'), ('der_pfut', 'ota')]:
                e_der = ET.SubElement(section, "e")
                p_der = ET.SubElement(e_der, "p")
                l_der = ET.SubElement(p_der, "l")
                l_der.text = stem
                ET.SubElement(l_der, "s", n="vblex").tail = ""
                ET.SubElement(l_der, "s", n=der_tag).tail = ""
                ET.SubElement(l_der, "s", n="adj").tail = ""
                r_der = ET.SubElement(p_der, "r")
                r_der.text = epo_stem + epo_suffix
                ET.SubElement(r_der, "s", n="adj").tail = ""
            for der_tag, epo_vtag, epo_ptag in [
                ('der_ppas', 'vblex', 'pp'),
                ('der_ppa',  'vblex', 'pp3'),
                ('der_pprs', 'vbtr',  'ppres'),
            ]:
                e_der = ET.SubElement(section, "e")
                p_der = ET.SubElement(e_der, "p")
                l_der = ET.SubElement(p_der, "l")
                l_der.text = stem
                ET.SubElement(l_der, "s", n="vblex").tail = ""
                ET.SubElement(l_der, "s", n=der_tag).tail = ""
                ET.SubElement(l_der, "s", n="adj").tail = ""
                r_der = ET.SubElement(p_der, "r")
                r_der.text = epo  # Epo verb lemma (e.g. 'krei'), not a suffix combo
                ET.SubElement(r_der, "s", n=epo_vtag).tail = ""
                ET.SubElement(r_der, "s", n=epo_ptag).tail = ""
        elif raw_par == 'a__adj' and epo and epo.endswith('a') and ' ' not in epo:
            epo_stem = epo[:-1]  # 'bona' → 'bon'
            e_der = ET.SubElement(section, "e")
            p_der = ET.SubElement(e_der, "p")
            l_der = ET.SubElement(p_der, "l")
            l_der.text = stem
            ET.SubElement(l_der, "s", n="adj").tail = ""
            ET.SubElement(l_der, "s", n="der_qual").tail = ""
            ET.SubElement(l_der, "s", n="n").tail = ""
            r_der = ET.SubElement(p_der, "r")
            r_der.text = epo_stem + 'eco'
            ET.SubElement(r_der, "s", n="n").tail = ""
        elif raw_par == 'o__n' and epo and ' ' not in epo:
            # -oza suffix: suces+oza → sucesoza ("full of success")
            epo_stripped = epo[:-1] if epo.endswith('o') else epo  # 'sukceso' → 'sukcес'
            e_der = ET.SubElement(section, "e")
            p_der = ET.SubElement(e_der, "p")
            l_der = ET.SubElement(p_der, "l")
            l_der.text = stem
            ET.SubElement(l_der, "s", n="n").tail = ""
            ET.SubElement(l_der, "s", n="der_oz").tail = ""
            ET.SubElement(l_der, "s", n="adj").tail = ""
            r_der = ET.SubElement(p_der, "r")
            r_der.text = epo_stripped + 'a'
            ET.SubElement(r_der, "s", n="adj").tail = ""
            # -izar suffix: nom+izar → nomizar (to name); Epo: strip -o, add -i
            # Emit all tenses so the bidix covers nomizar/nomizas/nomizis/...
            if epo.endswith('o'):
                epo_verb = epo[:-1] + 'i'  # 'nomo' → 'nomi'
                for tense in ['inf', 'pri', 'pii', 'fti', 'cni', 'imp']:
                    e_iz = ET.SubElement(section, "e")
                    p_iz = ET.SubElement(e_iz, "p")
                    l_iz = ET.SubElement(p_iz, "l")
                    l_iz.text = stem
                    ET.SubElement(l_iz, "s", n="n").tail = ""
                    ET.SubElement(l_iz, "s", n="der_izar").tail = ""
                    ET.SubElement(l_iz, "s", n="vblex").tail = ""
                    ET.SubElement(l_iz, "s", n=tense).tail = ""
                    r_iz = ET.SubElement(p_iz, "r")
                    r_iz.text = epo_verb
                    ET.SubElement(r_iz, "s", n="vblex").tail = ""
                    ET.SubElement(r_iz, "s", n=tense).tail = ""
    return dictionary


def export_apertium(entries_path: Path, out_monodix: Path, bidix_entries_path: Path, out_bidix: Path) -> None:
    ensure_dir(out_monodix.parent)
    data = read_json(entries_path)
    
    # Handle both old format (list) and new format (dict with "entries" key)
    if isinstance(data, dict) and 'entries' in data:
        entries = data['entries']
    elif isinstance(data, list):
        entries = data
    else:
        entries = data
    
    # Build bilingual dictionary from separate file
    bidix_data = read_json(bidix_entries_path)
    if isinstance(bidix_data, dict) and 'entries' in bidix_data:
        bidix_entries = bidix_data['entries']
    elif isinstance(bidix_data, list):
        bidix_entries = bidix_data
    else:
        bidix_entries = bidix_data

    # Merge bidix-only entries into monodix so words with Epo translations
    # but absent from final_vocabulary are still morphologically analyzable.
    # Index bidix entries by lower-case lemma, preferring entries with non-null POS.
    bidix_by_lemma = {}
    for be in bidix_entries:
        lm = (be.get('lemma') or '').lower()
        if not lm:
            continue
        existing = bidix_by_lemma.get(lm)
        if existing is None or (not existing.get('pos') and be.get('pos')):
            bidix_by_lemma[lm] = be
    # Upgrade vocab entries that have no pos/paradigm using the bidix entry
    for ve in entries:
        lm = (ve.get('lemma') or '').lower()
        if not ve.get('pos') and not (ve.get('morphology') or {}).get('paradigm'):
            be = bidix_by_lemma.get(lm)
            if be and be.get('pos'):
                ve['pos'] = be['pos']
                if be.get('morphology'):
                    ve['morphology'] = be['morphology']
    existing_lemmas = {(e.get('lemma') or '').lower() for e in entries}
    extra = [e for e in bidix_entries if (e.get('lemma') or '').lower() not in existing_lemmas]
    mono_entries = entries + extra
    logging.info(f"Monodix: {len(entries)} vocab + {len(extra)} bidix-only = {len(mono_entries)} total")

    mono = build_monodix(mono_entries)
    write_xml_file(mono, out_monodix)

    logging.info(f"Building bilingual dictionary from {len(bidix_entries)} entries")
    bidi = build_bidix(bidix_entries)
    write_xml_file(bidi, out_bidix)
    logging.info("Exported Apertium XML: %s, %s", out_monodix, out_bidix)


def main(argv: Iterable[str]) -> int:
    ap = argparse.ArgumentParser(description="Export dictionaries to Apertium .dix (no commit)")
    ap.add_argument("--input", type=Path, default=Path(__file__).resolve().parents[1] / "work/final_vocabulary.json")
    ap.add_argument("--big-bidix", type=Path, default=Path(__file__).resolve().parents[1] / "dist/bidix_big.json")
    ap.add_argument("--out-mono", type=Path, default=Path(__file__).resolve().parents[1] / "dist/apertium-ido.ido.dix")
    ap.add_argument("--out-bidi", type=Path, default=Path(__file__).resolve().parents[1] / "dist/apertium-ido-epo.ido-epo.dix")
    ap.add_argument("-v", "--verbose", action="count", default=0)
    args = ap.parse_args(list(argv))

    configure_logging(args.verbose)
    # For monodix we still use final_vocabulary; for bidix we prefer BIG BIDIX if present
    input_for_bidi = args.big_bidix if args.big_bidix.exists() else args.input
    export_apertium(args.input, args.out_mono, input_for_bidi, args.out_bidi)
    return 0


if __name__ == "__main__":
    import sys
    raise SystemExit(main(sys.argv[1:]))


