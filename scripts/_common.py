import bz2
import gzip
import hashlib
import json
import logging
import os
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


