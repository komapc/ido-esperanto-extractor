PY=python3

RAW=data/raw
WORK=work
DIST=dist
REPORTS=reports

# Skip flags (set to 1 to skip)
SKIP_DOWNLOAD ?= 0
SKIP_EN_WIKT ?= 0
SKIP_FR_WIKT ?= 0
SKIP_FR_MEANINGS ?= 0
SKIP_WIKI ?= 0

# Pipeline manager options
FORCE ?= 0
STAGE ?=

.PHONY: all regenerate regenerate-fast regenerate-minimal regenerate-managed clean freq wikt_io wikt_eo wikt_io-stage1 wikt_io-stage2 wikt_eo-stage1 wikt_eo-stage2 wikt_en wiki wiki-stage1 wiki-stage2 align align_pivot normalize morph mono filter report export stats dump_coverage big_bidix conflicts big_bidix_stats web pivot_en pivot_fr compare test pipeline-status

all: regenerate-managed

# Pipeline-managed regeneration (with resumability)
regenerate-managed:
	@$(eval PIPELINE_ARGS := )
	@if [ "$(FORCE)" = "1" ]; then $(eval PIPELINE_ARGS := --force) fi
	@if [ -n "$(STAGE)" ]; then $(eval PIPELINE_ARGS := $(PIPELINE_ARGS) --stage $(STAGE)) fi
	$(PY) scripts/pipeline_manager.py $(PIPELINE_ARGS)

# Full regeneration with all sources (legacy, non-resumable)
regenerate:
ifneq ($(SKIP_DOWNLOAD),1)
	./scripts/download_dumps.sh
endif
	@echo "============================================================"
	@echo "Two-stage Wiktionary processing (with resumability)"
	@echo "============================================================"
	$(PY) scripts/process_wiktionary_two_stage.py --source io --target eo
	$(PY) scripts/process_wiktionary_two_stage.py --source eo --target io
	@# Copy processed files to expected names for align_bilingual.py
	cp $(WORK)/io_wiktionary_processed.json $(WORK)/io_wikt_io_eo.json
	cp $(WORK)/eo_wiktionary_processed.json $(WORK)/eo_wikt_eo_io.json
ifneq ($(SKIP_FR_WIKT),1)
	$(PY) scripts/parse_wiktionary_fr.py
endif
ifneq ($(SKIP_WIKI),1)
	@echo "============================================================"
	@echo "Two-stage Wikipedia processing (with resumability)"
	@echo "============================================================"
	$(PY) scripts/process_wikipedia_two_stage.py
	$(PY) scripts/build_frequency_io_wiki.py
endif
ifneq ($(SKIP_EN_WIKT),1)
	@echo "============================================================"
	@echo "Parsing English Wiktionary (FIXED template parser)"
	@echo "============================================================"
	$(PY) scripts/parse_wiktionary_en.py --input $(RAW)/enwiktionary-latest-pages-articles.xml.bz2 --out $(WORK)/en_wikt_en_io.json --progress-every 10000 -v
	$(PY) scripts/parse_wiktionary_en.py --input $(RAW)/enwiktionary-latest-pages-articles.xml.bz2 --out $(WORK)/en_wikt_en_eo.json --progress-every 10000 -v
	$(PY) scripts/parse_wiktionary_via.py --source en --io-input $(WORK)/en_wikt_en_io.json --eo-input $(WORK)/en_wikt_en_eo.json --out $(WORK)/bilingual_via_en.json --progress-every 1000
endif
	$(PY) scripts/align_bilingual.py
ifneq ($(SKIP_FR_MEANINGS),1)
	$(PY) scripts/parse_wiktionary_via.py --source fr --progress-every 1000
endif
	$(PY) scripts/normalize_entries.py
	$(PY) scripts/infer_morphology.py
	$(PY) scripts/filter_and_validate.py --wiki-top-n 1000
	$(PY) scripts/final_preparation.py
	$(PY) scripts/build_monolingual.py
	$(PY) scripts/build_one_big_bidix_json.py
	$(PY) scripts/report_coverage.py --top 5000
	$(PY) scripts/export_apertium.py
	$(PY) scripts/report_stats.py
	$(PY) scripts/report_io_dump_coverage.py
	$(PY) scripts/report_conflicts.py
	$(PY) scripts/report_big_bidix_stats.py
	$(PY) scripts/build_web_index.py

# Fast regeneration (skip downloads and French meanings parsing)
regenerate-fast:
	$(MAKE) regenerate SKIP_DOWNLOAD=1 SKIP_FR_MEANINGS=1

# Minimal regeneration (skip downloads, French Wiktionary, and French meanings)
regenerate-minimal:
	$(MAKE) regenerate SKIP_DOWNLOAD=1 SKIP_FR_WIKT=1 SKIP_FR_MEANINGS=1

# Compare old vs new dictionaries
compare:
	./compare_dictionaries.sh

freq:
	$(PY) scripts/build_frequency_io_wiki.py

wikt_io:
	$(PY) scripts/process_wiktionary_two_stage.py --source io

wikt_eo:
	$(PY) scripts/process_wiktionary_two_stage.py --source eo

wikt_io-stage1:
	$(PY) scripts/parse_wiktionary_stage1.py --source io

wikt_io-stage2:
	$(PY) scripts/process_wiktionary_stage2.py --source io

wikt_eo-stage1:
	$(PY) scripts/parse_wiktionary_stage1.py --source eo

wikt_eo-stage2:
	$(PY) scripts/process_wiktionary_stage2.py --source eo

wikt_en:
	$(PY) scripts/parse_wiktionary_en.py

wikt_fr:
	$(PY) scripts/parse_wiktionary_fr.py

wiki:
	$(PY) scripts/process_wikipedia_two_stage.py

wiki-stage1:
	$(PY) scripts/process_wikipedia_two_stage.py --skip-stage2

wiki-stage2:
	$(PY) scripts/process_wikipedia_two_stage.py --skip-stage1

align:
	$(PY) scripts/align_bilingual.py

align_pivot:
	$(PY) scripts/align_pivot_en_fr.py --pivot en --out work/bilingual_pivot_en.json
	$(PY) scripts/align_pivot_en_fr.py --pivot fr --out work/bilingual_pivot_fr.json
	$(PY) scripts/merge_with_pivots.py --base work/bilingual_raw.json --pivot-en work/bilingual_pivot_en.json --pivot-fr work/bilingual_pivot_fr.json --out work/bilingual_raw.json

pivot_en:
	$(PY) scripts/build_pivot_from_en.py

pivot_fr:
	$(PY) scripts/build_pivot_from_fr.py --input work/fr_wikt_fr_xx.json

normalize:
	$(PY) scripts/normalize_entries.py

morph:
	$(PY) scripts/infer_morphology.py

mono:
	$(PY) scripts/build_monolingual.py

filter:
	$(PY) scripts/filter_and_validate.py

report:
	$(PY) scripts/report_coverage.py --top 5000

export:
	$(PY) scripts/export_apertium.py

big_bidix:
	$(PY) scripts/build_one_big_bidix_json.py

conflicts:
	$(PY) scripts/report_conflicts.py

big_bidix_stats:
	$(PY) scripts/report_big_bidix_stats.py

web:
	$(PY) scripts/build_web_index.py

stats:
	$(PY) scripts/report_stats.py

dump_coverage:
	$(PY) scripts/report_io_dump_coverage.py

test:
	$(PY) run_tests.py

pipeline-status:
	$(PY) scripts/pipeline_manager.py --status

clean:
	rm -rf $(WORK) $(DIST) $(REPORTS)
	mkdir -p $(WORK) $(DIST) $(REPORTS)
	rm -f $(WORK)/pipeline_state.json


