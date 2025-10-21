# Orthogonal Architecture - Implementation Plan

## 🎯 Goal
Restructure the extraction pipeline to be clean, orthogonal, and easily extensible.

## 🏗️ New Directory Structure

```
ido-esperanto-extractor/
├── dumps/                   # Stage 0: Downloaded dumps
│   ├── io_wiktionary_YYYY-MM-DD.xml.bz2
│   ├── eo_wiktionary_YYYY-MM-DD.xml.bz2
│   ├── fr_wiktionary_YYYY-MM-DD.xml.bz2
│   └── io_wikipedia_YYYY-MM-DD.sql.gz
│
├── sources/                 # Stage 1: Parsed sources (standardized)
│   ├── source_io_wiktionary.json
│   ├── source_eo_wiktionary.json
│   ├── source_fr_wiktionary.json
│   └── source_io_wikipedia.json
│
├── output/                  # Stage 2: Final merged outputs
│   ├── BIG_BIDIX.json      # For Apertium (all entries)
│   ├── MONO_IDO.json       # Monolingual Ido dictionary
│   ├── vortaro.json        # For vortaro website (optimized)
│   └── metadata.json       # Pipeline metadata
│
├── dist/                    # Stage 3: Exported formats
│   ├── apertium-ido.ido.dix
│   └── apertium-ido-epo.ido-epo.dix
│
└── scripts/
    ├── run.py              # Master control script
    ├── config.py           # Configuration
    ├── 00_download_dumps.sh
    ├── 01_parse_io_wiktionary.py
    ├── 02_parse_eo_wiktionary.py
    ├── 03_parse_fr_wiktionary.py
    ├── 04_parse_io_wikipedia.py
    ├── 10_merge.py         # Unified merge
    ├── 20_export_apertium.py
    ├── 30_publish.py       # Publishing to vortaro/apertium
    └── utils/
        ├── __init__.py
        ├── json_utils.py
        └── metadata.py
```

## 📋 Standardized JSON Structure

### All source_*.json follow this format:

```json
{
  "metadata": {
    "source_name": "io_wiktionary",
    "file_type": "source_json",
    "origin": {
      "dump_file": "iowiktionary-latest-pages-articles.xml.bz2",
      "dump_date": "2025-10-21",
      "dump_url": "https://dumps.wikimedia.org/iowiktionary/latest/"
    },
    "extraction": {
      "date": "2025-10-21T14:30:00Z",
      "script": "scripts/01_parse_io_wiktionary.py",
      "version": "2.0"
    },
    "statistics": {
      "total_entries": 7549,
      "with_eo_translations": 7549,
      "with_morphology": 6200
    }
  },
  "entries": [
    {
      "lemma": "vorto",
      "pos": "noun",
      "translations": {
        "eo": ["vorto"]
      },
      "morphology": {
        "paradigm": "o__n"
      },
      "source_page": "https://io.wiktionary.org/wiki/vorto",
      "confidence": 0.9
    }
  ]
}
```

**Key Points:**
- Same structure for all sources
- Metadata includes dump date + extraction date
- Entries array is standard
- Optional fields (translations, morphology) based on source
- Easy to extend with new sources

## 🔄 Pipeline Stages

### Stage 0: Download Dumps (Cacheable)
**Script:** `scripts/00_download_dumps.sh`  
**Skip if:** Dumps exist and are < 7 days old  
**Time:** ~45 minutes  

### Stage 1: Parse Sources (Cacheable, Parallel)
**Scripts:** 
- `01_parse_io_wiktionary.py` → `sources/source_io_wiktionary.json`
- `02_parse_eo_wiktionary.py` → `sources/source_eo_wiktionary.json`
- `03_parse_fr_wiktionary.py` → `sources/source_fr_wiktionary.json`
- `04_parse_io_wikipedia.py` → `sources/source_io_wikipedia.json`

**Skip if:** Source JSON newer than dump AND parser unchanged  
**Time:** ~60 minutes total  
**Can run in parallel!**

### Stage 2: Merge (Always run, fast)
**Script:** `10_merge.py`  
**Reads:** All `sources/source_*.json`  
**Creates:**
- `output/BIG_BIDIX.json` (for Apertium)
- `output/MONO_IDO.json` (monolingual)
- `output/vortaro.json` (for website) ⭐
- `output/metadata.json`

**Time:** ~2 minutes  
**Auto-discovers all sources!**

### Stage 3: Export (Cacheable)
**Script:** `20_export_apertium.py`  
**Input:** `output/BIG_BIDIX.json`  
**Output:** `dist/*.dix` (XML)  
**Skip if:** .dix newer than BIG_BIDIX  
**Time:** ~5 minutes

### Stage 4: Publish (Manual/On-demand)
**Script:** `30_publish.py`  
**Actions:**
- Copy `vortaro.json` → vortaro repo
- Copy `*.dix` → apertium-ido-epo repo
- Or publish to GitHub Releases

## 🎮 Master Control (run.py)

### Usage Examples:

```bash
# Full pipeline with smart caching
./run.py

# Force full rebuild
./run.py --force

# Skip downloads (use existing dumps)
./run.py --skip-download

# Parse only one source (development)
./run.py --parse-only io_wiktionary

# Just merge (test merge logic)
./run.py --merge-only

# Full pipeline + publish to vortaro
./run.py --publish vortaro

# Dry run (show what would execute)
./run.py --dry-run
```

## 🚀 Migration Strategy

### Phase 1: Parallel Development (Week 1-2)
- Create new structure alongside old
- Rewrite parsers one by one
- Test outputs match old pipeline
- Don't break existing functionality

### Phase 2: Unified Merge (Week 3)
- Create merge.py
- Test against current BIG_BIDIX
- Create vortaro.json output

### Phase 3: Master Control (Week 4)
- Create run.py
- Implement caching
- Add publishing scripts
- Full testing

### Phase 4: Switchover (Week 5)
- Deprecate old scripts
- Update documentation
- Clean up old files

## 📦 Easy Extension: Adding New Pivots

### To add German Wiktionary pivot:

```bash
# 1. Create parser (follows same pattern)
cp scripts/03_parse_fr_wiktionary.py scripts/05_parse_de_wiktionary.py
# Edit to parse German Wiktionary
# Output: sources/source_de_wiktionary.json

# 2. Run
./run.py --parse-only de_wiktionary --merge

# 3. Update vortaro badges (1 line!)
# app.js: if (source.includes('de_wiktionary')) return '🇩🇪 DE';

# Done! German pivot integrated
```

**No changes to:**
- Merge script (auto-discovers sources/*)
- Export script (uses BIG_BIDIX)
- Other parsers (independent)

## ✅ Success Criteria

### For Each Stage:
- [ ] Produces standardized JSON with metadata
- [ ] Can be skipped if output is fresh
- [ ] Independent of other stages
- [ ] Properly logged/reported
- [ ] Handles errors gracefully

### For Overall System:
- [ ] Faster than current (with caching)
- [ ] Easier to understand
- [ ] Easy to add new sources
- [ ] Vortaro gets clean vortaro.json
- [ ] No data processing in vortaro

## 📝 Implementation Checklist

### Week 1:
- [x] Create feature branch
- [x] Create new directories (dumps/, sources/, output/)
- [x] Create .gitignore
- [ ] Create config.py (paths, settings)
- [ ] Rewrite parse_io_wiktionary.py → standardized
- [ ] Test IO Wiktionary parser

### Week 2:
- [ ] Rewrite parse_eo_wiktionary.py → standardized
- [ ] Rewrite parse_fr_wiktionary.py → standardized
- [ ] Rewrite parse_io_wikipedia.py → standardized
- [ ] Test all parsers produce consistent structure

### Week 3:
- [ ] Create 10_merge.py (unified merge)
- [ ] Auto-discover sources/*.json
- [ ] Generate BIG_BIDIX.json
- [ ] Generate MONO_IDO.json
- [ ] Generate vortaro.json (NEW!)
- [ ] Test outputs match current quality

### Week 4:
- [ ] Create run.py master script
- [ ] Implement caching logic
- [ ] Add progress reporting
- [ ] Create 30_publish.py
- [ ] Test full pipeline
- [ ] Documentation

### Week 5:
- [ ] Compare new vs old outputs
- [ ] Deprecate old scripts
- [ ] Update README
- [ ] Create PR
- [ ] Merge and deploy

## 🎯 First Milestone: IO Wiktionary Parser

**Goal:** Get first orthogonal parser working  
**Output:** `sources/source_io_wiktionary.json`  
**Test:** Compare with `dictionary_io_eo.json`  
**Time:** This week

Let's start! 🚀

