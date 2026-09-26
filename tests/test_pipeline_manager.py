"""Staleness rules of pipeline_manager: when a completed stage must re-run."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'scripts'))

import pipeline_manager as pm


@pytest.fixture
def raw_dir(tmp_path, monkeypatch):
    d = tmp_path / 'raw'
    d.mkdir()
    monkeypatch.setattr(pm, '_RAW_DIR', d)
    return d


def _stages(log):
    # Each stage appends its name to `log` when it actually runs.
    return [(name, [sys.executable, '-c', f"open({str(log)!r}, 'a').write('{name}\\n')"], name, None)
            for name in ('a', 'b', 'c')]


def _run(tmp_path, stages, start_from=None):
    log = tmp_path / 'log'
    log.write_text('')
    pm.PipelineManager(tmp_path / 'state.json').run_pipeline(stages, start_from=start_from)
    return log.read_text().split()


def test_completed_stages_are_skipped(tmp_path, raw_dir):
    stages = _stages(tmp_path / 'log')
    assert _run(tmp_path, stages) == ['a', 'b', 'c']
    assert _run(tmp_path, stages) == []


def test_explicit_stage_forces_it_and_downstream(tmp_path, raw_dir):
    stages = _stages(tmp_path / 'log')
    _run(tmp_path, stages)
    assert _run(tmp_path, stages, start_from='b') == ['b', 'c']


def test_unknown_stage_is_an_error(tmp_path, raw_dir):
    with pytest.raises(SystemExit):
        _run(tmp_path, _stages(tmp_path / 'log'), start_from='nope')


def test_replaced_dump_invalidates(tmp_path, raw_dir):
    dump = raw_dir / 'iowiki-latest-pages-articles.xml.bz2'
    dump.write_bytes(b'old')
    stages = _stages(tmp_path / 'log')
    _run(tmp_path, stages)
    dump.write_bytes(b'newer dump')
    assert _run(tmp_path, stages) == ['a', 'b', 'c']


def test_non_dump_files_do_not_invalidate(tmp_path, raw_dir):
    stages = _stages(tmp_path / 'log')
    _run(tmp_path, stages)
    (raw_dir / 'x.xml.bz2.part').write_bytes(b'partial')
    (raw_dir / 'x.xml.bz2.overlay.json').write_text('{}')
    (raw_dir / 'SHA256SUMS.txt').write_text('')
    assert _run(tmp_path, stages) == []


def test_fingerprint_is_taken_after_the_run(tmp_path, raw_dir):
    # A stage that writes into data/raw (download_dumps) must not look stale
    # on the next run just because of its own output.
    log = tmp_path / 'log'
    stages = [('dl', [sys.executable, '-c',
                      f"open({str(log)!r}, 'a').write('dl\\n');"
                      f"open({str(raw_dir / 'd.sql.gz')!r}, 'w').write('x')"], 'dl', None)]
    _run(tmp_path, stages)
    assert _run(tmp_path, stages) == []


def test_shell_script_content_is_fingerprinted(tmp_path, monkeypatch, raw_dir):
    monkeypatch.setattr(pm, '_REPO_DIR', tmp_path)
    sh = tmp_path / 'dl.sh'
    sh.write_text('echo 1\n')
    before = pm.stage_fingerprint(['dl.sh'])
    sh.write_text('echo 2\n')
    assert pm.stage_fingerprint(['dl.sh']) != before
