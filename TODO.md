# TODO - Dictionary Extraction Pipeline

**Last Updated:** October 23, 2025

## 🔴 CRITICAL Issues (From Oct 23, 2025 Session)

### 🔢 0. Number Recognition Testing **[NEW - Oct 23, 2025]**
**Status:** Code complete, needs production testing  
**Priority:** HIGH  
**Time:** 15-30 minutes

- [ ] **Deploy Updated Dictionaries to Production**
  - Updated dictionaries include number recognition fix
  - Deploy to translator APy server
  
- [ ] **Test Number Recognition in Production**
  - Word-based numbers: "un", "du", "tri", "kvar", "kin", etc.
  - Digit-based numbers: "1", "2", "3", "100", "2.5", etc.
  - Compound numbers: "dek tri" (13), "dudek" (20)
  
- [ ] **Verify Both Directions**
  - Ido → Esperanto: "un" → "unu", "1" → "1"
  - Esperanto → Ido: "unu" → "un", "1" → "1"

**Related PR:** komapc/ido-esperanto-extractor (number recognition fix merged)  
**Files Modified:** `scripts/infer_morphology.py`, `scripts/export_apertium.py`

---

### ⚠️ 1. Esperanto Wiktionary Low Coverage **[URGENT]**
**Status:** Investigation needed  
**Priority:** HIGH  
**Impact:** 200-400 potential entries being missed

**Problem:**
- Parser extracts 565 EO Wiktionary entries
- Only **39 have Ido translations** (6.9%)
- Most entries have EN/FR translations but NOT IO
- Huge missed opportunity for quality translations

**Quick Win Solutions:**
- [ ] **Use EN/FR as Via** ⭐ (1-2 hrs implementation)
  - If EO→EN exists and IO→EN exists, infer EO→IO
  - Expected: 200-400 new entries
  - Quality: Medium (via-based)

- [ ] Improve parser to extract more IO sections
- [ ] Manual review of high-value EO entries

---

### 📝 1.5. Document EC2 Pivot Extraction Results **[NEW - Oct 23, 2025]**
**Status:** Analysis needed  
**Priority:** MEDIUM  
**Time:** 30-60 minutes

- [ ] **Analyze EO Wiktionary Results**
  - Why only 39/565 entries have Ido translations?
  - What percentage have EN/FR translations but not IO?
  - Document patterns in missing translations
  
- [ ] **Document EN Wiktionary Pivot Findings**
  - Results from `run-ec2-en-wiktionary.sh` execution
  - Quality assessment of pivot-based translations
  - Comparison with direct translation sources
  
- [ ] **Create Recommendations**
  - Which pivot approaches work best?
  - What filtering thresholds are optimal?
  - Next steps for improving coverage

**Location:** `ec2-extraction-results/reports/`  
**Related Scripts:** `run-ec2-pivot-wiktionary.sh`, `run-ec2-en-wiktionary.sh`

---

### ⚠️ 2. Wikipedia Filtering Too Aggressive **[URGENT]**
**Status:** Analysis needed  
**Priority:** HIGH  
**Impact:** 1,000-3,000 proper nouns being discarded

**Problem:**
- Extracted: 68,015 Wikipedia titles
- Kept after filtering: **0 entries** (100% filtered!)
- Lost: All geographic names, proper nouns, technical terms

**Quick Win Solutions:**
- [ ] **Keep entries with Wikipedia language links** ⭐ (2-3 hrs)
  - These have verified EO translations
  - Expected: 1,000-3,000 proper noun entries
  
- [ ] Implement category-based filtering (keep geographic entities)
- [ ] Use Wikipedia importance scores

---

## 🎯 Current Priorities

### 1. Add More Data Sources
**Status:** Planning
**Priority:** High

#### New Sources to Integrate:

##### High Priority Sources:
- [ ] **English Wiktionary (Ido Section)**
  - Already have dump: `data/raw/enwiktionary-latest-pages-articles.xml.bz2`
  - Parser exists: `scripts/parse_wiktionary_en_fixed.py`
  - Status: Script exists but needs testing/integration
  - Expected: 2,000-5,000 additional entries

- [ ] **Esperanto Wiktionary (full integration)** 🔴 SEE CRITICAL ISSUE #1
  - Parser exists: `scripts/02_parse_eo_wiktionary.py`
  - Status: Only 39/565 entries have IO translations
  - **Problem:** Most have EN/FR but not IO (see Critical Issues above)
  - **Quick Win:** Use pivot approach for 200-400 entries
  - Expected total: 400-600 additional entries

- [ ] **Ido Wiktionary Updates**
  - Re-download latest dump (get newest entries)
  - Compare with current October 2025 dump
  - Expected: 100-500 new entries

##### Medium Priority Sources:
- [ ] **German Wiktionary (Pivot)**
  - Similar to French pivot approach
  - Ido section exists in DE Wiktionary
  - Parser pattern: Copy from `scripts/03_parse_fr_wiktionary.py`
  - Expected: 500-1,000 entries

- [ ] **Idolinguo Dictionary**
  - Manual curated Ido-Esperanto dictionary
  - URL: http://idolinguo.org.uk/vortaro
  - Format: HTML scraping needed
  - Expected: High quality, 1,000-2,000 entries

- [ ] **Wikidata Language Links**
  - Proper noun translations via Wikidata
  - Already have infrastructure in place
  - Needs: Better entity resolution
  - Expected: 5,000-10,000 proper nouns

##### Lower Priority Sources:
- [ ] **Spanish Wiktionary (Pivot)**
  - ES→IO and ES→EO translations
  - Large Wiktionary, good coverage
  - Expected: 800-1,500 entries

- [ ] **Russian Wiktionary (Pivot)**
  - RU→IO and RU→EO translations  
  - Good constructed language coverage
  - Expected: 500-1,000 entries

- [ ] **Italian Wiktionary (Pivot)**
  - IT→IO and IT→EO translations
  - Good romance language pivot
  - Expected: 400-800 entries

#### Questions to Answer:
- Which sources provide the **best quality** translations?
- Should we prioritize **coverage** (more words) or **quality** (better translations)?
- What's the **effort-to-value** ratio for each source?

---

### 2. Optimize Performance
**Status:** Planning
**Priority:** Medium

#### Current Performance (as of Oct 2025):
- Full pipeline: ~60-90 minutes
- IO Wiktionary parse: ~15-20 minutes
- FR Wiktionary parse: ~30-40 minutes (with meanings)
- Merge + export: ~5-10 minutes

#### Optimization Opportunities:

##### High Impact:
- [ ] **Parallel Processing**
  - Parse multiple Wiktionaries simultaneously
  - Use `multiprocessing` for XML parsing
  - Target: 40-60% speedup
  
- [ ] **Smarter Caching**
  - Cache parsed data with checksums
  - Skip reparse if dump unchanged
  - Currently: Basic caching in place
  - Improvement: Add dependency tracking

- [ ] **Optimize Regex Patterns**
  - Pre-compile all patterns (already done)
  - Reduce backtracking in complex patterns
  - Profile and optimize hot paths
  - Target: 10-15% speedup

##### Medium Impact:
- [ ] **Incremental Updates**
  - Only process changed pages
  - Use Wiktionary change logs
  - Skip full reparse if possible
  - Target: 80-90% speedup for updates

- [ ] **Database Backend**
  - Consider SQLite for intermediate data
  - Faster queries and joins
  - Better memory usage
  - Trade-off: Added complexity

- [ ] **Streaming XML Parser**
  - Use `lxml.etree.iterparse()` for large dumps
  - Reduce memory footprint
  - Already partially implemented
  - Improvement: Full streaming pipeline

##### Lower Priority:
- [ ] **Compile Python to Cython**
  - Hot path functions in Cython
  - Expected: 20-30% speedup on hot functions
  - Trade-off: Build complexity

- [ ] **Profile and Optimize**
  - Run profiler to find bottlenecks
  - Optimize top 5 slowest functions
  - Document performance characteristics

#### Target Performance:
- **Current:** 60-90 minutes full pipeline
- **Target:** 20-30 minutes full pipeline
- **Stretch:** <15 minutes with caching

---

## 📋 Next Actions

### ⭐ Quick Wins (Immediate - High Impact, Low Effort)

1. **Implement EO Wiktionary Pivot** 🔴 CRITICAL
   - Time: 1-2 hours
   - Impact: 200-400 new entries
   - Method: Use IO→EN and EO→EN to infer IO→EO
   - Status: Ready to implement

2. **Fix Wikipedia Language Link Filtering** 🔴 CRITICAL
   - Time: 2-3 hours  
   - Impact: 1,000-3,000 proper nouns
   - Method: Keep Wikipedia entries that have EO language links
   - Status: Ready to implement

3. **Document EC2 Extraction Scripts**
   - Time: 1-2 hours
   - Scripts exist: `docs/run-ec2-pivot-wiktionary.sh`
   - Add: Setup guide, troubleshooting, integration process
   - Status: Scripts working, needs docs

### Immediate (This Week)
1. **Test English Wiktionary Parser**
   - Run `scripts/parse_wiktionary_en_fixed.py`
   - Verify output quality
   - Expected: 2,000-5,000 entries
   - Document results in `reports/`

2. **Profile Current Pipeline**
   - Use `cProfile` to identify bottlenecks
   - Document timing for each stage
   - Create performance baseline
   - Current: ~13 minutes full regeneration

3. **Plan Source Priority**
   - Evaluate effort vs value for each source
   - Get feedback on priorities
   - Create implementation roadmap

### Short Term (This Month)
- [ ] Integrate English Wiktionary fully
- [ ] Test and integrate Esperanto Wiktionary
- [ ] Implement parallel Wiktionary parsing
- [ ] Document all new sources in README.md

### Medium Term (Next 3 Months)
- [ ] Add 3-5 new data sources
- [ ] Achieve 2x performance improvement
- [ ] Reach 60,000+ total entries
- [ ] Improve proper noun classification

---

## 🔍 Analysis Needed

**Please clarify:**
1. Which **new sources** are highest priority?
2. Is **performance** or **coverage** more important right now?
3. Do you have specific **sources** in mind we should integrate?
4. What's the **target entry count** for the dictionary?

---

## 🚨 **CRITICAL DATA FLOW ISSUES TO INVESTIGATE** **[NEW - Oct 24, 2025]**

### 🔴 **Issue 1: Esperanto Wiktionary Low Coverage**
**Status:** CRITICAL - Data loss  
**Problem:** Only 39 entries (0.5%) from Esperanto Wiktionary in final output  
**Expected:** Should be 200-400+ entries  
**Impact:** Missing hundreds of high-quality translations  

**Investigation needed:**
- [ ] Check if EO Wiktionary parser is working correctly
- [ ] Verify if entries are being filtered out during normalization
- [ ] Check if entries are lost during morphology inference
- [ ] Compare raw EO Wiktionary output vs final vocabulary

### 🔴 **Issue 2: Wikipedia Complete Filtering** ✅ **SOLVED**
**Status:** SOLVED - Architecture issue identified  
**Problem:** 0 Wikipedia entries in final output despite processing 68,360 titles  
**Root Cause:** Wikipedia entries have no translations, so they're filtered out during normalization  
**Expected:** Should be 1,000-3,000 proper noun entries  
**Impact:** Missing all geographic names, proper nouns, technical terms  

**Investigation Results:**
- [x] **Wikipedia extraction works correctly:** 68,360 titles extracted
- [x] **Filtering works correctly:** 33,169 entries pass validation (48.5%)
- [x] **Root cause found:** Entries filtered out during normalization because they have no translations
- [x] **Architecture issue:** Pipeline designed for bilingual dictionaries only

**Solution Required:**
- [ ] Modify normalization to preserve entries without translations for monolingual dictionary
- [ ] Add separate processing path for Wikipedia proper nouns
- [ ] Ensure Wikipedia entries flow to monolingual dictionary even without translations

### 🔴 **Issue 3: French Meanings Data Flow Issue**
**Status:** CRITICAL - Inconsistent data flow  
**Problem:** 1,001 French meaning entries in BIG BIDIX but 0 in final vocabulary  
**Expected:** French meanings should flow through to final output  
**Impact:** Missing 1,001 high-quality translations  

**Investigation needed:**
- [ ] Check why French meanings don't appear in final_vocabulary.json
- [ ] Verify if French meanings are being filtered out
- [ ] Check merge logic between BIG BIDIX and final vocabulary
- [ ] Ensure French meanings have proper morphology tags

---

## 🔧 **PERFORMANCE & ARCHITECTURE IMPROVEMENTS** **[NEW - Oct 24, 2025]**

### ⚡ **Issue 4: Wikipedia Two-Stage Processing** ✅ **COMPLETED**
**Status:** COMPLETED - Architecture improvement implemented  
**Problem:** Wikipedia processing is monolithic and not resumable  
**Solution:** Two-stage processing with resumability implemented  

**Stage 1: XML → Filtered JSON** ✅
- [x] Convert zipped XML dump to filtered JSON
- [x] Filter by content relevance (skip stubs, redirects, disambiguation)
- [x] Create intermediate artifact: `work/io_wikipedia_filtered.json`
- [x] Enable resumability: if artifact exists, skip Stage 1

**Stage 2: JSON → Final Processing** ✅
- [x] Convert filtered JSON to final parsed/cleaned format
- [x] Include all information needed for BIG BIDIX and MONO
- [x] Create final artifact: `work/io_wikipedia_processed.json`
- [x] Enable resumability: if artifact exists, skip Stage 2

**Results:**
- **Input:** 68,360 Wikipedia articles
- **Stage 1 filtered:** 58,153 relevant articles (85% retention)
- **Stage 2 processed:** 56,094 valid entries (96% of filtered)
- **Performance:** ~20 seconds for Stage 1, ~4 seconds for Stage 2
- **Resumability:** ✅ Both stages can be skipped if output exists

**Benefits Achieved:**
- ✅ Faster development iterations (skip XML parsing)
- ✅ Better debugging (inspect intermediate JSON)
- ✅ Resumable processing (continue from any stage)
- ✅ Cleaner separation of concerns

### ⚡ **Issue 5: Wiktionary Two-Stage Processing** ✅ **COMPLETED**
**Status:** COMPLETED - Architecture improvement implemented  
**Problem:** Wiktionary processing is monolithic and not resumable  
**Solution:** Two-stage processing with resumability implemented  

**Stage 1: XML → Filtered JSON** ✅
- [x] Convert zipped XML dump to filtered JSON
- [x] Filter by content relevance and quality (skip templates, very long lemmas)
- [x] Create intermediate artifacts: `work/{source}_wiktionary_filtered.json`
- [x] Enable resumability: if artifact exists, skip Stage 1

**Stage 2: JSON → Final Processing** ✅
- [x] Convert filtered JSON to final parsed/cleaned format
- [x] Include all information needed for BIG BIDIX and MONO
- [x] Create final artifacts: `work/{source}_wiktionary_processed.json`
- [x] Enable resumability: if artifact exists, skip Stage 2

**Results:**
- **Sources:** Ido and Esperanto Wiktionary
- **Performance:** Faster development iterations
- **Resumability:** ✅ Both stages can be skipped if output exists
- **Testing:** ✅ Comprehensive unit tests implemented

**Benefits Achieved:**
- ✅ Faster development iterations (skip XML parsing)
- ✅ Better debugging (inspect intermediate JSON)
- ✅ Resumable processing (continue from any stage)
- ✅ Cleaner separation of concerns
- ✅ Comprehensive unit testing framework

### ⚡ **Issue 6: Unit Testing Framework** ✅ **COMPLETED**
**Status:** COMPLETED - Testing infrastructure implemented  
**Problem:** No unit testing framework for code quality assurance  
**Solution:** Comprehensive testing framework with proper structure  

**Completed:**
- [x] Create tests/ directory with proper structure
- [x] Add test_wiktionary_simple.py with unit tests
- [x] Add run_tests.py test runner
- [x] Add conftest.py for pytest configuration
- [x] Add fixtures and temp directories for test artifacts
- [x] Integrate test target into Makefile
- [x] Test resumability and basic functionality

**Results:**
- **Test Coverage:** Wiktionary two-stage processing
- **Test Runner:** Automated test execution
- **CI/CD Ready:** Structured for automated testing
- **Quality Assurance:** Catch regressions early

### ⚡ **Issue 7: Regex Performance Optimization**
**Status:** COMPLETED - Performance improvement  
**Problem:** Regex patterns compiled repeatedly in hot paths  
**Solution:** Precompile all regex patterns at module level  

**Completed:**
- [x] Add MDC rule for precompiled regex
- [x] Update export_apertium.py with precompiled patterns
- [x] Verify all regex in exporter are precompiled
- [x] Consolidate duplicate template parsing logic into utils/template_parser.py

---

## 📊 Success Metrics

- **Dictionary Size:** Target 60,000+ entries (currently ~50,000)
- **Quality:** Maintain or improve translation accuracy
- **Performance:** <30 minutes for full pipeline
- **Sources:** 8+ data sources integrated
- **Coverage:** 95%+ of common vocabulary

---

## 🛠️ Technical Notes

### Adding a New Source (Template)

1. **Create Parser Script**
   - Copy template from `scripts/03_parse_fr_wiktionary.py`
   - Adapt to new source format
   - Output standardized JSON

2. **Update Merge Logic**
   - Add source to `scripts/10_merge.py` auto-discovery
   - Set source priority in config
   - Test merge conflicts

3. **Add Tests**
   - Create test data sample
   - Verify parser output
   - Test merge behavior

4. **Document**
   - Update README.md
   - Add source statistics to reports
   - Document any special handling

### Performance Optimization Checklist
- [ ] Profile with cProfile
- [ ] Identify top 5 bottlenecks
- [ ] Optimize hot paths first
- [ ] Measure improvement
- [ ] Document in reports/

---

## 📚 Resources

- Parser templates: `scripts/01_parse_io_wiktionary.py`, `scripts/03_parse_fr_wiktionary.py`
- Merge logic: `scripts/10_merge.py`
- Config: `config.json`
- Makefile: `Makefile` (pipeline orchestration)
- EC2 Scripts: `docs/run-ec2-pivot-wiktionary.sh`

---

## 📊 Recent Session Summary (Oct 23, 2025)

**Completed:**
- ✅ Full regeneration with French meanings (1,001 entries)
- ✅ Improved markup cleaning (bold preserved, templates handled)
- ✅ Wiki-top-n increased to 1000
- ✅ All PRs merged (#18 extractor, #10 vortaro, #49 apertium-ido-epo)
- ✅ Major dictionary improvements merged (feature/regenerate-fast-oct2025)
- ✅ Runtime: ~13 minutes (optimized)

**Discovered Issues:**
- 🔴 EO Wiktionary: Only 39/565 entries have IO translations
- 🔴 Wikipedia: 0/68,015 titles kept (too aggressive filtering)
- ℹ️ EN Wiktionary: Parser exists but not in production

**Current Stats:**
- Total entries: 8,359 (BIG BIDIX)
- Sources: IO Wiktionary (7,321), FR meanings (1,001), EO Wiktionary (39)
- Pipeline time: ~13 minutes full regeneration

**Next Focus:**
1. Fix EO Wiktionary pivot (200-400 entries)
2. Fix Wikipedia filtering (1,000-3,000 entries)
3. Integrate EN Wiktionary (2,000-5,000 entries)



