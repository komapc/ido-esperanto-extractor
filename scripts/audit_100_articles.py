#!/usr/bin/env python3
"""
Translate 100 largest Ido Wikipedia articles through apertium ido-epo,
collect all unknown/failed tokens, group by error type, ignore proper nouns.

Usage: python3 audit_100_articles.py
"""
import bz2
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict

DUMP = "data/raw/iowiki-latest-pages-articles.xml.bz2"
APERTIUM_DIR = "/home/mark/projects/apertium-dev/apertium-ido-epo"
PAIR = "ido-epo"
N_ARTICLES = 100
MIN_WORDS = 200   # skip stubs

# Wikitext cleanup
_RE_TEMPLATE = re.compile(r'\{\{[^}]*\}\}')
_RE_LINK = re.compile(r'\[\[(?:[^|\]]*\|)?([^\]]*)\]\]')
_RE_HTML = re.compile(r'<[^>]+>')
_RE_HEADING = re.compile(r'==+[^=]+=+')
_RE_REF = re.compile(r'<ref[^/]*/?>.*?</ref>', re.DOTALL)
_RE_TABLE = re.compile(r'\{\|.*?\|\}', re.DOTALL)
_RE_MULTI_NL = re.compile(r'\n{3,}')

def clean_wikitext(raw):
    t = _RE_TABLE.sub('', raw)
    t = _RE_REF.sub('', t)
    t = _RE_TEMPLATE.sub('', t)
    t = _RE_LINK.sub(r'\1', t)
    t = _RE_HTML.sub('', t)
    t = _RE_HEADING.sub('', t)
    t = re.sub(r"'{2,}", '', t)
    t = re.sub(r'\[\[File:[^\]]*\]\]', '', t, flags=re.IGNORECASE)
    t = re.sub(r'\[\[Image:[^\]]*\]\]', '', t, flags=re.IGNORECASE)
    t = re.sub(r'\[\[Imajo:[^\]]*\]\]', '', t, flags=re.IGNORECASE)
    t = re.sub(r'^\*.*$', '', t, flags=re.MULTILINE)
    t = re.sub(r'^\|.*$', '', t, flags=re.MULTILINE)
    t = re.sub(r'^\!.*$', '', t, flags=re.MULTILINE)
    t = _RE_MULTI_NL.sub('\n\n', t)
    return t.strip()


def iter_articles(path, min_words, limit):
    """Yield (title, text) for the `limit` largest mainspace articles."""
    candidates = []
    ns = '{http://www.mediawiki.org/xml/DTD/Special/Export-0.10/}'
    with bz2.open(path, 'rb') as f:
        for event, elem in ET.iterparse(f, events=['end']):
            tag = elem.tag.split('}')[-1]
            if tag != 'page':
                continue
            ns_val = elem.find('.//{*}ns')
            if ns_val is None or ns_val.text != '0':
                elem.clear()
                continue
            title_el = elem.find('.//{*}title')
            text_el = elem.find('.//{*}revision/{*}text')
            title = title_el.text if title_el is not None else ''
            raw = text_el.text if text_el is not None and text_el.text else ''
            elem.clear()

            # Skip redirects
            if raw.strip().lower().startswith('#redirect') or raw.strip().lower().startswith('#alidirektilo'):
                continue
            text = clean_wikitext(raw)
            words = len(text.split())
            if words >= min_words:
                candidates.append((words, title, text))

    candidates.sort(reverse=True)
    return [(t, tx) for _, t, tx in candidates[:limit]]


def translate_text(text, apertium_dir, pair):
    """Run text through apertium, return raw output."""
    result = subprocess.run(
        ['apertium', '-d', apertium_dir, pair],
        input=text, capture_output=True, text=True, timeout=60
    )
    return result.stdout


# Patterns for apertium failure tokens
_RE_UNKNOWN = re.compile(r'\*([a-zA-ZĈĉĜĝĤĥĴĵŜŝŬŭÀ-ÿ]+)')   # *word = unknown
_RE_AT = re.compile(r'@([a-zA-ZĈĉĜĝĤĥĴĵŜŝŬŭÀ-ÿ]+)')            # @word = no transfer

# Proper noun heuristic: starts with uppercase AND appears as a Wikipedia title
# We also flag CamelCase and all-caps as likely proper nouns.
_RE_PROPN = re.compile(r'^[A-ZĈĜĤĴŜŬ]')  # starts uppercase


def is_proper_noun(token, propn_set):
    """True if token looks like a proper noun."""
    if token in propn_set:
        return True
    if _RE_PROPN.match(token):
        return True
    return False


def classify_ido_word(word):
    """Return morphological category of an Ido lemma by its ending."""
    w = word.lower()
    if w.endswith('ar') or w.endswith('ir') or w.endswith('or'):
        return 'verb (inf)'
    if w.endswith('o'):
        return 'noun (-o)'
    if w.endswith('a'):
        return 'adj (-a)'
    if w.endswith('e'):
        return 'adv (-e)'
    if w.endswith('os') or w.endswith('as') or w.endswith('is') or w.endswith('us') or w.endswith('ez'):
        return 'verb (conjugated)'
    if w.endswith('anta') or w.endswith('inta') or w.endswith('onta'):
        return 'participle (-anta/-inta/-onta)'
    if w.endswith('ata') or w.endswith('ita') or w.endswith('ota'):
        return 'participle (-ata/-ita/-ota)'
    if w.endswith('ado') or w.endswith('uro') or w.endswith('eso'):
        return 'derived noun (-ado/-uro/-eso)'
    return 'other'


def main():
    print(f"Loading Wikipedia dump…", flush=True)
    articles = iter_articles(DUMP, MIN_WORDS, N_ARTICLES)
    print(f"Selected {len(articles)} articles", flush=True)

    # Build propn set from article titles
    propn_set = {t.split('(')[0].strip() for t, _ in articles}
    # Also add words that are all-caps or title-case sequences
    propn_set.update(t for t in propn_set if _RE_PROPN.match(t))

    # Counters
    star_tokens = defaultdict(int)    # *word unknowns (no analysis)
    at_tokens = defaultdict(int)      # @word (analysis but no transfer)
    article_counts = []

    total_words = 0
    for i, (title, text) in enumerate(articles, 1):
        words = len(text.split())
        total_words += words
        print(f"  [{i:3}/{N_ARTICLES}] {title[:55]:<55} ({words:,} words)", flush=True)

        translated = translate_text(text, APERTIUM_DIR, PAIR)

        stars = _RE_UNKNOWN.findall(translated)
        ats = _RE_AT.findall(translated)

        star_here = defaultdict(int)
        at_here = defaultdict(int)

        for tok in stars:
            if not is_proper_noun(tok, propn_set):
                star_tokens[tok] += 1
                star_here[tok] += 1
        for tok in ats:
            if not is_proper_noun(tok, propn_set):
                at_tokens[tok] += 1
                at_here[tok] += 1

        article_counts.append((title, words, len(star_here), len(at_here)))

    print(f"\n{'='*70}")
    print(f"AUDIT COMPLETE — {N_ARTICLES} articles, {total_words:,} total words")
    print(f"{'='*70}\n")

    # ── UNKNOWN WORDS (*word) ──────────────────────────────────────────────
    print(f"## UNKNOWN WORDS (*word) — {len(star_tokens)} distinct types\n")
    print(f"(no morphological analysis; word absent from monodix)\n")

    # Group by morphological category
    by_cat = defaultdict(list)
    for word, cnt in star_tokens.items():
        cat = classify_ido_word(word)
        by_cat[cat].append((cnt, word))

    for cat in sorted(by_cat):
        items = sorted(by_cat[cat], reverse=True)
        total_cat = sum(c for c, _ in items)
        print(f"### {cat}  ({len(items)} types, {total_cat} occurrences)")
        for cnt, word in items[:30]:
            print(f"  {word:<25} ×{cnt}")
        if len(items) > 30:
            print(f"  … and {len(items)-30} more")
        print()

    # ── TRANSFER FAILURES (@word) ──────────────────────────────────────────
    print(f"\n## TRANSFER FAILURES (@word) — {len(at_tokens)} distinct types\n")
    print(f"(word analyzed by lt-proc but no Esperanto translation in bidix)\n")

    by_cat2 = defaultdict(list)
    for word, cnt in at_tokens.items():
        cat = classify_ido_word(word)
        by_cat2[cat].append((cnt, word))

    for cat in sorted(by_cat2):
        items = sorted(by_cat2[cat], reverse=True)
        total_cat = sum(c for c, _ in items)
        print(f"### {cat}  ({len(items)} types, {total_cat} occurrences)")
        for cnt, word in items[:30]:
            print(f"  {word:<25} ×{cnt}")
        if len(items) > 30:
            print(f"  … and {len(items)-30} more")
        print()

    # ── TOP ARTICLES BY ERROR RATE ─────────────────────────────────────────
    print(f"\n## TOP ARTICLES BY ERROR COUNT\n")
    article_counts.sort(key=lambda x: x[2]+x[3], reverse=True)
    print(f"{'Title':<55} {'Words':>6} {'*':>5} {'@':>5}")
    print('-'*75)
    for title, words, stars, ats in article_counts[:20]:
        print(f"{title[:55]:<55} {words:>6,} {stars:>5} {ats:>5}")

    # ── SUMMARY ───────────────────────────────────────────────────────────
    print(f"\n## SUMMARY")
    total_star = sum(star_tokens.values())
    total_at   = sum(at_tokens.values())
    print(f"  Unknown (*): {len(star_tokens):4} types, {total_star:6} occurrences")
    print(f"  No-xfer (@): {len(at_tokens):4} types, {total_at:6} occurrences")
    print(f"  Total words: {total_words:,}")
    if total_words:
        err_rate = (total_star + total_at) / total_words * 100
        print(f"  Error rate:  {err_rate:.2f}%")


if __name__ == '__main__':
    main()
