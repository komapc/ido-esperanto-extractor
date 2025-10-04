#!/bin/bash

# Ido-Esperanto Dictionary Extraction Automation Script
# This script automates the entire workflow:
# 1. Download dump files
# 2. Extract Ido→Esperanto dictionary
# 3. Extract Esperanto→Ido dictionary  
# 4. Merge both dictionaries into a unified bidirectional dictionary

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_DIR="${SCRIPT_DIR}/data"
OUTPUT_DIR="${SCRIPT_DIR}"
PYTHON_SCRIPT="ido_esperanto_extractor.py"
MERGE_SCRIPT="merge_dictionaries.py"

# Dump file URLs and names
IDO_DUMP_URL="https://dumps.wikimedia.org/iowiktionary/latest/iowiktionary-latest-pages-articles.xml.bz2"
IDO_DUMP_FILE="iowiktionary-latest-pages-articles.xml.bz2"
EO_DUMP_URL="https://dumps.wikimedia.org/eowiktionary/latest/eowiktionary-latest-pages-articles.xml.bz2"
EO_DUMP_FILE="eowiktionary-latest-pages-articles.xml.bz2"

# Output file names
IDO_EO_DICT="dictionary_io_eo.json"
EO_IO_DICT="dictionary_eo_io.json"
IDO_EO_FAILED="failed_items_io_eo.json"
EO_IO_FAILED="failed_items_eo_io.json"
MERGED_DICT="dictionary_merged.json"

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to check if a file exists
file_exists() {
    [ -f "$1" ]
}

# Function to get file size in MB
get_file_size_mb() {
    if file_exists "$1"; then
        du -m "$1" | cut -f1
    else
        echo "0"
    fi
}

# Function to download a file with progress
download_file() {
    local url="$1"
    local output="$2"
    local description="$3"
    
    print_status "Downloading $description..."
    print_status "URL: $url"
    print_status "Output: $output"
    
    if command_exists wget; then
        wget --progress=bar:force -O "$output" "$url"
    elif command_exists curl; then
        curl -L --progress-bar -o "$output" "$url"
    else
        print_error "Neither wget nor curl is available. Please install one of them."
        exit 1
    fi
    
    if [ $? -eq 0 ]; then
        local size=$(get_file_size_mb "$output")
        print_success "Downloaded $description (${size} MB)"
    else
        print_error "Failed to download $description"
        exit 1
    fi
}

# Function to create data directory
create_data_dir() {
    if [ ! -d "$DATA_DIR" ]; then
        print_status "Creating data directory: $DATA_DIR"
        mkdir -p "$DATA_DIR"
    fi
}

# Function to check if dump file is needed
needs_download() {
    local file="$1"
    local min_size_mb="$2"
    
    if ! file_exists "$file"; then
        return 0  # File doesn't exist, needs download
    fi
    
    local size=$(get_file_size_mb "$file")
    if [ "$size" -lt "$min_size_mb" ]; then
        print_warning "File $file exists but is too small (${size} MB < ${min_size_mb} MB)"
        return 0  # File too small, needs download
    fi
    
    return 1  # File exists and is large enough
}

# Function to run dictionary extraction
extract_dictionary() {
    local language_pair="$1"
    local dump_file="$2"
    local description="$3"
    
    print_status "Extracting $description dictionary..."
    
    local start_time=$(date +%s)
    
    if [ "$language_pair" = "ido-esperanto" ]; then
        python3 "$PYTHON_SCRIPT" --language-pair "$language_pair" --dump "$dump_file"
    else
        python3 "$PYTHON_SCRIPT" --language-pair "$language_pair"
    fi
    
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    local minutes=$((duration / 60))
    local seconds=$((duration % 60))
    
    if [ $? -eq 0 ]; then
        print_success "$description extraction completed in ${minutes}m ${seconds}s"
    else
        print_error "$description extraction failed"
        exit 1
    fi
}

# Function to merge dictionaries
merge_dictionaries() {
    print_status "Merging dictionaries..."
    
    local start_time=$(date +%s)
    
    python3 "$MERGE_SCRIPT" --output "$MERGED_DICT"
    
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    local seconds=$((duration % 60))
    
    if [ $? -eq 0 ]; then
        print_success "Dictionary merge completed in ${seconds}s"
    else
        print_error "Dictionary merge failed"
        exit 1
    fi
}

# Function to display final statistics
show_final_stats() {
    print_status "Final Statistics:"
    echo "=================="
    
    # File sizes
    if file_exists "$IDO_EO_DICT"; then
        local size=$(get_file_size_mb "$IDO_EO_DICT")
        echo "📚 Ido→Esperanto dictionary: $IDO_EO_DICT (${size} MB)"
    fi
    
    if file_exists "$EO_IO_DICT"; then
        local size=$(get_file_size_mb "$EO_IO_DICT")
        echo "📚 Esperanto→Ido dictionary: $EO_IO_DICT (${size} MB)"
    fi
    
    if file_exists "$MERGED_DICT"; then
        local size=$(get_file_size_mb "$MERGED_DICT")
        echo "📚 Merged bidirectional dictionary: $MERGED_DICT (${size} MB)"
    fi
    
    if file_exists "$IDO_EO_FAILED"; then
        local size=$(get_file_size_mb "$IDO_EO_FAILED")
        echo "❌ Failed Ido→Esperanto items: $IDO_EO_FAILED (${size} MB)"
    fi
    
    if file_exists "$EO_IO_FAILED"; then
        local size=$(get_file_size_mb "$EO_IO_FAILED")
        echo "❌ Failed Esperanto→Ido items: $EO_IO_FAILED (${size} MB)"
    fi
    
    echo ""
    print_success "All dictionaries created successfully! 🎉"
}

# Main execution
main() {
    echo "🔄 Ido-Esperanto Dictionary Extraction Automation"
    echo "=================================================="
    echo ""
    
    # Check prerequisites
    print_status "Checking prerequisites..."
    
    if ! command_exists python3; then
        print_error "Python 3 is required but not installed"
        exit 1
    fi
    
    if ! file_exists "$PYTHON_SCRIPT"; then
        print_error "Extraction script not found: $PYTHON_SCRIPT"
        exit 1
    fi
    
    if ! file_exists "$MERGE_SCRIPT"; then
        print_error "Merge script not found: $MERGE_SCRIPT"
        exit 1
    fi
    
    print_success "Prerequisites check passed"
    echo ""
    
    # Create data directory
    create_data_dir
    
    # Download dump files if needed
    print_status "Checking dump files..."
    
    local ido_dump_path="$DATA_DIR/$IDO_DUMP_FILE"
    local eo_dump_path="$EO_DUMP_FILE"
    
    if needs_download "$ido_dump_path" 25; then
        download_file "$IDO_DUMP_URL" "$ido_dump_path" "Ido Wiktionary dump"
    else
        local size=$(get_file_size_mb "$ido_dump_path")
        print_success "Ido dump file already exists: $ido_dump_path (${size} MB)"
    fi
    
    if needs_download "$eo_dump_path" 15; then
        download_file "$EO_DUMP_URL" "$eo_dump_path" "Esperanto Wiktionary dump"
    else
        local size=$(get_file_size_mb "$eo_dump_path")
        print_success "Esperanto dump file already exists: $eo_dump_path (${size} MB)"
    fi
    
    echo ""
    
    # Extract Ido→Esperanto dictionary
    extract_dictionary "ido-esperanto" "$ido_dump_path" "Ido→Esperanto"
    echo ""
    
    # Extract Esperanto→Ido dictionary
    extract_dictionary "esperanto-ido" "$eo_dump_path" "Esperanto→Ido"
    echo ""
    
    # Merge dictionaries
    merge_dictionaries
    echo ""
    
    # Show final statistics
    show_final_stats
    
    echo ""
    print_status "Workflow completed successfully! ✅"
}

# Parse command line arguments
FORCE_DOWNLOAD=false
SKIP_EXTRACTION=false
SKIP_MERGE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --force-download)
            FORCE_DOWNLOAD=true
            shift
            ;;
        --skip-extraction)
            SKIP_EXTRACTION=true
            shift
            ;;
        --skip-merge)
            SKIP_MERGE=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --force-download    Force re-download of dump files"
            echo "  --skip-extraction   Skip dictionary extraction (only merge)"
            echo "  --skip-merge        Skip dictionary merging"
            echo "  --help, -h          Show this help message"
            echo ""
            echo "This script will:"
            echo "  1. Download Wiktionary dump files (if needed)"
            echo "  2. Extract Ido→Esperanto dictionary"
            echo "  3. Extract Esperanto→Ido dictionary"
            echo "  4. Merge both dictionaries into a unified bidirectional dictionary"
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Run main function
main
