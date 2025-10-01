#!/bin/bash

# Ido-Esperanto Dictionary Extractor (Bash + wget version)
# This script downloads all Ido words with Esperanto translations from io.wiktionary.org
# Usage: ./ido_esperanto_extractor.sh [limit]

set -euo pipefail

# Configuration
BASE_URL="https://io.wiktionary.org/w/api.php"
OUTPUT_FILE="ido_esperanto_dict.json"
TEMP_DIR="./temp_ido_extraction"
LIMIT=${1:-""}

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

# Check dependencies
check_dependencies() {
    local missing_deps=()
    
    for cmd in wget jq sed grep; do
        if ! command -v "$cmd" &> /dev/null; then
            missing_deps+=("$cmd")
        fi
    done
    
    if [ ${#missing_deps[@]} -ne 0 ]; then
        error "Missing required dependencies: ${missing_deps[*]}"
        error "Please install them and try again."
        exit 1
    fi
}

# Create temporary directory
setup_temp_dir() {
    if [ -d "$TEMP_DIR" ]; then
        rm -rf "$TEMP_DIR"
    fi
    mkdir -p "$TEMP_DIR"
    log "Created temporary directory: $TEMP_DIR"
}

# Clean up temporary files
cleanup() {
    if [ -d "$TEMP_DIR" ]; then
        rm -rf "$TEMP_DIR"
        log "Cleaned up temporary directory"
    fi
}

# Set up cleanup trap
trap cleanup EXIT

# Get all pages from io.wiktionary.org
get_all_pages() {
    log "Fetching all page titles from io.wiktionary.org..."
    
    local all_pages_file="$TEMP_DIR/all_pages.txt"
    local continue_param=""
    local page_count=0
    
    > "$all_pages_file"  # Clear file
    
    while true; do
        local url="${BASE_URL}?action=query&list=allpages&aplimit=500&format=json&apnamespace=0"
        
        if [ -n "$continue_param" ]; then
            url="${url}&apcontinue=${continue_param}"
        fi
        
        local response_file="$TEMP_DIR/pages_batch.json"
        
        if ! wget -q -O "$response_file" "$url"; then
            error "Failed to fetch page list from: $url"
            return 1
        fi
        
        # Debug: check if file was created and has content
        if [ ! -f "$response_file" ] || [ ! -s "$response_file" ]; then
            error "Response file is empty or doesn't exist"
            return 1
        fi
        
        # Extract page titles and add to file
        if ! jq -r '.query.allpages[]?.title // empty' "$response_file" >> "$all_pages_file" 2>/dev/null; then
            error "Failed to parse page list response"
            cat "$response_file"
            return 1
        fi
        
        local batch_count
        batch_count=$(jq -r '.query.allpages | length' "$response_file" 2>/dev/null || echo "0")
        page_count=$((page_count + batch_count))
        
        log "Fetched $page_count page titles..."
        
        # Check if we should limit results
        if [ -n "$LIMIT" ] && [ "$page_count" -ge "$LIMIT" ]; then
            head -n "$LIMIT" "$all_pages_file" > "$TEMP_DIR/limited_pages.txt"
            mv "$TEMP_DIR/limited_pages.txt" "$all_pages_file"
            break
        fi
        
        # Check for continuation
        continue_param=$(jq -r '.continue.apcontinue // empty' "$response_file" 2>/dev/null)
        if [ -z "$continue_param" ]; then
            break
        fi
        
        sleep 0.1  # Be respectful to the server
    done
    
    local total_pages
    total_pages=$(wc -l < "$all_pages_file")
    log "Total pages to process: $total_pages"
    
    echo "$all_pages_file"
}

# Get page content
get_page_content() {
    local title="$1"
    local encoded_title
    encoded_title=$(echo "$title" | sed 's/ /_/g' | sed 's/&/%26/g')
    
    local url="${BASE_URL}?action=query&titles=${encoded_title}&prop=revisions&rvprop=content&format=json"
    local content_file="$TEMP_DIR/page_content.json"
    
    if ! wget -q -O "$content_file" "$url"; then
        return 1
    fi
    
    # Extract content
    jq -r '.query.pages | to_entries[0].value.revisions[0]["*"] // empty' "$content_file" 2>/dev/null
}

# Extract Esperanto translations from wikitext
extract_esperanto_translations() {
    local content="$1"
    
    # Look for Ido section first
    if ! echo "$content" | grep -qi "== *Ido *=="; then
        return 1
    fi
    
    # Extract Ido section
    local ido_section
    ido_section=$(echo "$content" | sed -n '/== *[Ii]do *==/,/^== /p' | sed '$d')
    
    # Look for Esperanto translations
    local translations=""
    
    # Pattern 1: * Esperanto: translation
    translations+=$(echo "$ido_section" | grep -i "^\* *esperanto:" | sed 's/^\* *[Ee]speranto: *//i' | sed 's/{{[^}]*}}//g' | sed 's/\[\[\([^]|]*\)[^]]*\]\]/\1/g')$'\n'
    
    # Pattern 2: {{t|eo|translation}}
    translations+=$(echo "$ido_section" | grep -o '{{t[^}]*|eo|[^}]*}}' | sed 's/{{t[^|]*|eo|\([^}|]*\)[^}]*}}/\1/g')$'\n'
    
    # Pattern 3: {{l|eo|translation}}
    translations+=$(echo "$ido_section" | grep -o '{{l|eo|[^}]*}}' | sed 's/{{l|eo|\([^}]*\)}}/\1/g')$'\n'
    
    # Clean up and remove empty lines
    translations=$(echo "$translations" | sed 's/^ *//; s/ *$//; /^$/d' | sort -u)
    
    if [ -n "$translations" ]; then
        echo "$translations"
        return 0
    else
        return 1
    fi
}

# Extract part of speech
extract_part_of_speech() {
    local content="$1"
    echo "$content" | grep -o "=== *\(Noun\|Verb\|Adjective\|Adverb\|Pronoun\|Preposition\|Conjunction\|Interjection\) *===" | head -1 | sed 's/=//g' | sed 's/^ *//; s/ *$//' | tr '[:upper:]' '[:lower:]'
}

# Extract definitions
extract_definitions() {
    local content="$1"
    echo "$content" | grep "^# " | head -3 | sed 's/^# //' | sed 's/{{[^}]*}}//g' | sed 's/\[\[\([^]|]*\)[^]]*\]\]/\1/g'
}

# Process a single page
process_page() {
    local title="$1"
    local content
    
    content=$(get_page_content "$title")
    if [ -z "$content" ]; then
        return 1
    fi
    
    local translations
    if ! translations=$(extract_esperanto_translations "$content"); then
        return 1
    fi
    
    # Extract additional metadata
    local pos
    pos=$(extract_part_of_speech "$content")
    
    local definitions
    definitions=$(extract_definitions "$content")
    
    # Create JSON entry
    local json_entry
    json_entry=$(cat <<EOF
{
  "ido_word": "$title",
  "esperanto_translations": [$(echo "$translations" | sed 's/.*/"&"/' | paste -sd, -)],
  "part_of_speech": ${pos:+"\"$pos\""},
  "definitions": [$(echo "$definitions" | sed 's/.*/"&"/' | paste -sd, -)],
  "source_url": "https://io.wiktionary.org/wiki/$(echo "$title" | sed 's/ /_/g')"
}
EOF
)
    
    echo "$json_entry"
}

# Main extraction function
extract_words() {
    log "Starting Ido-Esperanto dictionary extraction..."
    
    local pages_file
    pages_file=$(get_all_pages)
    
    if [ ! -f "$pages_file" ]; then
        error "Failed to get page list"
        exit 1
    fi
    
    local total_pages
    total_pages=$(wc -l < "$pages_file")
    
    local extracted_words_file="$TEMP_DIR/extracted_words.json"
    echo "[]" > "$extracted_words_file"
    
    local processed=0
    local found=0
    
    while IFS= read -r title; do
        processed=$((processed + 1))
        
        if [ $((processed % 50)) -eq 0 ]; then
            log "Processing page $processed/$total_pages: $title"
        fi
        
        local entry
        if entry=$(process_page "$title"); then
            found=$((found + 1))
            log "✓ Found Ido word with Esperanto translation: $title"
            
            # Add to JSON array
            local temp_file="$TEMP_DIR/temp.json"
            jq --argjson entry "$entry" '. += [$entry]' "$extracted_words_file" > "$temp_file"
            mv "$temp_file" "$extracted_words_file"
        fi
        
        sleep 0.1  # Be respectful to the server
        
    done < "$pages_file"
    
    # Create final output
    local final_json
    final_json=$(cat <<EOF
{
  "metadata": {
    "extraction_date": "$(date -Iseconds)",
    "source": "io.wiktionary.org",
    "total_words": $found,
    "script_version": "1.0",
    "pages_processed": $processed
  },
  "words": $(cat "$extracted_words_file")
}
EOF
)
    
    echo "$final_json" | jq '.' > "$OUTPUT_FILE"
    
    log "Extraction complete!"
    log "Total pages processed: $processed"
    log "Ido words with Esperanto translations found: $found"
    log "Results saved to: $OUTPUT_FILE"
}

# Main function
main() {
    log "Ido-Esperanto Dictionary Extractor (Bash version)"
    
    check_dependencies
    setup_temp_dir
    extract_words
}

# Run main function
main "$@"
