import xml.etree.ElementTree as ET

from scripts.export_apertium import (_emit_euphonic_short, _euphonic_long_forms_lr,
                                     _serialize_inline)


def test_short_form_generates_with_alarm():
    section = ET.Element("section")
    _emit_euphonic_short(section, "e", "__cnjcoo")
    lr, rl = [_serialize_inline(e) for e in section]
    assert lr == '<e lm="e" r="LR"><i>e</i><par n="__cnjcoo"/></e>'
    assert rl == '<e lm="e" r="RL"><p><l><a/>e</l><r>e</r></p><par n="__cnjcoo"/></e>'


def test_long_forms_become_ido_to_epo_only():
    section = ET.fromstring(
        '<section>'
        '<e><p><l>ed<s n="cnjcoo"/></l><r>kaj<s n="cnjcoo"/></r></p></e>'
        '<e><p><l>e<s n="cnjcoo"/></l><r>kaj<s n="cnjcoo"/></r></p></e>'
        '<e><p><l>ad<s n="pr"/></l><r>al<s n="pr"/></r></p></e>'
        '<e><p><l>od<s n="n"/></l><r>odo<s n="n"/></r></p></e>'
        '</section>')
    assert _euphonic_long_forms_lr(section) == 2
    assert [e.get("r") for e in section] == ["LR", None, "LR", None]
