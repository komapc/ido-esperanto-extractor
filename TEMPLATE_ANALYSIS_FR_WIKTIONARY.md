# Template Analysis: French Wiktionary
**Date:** October 23, 2025

## Summary

Analysis of French Wiktionary to evaluate "via French" translations for Ido↔Esperanto pairs.

**Result:** ✅ **No templates to fix** - French uses definition matching, not translation templates.

**Data quality:** ⚠️ **1,050 pairs** - Much smaller than expected, moderate quality.

---

## Key Finding: Completely Different Architecture

### French Wiktionary Structure

**Unlike English/Ido/Esperanto Wiktionaries:**
- NO translation sections with `{{t|lang|word}}` templates
- NO `{{sense}}` or `{{qualifier}}` in translations
- NO template parsing issues!

**Instead:** Ido and Esperanto words appear on **the same page** with French definitions.

### Example: `enciklopedio`

🔗 https://fr.wiktionary.org/wiki/enciklopedio

```wiki
== {{langue|eo}} ==
=== {{S|nom|eo}} ===
'''enciklopedio'''
# [[encyclopédie|Encyclopédie]].

== {{langue|io}} ==
=== {{S|nom|io}} ===
'''enciklopedio'''
# [[encyclopédie|Encyclopédie]].
```

**Extraction logic:**
1. Page title: `enciklopedio`
2. Has both `{{langue|eo}}` (Esperanto) AND `{{langue|io}}` (Ido) sections
3. Both sections have French definition: `encyclopédie`
4. **Inference:** IO `enciklopedio` ↔ EO `enciklopedio`

---

## Comparison: French vs. English Wiktionary

| Aspect | English Wiktionary | French Wiktionary |
|--------|-------------------|-------------------|
| **Structure** | English word → translations in many languages | Each language on separate page |
| **Translation format** | `{{t\|eo\|word}}` templates | French definitions link pages |
| **Template issues** | ✅ YES - 95% truncated | ❌ NO - no translation templates |
| **Extraction method** | Parse translation templates | Match by French definition |
| **Parser complexity** | HIGH (template parsing) | MEDIUM (section matching) |
| **Data quality** | Medium (via intermediate) | Medium (definition matching) |
| **Potential yield** | ~600-800 pairs | ~1,050 pairs (actual) |

---

## French Wiktionary Data

### What We Have

```
fr_wikt_meanings.json: 1,050 entries
```

**Sample entries:**

| IO Word | EO Word | French Definition | Source |
|---------|---------|-------------------|--------|
| `enciklopedio` | `enciklopedio` | Encyclopédie | `fr_wiktionary_meaning` |
| `stulo` | `seĝo` | Siège avec dossier | `fr_wiktionary_meaning` |
| `ucelo` | `birdo` | Volatile | `fr_wiktionary_meaning` |
| `jovdio` | `ĵaŭdo` | Jour de la semaine | `fr_wiktionary_meaning` |

### Extraction Process

**Current implementation:** `scripts/parse_fr_wiktionary_meanings.py`

```python
# For each page in French Wiktionary:
1. Check if page has BOTH {{langue|io}} AND {{langue|eo}} sections
2. Extract French definition from each section
3. If definitions match → create IO↔EO pair
4. Source: "fr_wiktionary_meaning"
5. Confidence: 0.7 (moderate - based on definition matching)
```

---

## Template Inventory (Non-Translation)

Since French Wiktionary doesn't use translation templates, here are the templates it DOES use:

### Language/Section Templates

| Template | Usage | Example |
|----------|-------|---------|
| `{{langue\|eo}}` | Language section header | `== {{langue|eo}} ==` |
| `{{langue\|io}}` | Language section header | `== {{langue|io}} ==` |
| `{{S\|nom\|eo}}` | Part of speech (noun) | `=== {{S|nom|eo}} ===` |
| `{{S\|étymologie}}` | Etymology section | `=== {{S|étymologie}} ===` |

**Resolution:** **PARSE** - needed to identify Ido/Esperanto sections

### Link Templates

| Template | Usage | Example | Resolution |
|----------|-------|---------|------------|
| `{{lien\|word\|eo}}` | Link to Esperanto word | `{{lien|birdo|eo}}` | **PARSE** - extract word |
| `{{WP\|word\|lang=eo}}` | Wikipedia link | `{{WP|enciklopedio\|lang=eo}}` | **IGNORE** - external link |

### Pronunciation Templates

| Template | Usage | Resolution |
|----------|-------|------------|
| `{{pron\|...}}` | Pronunciation guide | **IGNORE** - metadata |
| `{{écouter\|...}}` | Audio pronunciation | **IGNORE** - metadata |
| `{{eo-flexions\|...}}` | Esperanto inflections | **IGNORE** - grammatical |
| `{{io-rég\|...}}` | Ido register | **IGNORE** - metadata |

### Reference Templates

| Template | Usage | Resolution |
|----------|-------|------------|
| `{{R:PV}}`, `{{R:PIV}}`, etc. | Dictionary references | **IGNORE** - bibliography |
| `{{R:Retavort}}` | Retavortaro reference | **IGNORE** - external source |

---

## Quality Assessment

### Current Data: 1,050 Pairs

**Method:** Definition matching (both Ido and Esperanto on same page)

**Quality indicators:**
- ✅ **High precision:** If both languages are on same page with same definition, likely correct
- ⚠️ **Moderate coverage:** Only 1,050 pairs found
- ✅ **No template issues:** Clean extraction, no truncation
- ⚠️ **Confidence: 0.7:** Lower than direct translations (0.9+)

### Why So Few Pairs?

**Scanned:** 1.26 million pages  
**Found:** 1,050 with both IO and EO sections

**Reasons for low count:**
1. **Small language coverage:** Ido and Esperanto are minor constructed languages
2. **Separate pages:** Most words have EITHER Ido OR Esperanto, not both
3. **No direct translations:** French Wiktionary doesn't have translation tables like English does

### Comparison to Other Sources

```
io_wiktionary           45,093 entries  ✅ Direct IO→EO
eo_wiktionary              983 entries  ✅ Direct EO→IO
io_wikipedia            77,808 entries  ✅ Direct IO↔EO
fr_wiktionary_meaning    1,050 entries  ⚠️ Via French definition
en_wiktionary_via        ~600-800 est.  ❌ 95% broken templates

Total direct:          123,884 entries
Total via (working):     1,050 entries  (0.8% of total)
```

---

## Analysis: Keep or Disable?

### Arguments for KEEPING French Via

✅ **No parser fix needed** - works correctly already  
✅ **Clean data** - no template truncation issues  
✅ **Low maintenance** - simple definition matching  
✅ **Already implemented** - `parse_fr_wiktionary_meanings.py` works  

### Arguments for DISABLING French Via

❌ **Very low yield:** 1,050 pairs (0.8% of total)  
❌ **Lower confidence:** 0.7 vs. 0.9+ for direct translations  
❌ **Indirect matching:** Based on French definitions, not explicit translations  
❌ **Processing cost:** Must scan 1.26M pages for 1K results  

---

## Recommendation

### Option 1: KEEP (Suggested)

**Rationale:**
- Already works correctly
- No template issues to fix
- Low maintenance burden
- Adds 1,050 unique pairs (0.8% boost)
- Processing cost acceptable (runs once during regeneration)

**Conditions:**
- Mark confidence as 0.7 (moderate)
- Keep source tag: `fr_wiktionary_meaning`
- Document method in README
- Monitor for false positives

### Option 2: DISABLE

**Rationale:**
- Very low yield (1,050 pairs)
- Indirect quality (definition matching)
- Focus on direct sources only

**Impact:**
- Lose 0.8% of entries
- Cleaner pipeline (fewer sources)
- Faster regeneration

---

## Decision Matrix

|  | English Via | French Via |
|---|-------------|------------|
| **Works correctly?** | ❌ NO (95% broken) | ✅ YES |
| **Template issues?** | ✅ YES (truncation) | ❌ NO |
| **Fix effort** | 4-6 hours | 0 hours ✅ |
| **Yield** | ~600-800 pairs | 1,050 pairs |
| **Quality** | Medium (if fixed) | Medium |
| **Maintenance** | High | Low ✅ |
| **Recommendation** | **DISABLE** ❌ | **KEEP** ✅ |

---

## Templates Resolution Table

### Structural Templates (Must Parse)

| Template | Count | Purpose | Resolution |
|----------|-------|---------|------------|
| `{{langue\|io}}` | High | Identify Ido section | **PARSE** |
| `{{langue\|eo}}` | High | Identify Esperanto section | **PARSE** |
| `{{S\|nom\|lang}}` | High | Part of speech | **PARSE** |
| `{{lien\|word\|lang}}` | Medium | Internal link | **PARSE** (extract word) |

### Metadata Templates (Ignore)

| Template | Count | Purpose | Resolution |
|----------|-------|---------|------------|
| `{{pron\|...}}` | High | Pronunciation | **IGNORE** |
| `{{écouter\|...}}` | Medium | Audio | **IGNORE** |
| `{{eo-flexions\|...}}` | High | Inflection table | **IGNORE** |
| `{{io-rég\|...}}` | Medium | Register info | **IGNORE** |
| `{{R:...}}` | High | References | **IGNORE** |
| `{{WP\|...}}` | Medium | Wikipedia link | **IGNORE** |
| `{{ébauche-étym\|...}}` | High | Etymology stub | **IGNORE** |

---

## No Action Needed

**Conclusion:** French Wiktionary via translations:
- ✅ Work correctly (no template parsing)
- ✅ Provide 1,050 clean pairs
- ✅ Low maintenance
- ✅ **RECOMMENDATION: KEEP**

**No parser changes needed.** Current implementation is functional.

---

## Final Comparison: All Via Sources

### English Via (DISABLED ❌)
- **Broken:** 95% template truncation
- **Yield:** ~600-800 pairs
- **Fix cost:** 4-6 hours
- **Status:** ❌ Disabled in Makefile

### French Via (WORKING ✅)
- **Functional:** Clean definition matching
- **Yield:** 1,050 pairs
- **Fix cost:** 0 hours
- **Status:** ✅ Can keep enabled

---

## Examples: French Wiktionary Pages

### 1. `enciklopedio` - Exact match
🔗 https://fr.wiktionary.org/wiki/enciklopedio

Both IO and EO sections have same word and definition → High confidence

### 2. `stulo` (IO) → `seĝo` (EO)
🔗 https://fr.wiktionary.org/wiki/stulo

Different IO/EO words, same French definition "Siège" → Correct translation via meaning

### 3. `ucelo` (IO) → `birdo` (EO)
🔗 https://fr.wiktionary.org/wiki/ucelo

Different words, definition "Volatile" (bird) → Correct via French

### 4. `jovdio` (IO) → `ĵaŭdo` (EO)
🔗 https://fr.wiktionary.org/wiki/jovdio

Both mean "Thursday" in French → Correct via definition

### 5. `laboro` - Exact match
🔗 https://fr.wiktionary.org/wiki/laboro

Same word in both languages, definition "Travail" (work) → High confidence

---

## Summary

| Aspect | English Wiktionary | French Wiktionary |
|--------|-------------------|-------------------|
| **Templates to analyze** | ✅ YES - many | ❌ NO - none for translations |
| **Parser broken** | ✅ YES - 95% fail | ❌ NO - works fine |
| **Resolution needed** | ✅ YES - rewrite parser | ❌ NO - already works |
| **Recommendation** | **DISABLE** ❌ | **KEEP** ✅ |

**Decision:** Keep French via enabled, disable English via.

