import bz2
import gzip
import hashlib
import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None  # type: ignore


DEFAULT_JSON_INDENT = 2


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def configure_logging(verbosity: int = 0) -> None:
    level = logging.DEBUG if verbosity > 0 else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(message)s")


def open_maybe_compressed(path: Path, mode: str = "rt", encoding: str = "utf-8"):
    suffix = path.suffix.lower()
    if suffix == ".gz":
        return gzip.open(path, mode, encoding=encoding)  # type: ignore[arg-type]
    if suffix == ".bz2":
        return bz2.open(path, mode, encoding=encoding)  # type: ignore[arg-type]
    return open(path, mode, encoding=encoding)


def compute_sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with open_maybe_compressed(path, mode="rb") as fh:  # type: ignore[arg-type]
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def read_json(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def write_json(path: Path, data: Any) -> None:
    ensure_dir(path.parent)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=DEFAULT_JSON_INDENT)


def read_yaml(path: Path) -> Any:
    if yaml is None:
        raise RuntimeError("pyyaml is required to read YAML files. Please install pyyaml.")
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def write_yaml(path: Path, data: Any) -> None:
    if yaml is None:
        raise RuntimeError("pyyaml is required to write YAML files. Please install pyyaml.")
    ensure_dir(path.parent)
    with open(path, "w", encoding="utf-8") as fh:
        yaml.safe_dump(data, fh, sort_keys=False, allow_unicode=True)


def load_text(path: Path) -> str:
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def save_text(path: Path, text: str) -> None:
    ensure_dir(path.parent)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def clean_lemma(lemma: str) -> str:
    """Clean Wiktionary markup from lemmas while preserving actual content.
    
    Handles:
    - Bold/italic markup: '''text''' → text
    - Wiki links: [[text]] or [[link|text]] → text
    - Templates: {{template|param}} → extracted content
    - Language codes: word (io) → word
    - Numbered definitions: '''1.''' word → word
    - Gender symbols: (''♀'') → (empty, should skip entry)
    - Markup artifacts
    
    Returns cleaned lemma or empty string if unusable.
    """
    if not lemma:
        return ""
    
    original = lemma
    
    # 1. BOLD/ITALIC: Remove bold/italic markup (''', '', etc.)
    #    Just strip the quotes, keep the content
    lemma = re.sub(r"'{2,}", "", lemma)
    
    # 2. WIKILINKS: Clean wiki links [[...]]
    #    [[word]] → word
    #    [[link|display]] → display (the part after |)
    lemma = re.sub(r"\[\[([^|\]]+)\|([^\]]+)\]\]", r"\2", lemma)  # [[link|text]] → text
    lemma = re.sub(r"\[\[([^\]]+)\]\]", r"\1", lemma)  # [[word]] → word
    
    # 3. TEMPLATES: Handle common template types {{...}}
    #    Language codes: {{io}}, {{eo}}, {{en}} etc. → remove entirely
    #    Translation: {{tr|io|word}} → extract word
    #    General: {{template|param}} → extract param or remove
    
    # Remove language code templates (standalone)
    lemma = re.sub(r"\{\{[a-z]{2,3}\}\}", "", lemma)
    
    # Extract content from translation templates: {{tr|lang|word}} → word
    lemma = re.sub(r"\{\{tr\|[^|]+\|([^}]+)\}\}", r"\1", lemma)
    
    # Extract content from parameterized templates: {{template|content}} → content
    lemma = re.sub(r"\{\{[^|]+\|([^}]+)\}\}", r"\1", lemma)
    
    # Remove remaining simple templates: {{template}} → (removed)
    lemma = re.sub(r"\{\{[^}]+\}\}", "", lemma)
    
    # Clean up any leftover brackets
    lemma = re.sub(r"[\{\}\[\]]", "", lemma)
    
    # 4. OTHER CLEANING
    # Remove numbered definitions at start (e.g., "1. word" or "'''1.''' word")
    lemma = re.sub(r"^'{0,3}\s*\d+\.'{0,3}\s*", "", lemma)
    
    # Remove language codes in parentheses at end (e.g., "word (io)")
    lemma = re.sub(r"\s*\([a-z]{2,3}\)\s*$", "", lemma, flags=re.IGNORECASE)
    
    # Remove gender symbols (♀, ♂) - if this is ALL that's left, return empty
    lemma = re.sub(r"^\s*\(['']*[♀♂]['']*\)\s*$", "", lemma)
    lemma = re.sub(r"\s*\(['']*[♀♂]['']*\)\s*", " ", lemma)
    
    # Remove remaining parenthetical wiki markup like (''...)
    lemma = re.sub(r"\(['']+\)", "", lemma)
    
    # Strip whitespace and common punctuation artifacts
    lemma = lemma.strip(" \t\n\r\f\v:;,.–-|'\"")
    
    # Normalize multiple spaces
    lemma = re.sub(r"\s+", " ", lemma)
    
    # Log if significant cleaning happened (for debugging)
    if lemma != original and len(original) > 0:
        if lemma == "":
            logging.debug(f"Cleaned lemma to empty: '{original}'")
        elif len(original) - len(lemma) > 5:
            logging.debug(f"Cleaned lemma: '{original}' → '{lemma}'")
    
    return lemma


def is_valid_lemma(lemma: str) -> bool:
    """Check if cleaned lemma is a valid dictionary word.
    
    Rejects:
    - Empty or too short
    - Starts with special chars (markup remnants)
    - Contains unresolved markup
    - Obvious titles/phrases (very long with colons)
    """
    if not lemma or len(lemma) < 2:
        return False
    
    # Reject if starts with special chars (markup remnants)
    if lemma[0] in "'''([{%#*<>":
        return False
    
    # Reject if contains unresolved markup
    if any(x in lemma for x in ["'''", "''", "[[", "]]", "{{", "}}","<", ">"]):
        return False
    
    # Reject obvious song/book titles (have colons and are long)
    if ":" in lemma and len(lemma) > 30:
        return False
    
    # Reject if entirely non-alphabetic (except allowed chars like - and space)
    if not any(c.isalpha() for c in lemma):
        return False
    
    return True




