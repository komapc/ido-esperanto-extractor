from scripts.wiktionary_parser import extract_pos


def test_nombro_in_a_definition_is_not_a_numeral_label():
    # io.wiktionary 'kalkular': "nombro" is a word of the gloss
    text = ("*Semantiko: ([[tr.]]) (1) [[determinar|Determinar]], [[per]] "
            "[[operaco|operaci]] [[matematikala]], [[ye]] [[nombro|nombri]] [[donar|donita]]\n"
            "*Morfologio: [[kalkul]][[.ar]] [[Kategorio:Io KAL]]\n")
    assert extract_pos(text) != "num"


def test_numeral_category_still_gives_num():
    # io.wiktionary 'quar'
    text = ("*Semantiko: ••••  [[Kategorio:Numeri]]\n"
            "*Morfologio: quar [[Kategorio:Io Q]]\n")
    assert extract_pos(text) == "num"
