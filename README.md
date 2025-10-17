# Ido ↔ Esperanto Dictionary Extraction Pipeline

This project rebuilds Ido monolingual, Esperanto monolingual, and Ido–Esperanto bilingual dictionaries from Wiktionary, Wikipedia, and (optionally) Wikidata. See `REGENERATION_PLAN.md` for the full design.

## Outputs
- Ido dictionary (JSON/YAML): `dist/ido_dictionary.json` (and `.yaml`)
- Esperanto dictionary (JSON/YAML): `dist/esperanto_dictionary.json` (and `.yaml`)
- Bilingual IO–EO dictionary (JSON/YAML): `dist/bilingual_io_eo.json` (and `.yaml`)
- Export-only (not committed to Apertium repos):
  - `dist/apertium-ido.ido.dix`
  - `dist/apertium-ido-epo.ido-epo.dix`

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

# 7) Export Apertium (no auto-commit to external repos)
python3 scripts/export_apertium.py
```

## Merging Logic
- `scripts/merge_dictionaries.py` merges JSON/YAML sources with deterministic, provenance-aware conflict resolution and sense preservation.

## Legacy Notice
Previous ad-hoc scripts (e.g., `ido_esperanto_extractor.py`, `create_ido_monolingual.py`, `create_ido_epo_bilingual.py`, `add_*`) are considered deprecated and will be removed after the new pipeline is stabilized. They can be referenced to inform the new implementation but will not be used going forward.

## Git Workflow
- Use feature branches and open PRs. Do not push generated `.dix` directly to Apertium repos from this pipeline.