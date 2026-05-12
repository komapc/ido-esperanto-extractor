# Pipeline Manager

Runs the extraction pipeline with per-stage state tracking, so interrupted runs
can resume from the failed stage rather than starting over.

## Usage

```bash
# Full pipeline (~2 hours)
python3 scripts/pipeline_manager.py

# Check status
python3 scripts/pipeline_manager.py --status

# Resume from a specific stage
python3 scripts/pipeline_manager.py --stage <stage_name>

# Force re-run all stages
python3 scripts/pipeline_manager.py --force
```

## Stages

| # | Stage | Script | Key output |
|---|-------|--------|------------|
| 1 | `download_dumps` | `download_dumps.sh` | `data/raw/*.gz` |
| 2 | `wiktionary_io` | `process_wiktionary_two_stage.py --source io` | `work/io_wiktionary_processed.json` |
| 3 | `wiktionary_eo` | `process_wiktionary_two_stage.py --source eo` | `work/eo_wiktionary_processed.json` |
| 4 | `copy_for_alignment` | *(inline)* | `work/io_wikt_io_eo.json` |
| 5 | `wiktionary_fr` | `parse_wiktionary_fr.py` | `work/fr_wikt_io_xx.json` |
| 6 | `wikipedia` | `process_wikipedia_two_stage.py` | `work/io_wikipedia_processed.json` |
| 7 | `wikipedia_frequency` | `build_frequency_io_wiki.py` | `work/io_wiki_frequency.json` |
| 8 | `wiktionary_en` | `parse_wiktionary_en.py` | `work/en_wikt_en_both.json` |
| 9 | `via_english` | `parse_wiktionary_via.py --source en` | `work/bilingual_via_en.json` |
| 10 | `align_bilingual` | `align_bilingual.py` | `work/bilingual_raw.json` |
| 11 | `via_french` | `parse_wiktionary_via.py --source fr` | `work/bilingual_via_fr.json` |
| 11b | `wikipedia_langlinks` | `parse_wikipedia_langlinks.py` | `work/io_eo_langlinks.json` |
| 11c | `wikidata_labels` | `parse_wikidata_labels.py` | `work/io_eo_wikidata.json` |
| 11d | `eowiki_langlinks` | `parse_wikipedia_langlinks.py --source-wiki eo` | `work/eo_io_langlinks.json` |
| 12 | `prepare_vocabulary` | `prepare_vocabulary.py` | `work/final_vocabulary.json` |
| 13 | `build_monolingual` | `build_monolingual.py` | `dist/ido_dictionary.json` |
| 14 | `build_big_bidix` | `build_one_big_bidix_json.py` | `dist/bidix_big.json` |
| 15 | `report_coverage` | `report_coverage.py` | `reports/frequency_coverage.md` |
| 16 | `export_apertium` | `export_apertium.py` | `dist/*.dix` |
| 17 | `report_stats` | `report_stats.py` | `reports/stats_summary.md` |
| 18 | `report_dump_coverage` | `report_io_dump_coverage.py` | `reports/io_dump_coverage.md` |
| 19 | `report_conflicts` | `report_conflicts.py` | `reports/bidix_conflicts.md` |
| 20 | `report_big_bidix_stats` | `report_big_bidix_stats.py` | `reports/big_bidix_stats.md` |
| 21 | `build_web_index` | `build_web_index.py` | `dist/web_index.json` |
| 22 | `export_vortaro` | `export_vortaro.py` | `dist/vortaro_dictionary.json` |

## State file

State is stored in `work/pipeline_state.json`. Stage statuses: `pending`,
`running`, `completed`, `failed`.

If the state file becomes corrupted, delete it and start over:
```bash
rm work/pipeline_state.json
python3 scripts/pipeline_manager.py
```

## Gotcha: stale export_apertium

The pipeline manager tracks stage completion by timestamp. If you rebuild
`dist/bidix_big.json` manually (e.g. by re-running `build_one_big_bidix_json.py`
directly), the `export_apertium` stage still shows "completed" from the previous
run and will be skipped.

Always re-run export after a manual bidix rebuild:
```bash
python3 scripts/export_apertium.py
python3 scripts/export_vortaro.py
```
