#!/usr/bin/env python3
import argparse
import logging
from pathlib import Path
from typing import Iterable

from _common import read_json, ensure_dir, configure_logging
import xml.etree.ElementTree as ET


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
    for s in ["n", "adj", "adv", "vblex", "pr", "prn", "det", "num", "cnjcoo", "cnjsub", "ij", "sg", "pl", "sp", "nom", "acc", "inf", "pri", "pii", "fti", "cni", "imp", "p1", "p2", "p3", "m", "f", "mf", "nt", "np", "ant", "cog", "top", "al"]:
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
        if par in ("__pr", "__det", "__prn", "__cnjcoo", "__cnjsub"):
            return par.replace("__", "")
        # Map raw pos for function words
        if pos in ("pr", "det", "prn", "cnjcoo", "cnjsub"):
            return pos
        return None

    # Sort entries alphabetically by lemma before adding to section
    sorted_entries = sorted(entries, key=lambda e: (e.get("lemma", "").lower(), e.get("lemma", "")))
    
    for e in sorted_entries:
        # New format doesn't have "language" field - all entries are Ido by default
        # Old format had language field, so check if present
        if e.get("language") and e.get("language") != "io":
            continue
        
        lm = e.get("lemma")
        if not lm:
            continue
            
        raw_par = (e.get("morphology") or {}).get("paradigm") or "o__n"
        pos = e.get("pos") if isinstance(e.get("pos"), str) else None
        # Normalize function-word paradigms
        par = raw_par
        if raw_par in {"pr", "det", "prn", "cnjcoo", "cnjsub"}:
            par = "__" + raw_par
        en = ET.SubElement(section, "e", lm=str(lm))
        i = ET.SubElement(en, "i")
        i.text = str(lm)
        ET.SubElement(en, "par", n=str(par))
    return dictionary


def build_bidix(entries):
    dictionary = ET.Element("dictionary")
    alphabet = ET.SubElement(dictionary, "alphabet")
    alphabet.text = "abcdefghijklmnopqrstuvwxyzĉĝĥĵŝŭABCDEFGHIJKLMNOPQRSTUVWXYZĈĜĤĴŜŬ"
    sdefs = ET.SubElement(dictionary, "sdefs")
    for s in ["n", "adj", "adv", "vblex", "pr", "prn", "det", "num", "cnjcoo", "cnjsub", "ij", "sg", "pl", "sp", "nom", "acc", "inf", "pri", "pii", "fti", "cni", "imp", "p1", "p2", "p3"]:
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
        if pos in ("pr", "det", "prn", "cnjcoo", "cnjsub"):
            return pos
        return None

    # Sort entries alphabetically by lemma before adding to section
    sorted_entries = sorted(entries, key=lambda e: (e.get("lemma", "").lower(), e.get("lemma", "")))
    
    for e in sorted_entries:
        # New format doesn't have "language" field - all entries are Ido by default
        if e.get("language") and e.get("language") != "io":
            continue
        
        lm = e.get("lemma")
        if not lm:
            continue
            
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
                        # Append sources indicator in braces if available (short codes)
                        sources = []
                        srcs = tr.get("sources") or []
                        for sname in srcs:
                            if "io_wiktionary" in sname:
                                sources.append("wikt_io")
                            elif "eo_wiktionary" in sname:
                                sources.append("wikt_eo")
                            elif "wikipedia" in sname:
                                sources.append("wiki_io")
                            elif "pivot_en" in sname:
                                sources.append("pivot_en")
                            elif "pivot_fr" in sname:
                                sources.append("pivot_fr")
                            elif "fr_wiktionary_meaning" in sname:
                                sources.append("fr_wikt_m")
                            elif "langlinks" in sname:
                                sources.append("ll")
                        label = f"{term}"
                        if sources:
                            label = f"{term}{{{','.join(sorted(set(sources)))}}}"
                        eo_terms.append(label)
        if not eo_terms:
            continue
        # Use first translation as primary
        epo = eo_terms[0]
        en = ET.SubElement(section, "e")
        p = ET.SubElement(en, "p")
        l = ET.SubElement(p, "l")
        l.text = str(lm)
        s_tag = map_s_tag(raw_par or "", pos)
        if s_tag:
            ET.SubElement(l, "s", n=s_tag)
        r = ET.SubElement(p, "r")
        r.text = str(epo)
        if s_tag:
            ET.SubElement(r, "s", n=s_tag)
    return dictionary


def export_apertium(entries_path: Path, out_monodix: Path, out_bidix: Path) -> None:
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
    bidi = build_bidix(entries)
    write_xml_file(mono, out_monodix)
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
    export_apertium(input_for_bidi, args.out_mono, args.out_bidi)
    return 0


if __name__ == "__main__":
    import sys
    raise SystemExit(main(sys.argv[1:]))


