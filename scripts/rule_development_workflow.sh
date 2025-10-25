#!/bin/bash
# Rule Development Workflow Script
# This script provides a complete workflow for developing and testing morphological rules

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
RULES_FILE="rules/apertium-ido.ido.dix.rules"
DICTIONARY_FILE="../../apertium/apertium-ido-epo/apertium-ido.ido.dix"
MERGE_SCRIPT="scripts/merge_with_extractor.py"
TEST_SENTENCES=(
    "Me esas bona"
    "La kati esas bela"
    "Me iras a la domo"
    "La hundi esas granda"
)

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

# Function to show usage
show_usage() {
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  edit-rules     - Open rules file for editing"
    echo "  test-rules     - Test rules with sample data"
    echo "  test-translate - Test translation with sample sentences"
    echo "  build          - Build the complete dictionary"
    echo "  validate       - Validate dictionary syntax"
    echo "  full-test      - Run complete test suite"
    echo "  help           - Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 edit-rules"
    echo "  $0 test-rules"
    echo "  $0 full-test"
}

# Function to edit rules
edit_rules() {
    print_status "Opening rules file for editing: $RULES_FILE"
    
    if [ ! -f "$RULES_FILE" ]; then
        print_error "Rules file not found: $RULES_FILE"
        exit 1
    fi
    
    # Use the default editor or vim
    ${EDITOR:-vim} "$RULES_FILE"
    
    print_success "Rules file edited. Run '$0 test-rules' to test changes."
}

# Function to test rules with sample data
test_rules() {
    print_status "Testing rules with sample data..."
    
    if [ ! -f "$MERGE_SCRIPT" ]; then
        print_error "Merge script not found: $MERGE_SCRIPT"
        exit 1
    fi
    
    # Test with sample data
    python3 "$MERGE_SCRIPT" --test-mode --validate
    
    if [ $? -eq 0 ]; then
        print_success "Rules test passed!"
    else
        print_error "Rules test failed!"
        exit 1
    fi
}

# Function to test translation
test_translate() {
    print_status "Testing translation with sample sentences..."
    
    if [ ! -f "$DICTIONARY_FILE" ]; then
        print_error "Dictionary file not found: $DICTIONARY_FILE"
        print_status "Run '$0 build' first to create the dictionary"
        exit 1
    fi
    
    # Change to Apertium directory for translation testing
    cd ../../apertium/apertium-ido-epo/ || {
        print_error "Failed to change to Apertium directory"
        exit 1
    }
    
    # Test each sentence
    for sentence in "${TEST_SENTENCES[@]}"; do
        print_status "Testing: '$sentence'"
        echo "$sentence" | apertium ido-epo || {
            print_warning "Translation failed for: '$sentence'"
        }
        echo ""
    done
    
    # Return to extractor directory
    cd ../../projects/extractor/ || {
        print_error "Failed to return to extractor directory"
        exit 1
    }
    
    print_success "Translation tests completed!"
}

# Function to build dictionary
build_dictionary() {
    print_status "Building complete dictionary..."
    
    # Check if we have an extractor file
    if [ -f "extractor_output.json" ]; then
        print_status "Using extractor output file"
        python3 "$MERGE_SCRIPT" --extractor-file extractor_output.json --validate
    else
        print_status "No extractor file found, using test data"
        python3 "$MERGE_SCRIPT" --test-mode --validate
    fi
    
    if [ $? -eq 0 ]; then
        print_success "Dictionary built successfully!"
    else
        print_error "Dictionary build failed!"
        exit 1
    fi
}

# Function to validate dictionary
validate_dictionary() {
    print_status "Validating dictionary syntax..."
    
    if [ ! -f "$DICTIONARY_FILE" ]; then
        print_error "Dictionary file not found: $DICTIONARY_FILE"
        exit 1
    fi
    
    # Use xmllint for validation
    if command -v xmllint >/dev/null 2>&1; then
        xmllint --noout "$DICTIONARY_FILE" && {
            print_success "Dictionary validation passed!"
        } || {
            print_error "Dictionary validation failed!"
            exit 1
        }
    else
        print_warning "xmllint not found, skipping XML validation"
        # Basic check with Python
        python3 -c "
import xml.etree.ElementTree as ET
try:
    ET.parse('$DICTIONARY_FILE')
    print('✓ Dictionary XML is well-formed')
except ET.ParseError as e:
    print(f'✗ Dictionary XML error: {e}')
    exit(1)
"
    fi
}

# Function to run full test suite
full_test() {
    print_status "Running complete test suite..."
    
    # Test 1: Rules syntax
    print_status "Step 1: Testing rules syntax..."
    test_rules
    
    # Test 2: Build dictionary
    print_status "Step 2: Building dictionary..."
    build_dictionary
    
    # Test 3: Validate dictionary
    print_status "Step 3: Validating dictionary..."
    validate_dictionary
    
    # Test 4: Test translation
    print_status "Step 4: Testing translation..."
    test_translate
    
    print_success "All tests passed! Rules are ready for use."
}

# Main script logic
case "${1:-help}" in
    "edit-rules")
        edit_rules
        ;;
    "test-rules")
        test_rules
        ;;
    "test-translate")
        test_translate
        ;;
    "build")
        build_dictionary
        ;;
    "validate")
        validate_dictionary
        ;;
    "full-test")
        full_test
        ;;
    "help"|*)
        show_usage
        ;;
esac
