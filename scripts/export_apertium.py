#!/usr/bin/env python3
import argparse
import logging
import re
from pathlib import Path
from typing import Dict, Iterable

from _common import read_json, ensure_dir, configure_logging, clean_lemma
from lexicon_filters import is_junk_verb
from conflict_resolution import pick_best
import xml.etree.ElementTree as ET
from xml.sax.saxutils import quoteattr


# Maps contraction surface form → base preposition lemma (used by monodix/bidix).
# We encode contractions as explicit <p> entries so lt-proc -b can handle them
# without needing multi-token output (which lt-proc -b does not support).
_PREP_ART: Dict[str, str] = {
    'dal': 'da',  # da + la → da<pr><def>
    'del': 'de',  # de + la → de<pr><def>
    'dil': 'di',  # di + la → di<pr><def>
    'el':  'e',   # e + la  → e<pr><def>
    'sil': 'si',  # si + la → si<pr><def>
    # NOTE: 'al' is NOT here — see _FUNCTION_WORDS comment
}

# Esperanto preposition equivalent for each Ido base preposition
_PREP_ART_EPO: Dict[str, str] = {
    'da': 'de', 'de': 'de', 'di': 'de', 'e': 'al', 'si': 'al',
}

_KATEGORIO_RE = re.compile(r'\s*Kategorio:[^\s]+.*$', re.IGNORECASE)


# Priority used when a lemma has multiple candidate entries (different sources/POS).
# Higher = preferred. Closed-class paradigms beat content-class because function
# words (la, kun, di, me, ke, ...) are commonly polluted by junk a__adj/o__n
# entries from BERT/fr_wiktionary alignments and would otherwise lose to them.
def _paradigm_priority(p: str) -> int:
    if p in ('prn', '__prn'):
        return 10
    if p in ('__pr', '__det', '__cnjcoo', '__cnjsub', 'prep_art', '__prep_art', '__num', 'num', '__adv', '__ij'):
        return 8
    if p in ('vblex', 'ar__vblex', 'adj', 'a__adj', 'adv', 'e__adv'):
        return 5
    if p in ('pr', 'det', 'num', 'cnjcoo', 'cnjsub'):
        return 3
    if p in ('o__n', 'n') or not p:
        return 1
    return 2


def _clean_translation_term(raw: str) -> str:
    """Strip arrow artifacts and Kategorio references from a translation term."""
    term = clean_lemma(raw).strip()
    term = _KATEGORIO_RE.sub('', term).strip()
    return term


# Container tags whose direct children each go on their own indented line.
# Everything else (notably <e>, <sdef>, <alphabet>) is serialised inline so that
# NO whitespace is ever introduced inside <l>/<r>/<i>/<g>/<b> text — that would
# corrupt surface forms. Indentation only ever appears *between* elements, which
# lttoolbox ignores (this matches the layout of the official Apertium dictionaries).
_BLOCK_TAGS = {"dictionary", "sdefs", "pardefs", "pardef", "section"}


def _serialize_inline(elem: ET.Element) -> str:
    """One <e>/<sdef>/… element on a single line, lt-proc-safe."""
    s = ET.tostring(elem, encoding="unicode")
    # <s n="n" /> -> <s n="n"/> : CRITICAL for lt-proc compatibility.
    return s.replace(" />", "/>").strip()


def _write_elem(elem: ET.Element, indent: str, out: list) -> None:
    if elem.tag in _BLOCK_TAGS and len(elem):
        attrs = "".join(f" {k}={quoteattr(v)}" for k, v in elem.attrib.items())
        out.append(f"{indent}<{elem.tag}{attrs}>")
        for child in elem:
            _write_elem(child, indent + "  ", out)
        out.append(f"{indent}</{elem.tag}>")
    else:
        out.append(indent + _serialize_inline(elem))


def write_xml_file(elem: ET.Element, output_path: Path, header_comment: str = None) -> None:
    """Write Apertium XML, pretty-printed one entry per line (human-readable and
    diffable, as Apertium trunk requires) without breaking lt-proc. An optional
    header_comment is emitted in the XML prolog (it must not contain '--')."""
    lines = ['<?xml version="1.0" encoding="UTF-8"?>']
    if header_comment:
        assert "--" not in header_comment, "XML comments may not contain '--'"
        lines.append("<!--\n" + header_comment.strip("\n") + "\n-->")
    _write_elem(elem, "", lines)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
        f.write("\n")

# Documentation of the language-specific derivation symbols (sdefs) used by both
# dictionaries, emitted into each .dix header so the custom tags are auditable —
# a requirement for upstreaming to official Apertium. Ido and Esperanto share a
# regular, productive suffix system; these symbols tag the derived analyses so
# the bilingual dictionary can map each Ido derivation to its Esperanto form.
_DERIVATION_DOC = """\
  Language-specific symbols — Ido productive derivational morphology
  (symbol  =  Ido suffix  ->  Esperanto output; example verb 'krear', noun 'monto'):

    der_act   Ido -ad-  action noun             krear    -> kreado     [n]
    der_pres  Ido -ant- agent / present noun     krear    -> kreanto    [n]
    der_past  Ido -int- past noun                krear    -> kreinto    [n]
    der_ppra  Ido -ant- active present participle krear   -> kreanta    [adj]
    der_ppa   Ido -int- active past participle    krear   -> kreinta    [adj]
    der_pprs  Ido -at-  passive present participle krear  -> kreata     [adj]
    der_ppas  Ido -it-  passive past participle   krear   -> kreita     [adj]
    der_pfut  Ido -ot-  passive future participle krear   -> kreota     [adj]
    der_qual  Ido -es-  abstract quality (from adj) bona  -> boneco     [n]
    der_ala   Ido -al-  relational adjective      ekonomio -> ekonomia  [adj]
    der_oz    Ido -oz-  'full of' adjective       sukceso  -> sukcesa   [adj]
    der_aro   Ido -ar-  collective noun           monto    -> montaro   [n]
    der_aj    Ido -aj-  concrete manifestation    (monodix analysis only)
    der_izar  Ido -iz-  'provide with' verb       (monodix analysis only)
    der_esar  Ido -es-  passive verb formant      (monodix analysis only)
"""

_MONODIX_HEADER = """\
  apertium-ido: Ido morphological dictionary.

  AUTO-GENERATED — do not edit by hand. Regenerate with the
  ido-esperanto-extractor pipeline (scripts/export_apertium.py). Lexical data is
  derived from Wiktionary, Wikipedia/Wikidata interwiki links and a cognate
  aligner; see the extractor for per-entry provenance. Sources are CC BY-SA;
  this dictionary is GPL-3.0.

""" + _DERIVATION_DOC

_BIDIX_HEADER = """\
  apertium-ido-epo: Ido <-> Esperanto bilingual dictionary.

  AUTO-GENERATED — do not edit by hand. Regenerate with the
  ido-esperanto-extractor pipeline (build_one_big_bidix_json.py then
  scripts/export_apertium.py). Lexical data is derived from Wiktionary,
  Wikipedia/Wikidata interwiki links and a cognate aligner; see the extractor
  for per-entry provenance. Sources are CC BY-SA; this dictionary is GPL-3.0.

""" + _DERIVATION_DOC


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
    if paradigm in {"__pr", "__det", "__prn", "__cnjcoo", "__cnjsub", "__prep_art", "__adv", "__ij"}:
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


def map_s_tag(par: str | None, pos: str | None) -> str | None:
    if not par:
        return pos if pos in ("pr", "det", "prn", "cnjcoo", "cnjsub", "ij") else None
        
    if par == "o__n":
        return "n"
    if par == "a__adj":
        return "adj"
    if par in ("e__adv", "__adv"):
        return "adv"
    if par == "ar__vblex":
        return "vblex"
    if par == "num":
        return "num"
    if par in ("__pr", "__det", "__prn", "__cnjcoo", "__cnjsub", "__ij"):
        return par.replace("__", "")

    # Map raw pos for function words as fallback
    if pos in ("pr", "det", "prn", "cnjcoo", "cnjsub", "ij"):
        return pos
    return None


# Personal pronouns that form a possessive (Ido lemma + 'a' -> EO pronoun + 'a',
# e.g. mea->mia, elua->ŝia, sua->sia). The EO side is derived from each pronoun's
# own sourced translation — no hardcoded Ido→EO possessive map.
# NOTE: this inventory is the only remaining hardcoded closed-class list here;
# TODO source it from the Wiktionary Ido pronoun-table parser (FLOW_REVIEW.md,
# deferred together with `il`).
_PERSONAL_PRONOUNS = frozenset({
    'me', 'tu', 'vu', 'lu', 'elu', 'ilu', 'olu', 'ni', 'vi', 'li', 'su',
})

# apertium-epo lemmatises the Esperanto personal pronouns as `prpers` with
# person/gender/number features (NOT as their surface form mi/ci/li/…), and its
# morphology only emits/accepts that paradigm. The ido→epo direction already
# bridges this in the .t1x (prn_to_subj / prn_to_obj map the bidix lemma →
# prpers + case). But epo→ido has no such path: apertium-epo analyses "mi" as
# `prpers<prn>…`, which the bidix never lists, so personal pronouns come out
# untranslated (@prpers). The two tables below add the epo→ido (RL) bidix
# entries that close that gap. This is closed-class grammatical morphology (the
# prpers paradigm is fixed by apertium-epo), not vocabulary.
#   surface -> (person, gender, number)  [apertium-epo prpers core features]
_EO_PRPERS_FEATS = {
    'mi':  ('p1', 'mf', 'sg'),
    'ni':  ('p1', 'mf', 'pl'),
    'ci':  ('p2', 'mf', 'sp'),
    'vi':  ('p2', 'mf', 'sp'),
    'li':  ('p3', 'm',  'sg'),
    'ŝi':  ('p3', 'f',  'sg'),
    'ĝi':  ('p3', 'nt', 'sg'),
    'ili': ('p3', 'mf', 'pl'),
}
# epo→ido needs ONE deterministic Ido pronoun per prpers feature-form (several
# Ido forms share a target — il/ilu/lu all → li; tu/vu/vi all → EO vi). Each
# feature tuple (person, gender, number) must appear once or biltrans returns an
# ambiguous reading. EO `vi`/`ci` share (p2,mf,sp): the gold corpus maps EO vi ↔
# Ido tu in the large majority, so p2 → tu. Canonical subject forms below; all
# generate cleanly in apertium-ido.
_EO_TO_IDO_PRN = {
    'mi': 'me', 'ni': 'ni', 'vi': 'tu',
    'li': 'il', 'ŝi': 'el', 'ĝi': 'ol', 'ili': 'li',
}


def _emit_prpers_rl_entries(section):
    """Emit the epo→ido (RL-only) personal-pronoun entries once: every prpers
    surface analysis apertium-epo can produce (subject, nominative, accusative,
    object) → the canonical Ido pronoun. RL-only so they never compete with the
    LR generation entries emitted per Ido pronoun in the main loop."""
    for eo_surf, ido_prn in _EO_TO_IDO_PRN.items():
        pers, gen, num = _EO_PRPERS_FEATS[eo_surf]
        # The forms apertium-epo emits (the first surviving reading after CG +
        # pretransfer is what reaches biltrans): nom/acc/obj are gender-specific.
        # The subject reading is gender-specific for ŝi/ĝi but apertium-epo also
        # emits a gender-underspecified `subj … mf …` reading for the masculine
        # "li" (its default-gender 3sg) — add that ONLY for masculine, or el/ol
        # would collide with il on `subj p3 mf sg`.
        forms = [
            ('subj', pers, gen, num),
            (pers, gen, num, 'nom'),
            (pers, gen, num, 'acc'),
            ('obj', pers, gen, num),
        ]
        if gen == 'm':
            forms.insert(1, ('subj', pers, 'mf', num))
        seen = set()
        for form in forms:
            if form in seen:
                continue
            seen.add(form)
            e_rl = ET.SubElement(section, "e")
            e_rl.set("r", "RL")
            p_rl = ET.SubElement(e_rl, "p")
            l_rl = ET.SubElement(p_rl, "l")
            l_rl.text = ido_prn
            ET.SubElement(l_rl, "s", n="prn").tail = ""
            r_rl = ET.SubElement(p_rl, "r")
            r_rl.text = "prpers"
            for t in ("prn",) + form:
                ET.SubElement(r_rl, "s", n=t).tail = ""


def build_monodix(entries):
    dictionary = ET.Element("dictionary")
    alphabet = ET.SubElement(dictionary, "alphabet")
    alphabet.text = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    # Define sdefs for monolingual dictionary
    sdefs = ET.SubElement(dictionary, "sdefs")
    for s in ["n", "adj", "adv", "vblex", "pr", "prn", "det", "num", "cnjcoo", "cnjsub", "ij", "sg", "pl", "sp", "nom", "acc", "inf", "pri", "pii", "fti", "cni", "imp", "pp", "p1", "p2", "p3", "m", "f", "mf", "nt", "np", "ant", "cog", "top", "al", "ciph", "able", "pasv", "act", "ord", "def", "sent", "der_pres", "der_act", "der_qual", "der_oz", "der_ala", "der_aro", "der_izar", "der_esar", "der_past", "der_ppa", "der_ppas", "der_pprs", "der_pfut", "der_ppra", "der_aj"]:
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
        def add_paradigm(name, l_text, r_s):
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
        add_paradigm("__adv", "", ["adv"])
        add_paradigm("ar__vblex", "ar", ["vblex", "inf"])
        add_paradigm("__ij", "", ["ij"])
        
        # Bidirectional number paradigm
        pd_num = ET.SubElement(pardefs, "pardef", n="num")
        e_num = ET.SubElement(pd_num, "e")
        p_num = ET.SubElement(e_num, "p")
        ET.SubElement(p_num, "l")
        r_num = ET.SubElement(p_num, "r")
        ET.SubElement(r_num, "s", n="num")

        # Add a specific num_regex pardef that works for both analysis and generation
        num_regex_pd = ET.SubElement(pardefs, "pardef", n="num_regex")
        nr_e = ET.SubElement(num_regex_pd, "e")
        ET.SubElement(nr_e, "re").text = "[0-9]+([.,][0-9]+)*"
        nr_p = ET.SubElement(nr_e, "p")
        # For analysis: match regex, output tags
        # For generation: match tags, output regex (passed through)
        ET.SubElement(nr_p, "l")
        nr_r = ET.SubElement(nr_p, "r")
        ET.SubElement(nr_r, "s", n="num")
        ET.SubElement(nr_r, "s", n="ciph")
        ET.SubElement(nr_r, "s", n="sp")
        ET.SubElement(nr_r, "s", n="nom")


    section = ET.SubElement(dictionary, "section", id="main", type="standard")
    # Number passthrough: regex entries must be first in section
    _num_sec = ET.SubElement(section, "e")
    ET.SubElement(_num_sec, "par", n="num_regex")
    # Digit-form ordinals: 1ma, 16ma, 16-ma
    _num_ord_sec = ET.SubElement(section, "e")
    ET.SubElement(_num_ord_sec, "par", n="num_ord_regex")

    # Sentence punctuation as real lexical units (inconditional section).
    # Without these the analyzer passes '.'/'?'/'!' through as blanks, so t1x
    # patterns match ACROSS sentence boundaries ("Il dormas. Bela kato venas."
    # → the vblex+adj+nom transitive rule fired across the period, yielding
    # "Belan katon venas."). A <sent> LU breaks token adjacency at the
    # boundary. Clause punctuation (, ; :) is deliberately left as blanks —
    # rules legitimately match across it (adj , adj nom chains).
    punct_section = ET.SubElement(dictionary, "section", id="punct", type="inconditional")
    for mark in (".", "?", "!", "…"):
        pe = ET.SubElement(punct_section, "e")
        pp = ET.SubElement(pe, "p")
        ET.SubElement(pp, "l").text = mark
        pr = ET.SubElement(pp, "r")
        pr.text = mark
        ET.SubElement(pr, "s", n="sent")

    # Deduplicate entries by lemma, prioritizing more specific paradigms over o__n
    best_entries = {}
    for e in entries:
        if e.get("language") and e.get("language") != "io":
            continue
        lm = str(e.get("lemma") or "").strip()
        if not lm:
            continue
        
        raw_par = (e.get("morphology") or {}).get("paradigm")
        
        if lm not in best_entries:
            best_entries[lm] = e
        else:
            old_par = (best_entries[lm].get("morphology") or {}).get("paradigm")
            if _paradigm_priority(raw_par) > _paradigm_priority(old_par):
                best_entries[lm] = e

    # Sort and collect entries for the section
    final_list = []

    # Track all lemmas added to prevent any duplicates
    global_seen_lemmas = set()

    # Step 1: Pre-process best entries and their possessives
    for lm, e in best_entries.items():
        clean_lm = lm
        raw_par = (e.get("morphology") or {}).get("paradigm")
        pos = e.get("pos") if isinstance(e.get("pos"), str) else None
        if not raw_par: raw_par = "o__n"

        # Expand paradigm
        par = raw_par
        if raw_par == "adv": par = "__adv"
        elif raw_par == "adj": par = "a__adj"
        elif raw_par == "num": par = "num"  # numerals: invariant, no inflection paradigm
        elif raw_par == "ij": par = "__ij"  # interjections: invariant
        elif raw_par == "n": par = "o__n"
        elif raw_par == "vblex": par = "ar__vblex"
        elif raw_par == 'prep_art': pass
        elif raw_par in {"pr", "det", "prn", "cnjcoo", "cnjsub", "prep", "conj", "article"}:
            if raw_par == "prep": par = "__pr"
            elif raw_par == "conj": par = "__cnjcoo"
            elif raw_par == "article": par = "__det"
            else: par = "__" + raw_par
        elif pos in {"pr", "det", "prn", "cnjcoo", "cnjsub"}:
            par = "__" + pos

        # Add base entry if not seen
        if clean_lm not in global_seen_lemmas:
            stem = extract_stem(clean_lm, str(par))
            # Defensive: skip if stem is empty AND paradigm uses suffix
            # matching (e.g. lemma 'ar' + paradigm 'ar__vblex' yields empty
            # stem since 'ar'[:-2] == ''). An empty-stem dix entry binds to
            # paradigm-only paths in lt-comp's transducer, producing
            # empty-lemma analyses for surface forms like 'esas' that match
            # paradigm `<l>esas</l>` rules. Such entries are almost always
            # io.wiktionary "Radiko por:" pages (morphological roots, not
            # lemmas) — even with the parser-level filter, this keeps the
            # dix safe against new root pages getting through.
            _SUFFIX_PARADIGMS = {'ar__vblex', 'ir__vblex', 'o__n', 'a__adj', 'e__adv'}
            if not stem and str(par) in _SUFFIX_PARADIGMS:
                continue
            final_list.append({
                'lm': clean_lm, 'stem': stem, 'par': str(par), 'raw_par': raw_par
            })
            global_seen_lemmas.add(clean_lm)

        # Add possessive if needed and not seen.
        # a__adj prepends the lemma's -a, so the stem is the bare pronoun
        # (me -> i="me" + "a" = surface "mea"); using poss_lm here yielded "meaa".
        if str(raw_par).strip('_') == 'prn' and clean_lm.lower() in _PERSONAL_PRONOUNS:
            poss_lm = clean_lm + 'a'
            if poss_lm not in global_seen_lemmas:
                final_list.append({
                    'lm': poss_lm, 'stem': clean_lm, 'par': "a__adj", 'raw_par': "adj"
                })
                global_seen_lemmas.add(poss_lm)

    # Sort final list by lemma
    final_list.sort(key=lambda x: (x['lm'].lower(), x['lm']))

    for item in final_list:
        clean_lm = item['lm']
        stem = item['stem']
        par = item['par']
        raw_par = item['raw_par']

        if raw_par == 'prep_art':
            lm_lc = clean_lm.lower()
            if lm_lc in _PREP_ART:
                base_prep = _PREP_ART[lm_lc]
                en = ET.SubElement(section, "e", lm=base_prep)
                p_elem = ET.SubElement(en, "p")
                l_elem = ET.SubElement(p_elem, "l")
                l_elem.text = clean_lm
                r_elem = ET.SubElement(p_elem, "r")
                r_elem.text = base_prep
                ET.SubElement(r_elem, "s", n="pr").tail = ""
                ET.SubElement(r_elem, "s", n="def").tail = ""
            else:
                en = ET.SubElement(section, "e", lm=clean_lm)
                i = ET.SubElement(en, "i")
                i.text = clean_lm
                par_elem = ET.SubElement(en, "par")
                par_elem.set("n", "__prep_art")
                par_elem.tail = ""
            continue

        en = ET.SubElement(section, "e", lm=clean_lm)
        i = ET.SubElement(en, "i")
        i.text = stem
        par_elem = ET.SubElement(en, "par")
        par_elem.set("n", par)
        par_elem.tail = "" 
    
    return dictionary


def _demote_eo_feminine(order, ido_lemma):
    """Demote an Esperanto feminine (-ino) candidate below its non-feminine base
    when both are present, so a gender-NEUTRAL Ido noun does not pick the feminine
    Esperanto gloss. Ido marks the feminine explicitly (-ino), so a bare Ido word
    like `habitanto` is neutral and must map to `loĝanto`, not `loĝantino` (the
    en_wiktionary pivot lists both because English "inhabitant" is gender-neutral).

    Only fires when the -ino candidate is literally the feminine of another
    candidate (base = stem+"o" is present), so root-final -ino words (maŝino,
    vitamino) are untouched; skipped when the Ido lemma is itself feminine-marked
    (-ino/-ina), where the Esperanto -ino is correct. pick_best uses insertion
    order as its tiebreak, so reordering is the idiomatic lever.
    """
    low = (ido_lemma or "").casefold()
    if low.endswith("ino") or low.endswith("ina"):
        return order
    present = {t.casefold() for t in order}
    fem = {t for t in order
           if t.casefold().endswith("ino") and t.casefold()[:-3] + "o" in present}
    if not fem:
        return order
    return [t for t in order if t not in fem] + [t for t in order if t in fem]


def _demote_eo_inchoative(order, ido_lemma):
    """Demote an Esperanto inchoative/middle (-iĝi) candidate below its base (-i)
    verb when both are present, so a plain transitive Ido verb does not pick the
    -iĝi gloss. The pivots list both because the English/French infinitive is
    ambiguous: komencar -> [komenciĝi, komenci] must resolve to `komenci` (not
    `komenciĝi`); likewise finar -> fini, movar -> movi.

    Only fires when the -iĝi candidate is literally the inchoative of another
    candidate (base = stem+"i" is present), so a verb whose only gloss is -iĝi is
    untouched; restricted to verb infinitives and skipped for Ido inchoatives
    (-eskar), where the Esperanto -iĝi is the correct reading. Mirrors
    _demote_eo_feminine; pick_best uses insertion order as its tiebreak.
    """
    low = (ido_lemma or "").casefold()
    if not low.endswith(("ar", "ir", "or")) or low.endswith("eskar"):
        return order
    present = {t.casefold() for t in order}
    incho = {t for t in order
             if t.casefold().endswith("iĝi") and t.casefold()[:-3] + "i" in present}
    if not incho:
        return order
    return [t for t in order if t not in incho] + [t for t in order if t in incho]


def _eo_candidates(e):
    """Ordered (term, [sources]) EO candidates for an entry, deduped by term.

    Order is preserved (eo_translations then senses) so it doubles as the
    insertion-order tiebreak for conflict_resolution.pick_best.
    """
    order, by_term = [], {}

    def add(raw_term, sources):
        term = _clean_translation_term(str(raw_term))
        if not term:
            return
        if term not in by_term:
            by_term[term] = set()
            order.append(term)
        by_term[term].update(s for s in (sources or []) if s)

    for t in (e.get("eo_translations") or []):
        if t:
            add(t, [])
    for s in e.get("senses") or []:
        for tr in s.get("translations") or []:
            if tr.get("lang") == "eo" and tr.get("term"):
                srcs = tr.get("sources") or ([tr["source"]] if tr.get("source") else [])
                add(tr["term"], srcs)
    order = _demote_eo_feminine(order, e.get("lemma"))
    order = _demote_eo_inchoative(order, e.get("lemma"))
    return [(t, sorted(by_term[t])) for t in order]


def build_bidix(entries):

    dictionary = ET.Element("dictionary")
    alphabet = ET.SubElement(dictionary, "alphabet")
    alphabet.text = "abcdefghijklmnopqrstuvwxyzĉĝĥĵŝŭABCDEFGHIJKLMNOPQRSTUVWXYZĈĜĤĴŜŬ"
    sdefs = ET.SubElement(dictionary, "sdefs")
    for s in ["n", "adj", "adv", "vblex", "vbtr", "pr", "prn", "det", "num", "cnjcoo", "cnjsub", "ij", "sg", "pl", "sp", "nom", "acc", "inf", "pri", "pii", "fti", "cni", "imp", "pp", "pp3", "ppres", "p1", "p2", "p3", "subj", "obj", "m", "f", "mf", "nt", "ciph", "np", "def", "sent", "der_pres", "der_act", "der_qual", "der_oz", "der_ala", "der_aro", "der_izar", "der_esar", "der_past", "der_ppa", "der_ppas", "der_pprs", "der_pfut", "der_ppra", "der_aj"]:
        ET.SubElement(sdefs, "sdef", n=s)
    # Structural pardefs: regex-based rules that are independent of vocabulary data
    pardefs = ET.SubElement(dictionary, "pardefs")
    _num_pd = ET.SubElement(pardefs, "pardef", n="num_regex")
    
    # Entry 1: Ido <num.ciph.sp.nom> <-> Esperanto <num.ciph.sp.nom>
    _num_e1 = ET.SubElement(_num_pd, "e")
    ET.SubElement(_num_e1, "re").text = "[0-9]+([.,][0-9]+)*"
    _num_p1 = ET.SubElement(_num_e1, "p")
    _num_l1 = ET.SubElement(_num_p1, "l")
    ET.SubElement(_num_l1, "s", n="num")
    ET.SubElement(_num_l1, "s", n="ciph")
    ET.SubElement(_num_l1, "s", n="sp")
    ET.SubElement(_num_l1, "s", n="nom")
    _num_r1 = ET.SubElement(_num_p1, "r")
    ET.SubElement(_num_r1, "s", n="num")
    ET.SubElement(_num_r1, "s", n="ciph")
    ET.SubElement(_num_r1, "s", n="sp")
    ET.SubElement(_num_r1, "s", n="nom")

    # Entry 2: Ido <num.ciph.sp.nom> <-> Esperanto <num.ciph.sp.acc>
    # Note: Ido numbers don't have -n, so always map to nominative on Ido side
    _num_e2 = ET.SubElement(_num_pd, "e")
    ET.SubElement(_num_e2, "re").text = "[0-9]+([.,][0-9]+)*"
    _num_p2 = ET.SubElement(_num_e2, "p")
    _num_l2 = ET.SubElement(_num_p2, "l")
    ET.SubElement(_num_l2, "s", n="num")
    ET.SubElement(_num_l2, "s", n="ciph")
    ET.SubElement(_num_l2, "s", n="sp")
    ET.SubElement(_num_l2, "s", n="nom")
    _num_r2 = ET.SubElement(_num_p2, "r")
    ET.SubElement(_num_r2, "s", n="num")
    ET.SubElement(_num_r2, "s", n="ciph")
    ET.SubElement(_num_r2, "s", n="sp")
    ET.SubElement(_num_r2, "s", n="acc")

    # Entry 3: Generic fallback <num> <-> <num>
    _num_e3 = ET.SubElement(_num_pd, "e")
    ET.SubElement(_num_e3, "re").text = "[0-9]+([.,][0-9]+)*"
    _num_p3 = ET.SubElement(_num_e3, "p")
    _num_l3 = ET.SubElement(_num_p3, "l")
    ET.SubElement(_num_l3, "s", n="num")
    _num_r3 = ET.SubElement(_num_p3, "r")
    ET.SubElement(_num_r3, "s", n="num")
    section = ET.SubElement(dictionary, "section", id="main", type="standard")
    # Regex number passthrough: maps Ido digits → same digits in Esperanto
    _num_sec = ET.SubElement(section, "e")
    ET.SubElement(_num_sec, "par", n="num_regex")

    # Identity mappings for the sentence-punctuation LUs emitted by the
    # monodix punct section (see build_monodix) — without them lt-proc -b
    # marks every period '@'.
    for mark in (".", "?", "!", "…"):
        pe = ET.SubElement(section, "e")
        pp = ET.SubElement(pe, "p")
        pl = ET.SubElement(pp, "l")
        pl.text = mark
        ET.SubElement(pl, "s", n="sent")
        pr = ET.SubElement(pp, "r")
        pr.text = mark
        ET.SubElement(pr, "s", n="sent")

    # Use top-level map_s_tag

    # Deduplicate entries by (lemma, epo_translation), prioritizing more specific paradigms
    best_bidix_entries = {}
    for e in entries:
        if e.get("language") and e.get("language") != "io":
            continue
        lm = str(e.get("lemma") or "").strip()
        if not lm:
            continue
        
        # Collect EO candidates and pick the winner deterministically (source rank
        # + insertion order) instead of the old order-dependent eo_terms[0].
        cands = _eo_candidates(e)
        if not cands:
            continue
        epo = pick_best(cands)

        raw_par = (e.get("morphology") or {}).get("paradigm")

        # Key includes paradigm so noun/adj/verb entries for the same (lemma, epo) pair
        # are kept as separate bidix entries rather than collapsed — avoids losing e.g.
        # kat<n>→kato<n> when a noisy adj entry with the same translation wins priority.
        key = (lm, epo, raw_par or '')
        if key not in best_bidix_entries:
            best_bidix_entries[key] = e
        else:
            old_par = (best_bidix_entries[key].get("morphology") or {}).get("paradigm")
            if _paradigm_priority(raw_par) > _paradigm_priority(old_par):
                best_bidix_entries[key] = e

    # FINAL deduplication pass for bidix
    seen_bidix_keys = set()
    deduped_final_bidix = []
    # Sort by Ido lemma, then Epo lemma
    # Sort by Ido lemma, with translation source quality as the tiebreaker so
    # Wiktionary-confirmed translations come BEFORE en_wiktionary_via / BERT-
    # only ones in the .dix file. apertium-lt-proc -b returns the first match,
    # so the ordering matters: e.g. atmosfero had both 'atmosfero' (correct,
    # io_wiktionary) and 'etoso' (legitimate but secondary, en_wiktionary_via)
    # translations and 'etoso' was winning on default insertion order. Quality
    # buckets (lower = better):
    #   0  io_wiktionary / eo_wiktionary / fr_wiktionary_meaning / function_word_override
    #   1  bert + wiktionary corroboration
    #   2  en_wiktionary_via
    #   3  bert_embeddings only
    _LOW_QUAL = frozenset({'bert_embeddings', 'en_wiktionary_via'})
    def _entry_quality(e):
        sources = set()
        for s in e.get('senses') or []:
            for tr in s.get('translations') or []:
                if tr.get('lang') == 'eo':
                    sources.update(tr.get('sources') or [])
        wikt = sources - _LOW_QUAL
        bert = 'bert_embeddings' in sources
        en_via = 'en_wiktionary_via' in sources
        if wikt:
            return 1 if bert else 0
        if en_via:
            return 2
        return 3

    final_list_bidix = sorted(
        best_bidix_entries.values(),
        key=lambda e: (
            str(e.get("lemma") or "").lower(),
            _entry_quality(e),
            str(e.get("lemma") or ""),
        ),
    )
    
    # Process and build final XML here
    _generated_contraction_bases: set = set()

    for e in final_list_bidix:
        clean_lm = str(e.get("lemma")).strip()
        raw_par = (e.get("morphology") or {}).get("paradigm") or None
        pos = e.get("pos") if isinstance(e.get("pos"), str) else None

        # Chemical-symbol guard: two-char XY lemmas (e.g. "Ca", "Fe", "Na") from
        # wikidata_labels get inferred as a__adj because they end in 'a', producing
        # stem "C" which collides with sentence-initial `ca<adj>` (Ido demonstrative).
        # Skip them when there is no explicit POS to confirm they are adjectives.
        if (len(clean_lm) == 2 and clean_lm[0].isupper() and clean_lm[1].islower()
                and raw_par == 'a__adj' and pos is None):
            logging.debug("Skipping chemical-symbol-shaped bidix entry: %s", clean_lm)
            continue

        # Prep-article contractions: generate 1-to-1 base_prep<pr><def> mapping.
        # Must be checked before eo_terms collection since these entries have no
        # stored translations — their Epo equivalent is in _PREP_ART_EPO.
        if raw_par == 'prep_art':
            lm_lc = clean_lm.lower()
            base_prep = _PREP_ART.get(lm_lc)
            if base_prep and base_prep not in _generated_contraction_bases:
                _generated_contraction_bases.add(base_prep)
                epo_prep = _PREP_ART_EPO.get(base_prep, 'de')
                en2 = ET.SubElement(section, "e")
                p2 = ET.SubElement(en2, "p")
                l2 = ET.SubElement(p2, "l")
                l2.text = base_prep
                ET.SubElement(l2, "s", n="pr").tail = ""
                ET.SubElement(l2, "s", n="def").tail = ""
                r2 = ET.SubElement(p2, "r")
                r2.text = epo_prep
                ET.SubElement(r2, "s", n="pr").tail = ""
                ET.SubElement(r2, "s", n="def").tail = ""
            continue

        # Get translation: deterministic winner (already filtered in pre-pass).
        cands = _eo_candidates(e)
        if not cands:
            continue
        epo = pick_best(cands)

        en = ET.SubElement(section, "e")
        p = ET.SubElement(en, "p")

        if not raw_par:
            logging.debug("No paradigm for %s (pos=%s) — skipping bidix entry", clean_lm, pos)
            section.remove(en)
            continue

        ido_tag = map_s_tag(raw_par, pos)

        # Pronoun possessive derivation: me -> mea (mia), elu -> elua (ŝia).
        # Adjective entry: lemma+'a' <adj> -> EO-pronoun+'a' <adj>. The EO stem is
        # the pronoun's own sourced translation (epo), so no hardcoded Ido→EO map.
        lm_lower = clean_lm.lower()
        if str(raw_par).strip('_') == 'prn' and lm_lower in _PERSONAL_PRONOUNS and epo:
            epo_poss_stem = epo
            e_poss = ET.SubElement(section, "e")
            p_poss = ET.SubElement(e_poss, "p")
            # Left is the a__adj STEM (the bare pronoun), matching the analyser's
            # lemma for the possessive surface: 'mea' -> me<adj>, 'sua' -> su<adj>.
            l_poss = ET.SubElement(p_poss, "l")
            l_poss.text = clean_lm
            ET.SubElement(l_poss, "s", n="adj").tail = ""
            r_poss = ET.SubElement(p_poss, "r")
            r_poss.text = epo_poss_stem + 'a'
            ET.SubElement(r_poss, "s", n="adj").tail = ""

        # Extract stem from lemma for bilingual dictionary
        stem = extract_stem(clean_lm, str(raw_par))
        
        # Left (Ido) - use STEM, not full lemma
        l = ET.SubElement(p, "l")
        l.text = stem

        # Determine tags for Left (Ido)
        l_tags = []
        if ido_tag:
            l_tags = [ido_tag]

        for t in l_tags:
            s_elem = ET.SubElement(l, "s")
            s_elem.set("n", t)
            s_elem.tail = ""

        # Right (Esperanto)
        r = ET.SubElement(p, "r")
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
            # -esar: kreesar → passive construction; t1x vbpasv rule produces "esti<tense> + verb<pp>"
            # Right side carries the base Epo lemma so clip side="tl" part="lem" returns it
            if False:
                for tense in ['inf', 'pri', 'pii', 'fti', 'cni', 'imp']:
                    e_es = ET.SubElement(section, "e")
                    p_es = ET.SubElement(e_es, "p")
                    l_es = ET.SubElement(p_es, "l")
                    l_es.text = stem
                    ET.SubElement(l_es, "s", n="vblex").tail = ""
                    ET.SubElement(l_es, "s", n="der_esar").tail = ""
                    ET.SubElement(l_es, "s", n="vblex").tail = ""
                    ET.SubElement(l_es, "s", n=tense).tail = ""
                    r_es = ET.SubElement(p_es, "r")
                    r_es.text = epo
                    ET.SubElement(r_es, "s", n="vblex").tail = ""
                    ET.SubElement(r_es, "s", n=tense).tail = ""
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
            epo_stripped = epo[:-1] if epo.endswith('o') else epo  # 'sukceso' → 'sukcese'
            # -ala suffix: ekonomi+ala → ekonomiala ("relating to economy"); Epo: ekonomia
            e_ala = ET.SubElement(section, "e")
            p_ala = ET.SubElement(e_ala, "p")
            l_ala = ET.SubElement(p_ala, "l")
            l_ala.text = stem
            ET.SubElement(l_ala, "s", n="n").tail = ""
            ET.SubElement(l_ala, "s", n="der_ala").tail = ""
            ET.SubElement(l_ala, "s", n="adj").tail = ""
            r_ala = ET.SubElement(p_ala, "r")
            r_ala.text = epo_stripped + 'a'
            ET.SubElement(r_ala, "s", n="adj").tail = ""
            # -oza suffix: suces+oza → sucesoza ("full of success")
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
            # -aro collective: mont+aro → montaro (mountain range), hom+aro → homaro.
            # EO collective is also -aro (generated compositionally by apertium-epo), so
            # the right side carries the EO collective lemma; <sg/pl><nom> passes through.
            e_aro = ET.SubElement(section, "e")
            p_aro = ET.SubElement(e_aro, "p")
            l_aro = ET.SubElement(p_aro, "l")
            l_aro.text = stem
            ET.SubElement(l_aro, "s", n="n").tail = ""
            ET.SubElement(l_aro, "s", n="der_aro").tail = ""
            ET.SubElement(l_aro, "s", n="n").tail = ""
            r_aro = ET.SubElement(p_aro, "r")
            r_aro.text = epo_stripped + 'aro'
            ET.SubElement(r_aro, "s", n="n").tail = ""
            # -izar suffix: nom+izar → nomizar (to name); Epo: strip -o, add -i
            # Emit all tenses so the bidix covers nomizar/nomizas/nomizis/...
            if False and epo.endswith('o'):
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

    # epo→ido personal-pronoun entries (prpers → canonical Ido pronoun), emitted
    # once. RL-only, so they never compete with the per-pronoun LR entries above.
    _emit_prpers_rl_entries(section)
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
    # Index bidix entries by lower-case lemma, preferring entries with non-null POS,
    # and tracking a separate index of function_word_override entries (authoritative
    # for fundamental closed-class words whose Wiktionary harvest produces wrong
    # POS/paradigm or multi-word EO targets that get filtered).
    bidix_by_lemma = {}
    bidix_override_by_lemma = {}
    for be in bidix_entries:
        lm = (be.get('lemma') or '').lower()
        if not lm:
            continue
        existing = bidix_by_lemma.get(lm)
        if existing is None or (not existing.get('pos') and be.get('pos')):
            bidix_by_lemma[lm] = be
        # closed_class_tables (structured pronoun/correlative tables, rank-0
        # source) shares the function-word override's monodix authority: the
        # open Wiktionary harvest gives these lemmas wrong POS/paradigms
        # (quo → o__n noun, resurrecting the spurious qu<n> analyses). The
        # *_qualified twin deliberately does NOT qualify.
        if any((p.get('source') in ('function_word_override', 'closed_class_tables'))
               for p in (be.get('provenance') or [])):
            bidix_override_by_lemma[lm] = be
    # Upgrade vocab entries that have no pos/paradigm using the bidix entry,
    # and force-override pos/morphology when bidix has a function_word_override
    # entry (it is authoritative for that lemma).
    for ve in entries:
        lm = (ve.get('lemma') or '').lower()
        ov = bidix_override_by_lemma.get(lm)
        if ov:
            ve['pos'] = ov.get('pos')
            ve['morphology'] = ov.get('morphology') or {}
            continue
        if not ve.get('pos') and not (ve.get('morphology') or {}).get('paradigm'):
            be = bidix_by_lemma.get(lm)
            if be and be.get('pos'):
                ve['pos'] = be['pos']
                if be.get('morphology'):
                    ve['morphology'] = be['morphology']
    existing_lemmas = {(e.get('lemma') or '').lower() for e in entries}
    extra = [e for e in bidix_entries if (e.get('lemma') or '').lower() not in existing_lemmas]
    mono_entries = entries + extra
    # Drop single-letter-stem junk verbs (par/car/ir...) that leak from
    # final_vocabulary too — their ar__vblex paradigm over-generates "pos" etc.
    before = len(mono_entries)
    mono_entries = [e for e in mono_entries
                    if not is_junk_verb(e.get('lemma'), e.get('pos'),
                                        (e.get('morphology') or {}).get('paradigm'))]
    if before != len(mono_entries):
        logging.info(f"Dropped {before - len(mono_entries)} single-letter-stem junk verbs")
    logging.info(f"Monodix: {len(entries)} vocab + {len(extra)} bidix-only = {len(mono_entries)} total")

    # Feminine-shadow guard: drop monodix entries `lemma<n>` (paradigm o__n)
    # with empty senses when `lemma + 'ino'` is also a noun lemma with
    # translations. Without this, apertium-ido's o__n feminine `-ino` paradigm
    # makes input `Origino` analyze as feminine of `Origo` and fall through
    # to a no-translation `@Orig<n><f>` lookup → output truncates to `Orig`.
    _has_translations_lemmas = set()
    for e in mono_entries:
        lm = (e.get('lemma') or '').lower()
        if not lm:
            continue
        if any(t for s in (e.get('senses') or []) for t in (s.get('translations') or [])):
            _has_translations_lemmas.add(lm)
    pre_count = len(mono_entries)
    filtered = []
    drop_count = 0
    for e in mono_entries:
        lm = (e.get('lemma') or '').lower()
        par = (e.get('morphology') or {}).get('paradigm')
        senses = e.get('senses') or []
        has_tr = any(s.get('translations') for s in senses)
        if (par == 'o__n' and lm.endswith('o') and not has_tr
                and (lm[:-1] + 'ino') in _has_translations_lemmas):
            drop_count += 1
            continue
        filtered.append(e)
    if drop_count:
        logging.info(f"Monodix feminine-shadow guard: dropped {drop_count} entries")
    mono_entries = filtered

    mono = build_monodix(mono_entries)
    write_xml_file(mono, out_monodix, header_comment=_MONODIX_HEADER)

    logging.info(f"Building bilingual dictionary from {len(bidix_entries)} entries")
    bidi = build_bidix(bidix_entries)
    write_xml_file(bidi, out_bidix, header_comment=_BIDIX_HEADER)
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


