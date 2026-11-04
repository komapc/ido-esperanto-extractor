import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from parse_verb_transitivity import en_labels, eo_labels, fr_labels, io_labels, page_rows


def test_io_labels():
    assert io_labels("*Semantiko: ([[netr.]])\n") == {"intr"}
    assert io_labels("*Semantiko: ([[tr.]])\n*Semantiko: ([[netr.]])\n") == {"tr", "intr"}
    assert io_labels("*Semantiko: [[Kategorio:Fiziko]]\n") == set()


def test_eo_labels_use_the_template_not_prose():
    assert eo_labels("{{Esperanta verbo|netransitiva=jes}}") == {"intr"}
    assert eo_labels("{{Esperanta verbo|transitiva=jes}}") == {"tr"}
    assert eo_labels("#: {{vian|fari ''(transitiva)''}}") == set()


def test_en_labels_stay_inside_the_language_section():
    text = "==English==\n# {{lb|io|intransitive}} x\n==Ido==\n# {{lb|io|transitive|or|intransitive}} y\n==Malay==\n"
    assert en_labels(text, "io") == {"tr", "intr"}
    assert en_labels("==Ido==\n# {{lb|io|ambitransitive}} y\n", "io") == {"tr", "intr"}
    assert en_labels("==Esperanto==\n# {{lb|eo|transitive}} y\n", "io") == set()


def test_fr_labels():
    assert fr_labels("== {{langue|eo}} ==\n'''alveni''' {{t|eo}}\n", "eo") == {"tr"}
    assert fr_labels("== {{langue|eo}} ==\n'''agi''' {{i|eo}}\n== {{langue|io}} ==\n{{t|io}}", "eo") == {"intr"}


def test_page_rows_keep_only_verbs():
    assert list(page_rows("io", "enirar", "*Semantiko: ([[netr.]])")) == [("io", "enirar", "io", "intr")]
    assert list(page_rows("io", "domo", "*Semantiko: ([[netr.]])")) == []
