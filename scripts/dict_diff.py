#!/usr/bin/env python3
"""Diff two Apertium bidix (.dix) files — see exactly what a rebuild would change.

The reproducibility safety net (PIPELINE_AUDIT.md P2): before deploying a freshly
built dictionary, diff it against the currently-deployed one so drift (a changed
or dropped translation like di→de ⇒ di→antaŭ) is reviewed, not shipped blind.

Reports per Ido side: added / removed entries and changed EO targets.

Usage:
  python3 scripts/dict_diff.py OLD.dix NEW.dix
  python3 scripts/dict_diff.py ../apertium-ido-epo/apertium-ido-epo.ido-epo.dix \
                               dist/apertium-ido-epo.ido-epo.dix --show 40
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

_ENTRY_RE = re.compile(r'<e\b[^>]*>.*?<l>(.*?)</l>\s*<r>(.*?)</r>.*?</e>', re.DOTALL)
_TAG_RE = re.compile(r'<s n="([^"]*)"/>')


def _norm(side: str) -> str:
    """'<l>til<s n="pr"/></l>' inner → 'til<pr>' (lemma + tag signature)."""
    lemma = side.split('<', 1)[0].strip()
    tags = ''.join(f'<{t}>' for t in _TAG_RE.findall(side))
    return lemma + tags


def _load(path: Path) -> dict:
    """Map Ido side → set of EO sides."""
    text = path.read_text(encoding='utf-8')
    out = defaultdict(set)
    for l, r in _ENTRY_RE.findall(text):
        out[_norm(l)].add(_norm(r))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('old', type=Path)
    ap.add_argument('new', type=Path)
    ap.add_argument('--show', type=int, default=30)
    ap.add_argument('--report', type=Path, help='also write a markdown report here')
    args = ap.parse_args()

    old, new = _load(args.old), _load(args.new)
    old_keys, new_keys = set(old), set(new)

    added = sorted(new_keys - old_keys)
    removed = sorted(old_keys - new_keys)
    changed = sorted(k for k in old_keys & new_keys if old[k] != new[k])

    lines = [
        f"# bidix diff", "",
        f"- old: `{args.old}` ({len(old)} Ido lemmas)",
        f"- new: `{args.new}` ({len(new)} Ido lemmas)",
        f"- **added {len(added)}, removed {len(removed)}, changed {len(changed)}**", "",
    ]
    if changed:
        lines.append("## Changed translations (review these)")
        for k in changed[:args.show]:
            lines.append(f"- `{k}`: {sorted(old[k])} → {sorted(new[k])}")
        if len(changed) > args.show:
            lines.append(f"- … and {len(changed) - args.show} more")
        lines.append("")
    if removed:
        lines.append(f"## Removed ({len(removed)})")
        lines.append("  " + ", ".join(f"`{k}`" for k in removed[:args.show]))
        lines.append("")

    out = "\n".join(lines)
    print(out)
    if args.report:
        args.report.write_text(out + "\n", encoding='utf-8')
        print(f"(report written to {args.report})")
    # Exit non-zero if anything changed — usable as a CI/pre-deploy gate.
    return 1 if (added or removed or changed) else 0


if __name__ == '__main__':
    raise SystemExit(main())
