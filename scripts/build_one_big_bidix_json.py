#!/usr/bin/env python3
import argparse
import logging
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from _common import read_json, write_json, configure_logging
from infer_morphology import infer_paradigm as _infer_paradigm
from lexicon_filters import (
    is_junk_lemma, dedupe_eo_candidates, fold_inflected_eo_duplicates)
import re


# Normalize verbose Wiktionary POS names to short Apertium tags so that all
# entries in bidix_big.json carry a consistent POS regardless of source.
_SHORT_POS: Dict[str, str] = {
    "noun": "n", "adjective": "adj", "adverb": "adv", "verb": "vblex",
    "preposition": "pr", "conjunction": "cnjcoo",
    "subordinating conjunction": "cnjsub", "determiner": "det", "pronoun": "prn",
    "interjection": "ij", "numeral": "num",
}


# Translations for closed-class function words the pipeline provably fails to
# extract correctly. Kept minimal — one canonical Esperanto equivalent each.
# Empirically verified NECESSARY (2026-06-04): removing any of these and
# rebuilding regresses the word (the correct EO is absent or loses to noise) —
# see scripts/dict_diff.py / the P4 audit. Pipeline-gap cases ("Wiktionary has
# it but pipeline misses it") could be retired later by fixing extraction.
_FUNCTION_WORD_OVERRIDES: Dict[str, Dict[str, str]] = {
    'e':    {'pos': 'cnjcoo',   'eo': 'kaj'},   # and (Wiktionary has it but pipeline misses it)
    'ed':   {'pos': 'cnjcoo',   'eo': 'kaj'},   # and (before vowels — no standalone Wiktionary entry)
    'o':    {'pos': 'cnjcoo',   'eo': 'aŭ'},    # or (Wiktionary has it but pipeline misses it)
    'a':    {'pos': 'pr',       'eo': 'al'},    # to/toward (Wiktionary translation blank)
    'al':   {'pos': 'pr',       'eo': 'al'},    # a+la contraction, kept as pr to avoid double-article
    'dal':  {'pos': 'prep_art', 'eo': 'de'},    # da + la (contraction); transfer expands to "de la"
    'dil':  {'pos': 'prep_art', 'eo': 'de'},    # di + la (contraction); io_wiktionary EO is multi-word, filtered upstream
    'til':  {'pos': 'pr',       'eo': 'ĝis'},   # until — io_wiktionary EO is junk-grade ("ĝis la revido")
    'quan': {'pos': 'prn',      'eo': 'kiun'},  # accusative of qua; not derived by __prn paradigm
    'qui':  {'pos': 'prn',      'eo': 'kiuj'},  # plural relative/interrogative pronoun
    'quo':  {'pos': 'prn',      'eo': 'kio'},   # interrogative "what" (NOT a noun — see _IDO_REL_INT_PRN)
    'di qua': {'pos': 'prn',    'eo': 'de kiu'},  # relative "of/from which"; io_wikt gloss "kies" is only the possessive sense
    'di qui': {'pos': 'prn',    'eo': 'de kiuj'}, # plural
    'saluto': {'pos': 'ij',     'eo': 'saluton'}, # greeting
}

# Ido relative/interrogative correlative pronouns (the qu- series). These are
# closed-class, but ending-based POS inference mis-tags them ('quo' -> noun
# because it ends in -o, 'qua' -> adj). Critically, 'quo' as a noun generates
# 'qui' as its plural, so 'qui' is then mis-analysed as qu<n><pl> (→ "kio")
# instead of the pronoun "kiuj". Force the whole series to prn so the spurious
# noun/adjective paradigms (and their inflected forms) are never built.
_IDO_REL_INT_PRN = {'qua', 'qui', 'quo', 'quan', 'quin', 'quon',
                    'di qua', 'di qui', 'di quo'}


# BERT vocab pre-filter: the source vocab includes a lot of non-Ido garbage
# (text fragments like "(białystok),", "$28,750", "(1.1", "the", "and", and
# loanwords from FR/PL/DE that BERT happens to embed near Ido words).
# These produce confidently-wrong translations because BERT's nearest-neighbor
# lookup just maps the junk lemma to its closest EO neighbor.
#
# Filter rules (drop the entry if the lemma fails any):
#   - non-empty + length >= 3
#   - only ASCII letters + hyphen (Ido orthography is plain ASCII a-z; any
#     non-ASCII letter — é, ñ, ç, ł, ś, etc. — signals a foreign loan)
#   - no digits, parens, quotes, $, %, /, <, >, etc.
#
# Note: this catches *shape* junk only (~13% of BERT vocab). The remaining
# wrongness from the article audit (~70% of BERT-only translations are
# semantically wrong) is in *clean-shape lemmas with bad translations*
# (e.g. donis→domon, kartago→goya). That's a different problem (BERT
# translation quality) — out of scope here, requires either a confidence
# threshold filter or dropping BERT-only entirely.
_IDO_LEMMA_RE = re.compile(r'^[a-zA-Z\-]+$')
# Verb conjugation surface forms (-as/-is/-os/-us/-ez) aren't lemmas — they're
# inflections of -ar/-ir verbs that the morphology pipeline derives from the
# verb root via the ar__vblex paradigm. BERT entries like 'esas → havas' are
# wrong because esas is a conjugation, not a lemma. Capitalized forms (proper
# nouns like 'Markus', 'Edipus') are excluded by the all-lowercase check.
_IDO_VERB_INFLECTION_RE = re.compile(r'^[a-z]{2,}(?:as|is|os|us|ez)$')

def _is_valid_ido_lemma(lm: str) -> bool:
    if not lm or len(lm) < 3:
        return False
    if not _IDO_LEMMA_RE.match(lm):
        return False
    if len(lm) <= 8 and _IDO_VERB_INFLECTION_RE.match(lm):
        return False
    return True


def _filter_bert_junk(entries: List[Dict[str, Any]], src_path: Path) -> List[Dict[str, Any]]:
    """Drop BERT entries with non-Ido-shaped lemmas.

    Only filters BERT source files; other sources pass through unchanged.
    """
    name = src_path.name
    if 'bert' not in name.lower():
        return entries
    kept, dropped = [], 0
    for e in entries:
        lm = e.get('lemma') or ''
        if _is_valid_ido_lemma(lm):
            kept.append(e)
        else:
            dropped += 1
    if dropped:
        logging.info("BERT pre-filter: dropped %d/%d junk-shaped lemmas (parens, digits, non-ASCII diacritics)", dropped, len(entries))
    return kept


def build_big_bidix(entries_paths: List[Path]) -> List[Dict[str, Any]]:
    # Load and merge all input files
    entries = []
    for path in entries_paths:
        if path.exists():
            logging.info("Loading %s", path)
            data = read_json(path)
            if isinstance(data, dict):
                file_entries = data.get('entries', [])
            else:
                file_entries = data
            file_entries = _filter_bert_junk(file_entries, path)
            entries.extend(file_entries)
        else:
            logging.warning("File not found: %s (skipping)", path)
    # Map: (lemma, pos) -> { 'lemma':.., 'pos':.., 'language':'io', 'morphology':.., 'translations': term -> set(sources), 'provenance': set(sources) }
    by_key: Dict[Tuple[str, str], Dict[str, Any]] = {}

    def sources_from_prov(prov_list: Any) -> List[str]:
        out: List[str] = []
        for p in prov_list or []:
            if isinstance(p, dict):
                s = str(p.get('source') or '')
                if s:
                    out.append(s)
        return out

    EO_ALLOWED_RE = re.compile(r"^[A-Za-zĈĜĤĴŜŬĉĝĥĵŝŭ\-]+$")

    def clean_terms(raw: str):
        """Split on commas/semicolons, clean each part, yield valid terms."""
        for part in re.split(r'[,;]', raw or ''):
            t = clean_term(part)
            if t:
                yield t

    def clean_term(term: str) -> str:
        t = (term or '').strip()
        if not t:
            return ''
        # Drop table/template artifacts and categories
        if any(x in t for x in ['|', '{', '}', 'bgcolor']):
            return ''
        t = re.sub(r"\s*Kategorio:[^\s]+.*$", "", t)
        t = re.sub(r"\s+", " ", t).strip()
        # Drop bullet/star artifacts
        if '*' in t:
            return ''
        # Enforce Esperanto orthography (letters + hyphen); remove spaces for test
        test = t.replace(' ', '')
        if not EO_ALLOWED_RE.match(test):
            return ''
        # Reject likely definitions (3+ words are descriptions, not translations)
        if t.count(' ') >= 2:
            return ''
        return t

    for e in entries:
        # Allow entries without a language field (source_io_wiktionary.json format)
        lang_field = e.get('language')
        if lang_field is not None and lang_field != 'io':
            continue
        lemma = (e.get('lemma') or '').strip()
        pos = _SHORT_POS.get((e.get('pos') or '').strip(), (e.get('pos') or '').strip())
        if not lemma or not lemma[0].isalpha() or re.search(r'[(),;:!@#$%^&*\[\]{}|<>?/\\]', lemma):
            continue
        # POS sanity: Ido lemma endings are reliable. If the source POS
        # contradicts the ending, override from the ending. This catches
        # legacy inputs (e.g. fr_wikt_meanings.json hard-coded pos='adjective'
        # for all entries regardless of -o/-a/-e/-ar).
        # Closed-class POS tags are protected from override — words like
        # 'la' (det), 'da' (pr), 'kad' (cnjcoo) are short and end in vowels
        # but they are NOT inflectable content words.
        _CLOSED_CLASS = {'det', 'pr', 'prn', 'cnjcoo', 'cnjsub', 'ij', 'num',
                          'np', 'prep_art', 'rel'}
        ll = lemma.lower()
        morphology = e.get('morphology') or {}
        pos_overridden = False
        # Closed-class qu- pronoun series: force prn (overriding any source POS
        # and the ending-based inference below) and drop the stale paradigm so
        # _infer_paradigm picks __prn. Prevents the quo<n>→qui<n><pl> mis-analysis.
        if ll in _IDO_REL_INT_PRN:
            pos = 'prn'
            morphology = {}
        # Missing/empty POS: infer from the (reliable) Ido lemma ending so the
        # merge key is consistent. Otherwise a zero-EO entry stored with no POS
        # (key=('bakilo','')) never unifies with the morphological-expansion
        # entry that carries its EO gloss (key=('bakilo','n')), forking a
        # duplicate instead of attaching the translation.
        # Restricted to lowercase lemmas: capitalized langlink/wikidata entries
        # may be proper nouns (Nauvoo, Korea) — inferring 'n'/'adj' there would
        # recase them via the lowercasing rule below and break capitalized MT
        # lookup. All morphological-expansion recall targets are lowercase.
        if not pos and lemma[:1].islower():
            if ll.endswith('ar') and len(ll) > 3:
                pos = 'vblex'; pos_overridden = True
            elif ll.endswith('o'):
                pos = 'n'; pos_overridden = True
            elif ll.endswith('a') and not ll.endswith('ia'):
                pos = 'adj'; pos_overridden = True
            elif ll.endswith('e') and len(ll) > 2:
                pos = 'adv'; pos_overridden = True
        if pos in _CLOSED_CLASS:
            pass  # Don't override closed-class POS based on ending
        elif ll.endswith('o') and pos and pos not in ('n', 'np'):
            pos = 'n'; pos_overridden = True
        elif ll.endswith('ar') and len(ll) > 3 and pos and pos != 'vblex':
            pos = 'vblex'; pos_overridden = True
        elif ll.endswith('a') and not ll.endswith('ia') and pos and pos != 'adj':
            pos = 'adj'; pos_overridden = True
        elif ll.endswith('e') and len(ll) > 2 and pos and pos != 'adv':
            pos = 'adv'; pos_overridden = True
        # When we override the POS, the source's paradigm is also stale
        # (e.g. fr_wikt_meanings always supplies o__n regardless). Clear it
        # so the downstream _infer_paradigm() picks one matching the new POS.
        if pos_overridden:
            morphology = {}
        # Same idea even when POS wasn't overridden: if upstream sent us a
        # paradigm whose POS-implication contradicts the entry's POS, drop
        # the paradigm. e.g. lemma=abisinia, pos=adj, paradigm=o__n.
        else:
            par = (morphology or {}).get('paradigm')
            if par == 'o__n' and pos == 'adj':
                morphology = {}
            elif par == 'a__adj' and pos == 'n':
                morphology = {}
            elif par == 'e__adv' and pos in ('n', 'adj'):
                morphology = {}
            elif par == 'ar__vblex' and pos in ('n', 'adj', 'adv'):
                morphology = {}
        # Closed-class function words (pronouns, determiners, prepositions,
        # conjunctions, interjections) are never proper nouns — force the lemma
        # lowercase so a capitalized source variant (e.g. io_wiktionary 'Vu',
        # which carries the __prn paradigm + 'vi' translation) merges with the
        # analyser's lowercase form instead of producing an unmatched bidix entry.
        if pos and pos.lower() in ('prn', 'det', 'pr', 'cnjcoo', 'cnjsub', 'ij'):
            lemma = lemma.lower()
        key = (lemma.lower(), pos.lower())
        rec = by_key.get(key)
        if rec is None:
            rec = {
                'lemma': lemma,
                'pos': pos or None,
                'language': 'io',
                'morphology': morphology,
                '_eo_terms': {},  # term -> set(sources)
                '_all_sources': set(),
            }
            by_key[key] = rec
        else:
            # Common nouns (pos n/adj/adv/vblex) should be lowercase. If
            # multiple sources mix `Aglo` and `aglo`, lowercase wins so the
            # bidix stem matches what apertium-ido analyzer outputs for
            # lowercase user input. Proper nouns (np) keep original case.
            if pos in ('n', 'adj', 'adv', 'vblex') and lemma.islower() and not rec['lemma'].islower():
                rec['lemma'] = lemma
        # Accumulate sources
        for s in sources_from_prov(e.get('provenance')):
            rec['_all_sources'].add(s)
        # Collect only EO translations, aggregate per term sources
        for s in e.get('senses', []) or []:
            for tr in s.get('translations', []) or []:
                if tr.get('lang') != 'eo':
                    continue
                src = str(tr.get('source') or '')
                for term in clean_terms(tr.get('term') or ''):
                    cur = rec['_eo_terms'].setdefault(term, set())
                    if src:
                        cur.add(src)
        # Also collect top-level translations (source_io_wiktionary.json format)
        for tr in e.get('translations', []) or []:
            if tr.get('lang') != 'eo':
                continue
            src = str(tr.get('source') or '')
            for term in clean_terms(tr.get('term') or ''):
                cur = rec['_eo_terms'].setdefault(term, set())
                if src:
                    cur.add(src)

    # Inject function-word overrides for words absent from all sources.
    _POS_TO_PAR: Dict[str, str] = {
        'n': 'o__n', 'adj': 'a__adj', 'adv': 'e__adv', 'vblex': 'ar__vblex',
        'pr': '__pr', 'det': '__det', 'prn': '__prn',
        'cnjcoo': '__cnjcoo', 'cnjsub': '__cnjsub', 'ij': '__ij', 'num': 'num',
        'prep_art': '__prep_art'
    }

    for lemma_lc, info in _FUNCTION_WORD_OVERRIDES.items():
        key = (lemma_lc, info['pos'])
        # Optional explicit paradigm overrides the pos→paradigm mapping
        # (used for irregular forms like 'nur' where pos='adv' but paradigm must be '__adv', not 'e__adv').
        par = info.get('paradigm') or _POS_TO_PAR.get(info['pos'], '__' + info['pos'])
        
        # Always ensure the entry exists with correct morphology and translation
        if key not in by_key:
            by_key[key] = {
                'lemma': lemma_lc,
                'pos': info['pos'],
                'language': 'io',
                '_eo_terms': {},
                '_all_sources': {'function_word_override'},
            }
        
        by_key[key]['morphology'] = {'paradigm': par, 'features': {}}
        # Inject or override translation
        by_key[key]['_eo_terms'][info['eo']] = {'function_word_override'}
        # Mark provenance so downstream consumers (e.g. export_apertium monodix
        # builder) can recognize this lemma as authoritatively overridden.
        by_key[key]['_all_sources'].add('function_word_override')
    for rec in by_key.values():
        if not (rec.get('morphology') or {}).get('paradigm'):
            par = _infer_paradigm(rec)
            if not par:
                # infer_morphology expects verbose POS; fall back to short-form map
                par = _POS_TO_PAR.get(str(rec.get('pos') or ''))
            if par:
                rec['morphology'] = {'paradigm': par, 'features': {}}

    # BERT translations are low-priority: skip them for lemmas that already have Wiktionary coverage.
    _BERT_SOURCES = frozenset({'bert_embeddings'})

    # Build set of lemmas with translations from io_wiktionary specifically.
    # Used by the feminine-shadow guard below: when both 'origo' and 'origino'
    # are listed by io_wiktionary, and only 'origino' has actual translations,
    # apertium-ido's o__n feminine `-ino` derivation creates a spurious
    # `Orig<n><f>` analysis path that hits BERT's wrong translation. en_via /
    # fr_via attestations don't qualify here — for genuine person nouns
    # (`dano`/`danino`, `franco`/`francino`) both forms are correctly attested
    # via en_wiktionary_via and the feminine derivation is real.
    _io_wikt_lemmas = set()
    for (_lm, _pos), rec in by_key.items():
        for srcs in rec['_eo_terms'].values():
            if 'io_wiktionary' in srcs:
                _io_wikt_lemmas.add(_lm)
                break

    # Materialize final structure: senses with EO-only translations; keep multi-provenance per translation
    out: List[Dict[str, Any]] = []
    for (_lm, _pos), rec in sorted(by_key.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        # Drop non-lexical junk lemmas (foreign-script spellings leaked from
        # langlink/wikidata titles, MediaWiki artifacts, numeric ordinals) so they
        # never reach the monodix or the vortaro. See scripts/lexicon_filters.py.
        if is_junk_lemma(rec['lemma']):
            continue
        # Merge EO candidates that differ only by letter-case, casing driven by
        # the Ido lemma (lowercase common noun → lowercase gloss; Aachen→Akeno
        # keeps the capital). Collapses the 'Lifto'/'lifto' duplicate pairs the
        # candidate audit found and fixes the capitalised-first-gloss ordering.
        # Then fold any candidate that is the -j/-n/-jn inflection of another
        # candidate of the same entry into its base (e.g. wikidata's `urboj`
        # alongside `urbo`), merging sources onto the base form.
        rec['_eo_terms'] = {
            term: set(srcs) for term, srcs in fold_inflected_eo_duplicates(
                dedupe_eo_candidates(
                    rec['lemma'],
                    [(t, sorted(s)) for t, s in rec['_eo_terms'].items()]))
        }
        # Wiktionary wins: if any translation comes from a non-BERT source, drop BERT-only translations.
        has_wikt = any(srcs - _BERT_SOURCES for srcs in rec['_eo_terms'].values())
        # Feminine-shadow guard: when this entry is `lemma<n>` with paradigm
        # `o__n` and `lemma + 'ino'` is Wiktionary-attested, drop ALL BERT
        # translations. Apertium-Ido's o__n paradigm has a feminine `-ino`
        # derivation, so a spurious `origo<n>` would let `Origino` analyze as
        # `Orig<f>` and hit the wrong BERT entry.
        is_feminine_shadow = (
            (rec.get('morphology') or {}).get('paradigm') == 'o__n'
            and _lm.endswith('o')
            and (_lm[:-1] + 'ino') in _io_wikt_lemmas
            and not has_wikt
        )
        # When the feminine-shadow rule applies and dropping BERT translations
        # would leave the entry empty, drop the entry entirely so the monodix
        # builder also excludes it. Otherwise apertium-ido keeps `<e lm="origo">`
        # in the monodix and the spurious `Orig<n><f>` analysis still produces
        # a no-translation fallback (output: `Orig` instead of `Origino`).
        if is_feminine_shadow:
            non_bert = [t for t, s in rec['_eo_terms'].items() if (s - _BERT_SOURCES)]
            if not non_bert:
                continue
        translations: List[Dict[str, Any]] = []
        for term, srcs in rec['_eo_terms'].items():
            if has_wikt and not (srcs - _BERT_SOURCES):
                continue  # skip BERT-only translation when Wiktionary has coverage
            if is_feminine_shadow and not (srcs - _BERT_SOURCES):
                continue  # skip BERT-only translation that competes with longer Wikt -ino lemma
            # Suppress non-cognate BERT-only translations. BERT at 0.99 still
            # aligns adjectives/nouns by POS distributional patterns rather than
            # semantics, producing noise like mortala→serioza, agresiva→efektiva.
            # Keep BERT only when the eo term is a cognate of the io lemma
            # (shared 4-char prefix), e.g. abunde→abunde, adapto→adapto.
            if not (srcs - _BERT_SOURCES) and term[:4].lower() != _lm[:4].lower():
                continue
            translations.append({
                'lang': 'eo',
                'term': term,
                # keep all sources; do not include confidence
                'sources': sorted(srcs),
            })
        senses = []
        if translations:
            senses.append({'senseId': None, 'gloss': None, 'translations': translations})
        out.append({
            'lemma': rec['lemma'],
            'pos': rec['pos'],
            'language': 'io',
            'senses': senses,
            'morphology': rec.get('morphology') or {},
            # retain union of sources at entry level as provenance summary
            'provenance': [{'source': s} for s in sorted(rec['_all_sources'])],
        })
    return out


def main(argv: Iterable[str]) -> int:
    ap = argparse.ArgumentParser(description='Build ONE BIG BIDIX JSON (EO-only translations, multi-provenance, no confidence)')
    ap.add_argument('--input', type=Path, action='append', help='Input JSON file(s) to merge (can be specified multiple times)')
    ap.add_argument('--out', type=Path, default=Path(__file__).resolve().parents[1] / 'dist/bidix_big.json')
    ap.add_argument('-v', '--verbose', action='count', default=0)
    args = ap.parse_args(list(argv))

    configure_logging(args.verbose)
    
    # Default inputs if none specified
    base_path = Path(__file__).resolve().parents[1]
    inputs = args.input if args.input else [
        # prepare_vocabulary.py output: normalized + morphology-inferred + filtered
        # (replaces the old bilingual_with_morph.json + source_io_wiktionary.json pair)
        base_path / 'work/final_vocabulary.json',
        # Wikipedia interlanguage links (io→eo article-title pairs).
        # Useful for proper nouns, places, and concepts that have Wikipedia
        # articles in both languages but no Wiktionary entry.
        base_path / 'work/io_eo_langlinks.json',
        # eo.wiki langlinks (eo→io perspective). ~98% overlap with io_eo_langlinks;
        # adds ~300 novel pairs that the io-side pass misses.
        base_path / 'work/eo_io_langlinks.json',
        # Wikidata item labels: items with both io and eo labels/aliases.
        # Complements langlinks with common nouns, scientific terms, and items
        # that have Wikidata entries but no Wikipedia article in both languages.
        base_path / 'work/io_eo_wikidata.json',
        # Morphological expansion: derived forms (e.g. abasata→malaltigata) from
        # known verb/noun pairs. Only includes forms validated in io.wiki corpus.
        base_path / 'work/io_eo_morphological.json',
        # Function words whose EO translations the live parser cannot extract from the Wiktionary dump.
        # Keep this list minimal — entries here override BERT but lose to any live Wiktionary extraction.
        base_path / 'data/sources/source_function_words_seed.json',
        # BERT cross-lingual alignment (lowest priority: only fills gaps not covered by anything above)
        base_path / 'data/sources/source_bert_embeddings.json',
    ]
    
    big = build_big_bidix(inputs)
    write_json(args.out, big)
    logging.info('Wrote %s (%d entries)', args.out, len(big))
    return 0


if __name__ == '__main__':
    import sys
    raise SystemExit(main(sys.argv[1:]))


