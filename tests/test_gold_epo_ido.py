"""epo->ido gold set: derivation from the reviewed ido->epo set and multi-reference chrF."""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


gold = _load("build_gold_epo_ido")
ev = _load("eval_translation")


def test_build_reverses_and_merges_alternatives(tmp_path):
    src = tmp_path / "ido_epo.tsv"
    src.write_text(
        "# comment\n"
        "Vu parolas.\tVi parolas.\tpronoun\n"
        "Tu parolas.\tVi parolas.\tpronoun,agreement\n"
        "Me venas.\tMi venas.\tbasic\n",
        encoding="utf-8",
    )
    rows = gold.build(src)
    assert rows == [
        ("Vi parolas.", ["Vu parolas.", "Tu parolas."], ["pronoun", "agreement"]),
        ("Mi venas.", ["Me venas."], ["basic"]),
    ]


def test_committed_epo_ido_gold_is_in_sync_with_generator(tmp_path):
    out = tmp_path / "epo_ido.tsv"
    rows = gold.build(ROOT / "data/gold/ido_epo.tsv")
    body = "".join(f"{eo}\t{' | '.join(r)}\t{','.join(t)}\n" for eo, r, t in rows)
    assert (ROOT / "data/gold/epo_ido.tsv").read_text(encoding="utf-8") == gold.HEADER + body


def test_best_chrf_takes_the_closest_reference():
    assert ev.best_chrf("Tu parolas.", "Vu parolas. | Tu parolas.") == 100.0
    assert ev.best_chrf("Tu parolas.", "Vu parolas.") < 100.0
    assert ev.best_chrf("Me venas.", "Me venas.") == 100.0
