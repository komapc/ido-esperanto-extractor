from scripts.wiktionary_parser import extract_pos, extract_pos_by_section


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


# io.wiktionary 'centimo': I = the coin, II = the fraction 1/100 (the only
# section carrying [[Kategorio:Numeri]]).
_CENTIMO = (
    "==I {{io}} (pekunio)==\n"
    "*Semantiko: [[pekunio]]   [[Kategorio:Ekonomiko]]\n"
    "*Morfologio: [[centim]][[.o]] [[Kategorio:Io CE]]\n"
    "==II {{io}} (numero)==\n"
    "*Semantiko: [[1/100]]   [[Kategorio:Numeri]]\n"
    "*Morfologio: [[cent]][[.im.o]] [[Kategorio:Io CE]]\n"
)


def test_numeral_category_of_a_later_sense_does_not_make_the_page_a_numeral():
    assert extract_pos(_CENTIMO) == "num"          # whole page: the later sense wins
    assert extract_pos_by_section(_CENTIMO, "centimo") != "num"


def test_single_section_page_is_left_to_extract_pos():
    text = "*Semantiko: ••••  [[Kategorio:Numeri]]\n*Morfologio: quar [[Kategorio:Io Q]]\n"
    assert extract_pos_by_section(text, "quar") is None
