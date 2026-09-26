"""is_inflected_form: 'pluralo de X' drops only regular noun inflections of X."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'scripts'))

from wiktionary_parser import is_inflected_form


def sem(text):
    return f"*Semantiko: {text}\n*Morfologio: x\n"


@pytest.mark.parametrize("title, text", [
    ("kati", "[[pluralo]] [[de]] ''[[kato]]''"),
    ("katon", "[[akuzativo]] [[de]] [[kato]]"),
])
def test_regular_noun_inflections_are_dropped(title, text):
    assert is_inflected_form(sem(text), title)


@pytest.mark.parametrize("title, text", [
    ("eli", "[[pluralo]] [[de]] ''[[elu]]''  [[Kategorio:Pronomi]]"),
    ("vi", "[[pluralo]] [[de]] [[vu]], [[tu]]   [[Kategorio:Pronomi]]"),
    ("qui", "[[pluralo]] di ''[[qua]]''. [[Kategorio:Pronomi]]"),
    ("le", "[[pluralo]] [[de]] [[artiklo]] [[la]]"),
    ("singli", "[[pluralo]] [[de]] [[singlu]]"),
])
def test_closed_class_lemmas_are_kept(title, text):
    assert not is_inflected_form(sem(text), title)


def test_without_title_keeps_old_behaviour():
    assert is_inflected_form(sem("[[pluralo]] [[de]] ''[[elu]]''"))


def test_verb_form_still_dropped():
    assert is_inflected_form(sem("prezenta formo de verbo esar"), "esas")
