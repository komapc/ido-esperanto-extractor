#!/usr/bin/env python3
import argparse
import logging
import re
from pathlib import Path
from typing import Iterable

from _common import read_json, ensure_dir, configure_logging
import xml.etree.ElementTree as ET

# Precompiled regex patterns for performance
METADATA_MARKER_RE = re.compile(r'\{[^}]+\}')
KATEGORIO_PREFIX_RE = re.compile(r'\s*Kategorio:[A-Za-z]+\s+[A-Z]+\s*')


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


def build_monodix(entries):
    dictionary = ET.Element("dictionary")
    alphabet = ET.SubElement(dictionary, "alphabet")
    alphabet.text = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    # Define sdefs for monolingual dictionary
    sdefs = ET.SubElement(dictionary, "sdefs")
    for s in ["n", "adj", "adv", "vblex", "pr", "prn", "det", "num", "cnjcoo", "cnjsub", "ij", "sg", "pl", "sp", "nom", "acc", "inf", "pri", "pii", "fti", "cni", "imp", "pp", "p1", "p2", "p3", "m", "f", "mf", "nt", "np", "ant", "cog", "top", "al", "ciph", "able", "pasv", "act", "ord", "def"]:
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

    def get_stem(lemma: str, paradigm: str) -> str:
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

    for e in sorted_entries:
        # New format doesn't have "language" field - all entries are Ido by default
        # Old format had language field, so check if present
        if e.get("language") and e.get("language") != "io":
            continue
        
        lm = e.get("lemma")
        if not lm:
            continue
        
        # Clean lemma of any existing metadata markers
        clean_lm = str(lm)
        # Remove {wikt_io}, {wikt_eo}, etc. markers
        clean_lm = METADATA_MARKER_RE.sub('', clean_lm)
        # Remove Kategorio: prefixes and suffixes
        clean_lm = KATEGORIO_PREFIX_RE.sub('', clean_lm)
        # Remove any remaining whitespace
        clean_lm = clean_lm.strip()
            
        raw_par = (e.get("morphology") or {}).get("paradigm") or "o__n"
        pos = e.get("pos") if isinstance(e.get("pos"), str) else None

        # Normalize function-word paradigms
        par = raw_par
        # Special case for prepositional articles (dil, dal, etc.)
        if raw_par == 'prep_art':
            par = "__prep_art"
        elif raw_par in {"pr", "det", "prn", "cnjcoo", "cnjsub", "prep", "conj", "article"}:
            if raw_par == "prep": par = "__pr"
            elif raw_par == "conj": par = "__cnjcoo"
            elif raw_par == "article": par = "__det"
            else: par = "__" + raw_par
        elif pos in {"pr", "det", "prn", "cnjcoo", "cnjsub"}:
            par = "__" + pos

        # Calculate stem based on paradigm
        stem = get_stem(clean_lm, str(par))
        
        en = ET.SubElement(section, "e", lm=clean_lm)
        i = ET.SubElement(en, "i")
        i.text = stem
        par_elem = ET.SubElement(en, "par")
        par_elem.set("n", str(par))
        par_elem.tail = "" # No newlines
    return dictionary


def build_bidix(entries):
    # Ido Function Words and Contractions (re-used from infer_morphology)
    FUNCTION_WORDS = {
        'dil': 'prep_art', 'dal': 'prep_art', 'del': 'prep_art', 'al': 'prep_art', 
        'el': 'prep_art', 'ol': 'prep_art', 'sil': 'prep_art', 'vual': 'prep_art',
        'la': 'det', 'le': 'det', 'lo': 'det',
        'de': 'pr', 'di': 'pr', 'da': 'pr', 'a': 'pr', 'en': 'pr', 'pro': 'pr', 
        'per': 'pr', 'kon': 'pr', 'kontre': 'pr', 'pri': 'pr', 'por': 'pr', 
        'sur': 'pr', 'sub': 'pr', 'super': 'pr', 'tra': 'pr', 'cis': 'pr', 
        'trans': 'pr', 'ultre': 'pr', 'inter': 'pr', 'ex': 'pr', 'til': 'pr',
        'dum': 'pr', 'sine': 'pr', 'veze': 'pr', 'be': 'pr', 'po': 'pr',
        'propre': 'pr', 'lor': 'pr', 'avan': 'pr', 'dop': 'pr', 'infre': 'pr',
        'nome': 'pr', 'konten': 'pr', 'kontene': 'pr', 'pos': 'pr', 'pre': 'pr',
        'che': 'pr', 'ye': 'pr', 'coram': 'pr', 'koram': 'pr', 'travers': 'pr',
        'alonge': 'pr', 'segun': 'pr', 'vice': 'pr', 'kontree': 'pr', 'proxim': 'pr',
        'apud': 'pr', 'chefe': 'pr', 'dextre': 'pr', 'sinistre': 'pr',
        'e': 'cnjcoo', 'ed': 'cnjcoo', 'o': 'cnjcoo', 'od': 'cnjcoo', 
        'ma': 'cnjcoo', 'nam': 'cnjsub', 'ke': 'cnjsub', 'se': 'cnjsub', 
        'yen': 'cnjcoo', 'nek': 'cnjcoo', ' sive': 'cnjcoo',
        'me': 'prn', 'tu': 'prn', 'vu': 'prn', 'ilu': 'prn', 'elu': 'prn', 
        'olu': 'prn', 'eli': 'prn', 'ili': 'prn', 'oli': 'prn', 'ni': 'prn', 
        'vi': 'prn', 'li': 'prn', 'on': 'prn', 'onu': 'prn', 'su': 'prn',
        'ca': 'prn', 'ta': 'prn', 'cua': 'prn', 'qua': 'prn', 'qui': 'prn',
        'ulo': 'prn', 'ulo-ca': 'prn', 'ulo-ta': 'prn', 'nulo': 'prn',
        'omna': 'det', 'nula': 'det', 'irga': 'det', 'altra': 'det',
        'singla': 'det', 'vula': 'det', 'tala': 'det', 'quala': 'det',
    }

    dictionary = ET.Element("dictionary")
    alphabet = ET.SubElement(dictionary, "alphabet")
    alphabet.text = "abcdefghijklmnopqrstuvwxyzĉĝĥĵŝŭABCDEFGHIJKLMNOPQRSTUVWXYZĈĜĤĴŜŬ"
    sdefs = ET.SubElement(dictionary, "sdefs")
    for s in ["n", "adj", "adv", "vblex", "pr", "prn", "det", "num", "cnjcoo", "cnjsub", "ij", "sg", "pl", "sp", "nom", "acc", "inf", "pri", "pii", "fti", "cni", "imp", "p1", "p2", "p3", "ciph", "np", "def"]:
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
        if pos in ("pr", "det", "prn", "cnjcoo", "cnjsub"):
            return pos
        return None

    # Sort entries alphabetically by lemma before adding to section
    # Handle None lemmas safely by using 'or ""' to convert None to empty string
    sorted_entries = sorted(entries, key=lambda e: ((e.get("lemma") or "").lower(), e.get("lemma") or ""))
    
    for e in sorted_entries:
        # New format doesn't have "language" field - all entries are Ido by default
        if e.get("language") and e.get("language") != "io":
            continue
        
        lm = e.get("lemma")
        if not lm:
            continue
        
        # Clean lemma of any existing metadata markers
        clean_lm = str(lm)
        # Remove {wikt_io}, {wikt_eo}, etc. markers
        clean_lm = METADATA_MARKER_RE.sub('', clean_lm)
        # Remove Kategorio: prefixes and suffixes
        clean_lm = KATEGORIO_PREFIX_RE.sub('', clean_lm)
        # Remove any remaining whitespace
        clean_lm = clean_lm.strip()
            
        raw_par = (e.get("morphology") or {}).get("paradigm") or None
        pos = e.get("pos") if isinstance(e.get("pos"), str) else None
        
        # Collect EO translations - check both old and new formats
        eo_terms = []
        
        # New format: direct eo_translations field (BIG BIDIX format)
        if "eo_translations" in e and isinstance(e["eo_translations"], list):
            eo_terms.extend(e["eo_translations"])
        
        # Old format: senses with translations
        for s in e.get("senses", []) or []:
            for tr in s.get("translations", []) or []:
                if tr.get("lang") == "eo":
                    term = tr.get("term")
                    if term and term not in eo_terms:
                        # Clean term of any existing metadata markers
                        clean_term = term
                        # Remove {wikt_io}, {wikt_eo}, etc. markers
                        clean_term = METADATA_MARKER_RE.sub('', clean_term)
                        # Remove Kategorio: prefixes and suffixes
                        clean_term = KATEGORIO_PREFIX_RE.sub('', clean_term)
                        # Remove any remaining whitespace
                        clean_term = clean_term.strip()
                        eo_terms.append(clean_term)
        if not eo_terms:
            continue
        # Use first translation as primary
        epo = eo_terms[0]
        en = ET.SubElement(section, "e")
        p = ET.SubElement(en, "p")

        # Left (Ido)
        l = ET.SubElement(p, "l")
        l.text = clean_lm
        
        # Determine Ido tag
        raw_par = (e.get("morphology") or {}).get("paradigm") or None
        if not raw_par and clean_lm.lower() in FUNCTION_WORDS:
            raw_par = FUNCTION_WORDS[clean_lm.lower()]
        
        if not raw_par:
            raw_par = "o__n"
            
        pos = e.get("pos") if isinstance(e.get("pos"), str) else None
        ido_tag = map_s_tag(raw_par, pos)
        
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
    
    logging.info(f"Exporting {len(entries)} entries to Apertium XML")
    mono = build_monodix(entries)
    write_xml_file(mono, out_monodix)
    
    # Build bilingual dictionary from separate file
    bidix_data = read_json(bidix_entries_path)
    if isinstance(bidix_data, dict) and 'entries' in bidix_data:
        bidix_entries = bidix_data['entries']
    elif isinstance(bidix_data, list):
        bidix_entries = bidix_data
    else:
        bidix_entries = bidix_data
    
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


