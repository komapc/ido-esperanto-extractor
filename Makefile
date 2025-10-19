PY=python3

RAW=data/raw
WORK=work
DIST=dist
REPORTS=reports

.PHONY: all regenerate clean freq wikt_io wikt_eo wikt_en wiki align align_pivot normalize morph mono filter report export stats dump_coverage big_bidix conflicts big_bidix_stats

all: regenerate

regenerate:
	./scripts/download_dumps.sh
	$(PY) scripts/parse_wiktionary_io.py
	$(PY) scripts/parse_wiktionary_eo.py
	$(PY) scripts/extract_wikipedia_io.py
	$(PY) scripts/build_frequency_io_wiki.py
	$(PY) scripts/align_bilingual.py
	$(PY) scripts/align_pivot_en_fr.py --pivot en --out work/bilingual_pivot_en.json
	$(PY) scripts/align_pivot_en_fr.py --pivot fr --out work/bilingual_pivot_fr.json
	$(PY) scripts/merge_with_pivots.py --base work/bilingual_raw.json --pivot-en work/bilingual_pivot_en.json --pivot-fr work/bilingual_pivot_fr.json --out work/bilingual_raw.json
	$(PY) scripts/normalize_entries.py
	$(PY) scripts/infer_morphology.py
	$(PY) scripts/filter_and_validate.py --wiki-top-n 500
	$(PY) scripts/final_preparation.py
	$(PY) scripts/build_monolingual.py
	$(PY) scripts/build_one_big_bidix_json.py
	$(PY) scripts/report_coverage.py --top 5000
	$(PY) scripts/export_apertium.py
	$(PY) scripts/report_stats.py
	$(PY) scripts/report_io_dump_coverage.py
	$(PY) scripts/report_conflicts.py
	$(PY) scripts/report_big_bidix_stats.py

freq:
	$(PY) scripts/build_frequency_io_wiki.py

wikt_io:
	$(PY) scripts/parse_wiktionary_io.py

wikt_eo:
	$(PY) scripts/parse_wiktionary_eo.py

wikt_en:
	$(PY) scripts/parse_wiktionary_en.py

wiki:
	$(PY) scripts/extract_wikipedia_io.py

align:
	$(PY) scripts/align_bilingual.py

align_pivot:
	$(PY) scripts/align_pivot_en_fr.py --pivot en --out work/bilingual_pivot_en.json
	$(PY) scripts/align_pivot_en_fr.py --pivot fr --out work/bilingual_pivot_fr.json
	$(PY) scripts/merge_with_pivots.py --base work/bilingual_raw.json --pivot-en work/bilingual_pivot_en.json --pivot-fr work/bilingual_pivot_fr.json --out work/bilingual_raw.json

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

stats:
	$(PY) scripts/report_stats.py

dump_coverage:
	$(PY) scripts/report_io_dump_coverage.py

clean:
	rm -rf $(WORK) $(DIST) $(REPORTS)
	mkdir -p $(WORK) $(DIST) $(REPORTS)


