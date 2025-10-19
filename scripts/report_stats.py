#!/usr/bin/env python3
import argparse
import json
import logging
from pathlib import Path
from typing import Any, Dict, Iterable, List, Set

from _common import read_json, save_text, configure_logging


def provenance_sources(entry: Dict[str, Any]) -> Set[str]:
    prov = entry.get("provenance") or []
    return {str(p.get("source") or "") for p in prov if isinstance(p, dict)}


def compute_stats(final_path: Path, mono_path: Path, io_wikt_path: Path, eo_wikt_path: Path) -> Dict[str, Any]:
    final = read_json(final_path) if final_path.exists() else []
    mono = read_json(mono_path) if mono_path.exists() else []
    io_wikt = read_json(io_wikt_path) if io_wikt_path.exists() else []
    eo_wikt = read_json(eo_wikt_path) if eo_wikt_path.exists() else []

    # Provenance presence
    missing_prov = sum(1 for e in final if not e.get("provenance"))
    missing_source_field = 0
    for e in final:
        prov = e.get("provenance") or []
        if any(isinstance(p, dict) and ("source" not in p) for p in prov):
            missing_source_field += 1

    # Final dictionary split by source
    keys = ["io_wiktionary", "eo_wiktionary", "io_wikipedia", "whitelist"]
    final_by_source = {k: 0 for k in keys}
    for e in final:
        for k in keys:
            if any(k in s for s in provenance_sources(e)):
                final_by_source[k] += 1

    # Monolingual Ido split by source
    mono_by_source = {k: 0 for k in keys}
    for e in mono:
        for k in keys:
            if any(k in s for s in provenance_sources(e)):
                mono_by_source[k] += 1

    # Wiktionary translation counts
    io_to_eo = 0
    for e in io_wikt:
        for s in e.get("senses", []) or []:
            for tr in s.get("translations", []) or []:
                if (tr.get("lang") == "eo") and (tr.get("term") or "").strip():
                    io_to_eo += 1
    eo_to_io = 0
    for e in eo_wikt:
        for s in e.get("senses", []) or []:
            for tr in s.get("translations", []) or []:
                if (tr.get("lang") == "io") and (tr.get("term") or "").strip():
                    eo_to_io += 1

    # Wikipedia/Wikidata additions
    wiki_any = 0
    wiki_only = 0
    for e in final:
        srcs = provenance_sources(e)
        has_wiki = any("wikipedia" in s for s in srcs)
        has_wikt = any("wiktionary" in s for s in srcs)
        if has_wiki:
            wiki_any += 1
            if not has_wikt:
                wiki_only += 1

    # Coverage metrics for Ido entries without EO translations
    no_eo_total = 0
    no_eo_any_other = 0
    no_eo_en = 0
    for e in final:
        if e.get("language") != "io":
            continue
        senses = e.get("senses", []) or []
        has_eo = False
        has_other = False
        has_en = False
        for s in senses:
            for tr in s.get("translations", []) or []:
                term = (tr.get("term") or "").strip()
                if not term:
                    continue
                lang = tr.get("lang")
                if lang == "eo":
                    has_eo = True
                elif lang:
                    has_other = True
                    if lang == "en":
                        has_en = True
        if not has_eo:
            no_eo_total += 1
            if has_other:
                no_eo_any_other += 1
            if has_en:
                no_eo_en += 1

    return {
        "final_total": len(final),
        "final_by_source": final_by_source,
        "monolingual_total": len(mono),
        "monolingual_by_source": mono_by_source,
        "translations_from_wiktionaries": {"io_to_eo": io_to_eo, "eo_to_io": eo_to_io},
        "wikipedia_additions": {"any_wikipedia": wiki_any, "wikipedia_only": wiki_only, "wikidata": 0},
        "coverage_no_eo": {
            "ido_entries_without_eo": no_eo_total,
            "with_any_other_translation": no_eo_any_other,
            "with_english_translation": no_eo_en,
        },
    }


def render_markdown(stats: Dict[str, Any]) -> str:
    lines: List[str] = []
    a = lines.append
    a("# Dictionary Statistics\n")
    a(f"- Final entries: {stats['final_total']}")
    a(f"- Monolingual Ido entries: {stats['monolingual_total']}\n")
    a("## Final by Source")
    for k, v in stats["final_by_source"].items():
        a(f"- {k}: {v}")
    a("\n## Monolingual Ido by Source")
    for k, v in stats["monolingual_by_source"].items():
        a(f"- {k}: {v}")
    a("\n## Wiktionary Translations")
    a(f"- IO→EO: {stats['translations_from_wiktionaries']['io_to_eo']}")
    a(f"- EO→IO: {stats['translations_from_wiktionaries']['eo_to_io']}")
    a("\n## Wikipedia/Wikidata Additions")
    a(f"- any_wikipedia: {stats['wikipedia_additions']['any_wikipedia']}")
    a(f"- wikipedia_only: {stats['wikipedia_additions']['wikipedia_only']}")
    a(f"- wikidata: {stats['wikipedia_additions']['wikidata']}")
    a("\n## Coverage: Ido entries without EO translations")
    a(f"- no_EO_translation: {stats['coverage_no_eo']['ido_entries_without_eo']}")
    a(f"- with_any_other_translation: {stats['coverage_no_eo']['with_any_other_translation']}")
    a(f"- with_english_translation: {stats['coverage_no_eo']['with_english_translation']}")
    a("")
    return "\n".join(lines)


def main(argv: Iterable[str]) -> int:
    ap = argparse.ArgumentParser(description="Compute and report dictionary statistics")
    ap.add_argument("--final", type=Path, default=Path(__file__).resolve().parents[1] / "work/final_vocabulary.json")
    ap.add_argument("--mono", type=Path, default=Path(__file__).resolve().parents[1] / "dist/ido_dictionary.json")
    ap.add_argument("--io-wikt", type=Path, default=Path(__file__).resolve().parents[1] / "work/io_wikt_io_eo.json")
    ap.add_argument("--eo-wikt", type=Path, default=Path(__file__).resolve().parents[1] / "work/eo_wikt_eo_io.json")
    ap.add_argument("--out", type=Path, default=Path(__file__).resolve().parents[1] / "reports/stats_summary.md")
    ap.add_argument("-v", "--verbose", action="count", default=0)
    args = ap.parse_args(list(argv))

    configure_logging(args.verbose)
    stats = compute_stats(args.final, args.mono, args.io_wikt, args.eo_wikt)
    save_text(args.out, render_markdown(stats) + "\n")
    logging.info("Wrote %s", args.out)
    return 0


if __name__ == "__main__":
    import sys
    raise SystemExit(main(sys.argv[1:]))


