# Ido ↔ Esperanto Dictionary Extraction Pipeline

Builds Ido monolingual, Esperanto monolingual, and Ido–Esperanto bilingual dictionaries
from Wiktionary, Wikipedia, Wikidata, and BERT embedding alignment.
Outputs feed `apertium-ido`, `apertium-ido-epo`, and the vortaro web dictionary.

## Quick Start

```bash
# Full pipeline (~2 hours, resumable)
cd extractor
python3 scripts/pipeline_manager.py

# Check status / resume from a specific stage
python3 scripts/pipeline_manager.py --status
python3 scripts/pipeline_manager.py --stage <stage_name>

# Force re-run all stages
python3 scripts/pipeline_manager.py --force

# After rebuilding, copy outputs to consumer repos
bash ../core/deploy.sh
```

**Important:** After rebuilding `bidix_big.json`, always re-run `export_apertium.py` manually — the pipeline manager may have marked it complete before the bidix changed.

```bash
python3 scripts/export_apertium.py
python3 scripts/export_vortaro.py
```

## Pipeline Stages

Defined in `scripts/pipeline_manager.py`. Each stage is skipped if already completed; use `--force` or `--stage <name>` to rerun.

| # | Stage | Script | Key output |
|---|-------|--------|------------|
| 1 | `download_dumps` | `download_dumps.sh` | `data/raw/*.gz` |
| 2 | `wiktionary_io` | `process_wiktionary_two_stage.py --source io` | `work/io_wiktionary_processed.json` |
| 3 | `wiktionary_eo` | `process_wiktionary_two_stage.py --source eo` | `work/eo_wiktionary_processed.json` |
| 4 | `copy_for_alignment` | *(python inline)* | `work/io_wikt_io_eo.json` |
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

## Data Sources

All sources are merged by `build_one_big_bidix_json.py` into `dist/bidix_big.json`.
On conflict, higher-priority sources win; lower-priority translations are dropped.

| Source tag | Description | Bidix entries (provenance) |
|------------|-------------|---------------------------|
| `io_wiktionary` | Ido Wiktionary → Esperanto translations | 44,392 |
| `eowiki_langlinks` | eo.wiki interlanguage links → io article titles | 18,115 |
| `wikipedia_langlinks` | io.wiki interlanguage links → eo article titles | 17,865 |
| `io_wikipedia` | io.wiki article content (monolingual only) | 14,310 |
| `en_wiktionary_via` | English Wiktionary pivot (pages with io+eo translations) | 4,512 |
| `fr_wiktionary_via` | French Wiktionary pivot (pages with io+eo translations) | 1,043 |
| `eo_wiktionary` | Esperanto Wiktionary → Ido translations | 200 |
| `bert_embeddings` | XLM-RoBERTa cross-lingual alignment (cognates only, ≥0.99) | — |
| `function_word_override` | Seeded closed-class words | 10 |
| `wikidata_labels` | Wikidata items with io+eo labels (dump + wbgetentities API) | pending |

`bert_embeddings` applies a 4-character prefix cognate guard: only Esperanto translations
sharing the first 4 letters with the Ido lemma are kept, preventing distributional
alignment noise (e.g. `mortala→serioza`).

`morphological_expansion` derives io↔eo pairs from known root pairs via the shared Ido/Esperanto
affix system (`opakeso→opakeco`, `oficale→oficiale`), gated to forms attested in io.wiki frequency.

## Quality & Evaluation

Two metrics gate changes to the lexicon — run them before deploying.

- **Vortaro quality** — `make vortaro-eval` (`scripts/eval_vortaro.py`) → `reports/vortaro_quality.md`:
  precision@1 (top gloss vs a held-out `io_wiktionary` reference) + lemmatized recall over the
  top-5000 io.wiki tokens. The signal for any change to vocabulary generation.
- **Translation quality** — `scripts/eval_translation.py` → `reports/quality_trend.md`: chrF + coverage
  against the 130-sentence gold set (`data/gold/ido_epo.tsv`). Must stay flat-or-up on any bidix change.
- **Shared cleaning** — `scripts/lexicon_filters.py` (junk-lemma drop + case-variant dedup) runs inside
  `build_one_big_bidix_json.py`, so the monodix, bidix, and vortaro all benefit.
- **Blast-radius diffs** — `scripts/conflict_winner_diff.py` (which MT winners would change) and
  `make predeploy-check` (`scripts/dict_diff.py`: fresh dist vs deployed) review changes before deploy.

## Outputs

| File | Description | Current size |
|------|-------------|-------------|
| `dist/bidix_big.json` | Full bilingual dictionary (JSON) | ~92,800 entries |
| `dist/apertium-ido.ido.dix` | Ido monodix (lttoolbox XML) | ~98,900 entries |
| `dist/apertium-ido-epo.ido-epo.dix` | Ido–Esperanto bidix (lttoolbox XML) | ~103,600 entries |
| `dist/ido_dictionary.json` | Ido monolingual dictionary (JSON) | — |
| `dist/esperanto_dictionary.json` | Esperanto monolingual dictionary (JSON) | — |
| `dist/vortaro_dictionary.json` | Vortaro web dictionary | ~36,600 entries |

## Deploy

```bash
# Copy dist/ to consumer repos (apertium-ido, apertium-ido-epo, vortaro)
bash ../core/deploy.sh

# In each consumer repo: create regen branch, PR, merge, run make
# e.g.:
cd ../apertium-ido
git checkout -b chore/regen && git add . && git commit -m "chore: regen"
git push && gh pr create && gh pr merge --merge

# Recompile FST binaries
make

# Deploy vortaro to Cloudflare Pages
cd ../vortaro && npm run deploy
```

## BERT Source

Generated by `projects/embedding-aligner`. To regenerate the BERT source after
retraining or re-aligning:

```bash
cd ../projects/embedding-aligner
make                         # re-runs alignment (steps 14–20) from existing model
# then rebuild bidix:
cd ../../extractor
python3 scripts/build_one_big_bidix_json.py
python3 scripts/export_apertium.py
python3 scripts/export_vortaro.py
```

The BERT source file is `data/sources/source_bert_embeddings.json` (gitignored, ~7 MB).

## Data Files

Dump files live in `data/raw/` (gitignored). See `data/README.md` for the full list
and download commands. Typical total download: ~10 GB.

## Reports

After `pipeline_manager.py` completes, reports are in `reports/`:

| File | Contents |
|------|----------|
| `big_bidix_stats.md` | Entry and translation counts by source |
| `stats_summary.md` | Overall pipeline statistics |
| `frequency_coverage.md` | Coverage of top-N most frequent Ido words |
| `io_dump_coverage.md` | Ido Wiktionary dump analysis |
| `bidix_conflicts.md` | Lemmas with conflicting translations |

## Dictionary Maintenance Rules

All lexical data must be generated from sources — never edit `.dix` files directly
or add manual word lists. Every entry must be regeneratable from external data.
See `.kiro/steering/DICTIONARY_MAINTENANCE_RULES.md`.

## Further Reading

- `docs/PIPELINE_MANAGER.md` — stage reference and troubleshooting
- `docs/RULE_DEVELOPMENT_GUIDE.md` — how to add/modify morphological rules
- `docs/french-wiktionary.md` — French Wiktionary parser notes
- `docs/via-translations.md` — pivot (via) translation approach
- `docs/wikipedia-classification.md` — Wikipedia article classification
- `docs/markup-cleaning.md` — Wiktionary markup cleaning
