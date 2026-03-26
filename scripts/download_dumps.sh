#!/usr/bin/env bash
set -euo pipefail

# Downloads latest dumps for Ido/Esperanto Wiktionary and Ido Wikipedia.
# Outputs are stored under data/raw/.
#
# TODO: Add English Wiktionary as a translation source (like French Wiktionary).
#   enwiktionary has dense Ido coverage via {{io}} language sections.
#   Requires a new 05_parse_en_wiktionary.py following the pattern of
#   03_parse_fr_wiktionary.py, plus a new entry in config.json sources.
#   The dump is large (~1.5 GB); use --limit during development.
#   Once the parser exists, uncomment the enwiktionary URL below.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RAW_DIR="${ROOT_DIR}/data/raw"
mkdir -p "${RAW_DIR}"

declare -a URLS=(
  "https://dumps.wikimedia.org/iowiktionary/latest/iowiktionary-latest-pages-articles.xml.bz2"
  "https://dumps.wikimedia.org/eowiktionary/latest/eowiktionary-latest-pages-articles.xml.bz2"
  # TODO: uncomment when 05_parse_en_wiktionary.py exists
  # "https://dumps.wikimedia.org/enwiktionary/latest/enwiktionary-latest-pages-articles.xml.bz2"
  "https://dumps.wikimedia.org/frwiktionary/latest/frwiktionary-latest-pages-articles.xml.bz2"
  "https://dumps.wikimedia.org/iowiki/latest/iowiki-latest-pages-articles.xml.bz2"
  "https://dumps.wikimedia.org/iowiki/latest/iowiki-latest-langlinks.sql.gz"
)

echo "Downloading dumps to ${RAW_DIR}..."
for url in "${URLS[@]}"; do
  echo "-- ${url}"
  wget -c -P "${RAW_DIR}" "${url}"
done

echo "Computing SHA256 sums..."
(
  cd "${RAW_DIR}" >/dev/null
  sha256sum *.bz2 *.gz 2>/dev/null || true
) > "${RAW_DIR}/SHA256SUMS.txt"

echo "Done. Files in ${RAW_DIR}:"
ls -lh "${RAW_DIR}"




