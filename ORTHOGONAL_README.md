# Orthogonal Architecture - Implementation Guide

**Status:** ✅ Core Implementation Complete  
**Date:** October 21, 2025  
**Version:** 2.0-orthogonal

---

## 🎯 Overview

The orthogonal architecture refactors the extraction pipeline into clean, independent stages with:
- **Standardized JSON format** across all sources
- **Smart caching** - only re-parse when dumps change
- **Auto-discovery** - merge automatically finds all sources
- **Easy extensibility** - add new sources/pivots easily
- **Dedicated vortaro.json** - optimized for the dictionary website

---

## 📁 Directory Structure

```
ido-esperanto-extractor/
├── dumps/                      # Stage 0: Downloaded dumps
│   ├── iowiktionary-*.xml.bz2
│   ├── eowiktionary-*.xml.bz2
│   ├── frwiktionary-*.xml.bz2  (optional)
│   └── iowiki-*.sql.gz
│
├── sources/                    # Stage 1: Parsed sources (standardized)
│   ├── source_io_wiktionary.json
│   ├── source_eo_wiktionary.json
│   ├── source_fr_wiktionary.json (optional)
│   └── source_io_wikipedia.json  (optional)
│
├── output/                     # Stage 2: Merged outputs
│   ├── BIG_BIDIX.json         # For Apertium (all IO→EO)
│   ├── MONO_IDO.json          # Monolingual Ido
│   ├── vortaro.json           # For vortaro website ⭐
│   └── metadata.json          # Pipeline metadata
│
├── dist/                       # Stage 3: Exported formats
│   ├── apertium-ido.ido.dix
│   └── apertium-ido-epo.ido-epo.dix
│
├── scripts/
│   ├── 01_parse_io_wiktionary.py    ✅ Ido Wiktionary parser
│   ├── 02_parse_eo_wiktionary.py    ✅ Esperanto Wiktionary parser
│   ├── 03_parse_fr_wiktionary.py    ✅ French Wiktionary parser (pivot)
│   ├── 04_parse_io_wikipedia.py     ✅ Ido Wikipedia parser
│   ├── 10_merge.py                  ✅ Unified merge (auto-discovery)
│   ├── run.py                       ✅ Master control script
│   └── utils/
│       ├── json_utils.py
│       └── metadata.py
│
└── config.json                 # Configuration
```

---

## 🚀 Quick Start

### Full Pipeline (with smart caching)
```bash
cd /home/mark/apertium-ido-epo/tools/extractor/ido-esperanto-extractor

# Run full pipeline
python3 scripts/run.py

# Only re-parse sources if dumps are newer
# Merge always runs (fast)
```

### Parse Individual Sources
```bash
# Parse only Ido Wiktionary
python3 scripts/01_parse_io_wiktionary.py

# Parse only Esperanto Wiktionary
python3 scripts/02_parse_eo_wiktionary.py

# Parse only French Wiktionary (pivot)
python3 scripts/03_parse_fr_wiktionary.py

# Parse only Wikipedia
python3 scripts/04_parse_io_wikipedia.py
```

### Merge Sources
```bash
# Auto-discovers all sources/*.json and merges
python3 scripts/10_merge.py

# Creates:
#   output/BIG_BIDIX.json
#   output/MONO_IDO.json
#   output/vortaro.json    ← For website!
#   output/metadata.json
```

### Advanced Usage
```bash
# Force full rebuild
python3 scripts/run.py --force

# Skip downloads (use existing dumps)
python3 scripts/run.py --skip-download

# Parse only one source
python3 scripts/run.py --parse-only io_wiktionary

# Just merge (for testing)
python3 scripts/run.py --merge-only

# Dry run (see what would execute)
python3 scripts/run.py --dry-run
```

---

## 📊 Standardized JSON Format

All `sources/source_*.json` files follow this structure:

```json
{
  "metadata": {
    "source_name": "io_wiktionary",
    "file_type": "source_json",
    "origin": {
      "dump_file": "iowiktionary-latest-pages-articles.xml.bz2",
      "dump_date": "2025-10-02",
      "dump_size_mb": 29.84
    },
    "extraction": {
      "date": "2025-10-21T23:30:31",
      "script": "scripts/01_parse_io_wiktionary.py",
      "version": "2.0"
    },
    "statistics": {
      "total_entries": 7549,
      "with_translations": 7549,
      "with_morphology": 6200
    }
  },
  "entries": [
    {
      "lemma": "vorto",
      "pos": "noun",
      "translations": {
        "eo": ["vorto"],
        "en": ["word"],
        "fr": ["mot"]
      },
      "morphology": {
        "paradigm": "o__n"
      },
      "source_page": "https://io.wiktionary.org/wiki/vorto"
    }
  ]
}
```

**Key Features:**
- Same structure for ALL sources
- Metadata includes dump date + extraction date
- Easy to validate, merge, and process
- Optional fields based on source type

---

## 🔄 Pipeline Flow

```
┌─────────────────────────────────────────────────────────┐
│ STAGE 0: Download Dumps (Cached)                       │
│  - Download latest Wiktionary/Wikipedia dumps          │
│  - Skip if dumps < 7 days old                          │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│ STAGE 1: Parse Sources (Cached, Parallel-ready)        │
│  - 01_parse_io_wiktionary.py → source_io_wiktionary    │
│  - 02_parse_eo_wiktionary.py → source_eo_wiktionary    │
│  - 03_parse_fr_wiktionary.py → source_fr_wiktionary    │
│  - 04_parse_io_wikipedia.py  → source_io_wikipedia     │
│                                                         │
│  Only re-parse if:                                      │
│    - Dump is newer than source                          │
│    - Source file doesn't exist                          │
│    - Force rebuild requested                            │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│ STAGE 2: Merge (Always run, fast ~2 min)               │
│  - Auto-discovers all sources/*.json                    │
│  - Multi-source provenance tracking                     │
│  - Conflict resolution with source priority             │
│                                                         │
│  Creates 4 outputs:                                     │
│    - BIG_BIDIX.json  (for Apertium)                    │
│    - MONO_IDO.json   (monolingual)                     │
│    - vortaro.json    (for website) ⭐                   │
│    - metadata.json   (pipeline info)                    │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│ STAGE 3: Export (Cached)                               │
│  - BIG_BIDIX.json → apertium-ido-epo.ido-epo.dix      │
│  - MONO_IDO.json  → apertium-ido.ido.dix              │
│                                                         │
│  Skip if .dix newer than JSON                          │
└─────────────────────────────────────────────────────────┘
```

---

## 🌐 vortaro.json Format

The `output/vortaro.json` file is optimized for the vortaro website:

```json
{
  "metadata": {
    "creation_date": "2025-10-21T23:57:43",
    "total_words": 7549,
    "sources": ["io_wiktionary", "eo_wiktionary"],
    "version": "2.0-orthogonal"
  },
  "vorto": {
    "esperanto_words": ["vorto"],
    "sources": ["IO"],
    "morfologio": ["o__n"]
  },
  "kavalo": {
    "esperanto_words": ["ĉevalo"],
    "sources": ["IO", "FR"],
    "morfologio": ["o__n"]
  }
}
```

**Source Badges:**
- `IO` - Ido Wiktionary
- `EO` - Esperanto Wiktionary  
- `FR` - French Wiktionary (pivot)
- `WIKI` - Ido Wikipedia

**To use in vortaro website:**
```bash
# Copy to vortaro repo
cp output/vortaro.json /home/mark/apertium-dev/vortaro/dictionary.json

# Deploy
cd /home/mark/apertium-dev/vortaro
git add dictionary.json
git commit -m "Update dictionary with orthogonal pipeline"
git push
```

---

## ➕ Adding New Sources

### Example: Adding German Wiktionary Pivot

1. **Create parser** (follow existing pattern):
```bash
cp scripts/03_parse_fr_wiktionary.py scripts/05_parse_de_wiktionary.py
# Edit to parse German Wiktionary
# Output: sources/source_de_wiktionary.json
```

2. **Add to config.json**:
```json
{
  "sources": {
    "de_wiktionary": {
      "enabled": true,
      "url": "https://dumps.wikimedia.org/dewiktionary/latest/...",
      "parser": "scripts/05_parse_de_wiktionary.py"
    }
  }
}
```

3. **Run pipeline**:
```bash
python3 scripts/run.py
# Automatically discovers and merges new source!
```

4. **Update vortaro badges** (in `10_merge.py`):
```python
elif 'de_wiktionary' in source:
    source_badges.append('DE')
```

**That's it!** No changes needed to:
- Merge script (auto-discovers sources/)
- Export script (uses BIG_BIDIX)
- Other parsers (independent)

---

## 📊 Source Priority

When multiple sources provide the same information, priority determines which to keep:

```python
SOURCE_PRIORITY = {
    'io_wiktionary': 100,    # Most trusted
    'eo_wiktionary': 90,
    'io_wikipedia': 50,
    'fr_wiktionary': 30,
    'en_wiktionary': 20,
}
```

**Used for:**
- Morphology selection (prefer higher priority source)
- POS tagging (prefer non-null from higher priority)
- Conflict resolution

**Translations:** All translations from all sources are kept (no conflicts).

---

## ✅ Implementation Status

### Week 1: Core Parsers ✅
- [x] config.json created
- [x] utils/json_utils.py
- [x] utils/metadata.py
- [x] 01_parse_io_wiktionary.py ✅
- [x] 02_parse_eo_wiktionary.py ✅
- [x] 03_parse_fr_wiktionary.py ✅
- [x] 04_parse_io_wikipedia.py ✅

### Week 2: Merge & Control ✅
- [x] 10_merge.py (auto-discovery) ✅
- [x] run.py (master control) ✅
- [x] vortaro.json output ✅
- [x] Smart caching logic ✅

### Week 3: Testing & Polish
- [ ] Full pipeline test with all sources
- [ ] Compare outputs with old pipeline
- [ ] Performance benchmarking
- [ ] Edge case testing

### Week 4: Documentation & Deploy
- [ ] Update main README
- [ ] Migration guide
- [ ] Deprecate old scripts
- [ ] Production deployment

---

## 🧪 Testing

### Test Individual Components
```bash
# Test IO parser with limit
python3 scripts/01_parse_io_wiktionary.py --limit 100

# Test merge with current sources
python3 scripts/10_merge.py

# Test full pipeline in dry-run
python3 scripts/run.py --dry-run
```

### Validate Output
```bash
# Check vortaro.json structure
python3 -m json.tool output/vortaro.json | head -50

# Check metadata
cat output/metadata.json

# Count entries
jq '.entries | length' output/BIG_BIDIX.json
```

---

## 💡 Benefits

### Old System
- ❌ Monolithic scripts
- ❌ Different formats per source
- ❌ No caching (always re-parse)
- ❌ Hard to add new sources
- ❌ Vortaro does data processing

### New System (Orthogonal)
- ✅ Clean, independent stages
- ✅ Standardized JSON across all sources
- ✅ Smart caching (only parse what changed)
- ✅ Easy to add sources (auto-discovery)
- ✅ Vortaro gets ready-to-use JSON

---

## 📚 Files Reference

### Core Scripts
- **run.py** - Master orchestration with caching
- **10_merge.py** - Unified merge with auto-discovery
- **01-04_parse_*.py** - Individual source parsers

### Utilities
- **utils/json_utils.py** - JSON loading/saving/validation
- **utils/metadata.py** - Metadata generation

### Configuration
- **config.json** - Paths, sources, settings
- **.gitignore** - Excludes large dumps/outputs

### Documentation
- **ORTHOGONAL_ARCHITECTURE.md** - Original design plan
- **ORTHOGONAL_README.md** - This file (implementation guide)
- **README.md** - Main project README

---

## 🐛 Troubleshooting

### "No source files found"
```bash
# Run parsers first
python3 scripts/01_parse_io_wiktionary.py
python3 scripts/10_merge.py
```

### "Dump file not found"
```bash
# Check dumps directory
ls -lh dumps/

# Or use existing data directory
python3 scripts/01_parse_io_wiktionary.py --dump data/iowiktionary-latest-pages-articles.xml.bz2
```

### "Parser taking too long"
```bash
# Test with limit
python3 scripts/01_parse_io_wiktionary.py --limit 1000

# Or check existing old pipeline outputs
ls -lh work/
```

---

## 🎉 Success!

The orthogonal architecture is now implemented and working:

✅ **Independent parsers** - Easy to test and extend  
✅ **Standardized format** - Consistent across all sources  
✅ **Auto-discovery** - Merge finds sources automatically  
✅ **Smart caching** - Only re-parse when needed  
✅ **vortaro.json** - Ready-to-use for website  

**Next:** Test with full dumps and compare quality with old pipeline!

