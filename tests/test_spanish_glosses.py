import json

from scripts.wiktionary_parser import extract_translations, parse_meanings
from scripts.export_vortaro import clean_spanish_term, load_spanish_glosses


def test_spanish_line_with_sense_numbers():
    # io.wiktionary 'artiklo': a term shared by two senses
    sec = ('{|\n*{{es}}: (1, 2) [[artículo]] \n*{{it}}: (1, 2) [[articolo]] \n|}\n')
    assert extract_translations(sec, "es") == [["artículo"]]
    assert extract_translations("*{{es}}: (1) [[gato]], [[minino]]; (2) [[cola]]\n", "es") == [
        ["gato", "minino"], ["cola"]]


def test_shared_sense_numbers_are_not_terms():
    # used to give ["(1", "2) article", "item"]
    assert parse_meanings("(1, 2) [[article]], [[item]]") == [["article", "item"]]
    assert parse_meanings("(1-3) [[x]]") == [["x"]]


def test_clean_spanish_term():
    assert clean_spanish_term("[[") == ""                      # unfilled template
    assert clean_spanish_term("[[beatífico") == "beatífico"    # unclosed link
    assert clean_spanish_term("muerte ''f''") == "muerte"      # italic gender mark
    assert clean_spanish_term("''vaudeville''") == "vaudeville"
    assert clean_spanish_term("…") == ""


def test_load_spanish_glosses(tmp_path):
    p = tmp_path / "f.json"
    p.write_text(json.dumps({"entries": [
        {"lemma": "kato", "glosses": {"es": [["gato", "gata"], ["gato"]]}},
        {"lemma": "multe", "glosses": {"es": [["[["]]}},
        {"lemma": "domo"},
    ]}), encoding="utf-8")
    g = load_spanish_glosses(str(p))
    assert g["kato"] == ["gato", "gata"]
    assert not g.get("multe")
    assert "domo" not in g


def test_es_wiktionary_ido_terms_from_spanish_section_only():
    from scripts.parse_es_wiktionary_io import extract
    text = ("== {{lengua|es}} ==\n==== Traducciones ====\n"
            "{{t|io|a1=1|t1=urso|g1=m|a2=1|t2=ursino|g2=f}}\n"
            "{{t|io|t1=avulo/avino}}\n"
            "== {{lengua|it}} ==\n{{t|io|t1=ignorata}}\n")
    out = extract([("oso", "0", text), ("x", "10", "{{t|io|t1=no}}")])
    assert out["pairs"] == {"urso": ["oso"], "ursino": ["oso"]}
    assert out["skipped"] == [{"page": "oso", "value": "avulo/avino"}]


def test_merge_spanish_appends_es_wiktionary_after_io():
    from scripts.export_vortaro import merge_spanish
    spanish = {"kato": ["gato"]}
    added = merge_spanish(spanish, {"kato": ["gato", "minino"], "Homino": ["mujer"], "nekonata": ["x"]},
                          {"kato", "homino"})
    assert spanish == {"kato": ["gato", "minino"], "homino": ["mujer"]}
    assert added == 2
