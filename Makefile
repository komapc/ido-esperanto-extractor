PY=python3

RAW=data/raw
WORK=work
DIST=dist
REPORTS=reports

# Skip flags (set to 1 to skip)
SKIP_DOWNLOAD ?= 0
SKIP_EN_WIKT ?= 1
SKIP_FR_WIKT ?= 0
SKIP_FR_MEANINGS ?= 0

.PHONY: all regenerate regenerate-fast regenerate-minimal clean freq wikt_io wikt_eo wikt_en wiki align align_pivot normalize morph mono filter report export stats dump_coverage big_bidix conflicts big_bidix_stats web pivot_en pivot_fr compare

all: regenerate

# Full regeneration with all sources
regenerate:
ifneq ($(SKIP_DOWNLOAD),1)
	./scripts/download_dumps.sh
endif
	$(PY) scripts/parse_wiktionary_io.py
	$(PY) scripts/parse_wiktionary_eo.py
ifneq ($(SKIP_FR_WIKT),1)
	$(PY) scripts/parse_wiktionary_fr.py
endif
	$(PY) scripts/extract_wikipedia_io.py
	$(PY) scripts/build_frequency_io_wiki.py
	$(PY) scripts/align_bilingual.py
	$(PY) scripts/align_pivot_en_fr.py --pivot en --out work/bilingual_pivot_en.json
	$(PY) scripts/align_pivot_en_fr.py --pivot fr --out work/bilingual_pivot_fr.json
	# $(PY) scripts/build_pivot_from_en.py  # Skipped: requires English Wiktionary
	# $(PY) scripts/merge_with_pivots.py --base work/bilingual_raw.json --pivot-en work/bilingual_pivot_en.json --pivot-fr work/bilingual_pivot_fr.json --out work/bilingual_raw.json  # Skipped: depends on build_pivot_from_en.py
	$(PY) scripts/normalize_entries.py
	$(PY) scripts/infer_morphology.py
	$(PY) scripts/filter_and_validate.py --wiki-top-n 1000
	$(PY) scripts/final_preparation.py
ifneq ($(SKIP_FR_MEANINGS),1)
	$(PY) scripts/parse_fr_wiktionary_meanings.py -v --progress-every 10000
endif
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
	$(PY) scripts/parse_wiktionary_io.py

wikt_eo:
	$(PY) scripts/parse_wiktionary_eo.py

wikt_en:
	$(PY) scripts/parse_wiktionary_en.py

wikt_fr:
	$(PY) scripts/parse_wiktionary_fr.py

wiki:
	$(PY) scripts/extract_wikipedia_io.py

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

clean:
	rm -rf $(WORK) $(DIST) $(REPORTS)
	mkdir -p $(WORK) $(DIST) $(REPORTS)


