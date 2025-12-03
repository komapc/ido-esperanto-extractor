# Unified JSON Format Refactoring Plan

## Goals

1. All source JSON files use identical format with all relevant fields
2. Remove converter code - direct merging since formats match
3. Simple regeneration pipeline: sources → merged JSON → DIX files
4. Preserve all Apertium rules (.rlx, .t1x files)
5. Clean, orthogonal design with better code organization
6. Single format everywhere: JSON only (no YAML)

## Current State Analysis

### Source Formats (Inconsistent)

- **Wiktionary/Wikipedia sources** (`projects/data/sources/source_*.json`):
  - Format: `{"metadata": {...}, "entries": [{"lemma": "...", "translations": {...}, "source_page": "..."}]}`
  - Missing: `source` field per entry, `confidence` in translations, standardized `translations` array structure

- **BERT alignment** (`projects/embedding-aligner/results/*/bert_candidates.json`):
  - Format: `{"ido_word": [{"translation": "epo_word", "similarity": 0.95}]}`
  - Missing: `lemma` field name, `source`, `pos`, `morphology`, proper entry structure

- **Ido Lexicon** (`apdata/ido_lexicon.yaml`):
  - Format: YAML with `entries: [{lemma, pos, paradigm, source}]`
  - Problem: Different format (YAML), missing translations, different structure

- **Vortaro** (`projects/vortaro/dictionary.json`):
  - Format: `{"metadata": {...}, "word": {"esperanto_words": [...], "sources": [...], "morfologio": [...]}}`
  - Problem: Different structure entirely, different field names

### Current Problems

- Multiple converter functions in `format_converters.py` (will be removed)
- Complex merge logic in `merge_translations.py`, `merge_dictionaries.py` (will be simplified)
- Inconsistent field names (`esperanto_words` vs `translations`, `morfologio` vs `morphology`)
- Multiple formats (JSON, YAML) requiring conversion
- Regeneration requires multiple scripts and manual coordination
- No schema validation

## Target Unified Format

**All source files must use this exact JSON structure:**

```json
{
  "metadata": {
    "source_name": "io_wiktionary",
    "version": "1.0",
    "generation_date": "2025-01-XX",
    "statistics": {
      "total_entries": 1000,
      "entries_with_translations": 950,
      "entries_with_morphology": 800
    }
  },
  "entries": [
    {
      "lemma": "banko",
      "source": "io_wiktionary",
      "pos": "n",
      "morphology": {
        "paradigm": "o__n"
      },
      "translations": [
        {
          "term": "banko",
          "lang": "eo",
          "confidence": 1.0,
          "sources": ["io_wiktionary", "eo_wiktionary"]
        }
      ],
      "metadata": {
        "source_page": "https://io.wiktionary.org/wiki/banko"
      }
    }
  ]
}
```

**Required fields:**
- `lemma` (string, required) - The Ido word form
- `source` (string, required) - Primary source identifier (e.g., "io_wiktionary", "bert", "ido_lexicon")
- `translations` (array, required - can be empty) - List of translation objects
  - Each translation must have: `term` (string), `lang` (string, e.g., "eo"), `confidence` (float, 0.0-1.0), `sources` (array of strings)
  - Note: `sources` is an array to support multi-source provenance after merging
- `pos` (string, optional) - Part of speech
- `morphology` (object, optional) - Contains `paradigm` field
- `metadata` (object, optional) - Additional metadata like `source_page`

**Confidence defaults:**
- Wiktionary sources: `1.0`
- Wikipedia sources: `0.9`
- BERT alignment: Use actual `similarity` value (0.0-1.0)
- Lexicon: `1.0`

**Key principles:**
- **Deduplicate intelligently** while preserving full provenance
- Merge identical translations → keep all sources in array, take max confidence
- Keep different translations → all variants preserved with confidence scores
- Separate entries for different POS → flag conflicts for review
- Every entry and translation must track source(s) for full transparency

## Implementation Plan

### Phase 1: Define Unified Format Schema ✅

**Files created:**
- `projects/data/schema.json` - JSON schema definition ✅
- `projects/data/README.md` - Format documentation ✅
- `projects/data/scripts/validate_schema.py` - Validation script ✅
- `projects/data/scripts/merge_sources.py` - Unified merger ✅

### Phase 2: Update Source Generators

#### 2.1 Extractor Project

**Files to modify:**
- `projects/extractor/scripts/utils/parser_base.py` - Update `convert_wiktionary_to_standardized()`
- `projects/extractor/scripts/01_parse_io_wiktionary.py` - Ensure unified output
- `projects/extractor/scripts/02_parse_eo_wiktionary.py` - Ensure unified output
- `projects/extractor/scripts/04_parse_io_wikipedia.py` - Ensure unified output
- `projects/extractor/scripts/03_parse_fr_wiktionary.py` - Ensure unified output

**Changes:**
- Add `source` field to each entry (e.g., "io_wiktionary", "eo_wiktionary")
- Standardize `translations` to array format: `[{"term": "...", "lang": "eo", "confidence": 1.0, "source": "..."}]`
- Add `confidence` field: `1.0` for wiktionary, `0.9` for wikipedia
- Ensure all entries have consistent structure matching schema

#### 2.2 Embedding Aligner Project

**Files to modify:**
- `projects/embedding-aligner/scripts/align_bert_with_esperanto.py` - Update output format
- `projects/embedding-aligner/scripts/15_bert_crosslingual_alignment.py` - Update output format

**Changes:**
- Change output from `{"word": [{"translation": "...", "similarity": ...}]}` 
- To unified format: `{"metadata": {...}, "entries": [{"lemma": "...", "source": "bert", "translations": [{"term": "...", "lang": "eo", "confidence": similarity, "sources": ["bert"]}]}]}`
- Map `similarity` to `confidence` in translations
- Note: `sources` is array (single element initially, may be merged with other sources later)
- Output to `projects/data/sources/source_bert_alignment.json`

#### 2.3 Ido Lexicon (YAML → JSON Migration)

**Files to create:**
- `projects/data/scripts/migrate_lexicon_yaml_to_json.py` - One-time migration script

**Files to modify:**
- `projects/embedding-aligner/scripts/generate_ido_monodix_from_yaml.py` → Rename to `generate_ido_monodix_from_json.py`
- Update to read from `projects/data/sources/source_ido_lexicon.json`

**Changes:**
- Convert `apdata/ido_lexicon.yaml` → `projects/data/sources/source_ido_lexicon.json` (one-time)
- Add `source: "ido_lexicon"` to each entry
- Add empty `translations: []` array (lexicon is monolingual)
- Map `paradigm` → `morphology.paradigm`
- After migration, delete YAML file (or keep as backup, then remove)

#### 2.4 Vortaro Project

**Files to modify:**
- `projects/vortaro/app.js` - Update to read unified format directly
- `projects/vortaro/dictionary.json` - Will be regenerated from merged JSON (not a source)

**Changes:**
- Update vortaro code to read unified format: `entries[].lemma`, `entries[].translations[].term`, `entries[].translations[].sources`
- **Display ALL sources** for each translation in the UI for full transparency
- Show confidence scores to help users understand translation quality
- Remove dependency on old format (`esperanto_words`, `morfologio` fields)
- Vortaro becomes a consumer of merged JSON, not a source

### Phase 3: Simplify Merging ✅

**Files created:**
- `projects/data/scripts/merge_sources.py` - Intelligent merger with provenance ✅
  - Loads all `source_*.json` from `projects/data/sources/`
  - Validates each source against schema (fail hard on mismatch)
  - **Deduplication strategy:**
    - Same lemma + same translation → Merge, keep all sources array, take max confidence
    - Same lemma + different translations → Keep all variants with their confidence scores
    - Same lemma + different POS → Keep as separate entries, flag for review
    - Same lemma + different morphology → Prefer lexicon > wiktionary > bert
  - Outputs to `projects/data/merged/merged_bidix.json` and `merged_monodix.json`

**Files to remove:**
- `projects/embedding-aligner/scripts/format_converters.py` - No longer needed (all formats identical)
- `projects/embedding-aligner/scripts/merge_translations.py` - Replace with unified merger
- Complex merge logic in `projects/extractor/scripts/merge_dictionaries.py` - Replace with simple merger

### Phase 4: DIX Generation

**Files to create:**
- `projects/data/scripts/generate_monodix.py` - Generate monodix from merged JSON
- `projects/data/scripts/generate_bidix.py` - Generate bidix from merged JSON
- `projects/data/scripts/regenerate_all.py` - Master script that:
  1. Validates all source JSON files against schema (fail hard on error)
  2. Merges all sources → `merged_bidix.json` and `merged_monodix.json`
  3. Generates monodix → `ido.ido.dix`
  4. Generates bidix → `ido-epo.ido-epo.dix`
  5. Validates all generated XML files
  6. **Preserves .rlx and .t1x files** (they're in separate directory, never touched)
  7. Prints summary statistics

**Files to update:**
- `projects/extractor/scripts/export_apertium.py` - Simplify to use merged JSON or remove (replaced by generate_*.py)
- `projects/embedding-aligner/scripts/regenerate_bidix.py` - Update to use unified format or remove
- `projects/embedding-aligner/scripts/regenerate_monodix.py` - Update to use unified format or remove

### Phase 5: Directory Structure ✅

**New structure:**
```
projects/
├── data/
│   ├── sources/          # All source JSON (unified format)
│   │   ├── source_io_wiktionary.json
│   │   ├── source_eo_wiktionary.json
│   │   ├── source_io_wikipedia.json
│   │   ├── source_bert_alignment.json
│   │   ├── source_ido_lexicon.json  # Migrated from YAML
│   │   └── ...
│   ├── merged/           # Merged JSON files (gitignored - large)
│   │   ├── merged_bidix.json
│   │   └── merged_monodix.json
│   ├── generated/        # Generated DIX files (gitignored - large)
│   │   ├── ido.ido.dix
│   │   └── ido-epo.ido-epo.dix
│   ├── scripts/          # Data processing scripts
│   │   ├── merge_sources.py
│   │   ├── generate_monodix.py
│   │   ├── generate_bidix.py
│   │   ├── regenerate_all.py
│   │   └── migrate_lexicon_yaml_to_json.py  # One-time migration
│   ├── schema.json       # JSON schema for validation
│   └── README.md         # Documentation
├── extractor/            # Source extraction (outputs to data/sources/)
├── embedding-aligner/    # BERT alignment (outputs to data/sources/)
└── vortaro/             # Web interface (reads from data/merged/ directly)
```

**Files to update:**
- `.gitignore` - Add patterns for large generated files

### Phase 6: Rules Preservation

**Verification:**
- `.rlx` files are in `apertium/apertium-ido-epo/` (separate directory from generated DIX)
- `.t1x` files are in `apertium/apertium-ido-epo/` (separate directory from generated DIX)
- DIX generation only creates `.dix` files in `projects/data/generated/`
- Rules files are never touched by regeneration scripts
- Add documentation in `regenerate_all.py` and `README.md` explaining this

**Files to create:**
- `projects/data/scripts/validate_rules_preserved.py` - Verify rules files unchanged after regeneration
  - Checks modification times of .rlx and .t1x files before/after
  - Warns if any rules files were modified (should never happen)

**Best practice:**
- Rules (.rlx, .t1x) are manually edited and version controlled
- DIX files are generated from data sources
- Clear separation: rules = logic, DIX = data

### Phase 7: Cleanup and Migration

**Files to remove:**
- `projects/embedding-aligner/scripts/format_converters.py` - No longer needed
- `projects/embedding-aligner/scripts/merge_translations.py` - Replaced by unified merger
- `apdata/ido_lexicon.yaml` - Migrated to JSON (keep as backup initially, then delete)
- Old converter code in various scripts
- Duplicate merge functions

**Files to update:**
- Update all scripts that reference old formats
- Update all documentation
- Update README files in each project

**Migration steps:**
1. Convert YAML → JSON (one-time): `migrate_lexicon_yaml_to_json.py`
2. Update all source generators to output unified format
3. Delete old merged files: `projects/data/work/*.json`, `projects/extractor/work/*.json`
4. Run `regenerate_all.py` to create new merged files
5. Update vortaro to read unified format
6. Test end-to-end regeneration
7. Remove old converter/merge code

## Key Design Decisions

1. **Unified Format**: All sources output identical JSON structure - enables intelligent merging
2. **Single Format**: JSON only - no YAML, no conversion needed
3. **Multi-Source Provenance**: Translations have `sources` array to track all contributing sources
4. **Confidence Field**: Translations include `confidence` (0.0-1.0) for quality filtering
   - Wiktionary: 1.0
   - Wikipedia: 0.9
   - BERT: actual similarity value
5. **Intelligent Deduplication**: Merge identical translations while preserving all sources
   - Same translation from multiple sources → single entry with sources array
   - Different translations → keep all variants with confidence scores
   - Conflicting POS → keep separate entries, flag for review
6. **Conflict Resolution**: Clear priority for morphology (lexicon > wiktionary > bert)
7. **Vortaro Transparency**: Web interface shows ALL sources for each translation
8. **Rules Safety**: .rlx and .t1x are separate files in different directory, never overwritten
9. **Fail Hard**: Schema validation fails immediately on mismatch - no silent errors
10. **Clean Slate**: Delete old merged files, regenerate from sources

## Testing Strategy

1. **Format Validation**: Validate all source JSON against schema
2. **Merge Testing**: Verify merged output contains all sources
3. **DIX Generation**: Ensure generated DIX files are valid XML
4. **Rules Preservation**: Verify .rlx and .t1x files unchanged
5. **Round-trip**: Regenerate from sources, verify output matches

## Migration Notes

- Old source files can be converted using one-time migration script
- Existing merged files will be regenerated from sources
- Vortaro dictionary.json will be regenerated from merged JSON
- All changes are backward-incompatible (clean break as requested)

## Success Criteria

1. ✅ All source JSON files use identical format
2. ✅ No converter code needed for merging
3. ✅ Single command regenerates all DIX files
4. ✅ All Apertium rules (.rlx, .t1x) preserved
5. ✅ Code is simpler and more maintainable
6. ✅ Large files properly gitignored

## Progress Tracking

- [x] Phase 1: Define Unified Format Schema
- [x] Phase 3: Simplify Merging (scripts created)
- [x] Phase 5: Directory Structure
- [ ] Phase 2: Update Source Generators
- [ ] Phase 4: DIX Generation
- [ ] Phase 6: Rules Preservation
- [ ] Phase 7: Cleanup and Migration

