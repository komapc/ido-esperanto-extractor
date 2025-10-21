# Dictionary Comparison & Makefile Options

## Summary

**Task 1: Translation Comparison Tool** ✅
- Created `compare_dictionaries.sh` script
- Automatically tests old vs new dictionaries
- Generates detailed comparison report with statistics
- Includes backup/restore functionality

**Task 2: Makefile Skip Options** ✅  
- Added `SKIP_DOWNLOAD`, `SKIP_FR_WIKT`, `SKIP_FR_MEANINGS` variables
- Created `regenerate-fast` and `regenerate-minimal` targets
- Documented timing estimates for each option

---

## 1. Translation Comparison Tool

### Usage

```bash
cd /home/mark/apertium-ido-epo/tools/extractor/ido-esperanto-extractor

# Run comparison with default test sentences
make compare
# OR
./compare_dictionaries.sh

# Run with custom test file
./compare_dictionaries.sh my_test_sentences.txt
```

### What It Does

1. **Tests OLD dictionary**: Translates test sentences with current dictionary
2. **Installs NEW dictionary**: Copies from `dist/` to pair directory
3. **Tests NEW dictionary**: Translates same sentences with new dictionary  
4. **Generates Report**: Shows side-by-side comparison with statistics:
   - Number of sentences tested
   - How many translations are same/changed
   - Error counts for old vs new
   - Improvements summary
5. **User Choice**: Keep new dictionaries or restore old ones

### Test Sentences

Default test file: `test_sentences.txt`
```
Me havas granda kato.
La hundo kuras rapide.
Yen esas bela yorno.
Me volas manjar pomo.
La libro esas sur la tablo.
```

You can edit this file or create your own.

### Output Example

```
======================================================================
TRANSLATION COMPARISON REPORT
======================================================================

Sentence 1:
  IDO: Me havas granda kato.
  OLD: Mi havas grandan katon
  NEW: Mi havas grandan katon  
  ✅ SAME

Sentence 2:
  IDO: La hundo kuras rapide.
  OLD: *La hundo kuras #rapid
  NEW: La hundo kuras rapide
  🔄 CHANGED

======================================================================
SUMMARY
======================================================================
Total sentences: 10
Same: 7
Changed: 3
OLD dictionary errors: 5
NEW dictionary errors: 2
✅ NEW dictionary fixed 3 error(s)!
======================================================================
```

---

## 2. Makefile Skip Options

### Variables

Set to `1` to skip a step:

| Variable | Default | Description | Time Saved |
|----------|---------|-------------|-----------|
| `SKIP_DOWNLOAD` | 0 | Skip downloading dumps | ~1 min |
| `SKIP_EN_WIKT` | 1 | Skip English Wiktionary | Always skipped |
| `SKIP_FR_WIKT` | 0 | Skip French Wiktionary parsing | ~10 min |
| `SKIP_FR_MEANINGS` | 0 | Skip French meanings extraction | ~13 min |

### Quick Commands

```bash
# Full regeneration (includes everything)
make regenerate                    # ~1.5-2 hours

# Fast regeneration (skip downloads & FR meanings)
make regenerate-fast              # ~1 hour

# Minimal regeneration (IO/EO Wiktionary + Wikipedia only)
make regenerate-minimal           # ~20 minutes

# Custom: skip only downloads
make regenerate SKIP_DOWNLOAD=1

# Custom: skip downloads + French Wiktionary
make regenerate SKIP_DOWNLOAD=1 SKIP_FR_WIKT=1

# Custom: skip everything expensive
make regenerate SKIP_DOWNLOAD=1 SKIP_FR_WIKT=1 SKIP_FR_MEANINGS=1
```

### Timing Breakdown

| Target | Duration | Includes |
|--------|----------|----------|
| `regenerate` | ~1.5-2 hours | All sources: IO/EO/FR Wiktionary + Wikipedia + FR meanings |
| `regenerate-fast` | ~1 hour | IO/EO/FR Wiktionary + Wikipedia (no FR meanings) |
| `regenerate-minimal` | ~20 minutes | IO/EO Wiktionary + Wikipedia only |

### What Gets Skipped

**`SKIP_FR_WIKT=1`:**
- Skips parsing 790MB French Wiktionary dump
- Loses ~1,000 FR→IO/EO pivot translations
- Saves ~10 minutes

**`SKIP_FR_MEANINGS=1`:**
- Skips extracting detailed meanings from French Wiktionary
- Processes 7.4 million pages
- Loses ~1,050 meaning-specific translations
- Saves ~13 minutes

**`SKIP_DOWNLOAD=1`:**
- Uses existing dump files in `data/raw/`
- Essential if dumps are already downloaded
- Saves ~1 minute

---

## Files Created

1. `compare_dictionaries.sh` - Main comparison script
2. `test_sentences.txt` - Default test sentences  
3. `backup_old_dix/` - Backup directory for old dictionaries
4. `/tmp/old_translations.txt` - OLD dictionary test output
5. `/tmp/new_translations.txt` - NEW dictionary test output

## Next Steps

**Task 3**: Run actual comparison tests
```bash
cd /home/mark/apertium-ido-epo/tools/extractor/ido-esperanto-extractor
make compare
```

This will show if the new dictionaries improve translation quality!
