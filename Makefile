PY=python3

RAW=data/raw
WORK=work
DIST=dist
REPORTS=reports

.PHONY: all regenerate clean freq wikt_io wikt_eo wiki align normalize morph mono filter report export

all: regenerate

regenerate:
	./scripts/download_dumps.sh
	$(PY) scripts/parse_wiktionary_io.py
	$(PY) scripts/parse_wiktionary_eo.py
	$(PY) scripts/extract_wikipedia_io.py
	$(PY) scripts/build_frequency_io_wiki.py
	$(PY) scripts/align_bilingual.py
	$(PY) scripts/normalize_entries.py
	$(PY) scripts/infer_morphology.py
	$(PY) scripts/filter_and_validate.py --wiki-top-n 500
	$(PY) scripts/final_preparation.py
	$(PY) scripts/build_monolingual.py
	$(PY) scripts/report_coverage.py --top 5000
	$(PY) scripts/export_apertium.py

freq:
	$(PY) scripts/build_frequency_io_wiki.py

wikt_io:
	$(PY) scripts/parse_wiktionary_io.py

wikt_eo:
	$(PY) scripts/parse_wiktionary_eo.py

wiki:
	$(PY) scripts/extract_wikipedia_io.py

align:
	$(PY) scripts/align_bilingual.py

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

clean:
	rm -rf $(WORK) $(DIST) $(REPORTS)
	mkdir -p $(WORK) $(DIST) $(REPORTS)


