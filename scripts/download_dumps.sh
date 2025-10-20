#!/usr/bin/env bash
set -euo pipefail

# Downloads latest dumps for Ido/Esperanto Wiktionary and Ido Wikipedia.
# Outputs are stored under data/raw/.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RAW_DIR="${ROOT_DIR}/data/raw"
mkdir -p "${RAW_DIR}"

declare -a URLS=(
  "https://dumps.wikimedia.org/iowiktionary/latest/iowiktionary-latest-pages-articles.xml.bz2"
  "https://dumps.wikimedia.org/eowiktionary/latest/eowiktionary-latest-pages-articles.xml.bz2"
  "https://dumps.wikimedia.org/enwiktionary/latest/enwiktionary-latest-pages-articles.xml.bz2"
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




