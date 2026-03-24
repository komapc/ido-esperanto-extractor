#!/usr/bin/env python3
"""
Regression tests for bugs found during Ido-Saluto! article translation analysis.

Bugs covered:
  1. Arrow (↓) artifacts in Wiktionary translation terms not stripped by clean_lemma()
  2. Wrong paradigms for function words due to stale pipeline (ke→e__adv, pro→o__n, etc.)
  3. POS long-form names ("preposition", "conjunction") not normalized in export_apertium,
     causing segun/apud/cirkum to fall through to o__n default
  4. kande missing from FUNCTION_WORDS → got e__adv instead of cnjsub
"""

import sys
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'scripts'))

from _common import clean_lemma
from infer_morphology import infer_paradigm
from export_apertium import build_monodix, build_bidix


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _bidix_entries(entries):
    """Build bilingual dix and return list of (l_text, l_tags, r_text, r_tags) tuples."""
    tree = build_bidix(entries)
    section = tree.find('.//section[@id="main"]')
    result = []
    for e in section.findall('e'):
        p = e.find('p')
        if p is None:
            continue
        l = p.find('l')
        r = p.find('r')
        l_text = l.text or ''
        l_tags = [s.get('n') for s in l.findall('s')]
        r_text = r.text or '' if r is not None else ''
        r_tags = [s.get('n') for s in r.findall('s')] if r is not None else []
        result.append((l_text, l_tags, r_text, r_tags))
    return result


def _monodix_par(lemma, pos, paradigm=None):
    """Return the par/@n for a specific lemma in the generated monodix."""
    entry = {'lemma': lemma, 'pos': pos}
    if paradigm:
        entry['morphology'] = {'paradigm': paradigm}
    tree = build_monodix([entry])
    section = tree.find('.//section[@id="main"]')
    for e in section.findall('e'):
        if e.get('lm') == lemma:
            par = e.find('par')
            return par.get('n') if par is not None else None
    return None


def _monodix_stem(lemma, pos, paradigm=None):
    """Return the <i> stem text for a specific lemma in the generated monodix."""
    entry = {'lemma': lemma, 'pos': pos}
    if paradigm:
        entry['morphology'] = {'paradigm': paradigm}
    tree = build_monodix([entry])
    section = tree.find('.//section[@id="main"]')
    for e in section.findall('e'):
        if e.get('lm') == lemma:
            i = e.find('i')
            return i.text if i is not None else None
    return None


# ---------------------------------------------------------------------------
# Bug 1 — Arrow (↓) stripping in clean_lemma
# ---------------------------------------------------------------------------

class TestArrowStripping(unittest.TestCase):
    """clean_lemma() must strip Wiktionary ↓ arrows from translation terms."""

    def test_arrow_after_word(self):
        # Most common pattern: "la ↓ Kategorio:Eo LA"
        self.assertNotIn('↓', clean_lemma('la ↓ Kategorio:Eo LA'))

    def test_arrow_in_parens(self):
        # Pattern: "apud (↓) Kategorio:Eo AP"
        self.assertNotIn('↓', clean_lemma('apud (↓) Kategorio:Eo AP'))
        self.assertNotIn('()', clean_lemma('apud (↓) Kategorio:Eo AP'))

    def test_arrow_with_parenthetical(self):
        # Pattern: "de ↓ (indikante aganton)"
        self.assertNotIn('↓', clean_lemma('de ↓ (indikante aganton)'))

    def test_upward_arrow(self):
        self.assertNotIn('↑', clean_lemma('vorto ↑ noto'))

    def test_right_arrow(self):
        self.assertNotIn('→', clean_lemma('vorto → noto'))

    def test_arrow_only_becomes_empty(self):
        # A term that is only an arrow should become empty (filtered downstream)
        self.assertEqual(clean_lemma('↓').strip(), '')

    def test_multiple_arrows(self):
        result = clean_lemma('ĉe ↓ ↑ Kategorio:Eo')
        self.assertNotIn('↓', result)
        self.assertNotIn('↑', result)

    def test_clean_terms_unchanged(self):
        # Valid Esperanto terms must not be mangled
        for term in ('ĉe', 'kiam', 'sed', 'laŭ', 'je', 'ĉirkaŭ', 'de', 'en', 'la'):
            with self.subTest(term=term):
                self.assertEqual(clean_lemma(term), term)

    def test_arrow_survives_neither_in_monodix_nor_bidix(self):
        # End-to-end: a dirty term must not appear in exported XML
        entry = {
            'lemma': 'en', 'pos': 'preposition',
            'senses': [{'translations': [{'lang': 'eo', 'term': 'en ↓ Kategorio:Eo EN'}]}]
        }
        xml = ET.tostring(build_bidix([entry]), encoding='unicode')
        self.assertNotIn('↓', xml)
        self.assertNotIn('Kategorio', xml)


# ---------------------------------------------------------------------------
# Bug 2 — Correct paradigms for function words via infer_paradigm()
# ---------------------------------------------------------------------------

class TestFunctionWordParadigms(unittest.TestCase):
    """infer_paradigm() must return the correct paradigm, overriding ending heuristics."""

    def _par(self, lemma, pos=None):
        return infer_paradigm({'lemma': lemma, 'pos': pos})

    # Prepositions that end in -e (heuristic would give e__adv)
    def test_che_is_pr_not_adv(self):
        self.assertEqual(self._par('che'), 'pr')

    def test_ye_is_pr(self):
        self.assertEqual(self._par('ye'), 'pr')

    def test_segun_is_pr(self):
        self.assertEqual(self._par('segun'), 'pr')

    def test_apud_is_pr(self):
        self.assertEqual(self._par('apud'), 'pr')

    # Prepositions that end in -o (heuristic would give o__n)
    def test_pro_is_pr_not_noun(self):
        self.assertEqual(self._par('pro'), 'pr')

    # Conjunctions that end in -e (heuristic would give e__adv)
    def test_ke_is_cnjsub_not_adv(self):
        self.assertEqual(self._par('ke'), 'cnjsub')

    def test_kande_is_cnjsub_not_adv(self):
        # Bug found by test suite: kande was missing from FUNCTION_WORDS
        self.assertEqual(self._par('kande'), 'cnjsub')

    # Standard conjunctions and determiners
    def test_e_is_cnjcoo(self):
        self.assertEqual(self._par('e'), 'cnjcoo')

    def test_o_is_cnjcoo(self):
        self.assertEqual(self._par('o'), 'cnjcoo')

    def test_ma_is_cnjcoo(self):
        self.assertEqual(self._par('ma'), 'cnjcoo')

    def test_la_is_det(self):
        self.assertEqual(self._par('la'), 'det')

    def test_da_is_pr(self):
        self.assertEqual(self._par('da'), 'pr')

    def test_di_is_pr(self):
        self.assertEqual(self._par('di'), 'pr')

    # Contractions
    def test_dil_is_prep_art(self):
        self.assertEqual(self._par('dil'), 'prep_art')

    def test_dal_is_prep_art(self):
        self.assertEqual(self._par('dal'), 'prep_art')

    # Adverb that genuinely ends in -e (should stay e__adv)
    def test_ne_stays_adv(self):
        self.assertEqual(self._par('ne'), 'e__adv')


# ---------------------------------------------------------------------------
# Bug 3 — Long-form POS names normalized in build_monodix
# ---------------------------------------------------------------------------

class TestPosNormalizationMonodix(unittest.TestCase):
    """build_monodix() must handle verbose POS strings from Wiktionary."""

    def test_preposition_gives_pr_paradigm(self):
        self.assertEqual(_monodix_par('segun', 'preposition'), '__pr')

    def test_conjunction_gives_cnjcoo_paradigm(self):
        self.assertEqual(_monodix_par('ma', 'conjunction'), '__cnjcoo')

    def test_determiner_gives_det_paradigm(self):
        self.assertEqual(_monodix_par('la', 'determiner'), '__det')

    def test_pronoun_gives_prn_paradigm(self):
        self.assertEqual(_monodix_par('me', 'pronoun'), '__prn')

    def test_preposition_stem_is_full_lemma(self):
        # Function words use full lemma as stem (extract_stem returns lemma for __pr)
        self.assertEqual(_monodix_stem('segun', 'preposition'), 'segun')

    def test_conjunction_stem_is_full_lemma(self):
        self.assertEqual(_monodix_stem('ma', 'conjunction'), 'ma')

    def test_determiner_stem_is_full_lemma(self):
        self.assertEqual(_monodix_stem('la', 'determiner'), 'la')


# ---------------------------------------------------------------------------
# Bug 3 continued — build_bidix POS normalization and entry structure
# ---------------------------------------------------------------------------

class TestBidixEntryStructure(unittest.TestCase):
    """build_bidix() entries must have correct stems and POS tags on both sides."""

    def _entry(self, lemma, pos, term):
        return {
            'lemma': lemma, 'pos': pos,
            'senses': [{'translations': [{'lang': 'eo', 'term': term}]}]
        }

    def test_preposition_entry_has_pr_tag(self):
        entries = _bidix_entries([self._entry('segun', 'preposition', 'laŭ')])
        self.assertEqual(len(entries), 1)
        l_text, l_tags, r_text, r_tags = entries[0]
        self.assertEqual(l_text, 'segun')
        self.assertIn('pr', l_tags)
        self.assertEqual(r_text, 'laŭ')
        self.assertIn('pr', r_tags)

    def test_conjunction_entry_has_cnjcoo_tag(self):
        entries = _bidix_entries([self._entry('ma', 'conjunction', 'sed')])
        self.assertEqual(len(entries), 1)
        l_text, l_tags, r_text, r_tags = entries[0]
        self.assertEqual(l_text, 'ma')
        self.assertIn('cnjcoo', l_tags)

    def test_determiner_entry_has_det_tag(self):
        entries = _bidix_entries([self._entry('la', 'determiner', 'la')])
        self.assertEqual(len(entries), 1)
        l_text, l_tags, _, _ = entries[0]
        self.assertEqual(l_text, 'la')
        self.assertIn('det', l_tags)

    def test_arrow_term_cleaned_and_entry_present(self):
        # The full pattern: dirty term → cleaned → valid entry in dix
        entry = {
            'lemma': 'la', 'pos': 'determiner',
            'senses': [{'translations': [{'lang': 'eo', 'term': 'la ↓ Kategorio:Eo LA'}]}]
        }
        entries = _bidix_entries([entry])
        self.assertEqual(len(entries), 1)
        l_text, l_tags, r_text, r_tags = entries[0]
        self.assertEqual(l_text, 'la')
        self.assertEqual(r_text, 'la')
        self.assertNotIn('↓', r_text)

    def test_entry_with_only_arrow_term_is_skipped(self):
        # If cleaning leaves an empty term, the entry must be dropped entirely
        entry = {
            'lemma': 'test', 'pos': 'pr',
            'senses': [{'translations': [{'lang': 'eo', 'term': '↓'}]}]
        }
        entries = _bidix_entries([entry])
        self.assertEqual(len(entries), 0)


# ---------------------------------------------------------------------------
# Integration: verify actual source data is clean (if available)
# ---------------------------------------------------------------------------

class TestSourceDataClean(unittest.TestCase):
    """Verify the actual pipeline output files contain no arrow artifacts."""

    NORMALIZED = Path(__file__).resolve().parents[1] / 'work/bilingual_normalized.json'

    def setUp(self):
        if not self.NORMALIZED.exists():
            self.skipTest('bilingual_normalized.json not available')

    def test_no_arrow_in_eo_translations(self):
        import json
        data = json.loads(self.NORMALIZED.read_text())
        dirty = []
        for e in data:
            for s in e.get('senses', []):
                for t in s.get('translations', []):
                    if t.get('lang') == 'eo' and '↓' in (t.get('term') or ''):
                        dirty.append((e.get('lemma'), t['term']))
        self.assertEqual(dirty, [],
            msg=f"Found {len(dirty)} dirty translations still containing ↓: {dirty[:5]}")

    def test_function_words_have_correct_paradigms(self):
        import json
        data = json.loads(self.NORMALIZED.read_text())
        by_lemma = {e['lemma']: e for e in data if e.get('lemma')}
        checks = {
            'ke':    'cnjsub',
            'che':   'pr',
            'pro':   'pr',
            'segun': 'pr',
            'kande': 'cnjsub',
            'la':    'det',
            'ma':    'cnjcoo',
        }
        for lemma, expected_par in checks.items():
            with self.subTest(lemma=lemma):
                entry = by_lemma.get(lemma)
                if entry is None:
                    continue  # word may legitimately be absent
                actual = infer_paradigm(entry)
                self.assertEqual(actual, expected_par,
                    msg=f"infer_paradigm('{lemma}') = {actual!r}, expected {expected_par!r}")


if __name__ == '__main__':
    unittest.main(verbosity=2)
