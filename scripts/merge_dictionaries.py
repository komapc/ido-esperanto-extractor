#!/usr/bin/env python3
import argparse
import logging
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from _common import read_json, write_json, read_yaml, write_yaml, ensure_dir, configure_logging


def load_any(path: Path) -> Any:
    if path.suffix.lower() in {".yaml", ".yml"}:
        return read_yaml(path)
    return read_json(path)


def save_any(path: Path, data: Any) -> None:
    if path.suffix.lower() in {".yaml", ".yml"}:
        write_yaml(path, data)
    else:
        write_json(path, data)


def entry_key(entry: Dict[str, Any]) -> Tuple:
    if "id" in entry and entry["id"]:
        return ("id", entry["id"])
    # Fallback composite key for monolingual entries
    return (
        "composite",
        entry.get("language"),
        entry.get("lemma"),
        entry.get("pos"),
    )


def unique_list(items: Iterable[Any]) -> List[Any]:
    seen = set()
    out: List[Any] = []
    for it in items:
        key = tuple(sorted(it.items())) if isinstance(it, dict) else it
        if key in seen:
            continue
        seen.add(key)
        out.append(it)
    return out


def merge_senses(a: List[Dict[str, Any]], b: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    by_id: Dict[str, Dict[str, Any]] = {}
    def sid(s: Dict[str, Any]) -> str:
        return str(s.get("senseId") or s.get("id") or "")
    for s in a + b:
        k = sid(s)
        if k and k in by_id:
            # Merge translations and keep first gloss
            existing = by_id[k]
            existing_trans = existing.get("translations", [])
            new_trans = s.get("translations", [])
            existing["translations"] = unique_list([*existing_trans, *new_trans])
            if not existing.get("gloss") and s.get("gloss"):
                existing["gloss"] = s.get("gloss")
        else:
            by_id[k] = {**s}
    return list(by_id.values())


def merge_entries(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    out = {**a}
    for k, v in b.items():
        if k == "senses":
            out["senses"] = merge_senses(a.get("senses", []), b.get("senses", []))
        elif k == "provenance":
            out["provenance"] = unique_list([*(a.get("provenance", [])), *list(b.get("provenance", []))])
        elif k not in out or out[k] in (None, ""):
            out[k] = v
        # else keep original (prefer-first policy)
    return out


def merge_lists(inputs: List[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    merged: Dict[Tuple, Dict[str, Any]] = {}
    for lst in inputs:
        for entry in lst:
            k = entry_key(entry)
            if k in merged:
                merged[k] = merge_entries(merged[k], entry)
            else:
                merged[k] = entry
    # Sort deterministically by lemma then pos
    items = list(merged.values())
    items.sort(key=lambda e: (str(e.get("lemma", "")), str(e.get("pos", "")), str(e.get("language", ""))))
    return items


def normalize_container(obj: Any) -> List[Dict[str, Any]]:
    if isinstance(obj, list):
        return obj
    if isinstance(obj, dict):
        if "entries" in obj and isinstance(obj["entries"], list):
            return obj["entries"]
        # If dict of id -> entry
        if all(isinstance(v, dict) for v in obj.values()):
            return list(obj.values())
    raise ValueError("Unsupported input structure; expected list of entries or {entries: [...]}.")


def main() -> int:
    ap = argparse.ArgumentParser(description="Merge dictionary JSON/YAML files deterministically")
    ap.add_argument("--inputs", nargs="+", type=Path, required=True, help="Input JSON/YAML files")
    ap.add_argument("--output", type=Path, required=True, help="Output JSON/YAML file")
    ap.add_argument("-v", "--verbose", action="count", default=0)
    args = ap.parse_args()

    configure_logging(args.verbose)
    lists: List[List[Dict[str, Any]]] = []
    for p in args.inputs:
        logging.info("Loading %s", p)
        data = load_any(p)
        lists.append(normalize_container(data))

    merged = merge_lists(lists)
    ensure_dir(args.output.parent)
    save_any(args.output, merged)
    logging.info("Wrote %s (%d entries)", args.output, len(merged))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())




