#!/usr/bin/env python3
"""Build work/bilingual_raw.json: the union of every Ido-keyed candidate stream.

Despite the name, only `identical_form_heuristic` does any *aligning*
(io.wikt entry ↔ eo.wikt entry with the same lemma+POS). The rest of
`align()` is concatenation: each stream is appended as-is, keyed by Ido
lemma, and the real merge/dedup happens later in build_one_big_bidix_json.py.
Duplicates across streams are therefore expected and harmless here.

Streams, in order (see the `--- Stream N` markers in align()):
  1. identical-form io↔eo Wiktionary matches
  2. io.wikt entries passed through — with an EO gloss, or gloss-less but
     Ido-shaped and attested in some other language (monodix-only, so words
     like `dissendar` become analysable without a manual entry)
  3. io.wikipedia titles (monodix-only)
  4. eo.wikt entries inverted: each Ido translation on an EO page becomes
     an Ido record whose gloss is the EO page lemma
  5. via-English pivot pairs   (work/bilingual_via_en.json)
  6. via-French pivot pairs    (work/fr_wikt_via.json)

Streams 5–6 are skipped when their file is absent — silently, not as an
error. That interacts badly with pipeline_manager's stage order: this script
is stage 10 but `parse_wiktionary_via.py --source fr` (which writes
fr_wikt_via.json) is stage 11, so on a clean rebuild stream 6 is empty and
the French pairs only enter bilingual_raw.json on the *second* full run.

The `confidence` values attached to translations here (0.5 / 0.6 / 0.8) are
not a conflict signal: build_one_big_bidix_json.py drops them and keeps only
the source set, and conflict_resolution.py ranks by source.
"""
import argparse
import sys
import logging
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from _common import read_json, write_json, configure_logging


def _io_pos_class(lemma: str) -> str | None:
    l = (lemma or "").lower()
    if not l:
        return None
    if l.endswith("ar") or l.endswith("ir"):
        return "v"
    if l.endswith("o"):
        return "n"
    if l.endswith("a"):
        return "adj"
    if l.endswith("e"):
        return "adv"
    return None


def _eo_pos_class(lemma: str) -> str | None:
    l = (lemma or "").lower()
    if not l:
        return None
    if l.endswith("i"):
        return "v"
    if l.endswith("o"):
        return "n"
    if l.endswith("a"):
        return "adj"
    if l.endswith("e"):
        return "adv"
    return None


def identical_form_heuristic(io_entries: List[Dict[str, Any]], eo_entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    # Build index by lemma+pos for quick lookup
    def index_by_lemma_pos(entries: List[Dict[str, Any]]) -> Dict[Tuple[str, str], Dict[str, Any]]:
        idx: Dict[Tuple[str, str], Dict[str, Any]] = {}
        for e in entries:
            lemma = (e.get("lemma") or "").lower()
            pos = (e.get("pos") or "").lower()
            if lemma and pos:
                idx[(lemma, pos)] = e
        return idx

    io_idx = index_by_lemma_pos(io_entries)
    eo_idx = index_by_lemma_pos(eo_entries)

    aligned: List[Dict[str, Any]] = []
    for key, io_e in io_idx.items():
        if key not in eo_idx:
            continue
        eo_e = eo_idx[key]
        # Safety: POS already matches; now check overlapping English translations if present in senses
        def english_set(entry: Dict[str, Any]) -> set:
            out = set()
            for s in entry.get("senses", []) or []:
                for tr in s.get("translations", []) or []:
                    if tr.get("lang") == "en":
                        term = (tr.get("term") or "").strip().lower()
                        if term:
                            out.add(term)
            return out

        en_io = english_set(io_e)
        en_eo = english_set(eo_e)
        safe = True
        if en_io and en_eo and en_io.isdisjoint(en_eo):
            # If both sides have English translations but no overlap, skip
            safe = False
        if not safe:
            continue

        # Build a merged bilingual item with boosted confidence
        translations = []
        for s in io_e.get("senses", []) or []:
            for tr in s.get("translations", []) or []:
                if tr.get("lang") == "eo":
                    tr2 = dict(tr)
                    tr2["confidence"] = min(1.0, float(tr.get("confidence", 0.6)) + 0.2)
                    # add eo_wiktionary to translation-level sources when identical-form confirms
                    srcs = tr2.get("sources") or []
                    if not isinstance(srcs, list):
                        srcs = []
                    if "eo_wiktionary" not in srcs:
                        srcs.append("eo_wiktionary")
                    tr2["sources"] = sorted(set(srcs))
                    translations.append(tr2)
        item = {
            "lemma": io_e.get("lemma"),
            "pos": io_e.get("pos"),
            "language": "io",
            "senses": [{"senseId": None, "gloss": None, "translations": translations}],
            "provenance": [
                *list(io_e.get("provenance", []) or []),
                *list(eo_e.get("provenance", []) or []),
            ],
        }
        aligned.append(item)
    return aligned


def align(io_path: Path, eo_path: Path, out_path: Path,
          wiki_path: Path | None = None,
          via_en_path: Path | None = None,
          via_fr_path: Path | None = None) -> None:
    logging.info("Aligning bilingual dictionaries: %s + %s", io_path, eo_path)
    io_data = read_json(io_path)
    eo_data = read_json(eo_path)
    
    # Handle both formats: metadata wrapper or plain list
    io_entries = io_data.get("entries", io_data) if isinstance(io_data, dict) else io_data
    eo_entries = eo_data.get("entries", eo_data) if isinstance(eo_data, dict) else eo_data
    
    if not isinstance(io_entries, list):
        raise ValueError(f"io_wikt_io_eo.json must contain a list of entries (got {type(io_entries)})")
    if not isinstance(eo_entries, list):
        raise ValueError(f"eo_wikt_eo_io.json must contain a list of entries (got {type(eo_entries)})")

    # --- Stream 1: io.wikt ↔ eo.wikt entries with identical lemma+POS. This
    # is the only step in this function that actually *aligns* two sides.
    aligned = identical_form_heuristic(io_entries, eo_entries)
    # --- Stream 2: every io.wikt entry, passed through unaligned. Overlap
    # with stream 1 is expected; build_one_big_bidix_json.py merges by key.
    # Pass-through: include IO→EO entries as bilingual items even without EO confirmation.
    # Entries lacking an EO translation but having a valid Ido lemma shape and at least
    # one non-EO translation are kept too — they contribute to monodix morphological
    # recognition (lt-proc analysis) but are skipped by the bidix builder (which gates
    # on EO terms). This is how words like dissendar (in io.wiktionary, no EO target)
    # become recognizable without manual overrides.
    _IDO_LEMMA_SHAPE = ("o", "a", "e", "ar", "ir")
    _IDO_INFLECTION_TAILS = ("as", "is", "os", "us", "ez")  # conjugated forms — not lemmas
    kept_no_eo = 0
    for io_e in io_entries:
        translations = []
        for s in io_e.get("senses", []) or []:
            for tr in s.get("translations", []) or []:
                if tr.get("lang") == "eo" and tr.get("term"):
                    sources = tr.get("sources") or []
                    src = tr.get("source", "io_wiktionary")
                    if src:
                        sources = list(sorted(set(list(sources) + [src])))
                    translations.append({
                        "lang": "eo",
                        "term": tr.get("term"),
                        "confidence": float(tr.get("confidence", 0.5)),
                        "source": src,
                        "sources": sources,
                    })
        if not translations:
            # No EO target — keep for monodix only if Ido-shaped and Wiktionary-confirmed
            # (has at least one translation in another language).
            # Closed-class POS tags (adv/pr/det/prn/num/cnjcoo/cnjsub/ij) bypass the
            # lemma-shape filter: function words like 'kam', 'nun', 'maxim', 'od', 'an',
            # 'du', 'un', 'tri' don't have canonical -o/-a/-e/-ar/-ir endings but their
            # POS is established and they're definitely valid Ido lemmas.
            _CLOSED_CLASS = {"adv", "pr", "det", "prn", "num", "cnjcoo", "cnjsub", "ij",
                             "prep_art",
                             "adverb", "preposition", "determiner", "pronoun", "numeral",
                             "conjunction", "interjection", "subordinating conjunction"}
            lm = (io_e.get("lemma") or "").strip()
            lower = lm.lower()
            pos = io_e.get("pos") or ""
            has_other_tr = any(
                tr.get("lang") and tr.get("term")
                for s in (io_e.get("senses") or [])
                for tr in (s.get("translations") or [])
            )
            if not lm or not has_other_tr:
                continue
            if lower.endswith(_IDO_INFLECTION_TAILS):
                continue  # conjugated form, not a lemma
            if pos not in _CLOSED_CLASS and not lower.endswith(_IDO_LEMMA_SHAPE):
                continue  # non-canonical lemma shape (proper-name leftovers, etc.)
            item = {
                "lemma": lm,
                "pos": io_e.get("pos"),
                "language": "io",
                "senses": [],  # no EO target; bidix builder skips empty senses
                "provenance": list(io_e.get("provenance", []) or []),
            }
            aligned.append(item)
            kept_no_eo += 1
            continue
        item = {
            "lemma": io_e.get("lemma"),
            "pos": io_e.get("pos"),
            "language": "io",
            "senses": [{"senseId": None, "gloss": None, "translations": translations}],
            "provenance": list(io_e.get("provenance", []) or []),
        }
        aligned.append(item)
    if kept_no_eo:
        logging.info("Kept %d Ido-only entries without EO translation (monodix-only, Wiktionary-confirmed)", kept_no_eo)
    # --- Stream 3: io.wikipedia titles. No gloss — monodix coverage only.
    # Include Wikipedia titles (monolingual Ido entries) so they flow downstream
    if wiki_path is not None and wiki_path.exists():
        try:
            wiki_data = read_json(wiki_path)
            # Handle both list-of-entries and {'entries': [...]} formats
            if isinstance(wiki_data, dict):
                wiki_entries = wiki_data.get('entries', [])
            else:
                wiki_entries = wiki_data
        except Exception:
            wiki_entries = []
        added = 0
        for we in wiki_entries or []:
            if not isinstance(we, dict):
                continue
            if (we.get("language") or "") != "io":
                continue
            item = {
                "lemma": we.get("lemma"),
                "pos": we.get("pos"),
                "language": "io",
                "senses": [],  # no translations; may be kept in monolingual via filter step
                "provenance": list(we.get("provenance", []) or []),
            }
            aligned.append(item)
            added += 1
        logging.info("Added %d Wikipedia title entries", added)

    # --- Stream 4: eo.wikt pages, inverted. An EO page listing Ido
    # translations x, y becomes two Ido records (x→EO, y→EO). This is how
    # eo_wiktionary reaches the bidix at all: the pipeline is Ido-keyed, so
    # EO-side knowledge has to be re-expressed as Ido lemmas.
    # Flip EO→IO: create IO entries from EO pages (EO Wiktionary)
    added_flipped = 0
    for eo_e in eo_entries:
        io_terms = set()
        for s in eo_e.get("senses", []) or []:
            for tr in s.get("translations", []) or []:
                if tr.get("lang") == "io":
                    term = (tr.get("term") or "").strip()
                    if term:
                        io_terms.add(term)
        if not io_terms:
            continue
        eo_lemma = eo_e.get("lemma")
        tr_payload = [{
            "lang": "eo",
            "term": eo_lemma,
            "confidence": 0.6,
            "source": "eo_wiktionary",
            "sources": ["eo_wiktionary"],
        }]
        for io_term in sorted(io_terms):
            item = {
                "lemma": io_term,
                "pos": eo_e.get("pos"),
                "language": "io",
                "senses": [{"senseId": None, "gloss": None, "translations": tr_payload}],
                "provenance": list(eo_e.get("provenance", []) or []),
            }
            aligned.append(item)
            added_flipped += 1
    logging.info("Added %d flipped EO→IO items", added_flipped)

    # --- Stream 5: via-English pivot pairs. The POS-ending mismatch check is
    # the only quality gate a pivot pair gets before the merge: an English
    # word with an Ido noun and an Esperanto verb as translations is a
    # different sense on each side, not a translation pair.
    # Add via-English bilingual pairs (if available)
    if via_en_path is not None and via_en_path.exists():
        try:
            via_en_pairs = read_json(via_en_path)
        except Exception:
            via_en_pairs = []
        added_via_en = 0
        dropped_pos_mismatch = 0
        for pair in via_en_pairs or []:
            io_term = pair.get('lemma_io') or pair.get('io')
            eo_term = pair.get('lemma_eo') or pair.get('eo')
            prov0 = (pair.get('provenance') or [{}])[0]
            sense0 = (pair.get('senses') or [{}])[0]
            tr0 = (sense0.get('translations') or [{}])[0]
            via_word = pair.get('via') or prov0.get('page')
            confidence = pair.get('confidence', tr0.get('confidence', 0.8))

            if not io_term or not eo_term:
                continue

            ip, ep = _io_pos_class(io_term), _eo_pos_class(eo_term)
            if ip is not None and ep is not None and ip != ep:
                dropped_pos_mismatch += 1
                continue
            
            item = {
                "lemma": io_term,
                # POS is now populated by parse_wiktionary_via.py from
                # io_wiktionary_processed.json (so via-pivot pairs merge
                # cleanly with their io_wiktionary counterparts in build_bidix
                # rather than creating a parallel pos=None record).
                "pos": pair.get('pos'),
                "language": "io",
                "senses": [{
                    "senseId": None,
                    "gloss": f"via English: {via_word}" if via_word else None,
                    "translations": [{
                        "lang": "eo",
                        "term": eo_term,
                        "confidence": confidence,
                        "source": "en_wiktionary_via",
                        "sources": ["en_wiktionary_via"],
                        "via": via_word
                    }]
                }],
                "provenance": [{
                    "source": "en_wiktionary_via",
                    "page": via_word,
                    "rev": None
                }],
            }
            aligned.append(item)
            added_via_en += 1
        logging.info("Added %d via-English IO↔EO pairs (dropped %d for POS-ending mismatch)", added_via_en, dropped_pos_mismatch)

    # --- Stream 6: via-French pivot pairs. NOTE: the producer is pipeline
    # stage 11, this script is stage 10, so on a clean rebuild this file does
    # not exist yet and the stream is silently empty (see module docstring).
    # Add via-French bilingual pairs (if available). Same structure as via-en;
    # produced by `parse_wiktionary_via.py --source fr`.
    if via_fr_path is not None and via_fr_path.exists():
        try:
            via_fr_pairs = read_json(via_fr_path)
        except Exception:
            via_fr_pairs = []
        added_via_fr = 0
        dropped_pos_mismatch_fr = 0
        for pair in via_fr_pairs or []:
            io_term = pair.get('lemma_io') or pair.get('io')
            eo_term = pair.get('lemma_eo') or pair.get('eo')
            prov0 = (pair.get('provenance') or [{}])[0]
            sense0 = (pair.get('senses') or [{}])[0]
            tr0 = (sense0.get('translations') or [{}])[0]
            via_word = pair.get('via') or prov0.get('page')
            confidence = pair.get('confidence', tr0.get('confidence', 0.8))

            if not io_term or not eo_term:
                continue

            ip, ep = _io_pos_class(io_term), _eo_pos_class(eo_term)
            if ip is not None and ep is not None and ip != ep:
                dropped_pos_mismatch_fr += 1
                continue

            item = {
                "lemma": io_term,
                "pos": pair.get('pos'),
                "language": "io",
                "senses": [{
                    "senseId": None,
                    "gloss": f"via French: {via_word}" if via_word else None,
                    "translations": [{
                        "lang": "eo",
                        "term": eo_term,
                        "confidence": confidence,
                        "source": "fr_wiktionary_via",
                        "sources": ["fr_wiktionary_via"],
                        "via": via_word
                    }]
                }],
                "provenance": [{
                    "source": "fr_wiktionary_via",
                    "page": via_word,
                    "rev": None
                }],
            }
            aligned.append(item)
            added_via_fr += 1
        logging.info("Added %d via-French IO↔EO pairs (dropped %d for POS-ending mismatch)", added_via_fr, dropped_pos_mismatch_fr)

    write_json(out_path, aligned)
    logging.info("Wrote %s (%d aligned items)", out_path, len(aligned))


def main(argv: Iterable[str]) -> int:
    ap = argparse.ArgumentParser(description="Align IO→EO and EO→IO wiktionary outputs")
    ap.add_argument("--io", type=Path, default=Path(__file__).resolve().parents[1] / "work/io_wikt_io_eo.json")
    ap.add_argument("--eo", type=Path, default=Path(__file__).resolve().parents[1] / "work/eo_wikt_eo_io.json")
    ap.add_argument("--wiki", type=Path, default=Path(__file__).resolve().parents[1] / "work/io_wikipedia_processed.json")
    ap.add_argument("--via-en", type=Path, default=Path(__file__).resolve().parents[1] / "work/bilingual_via_en.json", help="Via-English bilingual pairs")
    ap.add_argument("--via-fr", type=Path, default=Path(__file__).resolve().parents[1] / "work/fr_wikt_via.json", help="Via-French bilingual pairs")
    ap.add_argument("--out", type=Path, default=Path(__file__).resolve().parents[1] / "work/bilingual_raw.json")
    ap.add_argument("-v", "--verbose", action="count", default=0)
    args = ap.parse_args(list(argv))

    configure_logging(args.verbose)
    align(args.io, args.eo, args.out, args.wiki, args.via_en, args.via_fr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))


