"""changed_titles must see edits older than the recentchanges retention window."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import fetch_wiktionary_overlay as overlay


def test_changed_titles_merges_revisions_and_logs(monkeypatch):
    calls = []

    def fake_api(lang, params):
        calls.append(dict(params))
        if params["list"] == "allrevisions":
            if "arvcontinue" not in params:
                return {"query": {"allrevisions": [{"title": "habitar"}, {"title": "plus"}]},
                        "continue": {"arvcontinue": "x", "continue": "-||"}}
            return {"query": {"allrevisions": [{"title": "plus"}, {"title": "tam"}]}}
        if params["letype"] == "delete":
            return {"query": {"logevents": [{"title": "forigita"}]}}
        return {"query": {"logevents": [
            {"title": "olda", "params": {"target_ns": 0, "target_title": "nova"}},
            {"title": "altra", "params": {"target_ns": 4, "target_title": "Wikivortaro:x"}},
        ]}}

    monkeypatch.setattr(overlay, "_api", fake_api)
    monkeypatch.setattr(overlay.time, "sleep", lambda _: None)

    assert overlay.changed_titles("io", "2026-08-31T10:46:18Z") == [
        "habitar", "plus", "tam", "forigita", "olda", "nova", "altra"]
    assert all(c["list"] != "recentchanges" for c in calls)
    assert calls[0]["arvstart"] == "2026-08-31T10:46:18Z"
