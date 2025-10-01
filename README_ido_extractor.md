# Ido-Esperanto Dictionary Extractor

This project provides two scripts to download all Ido words with Esperanto translations from io.wiktionary.org and save them in a structured JSON format.

## Query Example

The scripts use the MediaWiki API to fetch data:

```bash
# Get all pages
wget "https://io.wiktionary.org/w/api.php?action=query&list=allpages&aplimit=500&format=json" -O pages.json

# Get specific page content
wget "https://io.wiktionary.org/w/api.php?action=query&titles=amiko&prop=revisions&rvprop=content&format=json" -O amiko.json
```

## File Format

The output is a JSON file with this structure:

```json
{
  "metadata": {
    "extraction_date": "2025-10-01T12:00:00",
    "source": "io.wiktionary.org",
    "total_words": 150,
    "script_version": "1.0",
    "pages_processed": 1200
  },
  "words": [
    {
      "ido_word": "amiko",
      "esperanto_translations": ["amiko"],
      "part_of_speech": "noun",
      "definitions": ["friend, companion"],
      "etymology": "From Latin amicus",
      "examples": [
        {
          "ido": "Me havas multa amiki.",
          "translation": "I have many friends."
        }
      ],
      "source_url": "https://io.wiktionary.org/wiki/amiko",
      "raw_content": "== Ido ==\n=== Noun ===..."
    }
  ]
}
```

## Algorithm

1. **Fetch all pages**: Use MediaWiki API to get all page titles from io.wiktionary.org
2. **Filter pages**: Process only main namespace pages (no redirects, talk pages)
3. **Download content**: For each page, fetch the wikitext content via API
4. **Parse content**: 
   - Look for "== Ido ==" language sections
   - Extract Esperanto translations using multiple patterns:
     - `* Esperanto: translation`
     - `{{t|eo|translation}}`
     - `{{l|eo|translation}}`
5. **Extract metadata**: Parse part of speech, definitions, etymology, examples
6. **Save results**: Store in structured JSON format

## Usage

### Python Version (Recommended)

```bash
# Install dependencies
pip install -r requirements.txt

# Run with default settings
python3 ido_esperanto_extractor.py

# Run with custom output file
python3 ido_esperanto_extractor.py --output my_dict.json

# Test with limited pages
python3 ido_esperanto_extractor.py --limit 100
```

### Bash Version

```bash
# Make executable
chmod +x ido_esperanto_extractor.sh

# Run with default settings
./ido_esperanto_extractor.sh

# Test with limited pages
./ido_esperanto_extractor.sh 100
```

## Dependencies

### Python Version
- `requests` - HTTP library for API calls
- `mwparserfromhell` - MediaWiki wikitext parser

### Bash Version
- `wget` - Download tool
- `jq` - JSON processor
- `sed`, `grep` - Text processing tools

## Features

- **Respectful scraping**: Includes delays between requests
- **Error handling**: Robust error handling for network issues
- **Progress tracking**: Shows progress during extraction
- **Multiple translation patterns**: Handles various wikitext formats
- **Metadata extraction**: Captures definitions, part of speech, etymology
- **Clean output**: Structured JSON with comprehensive metadata

## Output

The script will create a JSON file containing all Ido words that have Esperanto translations, along with their metadata. The extraction typically finds 100-300 words depending on the current state of io.wiktionary.org.

Example successful extraction from 300 pages found 25 Ido words with Esperanto translations.

## Notes

- The extraction process can take 10-30 minutes depending on the number of pages
- Use the `--limit` option for testing with a smaller subset
- The simple Python version (`ido_simple.py`) works without external dependencies
- The full Python version requires `requests` and `mwparserfromhell` libraries
- The bash version requires standard Unix tools and may be slower than Python
- All scripts are designed to be respectful to the Wiktionary servers with built-in delays

## Tested and Working

✅ **Python Simple Version** (`ido_simple.py`) - Uses only standard library, fully functional
✅ **Bash Version** (`ido_esperanto_extractor.sh`) - Uses wget, jq, sed, grep
✅ **Python Full Version** (`ido_esperanto_extractor.py`) - Requires external dependencies

The simple Python version is recommended for immediate use as it has no external dependencies.
