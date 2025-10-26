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
    """Write properly formatted Apertium XML with declaration and indentation."""
    # Add XML declaration
    xml_declaration = b'<?xml version="1.0" encoding="UTF-8"?>\n'
    
    # Format the XML with indentation
    ET.indent(elem, space="  ")
    
    # Write to file
    with open(output_path, 'wb') as f:
        f.write(xml_declaration)
        f.write(ET.tostring(elem, encoding="utf-8"))
        f.write(b'\n')


def build_monodix(entries):
    dictionary = ET.Element("dictionary")
    alphabet = ET.SubElement(dictionary, "alphabet")
    alphabet.text = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    sdefs = ET.SubElement(dictionary, "sdefs")
    for s in ["n", "adj", "adv", "vblex", "pr", "prn", "det", "num", "cnjcoo", "cnjsub", "ij", "sg", "pl", "sp", "nom", "acc", "inf", "pri", "pii", "fti", "cni", "imp", "p1", "p2", "p3", "m", "f", "mf", "nt", "np", "ant", "cog", "top", "al", "ciph"]:
        ET.SubElement(sdefs, "sdef", n=s)
    pardefs = ET.SubElement(dictionary, "pardefs")
    # Basic paradigms
    def add_paradigm(name: str, l_text: str, r_s: list):
        pd = ET.SubElement(pardefs, "pardef", n=name)
        e = ET.SubElement(pd, "e")
        p = ET.SubElement(e, "p")
        ET.SubElement(p, "l").text = l_text
        r = ET.SubElement(p, "r")
        for s in r_s:
            ET.SubElement(r, "s", n=s)
    add_paradigm("o__n", "o", ["n", "sg", "nom"])  # minimal
    add_paradigm("a__adj", "a", ["adj"])  # minimal
    add_paradigm("e__adv", "e", ["adv"])  # minimal
    add_paradigm("ar__vblex", "ar", ["vblex", "inf"])  # minimal
    add_paradigm("num", "", ["num"])  # numbers: no inflection

    # Add regex paradigm for compound numbers (like 123, 4567, 12.34)
    # This follows the Esperanto pattern: <re>pattern</re><p><l></l><r>tags</r></p>
    pd = ET.SubElement(pardefs, "pardef", n="num_regex")
    e = ET.SubElement(pd, "e")
    re_elem = ET.SubElement(e, "re")
    re_elem.text = r"[0-9]+([.,][0-9]+)*"
    p = ET.SubElement(e, "p")
    ET.SubElement(p, "l")  # Empty left side
    r = ET.SubElement(p, "r")
    ET.SubElement(r, "s", n="num")
    ET.SubElement(r, "s", n="ciph")  # cipher (number)
    ET.SubElement(r, "s", n="sp")    # singular/plural
    ET.SubElement(r, "s", n="nom")   # nominative
    # Invariable paradigms for function words
    for iv in ["__pr", "__det", "__prn", "__cnjcoo", "__cnjsub"]:
        pd = ET.SubElement(pardefs, "pardef", n=iv)
        e = ET.SubElement(pd, "e")
        p = ET.SubElement(e, "p")
        ET.SubElement(p, "l").text = ""
        r = ET.SubElement(p, "r")
        ET.SubElement(r, "s", n=iv.replace("__", ""))

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
        if raw_par in {"pr", "det", "prn", "cnjcoo", "cnjsub"}:
            par = "__" + raw_par
        en = ET.SubElement(section, "e", lm=clean_lm)
        i = ET.SubElement(en, "i")
        i.text = clean_lm
        ET.SubElement(en, "par", n=str(par))
    return dictionary


def build_bidix(entries):
    dictionary = ET.Element("dictionary")
    alphabet = ET.SubElement(dictionary, "alphabet")
    alphabet.text = "abcdefghijklmnopqrstuvwxyzĉĝĥĵŝŭABCDEFGHIJKLMNOPQRSTUVWXYZĈĜĤĴŜŬ"
    sdefs = ET.SubElement(dictionary, "sdefs")
    for s in ["n", "adj", "adv", "vblex", "pr", "prn", "det", "num", "cnjcoo", "cnjsub", "ij", "sg", "pl", "sp", "nom", "acc", "inf", "pri", "pii", "fti", "cni", "imp", "p1", "p2", "p3", "ciph"]:
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
        l = ET.SubElement(p, "l")
        l.text = clean_lm
        s_tag = map_s_tag(raw_par or "", pos)
        if s_tag:
            ET.SubElement(l, "s", n=s_tag)
        r = ET.SubElement(p, "r")
        r.text = str(epo)
        if s_tag:
            ET.SubElement(r, "s", n=s_tag)
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


