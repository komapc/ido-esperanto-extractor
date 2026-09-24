import bz2
import json
import os

from scripts.wiktionary_parser import iter_pages

_DUMP = """<mediawiki>
<page><title>alfa</title><ns>0</ns><revision><text>old alfa</text></revision></page>
<page><title>beta</title><ns>0</ns><revision><text>beta</text></revision></page>
<page><title>gama</title><ns>0</ns><revision><text>gama</text></revision></page>
</mediawiki>"""


def _dump(tmp_path):
    path = tmp_path / "xxwiktionary-latest-pages-articles.xml.bz2"
    path.write_bytes(bz2.compress(_DUMP.encode()))
    return path


def test_without_overlay_reads_dump(tmp_path):
    assert [t for t, _, _ in iter_pages(_dump(tmp_path))] == ["alfa", "beta", "gama"]


def test_overlay_replaces_adds_and_deletes(tmp_path):
    dump = _dump(tmp_path)
    overlay = dump.with_name(dump.name + ".overlay.json")
    overlay.write_text(json.dumps({"since": "2026-09-01T00:00:00Z", "pages": {
        "alfa": {"ns": "0", "text": "new alfa"},
        "gama": {"deleted": True},
        "delta": {"ns": "0", "text": "delta"},
    }}))
    pages = {t: x for t, _, x in iter_pages(dump)}
    assert pages == {"alfa": "new alfa", "beta": "beta", "delta": "delta"}


def test_overlay_older_than_dump_is_ignored(tmp_path):
    dump = _dump(tmp_path)
    overlay = dump.with_name(dump.name + ".overlay.json")
    overlay.write_text(json.dumps({"pages": {"alfa": {"ns": "0", "text": "stale"}}}))
    st = dump.stat()
    os.utime(overlay, (st.st_atime - 60, st.st_mtime - 60))
    assert dict((t, x) for t, _, x in iter_pages(dump))["alfa"] == "old alfa"
