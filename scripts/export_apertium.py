#!/usr/bin/env python3
import argparse
import logging
from pathlib import Path
from typing import Iterable

from _common import read_json, ensure_dir, configure_logging
import xml.etree.ElementTree as ET


def pretty_bytes(elem: ET.Element) -> bytes:
    # Minimal pretty output compatible with Apertium
    return ET.tostring(elem, encoding="utf-8") + b"\n"


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

    section = ET.SubElement(dictionary, "section", id="main", type="standard")
    for e in entries:
        if e.get("language") != "io":
            continue
        lm = e.get("lemma")
        par = (e.get("morphology") or {}).get("paradigm") or "o__n"
        pos = e.get("pos")
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
    for e in entries:
        if e.get("language") != "io":
            continue
        lm = e.get("lemma")
        pos = e.get("pos")
        # Collect EO translations
        eo_terms = []
        for s in e.get("senses", []) or []:
            for tr in s.get("translations", []) or []:
                if tr.get("lang") == "eo":
                    term = tr.get("term")
                    if term:
                        eo_terms.append(str(term))
        if not eo_terms:
            continue
        # Use first translation as primary
        epo = eo_terms[0]
        en = ET.SubElement(section, "e")
        p = ET.SubElement(en, "p")
        l = ET.SubElement(p, "l")
        l.text = str(lm)
        if pos:
            ET.SubElement(l, "s", n=str(pos))
        r = ET.SubElement(p, "r")
        r.text = str(epo)
        if pos:
            ET.SubElement(r, "s", n=str(pos))
    return dictionary


def export_apertium(entries_path: Path, out_monodix: Path, out_bidix: Path) -> None:
    ensure_dir(out_monodix.parent)
    entries = read_json(entries_path)
    mono = build_monodix(entries)
    bidi = build_bidix(entries)
    out_monodix.write_bytes(pretty_bytes(mono))
    out_bidix.write_bytes(pretty_bytes(bidi))
    logging.info("Exported Apertium XML: %s, %s", out_monodix, out_bidix)


def main(argv: Iterable[str]) -> int:
    ap = argparse.ArgumentParser(description="Export dictionaries to Apertium .dix (no commit)")
    ap.add_argument("--input", type=Path, default=Path(__file__).resolve().parents[1] / "work/final_vocabulary.json")
    ap.add_argument("--out-mono", type=Path, default=Path(__file__).resolve().parents[1] / "dist/apertium-ido.ido.dix")
    ap.add_argument("--out-bidi", type=Path, default=Path(__file__).resolve().parents[1] / "dist/apertium-ido-epo.ido-epo.dix")
    ap.add_argument("-v", "--verbose", action="count", default=0)
    args = ap.parse_args(list(argv))

    configure_logging(args.verbose)
    export_apertium(args.input, args.out_mono, args.out_bidi)
    return 0


if __name__ == "__main__":
    import sys
    raise SystemExit(main(sys.argv[1:]))


