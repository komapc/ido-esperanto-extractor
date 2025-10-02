# Ido-Esperanto Dictionary Extractor

This tool extracts Ido words with Esperanto translations from the io.wiktionary.org dump file using robust XML parsing and intelligent filtering.

## Features

- **Robust XML parsing**: Proper handling of MediaWiki dump format
- **Intelligent filtering**: Removes invalid entries, suffixes, and radicals
- **Multiple meaning parsing**: Properly splits entries with multiple Esperanto translations
- **Part of speech extraction**: Identifies grammatical categories when available
- **Clean translations**: Removes wiki markup, categories, and artifacts
- **Memory efficient**: Streams processing for large dumps
- **Comprehensive statistics**: Detailed extraction metrics

## Usage

### Basic Usage

```bash
# Run with default settings (processes entire dump)
python3 ido_esperanto_extractor.py

# Limit processing for testing
python3 ido_esperanto_extractor.py --limit 1000

# Specify output file
python3 ido_esperanto_extractor.py --output my_dict.json
```

### Download Dump

```bash
# Download the latest dump (if not present)
python3 ido_esperanto_extractor.py --download

# Force re-download
python3 ido_esperanto_extractor.py --force-download
```

## Output Format

The tool generates a JSON file with this structure:

```json
{
  "metadata": {
    "extraction_date": "2025-10-02T09:55:00.630828",
    "total_words": 489,
    "script_version": "v2.0",
    "stats": {
      "pages_processed": 10001,
      "pages_with_ido_section": 630,
      "valid_entries_found": 489,
      "entries_with_pos": 0,
      "entries_with_multiple_meanings": 62,
      "skipped_by_category": 726,
      "skipped_by_title": 168,
      "skipped_no_translations": 141
    }
  },
  "words": [
    {
      "ido_word": "finar",
      "esperanto_translations": ["finiĝi", "fini"],
      "part_of_speech": null
    },
    {
      "ido_word": "kavalo", 
      "esperanto_translations": ["ĉevalo"],
      "part_of_speech": null
    }
  ]
}
```

## Key Improvements in v2.0

### 1. **Multiple Meaning Parsing**
- Properly splits entries with multiple Esperanto translations
- Handles numbered meanings: `(1) finiĝi; (2) fini` → `["finiĝi", "fini"]`
- Handles semicolon-separated meanings: `kanti; ĉirpi` → `["kanti", "ĉirpi"]`

### 2. **Part of Speech Extraction**
- Identifies grammatical categories when available in wikitext
- Maps Ido terms to English equivalents (substantivo → noun)

### 3. **Cleaner Output Format**
- Removed unnecessary fields (`source`, `extraction_method`)
- Focused on essential data: word, translations, part of speech
- Consistent structure for all entries

### 4. **Better Quality Filtering**
- Filters out malformed entries (like "frue" with `[['` translation)
- Ensures all translations are meaningful and properly formatted
- Removes empty or artifact translations

## Algorithm

1. **Download dump**: Gets the latest io.wiktionary dump (if needed)
2. **Stream parsing**: Processes XML pages incrementally
3. **Title filtering**: Removes non-word entries (punctuation, numbers, etc.)
4. **Category filtering**: Excludes suffixes, radicals, and compounds
5. **Section extraction**: Finds Ido language sections
6. **Translation extraction**: Extracts Esperanto translations using multiple patterns
7. **Multiple meaning parsing**: Splits complex translations into separate entries
8. **Part of speech extraction**: Identifies grammatical categories
9. **Data cleaning**: Removes wiki markup, categories, and artifacts
10. **Quality filtering**: Removes malformed or empty entries
11. **Output generation**: Creates structured JSON with metadata

## Translation Patterns

The extractor recognizes these patterns:

- `*{{eo}}: translation`
- `* Esperanto: translation`
- `{{t|eo|translation}}`
- `{{l|eo|translation}}`
- `{{ux|io|translation|translation}}`

## Multiple Meaning Examples

- **Numbered meanings**: `finar` → `["finiĝi", "fini"]`
- **Semicolon-separated**: `kantar` → `["kanti", "ĉirpi"]`
- **Complex entries**: `pronuncar` → `["prononci", "elparoli"]`

## Filtering Rules

### Title Filtering
- Must start with a letter
- Minimum 2 characters
- No special characters (`=`, `/`, `&`, etc.)
- Excludes system pages (MediaWiki, Help, etc.)

### Category Filtering
- Excludes pages with categories: `sufix`, `radik`, `kompon`, `affix`, etc.
- Focuses on actual dictionary words

### Translation Filtering
- Removes empty translations
- Filters out malformed entries (starting with `[[`)
- Cleans wiki markup and categories
- Preserves multiple valid translations

## Performance

- **Memory efficient**: Streams processing, doesn't load entire dump
- **Robust parsing**: Handles malformed XML gracefully
- **Progress tracking**: Shows processing statistics
- **Respectful**: No external API calls, works with local dump

## Dependencies

- Python 3.6+
- Standard library only (no external dependencies required)
- Optional: `mwparserfromhell` for enhanced template parsing

## Example Results

From a typical run processing ~10,000 pages:
- **Pages processed**: 10,001
- **Pages with Ido sections**: 630
- **Valid entries found**: 489
- **Entries with multiple meanings**: 62 (12.7%)
- **Success rate**: ~77.6% of Ido pages yield valid translations
- **Quality**: 0 malformed entries, 0 empty translations

## Notes

- The dump file is ~30MB compressed
- Processing time: ~2-5 minutes for full dump
- Output quality is significantly improved over previous versions
- Focuses on dictionary words, excludes technical/suffix entries
- Properly handles complex translation patterns and multiple meanings