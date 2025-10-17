#!/usr/bin/env python3
import argparse
import logging
from pathlib import Path
from typing import Any, Dict, Iterable, List, Set, Tuple

from _common import read_json, write_json, save_text, configure_logging


def key_from_entry(e: Dict[str, Any]) -> Tuple[str, str]:
    return (str(e.get('lemma', '')).lower(), str(e.get('morphology', {}).get('paradigm') or e.get('pos') or ''))


def load_entries(path: Path) -> List[Dict[str, Any]]:
    data = read_json(path)
    return data if isinstance(data, list) else data.get('entries', data)


def diff_sets(old: List[Dict[str, Any]], new: List[Dict[str, Any]]) -> Tuple[Set[Tuple[str, str]], Set[Tuple[str, str]]]:
    old_keys = {key_from_entry(e) for e in old}
    new_keys = {key_from_entry(e) for e in new}
    missing_in_old = new_keys - old_keys
    missing_in_new = old_keys - new_keys
    return missing_in_old, missing_in_new


def find_morphology_issues(entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    issues: List[Dict[str, Any]] = []
    for e in entries:
        lemma = e.get('lemma')
        par = (e.get('morphology') or {}).get('paradigm')
        if not par:
            issues.append({'lemma': lemma, 'issue': 'missing_paradigm'})
            continue
        if par not in {'o__n', 'a__adj', 'e__adv', 'ar__vblex', '__adv', '__pr', '__cnjcoo', '__cnjsub', '__prn', '__n', '__adj', '__vblex', '__det', '__num'}:
            issues.append({'lemma': lemma, 'issue': f'unknown_paradigm:{par}'})
    return issues


def main(argv: Iterable[str]) -> int:
    ap = argparse.ArgumentParser(description='Compare current monodix vs new JSON vocabulary')
    ap.add_argument('--old-json', type=Path, required=True, help='JSON from existing monodix (converted)')
    ap.add_argument('--new-json', type=Path, required=True, help='New final_vocabulary.json or ido_dictionary.json')
    ap.add_argument('--report-md', type=Path, required=True, help='Output markdown report')
    ap.add_argument('-v', '--verbose', action='count', default=0)
    args = ap.parse_args(list(argv))

    configure_logging(args.verbose)
    old_entries = load_entries(args.old_json)
    new_entries = load_entries(args.new_json)

    missing_in_old, missing_in_new = diff_sets(old_entries, new_entries)
    morph_issues = find_morphology_issues(new_entries)

    lines: List[str] = []
    lines.append('# Monodix vs New Vocabulary Comparison\n')
    lines.append(f'- Old entries: {len(old_entries)}')
    lines.append(f'- New entries: {len(new_entries)}\n')
    lines.append('## New-only entries (present now, missing before)\n')
    for lemma, par in sorted(missing_in_old)[:2000]:
        lines.append(f'- {lemma} [{par}]')
    if len(missing_in_old) > 2000:
        lines.append(f'... and {len(missing_in_old)-2000} more')
    lines.append('\n## Old-only entries (present before, missing now)\n')
    for lemma, par in sorted(missing_in_new)[:2000]:
        lines.append(f'- {lemma} [{par}]')
    if len(missing_in_new) > 2000:
        lines.append(f'... and {len(missing_in_new)-2000} more')
    lines.append('\n## Morphology issues (new)\n')
    for issue in morph_issues[:2000]:
        lines.append(f"- {issue['lemma']}: {issue['issue']}")
    if len(morph_issues) > 2000:
        lines.append(f'... and {len(morph_issues)-2000} more')

    save_text(args.report_md, '\n'.join(lines) + '\n')
    logging.info('Wrote %s', args.report_md)
    return 0


if __name__ == '__main__':
    import sys
    raise SystemExit(main(sys.argv[1:]))


