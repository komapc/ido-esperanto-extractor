# Ido ↔ Esperanto Dictionary Regeneration Plan

## Goals
- Rebuild Ido monolingual and Ido↔Esperanto bilingual dictionaries from reproducible pipelines.
- Source data from Wiktionary (Ido, Esperanto), Wikipedia (Ido), and Wikidata as needed.
- Produce artifacts suitable for Apertium: monodix (`apertium-ido.ido.dix`) and bidix (`apertium-ido-epo.ido-epo.dix`).
- Capture morphology, senses, and provenance. Ensure outputs are validated, sorted, and test-covered.

## High-level Pipeline (Script-per-Stage)
1. Acquire dumps (`scripts/download_dumps.sh`)
2. Parse and extract lexicons (`scripts/parse_wiktionary_io.py`, `scripts/parse_wiktionary_eo.py`, `scripts/extract_wikipedia_io.py`)
3. Build frequencies (`scripts/build_frequency_io_wiki.py`)
4. Align translations (IO→EO and EO→IO) (`scripts/align_bilingual.py`)
5. Enrich with morphology and sense/provenance (`scripts/infer_morphology.py`)
6. Consolidate and normalize (`scripts/normalize_entries.py`)
7. Filter and QA (`scripts/filter_and_validate.py`, `scripts/report_coverage.py`)
8. Export Apertium dictionaries (monodix + bidix) (`scripts/export_apertium.py`)
9. Report, version, and open PR (no commit to Apertium repo in this step)

---

## 1) Data Acquisition
- Ido Wiktionary dump: `iowiktionary-latest-pages-articles.xml.bz2`
- Esperanto Wiktionary dump: `eowiktionary-latest-pages-articles.xml.bz2`
- Ido Wikipedia dump: `iowiki-latest-pages-articles.xml.bz2`
- Ido Wikipedia langlinks (optional): `iowiki-latest-langlinks.sql.gz`
- Wikidata: on-demand via API + cached to `wikidata_cache.json`

Automation:
- Add a `scripts/download_dumps.sh` that downloads latest dumps (non-interactive, resumable).
- Pin dump date in a `data/sources.toml` with sha256 sums for reproducibility.

Outputs:
- Store raw dumps under `ido-esperanto-extractor/data/raw/` with date stamps.

## 2) Parsing & Extraction

### 2.1 Ido Wiktionary → IO lexicon with EO translations
- Parse page markup: extract lemma, POS, senses, inflection/morph hints, translation tables.
- Keep entries where translations include Esperanto.
- Record:
  - lemma, pos, sense gloss (when available)
  - target translation(s) in Esperanto
  - morphology hints (gender, number, verb forms)
  - provenance: page title, revision id, section anchors

Artifacts:
- `work/io_wikt_io_eo.json` (canonical entry schema; see Data Model below)

### 2.2 Esperanto Wiktionary → EO lexicon with IO translations
- Same process as above but inverted (EO headwords, IO translations).
- Artifacts: `work/eo_wikt_eo_io.json`

### 2.3 Ido Wikipedia → Named entities & domain vocabulary
- Extract titles, redirects, categories for vocabulary candidates.
- Use existing filters (as in current code) to exclude noise (dates, maintenance pages, templates).
- Enrich via langlinks and/or Wikidata for EO equivalents.
- Artifacts: 
  - `work/io_wiki_vocab.json` (categorized: person, geo, org, other)
  - `work/io_wiki_align_eo.json` (aligned to EO labels/titles where possible)

### 2.4 Wikidata (optional)
- For ambiguous or missing mappings, query labels/aliases in IO/EO, sitelinks, and P/Q types.
- Cache responses; rate-limit.
- Artifacts: `work/wikidata_enrichment.json`

### 2.5 Wikipedia Frequency Analysis
- Build frequency lists from Ido Wikipedia (existing code can be reused).
- Normalize tokens (casefolding, punctuation stripping, lemmatization where feasible).
- Use frequencies to prioritize coverage and validate that high-utility words are included.
- Artifacts:
  - `work/io_wiki_frequency.json` (token → freq, rank)
  - `reports/frequency_coverage.md` (top-N coverage and missing-high-frequency list)

## 3) Alignment & Consolidation
- Merge IO→EO pairs from Ido Wiktionary with EO→IO from Esperanto Wiktionary.
- Reconcile conflicts:
  - Prefer symmetrical pairs appearing in both directions.
  - Rank by provenance (Wiktionary > Wikipedia > Wikidata label-only).
  - Preserve multiple senses with sense ids where available.
- Integrate Wikipedia/Wikidata entries primarily for proper nouns and technical terms.
 - Identical-form heuristic (IO = EO): When the lemma string is identical in Ido and Esperanto Wiktionary, consider adding the pair if safe. Safety guards:
   - POS matches between IO and EO entries.
   - English translation sets (from each page's translation tables) intersect strongly or match exactly.
   - Not on a curated false-friends list.
   - Morphological compatibility (where relevant).
  After safety checks pass:
  - Confidence boost: increase the pair's confidence score because two independent sources corroborate the mapping (exact boost is configurable; capped at 1.0). This prioritizes these pairs in ranking and reduces the chance they are filtered out by confidence thresholds.
  - Dual provenance recorded: append two provenance entries to the item — one for Ido Wiktionary and one for Esperanto Wiktionary — including page title, revision id, and section anchor. This enables traceability, auditing, and automatic revalidation if either source page changes.

Artifacts:
- `work/bilingual_raw.json` (list of sense-annotated pairs)

## 4) Morphology & Lexical Modeling

### 4.1 Data Model (JSON)
Each entry should conform to:
```json
{
  "id": "io:lemma:pos[:senseId]",
  "lemma": "...",
  "pos": "noun|verb|adj|adv|propn|...",
  "language": "io|eo",
  "senses": [
    {
      "senseId": "wikt-<page>#<anchor>" ,
      "gloss": "...",
      "translations": [
        { "lang": "eo", "term": "...", "confidence": 0.0-1.0, "source": "io_wiktionary|eo_wiktionary|wikipedia|wikidata" }
      ]
    }
  ],
  "morphology": {
    "paradigm": "n-...|v-...|adj-...",
    "features": { "gender": null|"m/f/n", "number": "sg|pl|both", "transitivity": "tr|intr|both", "degree": "pos|cmp|sup" }
  },
  "provenance": [ { "source": "...", "page": "...", "rev": "..." } ]
}
```

### 4.2 Morphology Inference
- Derive paradigms using rules from existing `add_morphology.py` and improved heuristics:
  - Nouns: detect regular plural, gender markers; map to Apertium noun paradigms.
  - Verbs: detect infinitive, past/present/future markers; transitivity if indicated.
  - Adjectives/adverbs: degree, derivational relationships.
- Validate lemma–stem consistency.
- For proper nouns: limited morphology; ensure capitalization rules.

Artifacts:
- `work/bilingual_with_morph.json`

## 5) Normalization
- Canonicalize orthography and whitespace.
- Deduplicate by (lemma, pos, translation, sense/gloss).
- Sort by lemma for deterministic output.
- Keep provenance chains for auditability.

Artifacts:
- `work/bilingual_normalized.json`

## 6) Filtering & QA
- Filters:
  - Remove translation pairs failing POS compatibility.
  - Exclude categories flagged as non-lexical (dates, templates, disambiguations).
  - Threshold by confidence; demote single-source weak matches unless high-need.
- QA checks:
  - Schema validation.
  - Consistency: lemma vs paradigm, duplicates, conflicting senses.
  - Coverage reports: counts by POS, new vs existing lexicon deltas.
  - Sample-based human review lists.
  - Frequency coverage: ensure top-N Ido Wikipedia tokens (by rank threshold) are present or explicitly justified; produce missing-high-frequency report.

Artifacts:
- `reports/coverage.md`, `reports/conflicts.md`, `reports/samples.json`

## 7) Export to Apertium

### 7.1 Monodix (Ido)
- Generate `apertium-ido.ido.dix` with paradigms and entries from IO side.
- Ensure alphabetical ordering and zero validator errors (`xmllint`).

### 7.2 Bidix (Ido–Esperanto)
- Generate `apertium-ido-epo.ido-epo.dix` with sense-aware links, prioritizing symmetrical, high-confidence pairs.
- Emit `<par n="...">` usage consistent with monodix.

Validation:
- `make test` in project root.
- Run Apertium sample translations; compare to baseline.

Artifacts:
- `dist/apertium-ido.ido.dix`
- `dist/apertium-ido-epo.ido-epo.dix`

## 8) Reproducibility, Versioning, and PR Flow
- All steps runnable via `make regenerate` orchestrating the stage scripts (or a new orchestrator script) with pinned dump dates.
- Store metadata (dump dates, SHAs) in `data/sources.toml` and copy into `reports/run_metadata.json`.
- Commit artifacts to a feature branch and open PR; never push to main directly.
- Do not commit the generated Apertium `.dix` files to the Apertium repos as part of this pipeline; export them to `dist/` for manual review and a separate PR process.

---

## Implementation Plan (Incremental)
1. New `scripts/download_dumps.sh` + `data/sources.toml`
2. Robust Wiktionary parsers (IO and EO) → unified JSON
3. Wikipedia extraction refresh and filters (reuse/improve existing code)
4. Wikipedia frequency analysis and coverage reports
5. Alignment + normalization (`scripts/align_bilingual.py`, `scripts/normalize_entries.py`)
6. Morphology inference (`scripts/infer_morphology.py`)
7. QA and reporting (`scripts/filter_and_validate.py`, `scripts/report_coverage.py`)
8. Exporters to Apertium monodix/bidix (`scripts/export_apertium.py`)
9. Orchestrator (`make regenerate`) and end-to-end dry run

## Deprecations & Cleanup
- Mark legacy scripts as deprecated if superseded by new pipeline modules:
  - `create_ido_monolingual.py`, `create_ido_epo_bilingual.py`, `merge_dictionaries.py`, `full_merge.py`, and ad-hoc add_* scripts
- Keep them for reference during transition; remove once new pipeline passes QA.

## Dictionary Artifacts (Three Outputs)
- Ido monolingual dictionary (JSON/YAML): `dist/ido_dictionary.json` (and `.yaml`)
- Esperanto monolingual dictionary (JSON/YAML): `dist/esperanto_dictionary.json` (and `.yaml`)
- Bilingual Ido–Esperanto dictionary (JSON/YAML): `dist/bilingual_io_eo.json` (and `.yaml`)

Merging Logic:
- A dedicated merger script `scripts/merge_dictionaries.py` accepts multiple JSON/YAML inputs and resolves conflicts deterministically (preference rules, provenance-aware, sense-preserving).
- The merger is used both for bilingual alignment and final consolidation before export.

## Ideas to Expand Further
- Sense alignment scoring using gloss similarity (idf-weighted token overlap) to prefer best pairings.
- Derivational morphology graph to propagate paradigms across families.
- Named entity linker using Wikidata types to better segment propn vs common noun.
- Confidence calibration from multi-source agreement and historical acceptance.
- Continuous nightly rebuild with pinned dumps for traceability.

## Deliverables
- Plan (this document)
- New pipeline scripts and `Makefile` targets
- Rebuilt `apertium-ido.ido.dix` and `apertium-ido-epo.ido-epo.dix`
- QA reports and run metadata
- PR summarizing changes and impact
