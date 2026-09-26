#!/usr/bin/env bash
set -euo pipefail

# Downloads the Wikimedia dumps the pipeline reads into data/raw/.
#
# Each file is fetched only when the server copy is newer than the local one
# (curl -z), into a .part file that is integrity-checked before it atomically
# replaces the old dump. No resume (`wget -c`): "latest" is a moving target,
# and resuming a partial file against a newer dump silently splices two
# different files together.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RAW_DIR="${ROOT_DIR}/data/raw"
mkdir -p "${RAW_DIR}"

BASE="https://dumps.wikimedia.org"
declare -a URLS=(
  "${BASE}/iowiktionary/latest/iowiktionary-latest-pages-articles.xml.bz2"
  "${BASE}/eowiktionary/latest/eowiktionary-latest-pages-articles.xml.bz2"
  "${BASE}/frwiktionary/latest/frwiktionary-latest-pages-articles.xml.bz2"
  "${BASE}/enwiktionary/latest/enwiktionary-latest-pages-articles.xml.bz2"   # stage wiktionary_en
  "${BASE}/iowiki/latest/iowiki-latest-pages-articles.xml.bz2"
  "${BASE}/iowiki/latest/iowiki-latest-langlinks.sql.gz"
  "${BASE}/iowiki/latest/iowiki-latest-page_props.sql.gz"                   # stage wikidata_labels
  "${BASE}/eowiki/latest/eowiki-latest-langlinks.sql.gz"                    # stage eowiki_langlinks
  "${BASE}/eowiki/latest/eowiki-latest-page.sql.gz"                         # stage eowiki_langlinks
)

verify() {
  case "$1" in
    *.bz2) bzip2 -tq "$1" ;;
    *.gz)  gzip -tq "$1" ;;
    *)     true ;;
  esac
}

echo "Downloading dumps to ${RAW_DIR}..."
for url in "${URLS[@]}"; do
  name="$(basename "${url}")"
  dest="${RAW_DIR}/${name}"
  part="${dest}.part"
  echo "-- ${name}"
  rm -f "${part}"
  zflag=()
  [ -f "${dest}" ] && zflag=(-z "${dest}")
  # -R keeps the server mtime so the next -z comparison is meaningful.
  curl -fSL --retry 3 -R "${zflag[@]}" -o "${part}" "${url}"
  if [ ! -s "${part}" ]; then
    # -z matched: server copy is not newer, nothing written.
    rm -f "${part}"
    echo "   up to date"
    continue
  fi
  if ! verify "${part}"; then
    rm -f "${part}"
    echo "   ERROR: ${name} failed integrity check; kept the previous copy" >&2
    exit 1
  fi
  mv -f "${part}" "${dest}"
  echo "   updated"
done

echo "Computing SHA256 sums..."
(
  cd "${RAW_DIR}" >/dev/null
  sha256sum -- *-latest-*.bz2 *-latest-*.gz 2>/dev/null || true
) > "${RAW_DIR}/SHA256SUMS.txt"

echo "Done. Files in ${RAW_DIR}:"
ls -lh "${RAW_DIR}"
