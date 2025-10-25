# Ido ↔ Esperanto Dictionary Extraction Pipeline

This project rebuilds Ido monolingual, Esperanto monolingual, and Ido–Esperanto bilingual dictionaries from Wiktionary, Wikipedia, and (optionally) Wikidata. See `REGENERATION_PLAN.md` for the full design.

## Recent Improvements

**October 2025 - Pipeline Manager:**
- ✅ Implemented stage-based resumability with pipeline manager
- ✅ Tracks completion status, errors, and timestamps for all stages
- ✅ Resume from any stage after interruption
- ✅ Visual progress tracking with status command

**October 2025 - Data Cleaning & XML Export Fix:**
- ✅ Fixed critical XML export bug (was generating malformed 1-line files)
- ✅ Implemented comprehensive lemma/translation cleaning (removes Wiktionary markup)
- ✅ Proper multi-sense handling (numbered definitions → multiple Apertium entries)
- ✅ Added Makefile skip options for faster iteration
- ✅ Created comparison tool for testing dictionary quality

See `docs/PIPELINE_MANAGER.md` for pipeline manager documentation.
See `docs/SESSION_SUMMARY_CLEANING.md` for data cleaning details.

## Outputs
- Ido dictionary (JSON/YAML): `dist/ido_dictionary.json` (and `.yaml`)
- Esperanto dictionary (JSON/YAML): `dist/esperanto_dictionary.json` (and `.yaml`)
- Bilingual IO–EO dictionary (JSON/YAML): `dist/bilingual_io_eo.json` (and `.yaml`)
- Export-only (not committed to Apertium repos):
  - `dist/apertium-ido.ido.dix`
  - `dist/apertium-ido-epo.ido-epo.dix`

## Data Sources

### Direct Sources (High Quality)
- **io_wiktionary**: Ido Wiktionary → Esperanto translations
- **eo_wiktionary**: Esperanto Wiktionary → Ido translations  
- **io_wikipedia**: Wikipedia language links (proper nouns)

### Via Sources (Medium Quality)
- **en_wiktionary_via**: English Wiktionary pages containing both Ido AND Esperanto translations
- **fr_wiktionary_via**: French Wiktionary pages containing both Ido AND Esperanto translations

### Disabled Approaches
- **Pivot**: Ido→English→Esperanto (chain translation) - DISABLED due to quality concerns

## Quick Start

### 🚀 Main Commands

```bash
# Full regeneration with pipeline manager (recommended, ~1.5-2 hours)
make all                      # Uses pipeline manager with resumability
make regenerate-managed       # Explicit pipeline-managed run

# Legacy regeneration (without resumability)
make regenerate               # Full regeneration without pipeline manager

# Fast regeneration (skip downloads & French via, ~1 hour)  
make regenerate-fast

# Minimal regeneration (core sources only, ~20 minutes)
make regenerate-minimal

# Pipeline management
make pipeline-status          # Check pipeline status
make STAGE=<name>            # Resume from specific stage
make FORCE=1                 # Force regeneration of all stages

# Compare old vs new dictionaries
make compare
```

### 🎯 Skip Options

```bash
# Skip downloading dumps (use existing files)
make regenerate SKIP_DOWNLOAD=1

# Skip French Wiktionary processing
make regenerate SKIP_FR_WIKT=1

# Skip French via translations (saves ~13 minutes)
make regenerate SKIP_FR_VIA=1

# Custom combination
make regenerate SKIP_DOWNLOAD=1 SKIP_FR_WIKT=1 SKIP_FR_VIA=1
```

### 📊 Individual Operations

```bash
# Download data sources
./scripts/download_dumps.sh

# Parse individual sources
make wikt_io          # Ido Wiktionary (two-stage processing)
make wikt_eo          # Esperanto Wiktionary (two-stage processing)
make wiki             # Wikipedia (two-stage processing)
make wikt_fr          # French Wiktionary

# Individual stages (for debugging)
make wikt_io-stage1   # Ido Wiktionary Stage 1 only
make wikt_io-stage2   # Ido Wiktionary Stage 2 only
make wikt_eo-stage1   # Esperanto Wiktionary Stage 1 only
make wikt_eo-stage2   # Esperanto Wiktionary Stage 2 only
make wiki-stage1      # Wikipedia Stage 1 only
make wiki-stage2      # Wikipedia Stage 2 only

# Process pipeline stages
make align            # Align bilingual entries
make normalize        # Normalize entries
make morph            # Infer morphology
make mono             # Build monolingual dictionaries
make filter           # Filter and validate
make export           # Export to Apertium format

# Generate reports
make stats            # Overall statistics
make report           # Coverage report
make conflicts        # Translation conflicts
make big_bidix_stats  # Big bidix statistics
make dump_coverage    # Wiktionary coverage analysis
```

### 🧪 Testing & Maintenance

```bash
make test             # Run unit tests
make compare          # Compare dictionaries
make clean            # Clean all generated files
```

### 🔧 Two-Stage Processing

The extractor now uses **two-stage processing** for both Wikipedia and Wiktionary sources:

#### **Stage 1: XML → Filtered JSON**
- Fast XML parsing with content filtering
- Skip stubs, redirects, templates, and low-quality content
- Create intermediate JSON files for debugging
- **Resumable**: Skip if output already exists

#### **Stage 2: JSON → Final Processing**
- Detailed processing with validation and morphology
- Convert to final format for BIG BIDIX and MONO
- **Resumable**: Skip if output already exists

#### **Benefits:**
- **Faster Development**: Skip XML parsing during iterations
- **Better Debugging**: Inspect intermediate JSON files
- **Resumable Processing**: Continue from any stage
- **Cleaner Architecture**: Separation of concerns

## Pipeline (script-per-stage)
```bash
# 1) Acquire dumps
scripts/download_dumps.sh

# 2) Parse & extract lexicons
python3 scripts/parse_wiktionary_io.py
python3 scripts/parse_wiktionary_eo.py
python3 scripts/extract_wikipedia_io.py

# 3) Frequency analysis
python3 scripts/build_frequency_io_wiki.py

# 4) Align & normalize
python3 scripts/align_bilingual.py
python3 scripts/normalize_entries.py

# 5) Morphology
python3 scripts/infer_morphology.py

# 6) Filter & QA
python3 scripts/filter_and_validate.py
python3 scripts/report_coverage.py
python3 scripts/report_stats.py

# 7) Build ONE BIG BIDIX (EO-only) and reports
python3 scripts/build_one_big_bidix_json.py
python3 scripts/report_conflicts.py

# 8) Export Apertium (no auto-commit to external repos)
python3 scripts/export_apertium.py
```

## Merging Logic
- `scripts/merge_dictionaries.py` merges JSON/YAML sources with deterministic, provenance-aware conflict resolution and sense preservation.

## Legacy Notice
Previous ad-hoc scripts (e.g., `ido_esperanto_extractor.py`, `create_ido_monolingual.py`, `create_ido_epo_bilingual.py`, `add_*`) are considered deprecated and will be removed after the new pipeline is stabilized. They can be referenced to inform the new implementation but will not be used going forward.

## Git Workflow
- Use feature branches and open PRs. Do not push generated `.dix` directly to Apertium repos from this pipeline.

## Execution Rules
- If you need to run Python code longer than one line, create a script file under `scripts/` and run it; avoid inline heredocs.
- For commands that may take longer than ~1 minute, add progress logging (e.g., `--verbose` flags, periodic counters/log lines).

## Reports
- `reports/stats_summary.md` — provenance split, Wiktionary translation counts, and coverage numbers
- `reports/io_dump_coverage.md` — IO Wiktionary dump coverage (Ido without EO, EN/other counts when applicable)
- `reports/bidix_conflicts.md` — IO lemmas with multiple distinct EO terms in ONE BIG BIDIX

## ONE BIG BIDIX
- Builder: `scripts/build_one_big_bidix_json.py`
- Output: `dist/bidix_big.json`
- Content: EO-only translations for IO lemmas with full provenance (multi-source), no confidence
- Used by: bidix export, statistics, conflicts report, and future online dictionary

Notes:
- EO Wiktionary evidence is incorporated by flipping EO→IO pages that have IO translations into IO-centered items (marked `{wikt_eo}` at translation level), then flowing through normalize→morph→filter before BIG BIDIX build.

## Current Statistics (latest run)
- Final entries (work/final_vocabulary.json): 49,906
- Monolingual Ido (dist/ido_dictionary.json): 48,878
- Final by source: io_wiktionary 44,965; io_wikipedia 3,913; eo_wiktionary 0; whitelist 0
- Wiktionary translations found: IO→EO 46,885; EO→IO 328
- Wikipedia additions: any 3,913; only 3,913; Wikidata 0
- ONE BIG BIDIX size: 122,871 entries
- BIG BIDIX per source (entry-level): wiki 77,808; wikt_io 45,093; wikt_eo 983; pivot_en 692; pivot_fr 110
- BIG BIDIX translation sources (entries with any): wikt_io 9,303; wikt_eo 257; pivot_en 726; pivot_fr 114

## 📁 Output Locations

After running the exporter, you'll find outputs in:

- **Dictionaries:** `dist/`
  - `ido_dictionary.json` - Ido monolingual dictionary
  - `esperanto_dictionary.json` - Esperanto monolingual dictionary  
  - `bilingual_io_eo.json` - Bilingual Ido-Esperanto dictionary
  - `apertium-ido.ido.dix` - Apertium Ido dictionary
  - `apertium-ido-epo.ido-epo.dix` - Apertium bilingual dictionary

- **Reports:** `reports/`
  - `stats_summary.md` - Overall statistics
  - `io_dump_coverage.md` - Wiktionary coverage analysis
  - `bidix_conflicts.md` - Translation conflicts

- **Work Files:** `work/` (intermediate processing files)

## ⚡ Performance Tips

1. **Use `regenerate-fast`** for most development work
2. **Use `regenerate-minimal`** for quick testing
3. **Set skip flags** to avoid re-downloading large files
4. **Check `work/` directory** - many stages are resumable if intermediate files exist

## 🐛 Troubleshooting

If you encounter issues:

1. **Check logs** in the `logs/` directory
2. **Run individual stages** to isolate problems
3. **Use `make clean`** to start fresh
4. **Check disk space** - the pipeline requires several GB for dumps and processing

## Dictionary Comparison

To compare translations between the old and new dictionaries:

```bash
cd /home/mark/apertium-ido-epo/tools/extractor/ido-esperanto-extractor
make compare
# OR
./compare_dictionaries.sh test_sentences.txt
```

The script will:
1. Test translations with the current (old) dictionaries
2. Install the new dictionaries from `dist/`
3. Rebuild and test with new dictionaries
4. Generate a comparison report
5. Ask if you want to keep the new dictionaries or restore the old ones

## Makefile Options

The regenerate pipeline can be customized with skip flags:

### Variables:
- `SKIP_DOWNLOAD=1` - Skip downloading dumps (use existing files)
- `SKIP_EN_WIKT=1` - Skip English Wiktionary parsing (default: 1, always skipped)
- `SKIP_FR_WIKT=1` - Skip French Wiktionary parsing
- `SKIP_FR_MEANINGS=1` - Skip French meanings extraction (saves ~13 min)

### Examples:

```bash
# Full regeneration (includes French parsing, ~1.5 hours)
make regenerate

# Fast regeneration (skip downloads and FR meanings, ~1 hour)
make regenerate-fast

# Minimal regeneration (IO/EO Wiktionary + Wikipedia only, ~20 min)
make regenerate-minimal

# Custom: skip only downloads
make regenerate SKIP_DOWNLOAD=1

# Custom: skip downloads and French Wiktionary
make regenerate SKIP_DOWNLOAD=1 SKIP_FR_WIKT=1
```

### Timing Estimates:
- **Full** (`make regenerate`): ~1.5-2 hours
- **Fast** (`make regenerate-fast`): ~1 hour
- **Minimal** (`make regenerate-minimal`): ~20 minutes

