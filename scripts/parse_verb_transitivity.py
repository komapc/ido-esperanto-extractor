#!/usr/bin/env python3
"""Collect verb transitivity labels from the Wiktionary dumps.

Writes dist/verb_transitivity.tsv with one row per (language, verb, source):

    eo  eniri  fr  intr,tr

apertium-ido-epo/dev/gen_verb_classes.py reads the file to decide which Ido verbs
take no direct object. The labels are dropped by the translation parsers, so this
stage reads them directly:

  io.wiktionary  *Semantiko: ([[tr.]]) / ([[netr.]])
  eo.wiktionary  {{Esperanta verbo|transitiva=jes}} / netransitiva=jes
  en.wiktionary  {{lb|eo|transitive}} / intransitive / ambitransitive
  fr.wiktionary  {{t|eo}} / {{i|eo}} / {{transitif|eo}} / {{intransitif|eo}}
"""
import argparse
import logging
import re
from pathlib import Path
from typing import Iterable, Optional, Set

from wiktionary_parser import iter_pages

EN_SECTIONS = {"io": "Ido", "eo": "Esperanto"}
IS_VERB = {"io": re.compile(r"[a-z]{2,}ar$"), "eo": re.compile(r"\w{2,}i$")}


def io_labels(text: str) -> Set[str]:
    labels = set()
    for line in re.findall(r"(?mi)^\*?\s*Semantiko:.*$", text):
        if "[[netr.]]" in line:
            labels.add("intr")
        if "[[tr.]]" in line:
            labels.add("tr")
    return labels


def eo_labels(text: str) -> Set[str]:
    labels = set()
    for params in re.findall(r"\{\{Esperanta verbo\|([^{}]*)\}\}", text):
        if re.search(r"(?<![a-z])netransitiva\s*=\s*jes", params):
            labels.add("intr")
        if re.search(r"(?<![a-z])transitiva\s*=\s*jes", params):
            labels.add("tr")
    return labels


def en_labels(text: str, lang: str) -> Set[str]:
    heading = re.search(r"(?m)^==\s*%s\s*==\s*$" % EN_SECTIONS[lang], text)
    if not heading:
        return set()
    rest = text[heading.end():]
    following = re.search(r"(?m)^==[^=]", rest)
    section = rest[:following.start()] if following else rest
    labels = set()
    for params in re.findall(r"\{\{(?:lb|lbl|label|context|cx)\|%s\|([^{}]*)\}\}" % lang, section):
        parts = {p.strip().lower() for p in params.split("|")}
        if parts & {"transitive", "ambitransitive"}:
            labels.add("tr")
        if parts & {"intransitive", "ambitransitive"}:
            labels.add("intr")
    return labels


def fr_labels(text: str, lang: str) -> Set[str]:
    heading = re.search(r"\{\{langue\|%s\}\}" % lang, text)
    if not heading:
        return set()
    rest = text[heading.end():]
    following = re.search(r"==\s*\{\{langue\|", rest)
    section = rest[:following.start()] if following else rest
    labels = set()
    if re.search(r"\{\{(?:t|transitif)\|%s\s*[|}]" % lang, section):
        labels.add("tr")
    if re.search(r"\{\{(?:i|intransitif)\|%s\s*[|}]" % lang, section):
        labels.add("intr")
    return labels


def page_rows(source: str, title: str, text: str) -> Iterable[tuple]:
    if source == "io":
        found = {"io": io_labels(text)}
    elif source == "eo":
        found = {"eo": eo_labels(text)}
    elif source == "en":
        found = {lang: en_labels(text, lang) for lang in EN_SECTIONS}
    else:
        found = {lang: fr_labels(text, lang) for lang in EN_SECTIONS}
    for lang, labels in found.items():
        if labels and IS_VERB[lang].fullmatch(title):
            yield lang, title, source, ",".join(sorted(labels))


def collect(dumps: dict) -> list:
    rows = []
    for source, path in dumps.items():
        before = len(rows)
        for title, ns, text in iter_pages(path):
            if ns == "0":
                rows.extend(page_rows(source, title, text))
        logging.info("%s: %d labelled verbs", source, len(rows) - before)
    return sorted(rows)


def main(argv: Optional[list] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    raw = Path("data/raw")
    for source in ("io", "eo", "en", "fr"):
        ap.add_argument(f"--{source}", type=Path,
                        default=raw / f"{source}wiktionary-latest-pages-articles.xml.bz2")
    ap.add_argument("--out", type=Path, default=Path("dist/verb_transitivity.tsv"))
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    rows = collect({s: getattr(args, s) for s in ("io", "eo", "en", "fr")})
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("".join("\t".join(r) + "\n" for r in rows), encoding="utf-8")
    logging.info("Wrote %d rows to %s", len(rows), args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
