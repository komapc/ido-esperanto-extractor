# Via Translations in Final Output - Explained
**Date:** October 23, 2025

## What Are "Via" Translations?

**Via translations** are Ido↔Esperanto word pairs discovered through an intermediate language.

### Example

**English Wiktionary page for "dog":**
```
dog (English noun)

Translations:
- Ido: hundo
- Esperanto: hundo
```

**From this, we infer:** `hundo (io) ↔ hundo (eo)` [via English]

We didn't find this directly in Ido or Esperanto Wiktionary, but through English as an intermediary.

---

## Current Sources in BIG_BIDIX

**Checking your current output:**
```
"en_pivot"  ← English pivot (726 entries)
"fr_pivot"  ← French pivot (114 entries)
```

These are translations found VIA English/French.

---

## Question: Where Should Via Translations Go?

### Option 1: Include in BIG_BIDIX ✅ (CURRENT)

**BIG_BIDIX.json contains ALL translations:**
```json
{
  "lemma": "hundo",
  "senses": [
    {
      "translations": [
        {"lang": "eo", "term": "hundo", "sources": ["io_wiktionary"]},
        {"lang": "eo", "term": "hundo", "sources": ["en_wiktionary_via"]},
        {"lang": "eo", "term": "ĉeno", "sources": ["fr_wiktionary_via"]}
      ]
    }
  ]
}
```

**Pros:**
- ✅ Complete dataset in one place
- ✅ Users can see all possible translations
- ✅ Source tags distinguish quality (direct vs via)

**Cons:**
- ❌ More entries (may include lower-quality translations)
- ❌ Need to filter by source if you want only direct translations

---

### Option 2: Separate File (ALTERNATIVE)

**Two outputs:**
```
BIG_BIDIX.json          ← Only direct translations (io_wiktionary, eo_wiktionary, wikipedia)
BIG_BIDIX_with_via.json ← Direct + via translations
```

**Pros:**
- ✅ Clean separation of high-quality (direct) vs supplementary (via)
- ✅ Easy to use only direct translations
- ✅ Can still access via when needed

**Cons:**
- ❌ Two files to maintain
- ❌ Users need to know which to use

---

### Option 3: Source-Specific Files (GRANULAR)

**Multiple outputs:**
```
BIG_BIDIX_direct.json       ← io_wiktionary + eo_wiktionary + wikipedia
BIG_BIDIX_via_en.json       ← English via translations only
BIG_BIDIX_via_fr.json       ← French via translations only
BIG_BIDIX_complete.json     ← Everything combined
```

**Pros:**
- ✅ Maximum flexibility
- ✅ Can cherry-pick sources

**Cons:**
- ❌ Too many files (confusing)
- ❌ Overkill for most use cases

---

## My Recommendation: Option 1 (Current Approach)

**Keep via translations in BIG_BIDIX**, but with clear source tagging:

### Why?

1. **One source of truth** - Everything in BIG_BIDIX
2. **Source tags provide quality info**
   - `io_wiktionary` = High quality (direct)
   - `en_wiktionary_via` = Medium quality (via English)
   - `fr_wiktionary_via` = Medium quality (via French)

3. **Downstream tools can filter**
   ```python
   # Want only direct translations?
   direct_only = [t for t in translations 
                  if not any('via' in s for s in t['sources'])]
   
   # Want everything?
   all_translations = translations
   ```

4. **Vortaro can show source badges**
   - Direct sources get one badge (📕 IO)
   - Via sources get different badge (🔀 VIA EN)

---

## Implementation

### Current State
```json
{
  "sources": ["en_pivot", "fr_pivot"]  ← Confusing names
}
```

### After Renaming
```json
{
  "sources": ["en_wiktionary_via", "fr_wiktionary_via"]  ← Clear!
}
```

### In Vortaro
```javascript
// Badge display
if (source === 'io_wiktionary') {
    return '📕 IO';  // Direct
} else if (source === 'en_wiktionary_via') {
    return '🔀 EN';  // Via English
} else if (source === 'fr_wiktionary_via') {
    return '🔀 FR';  // Via French
}
```

---

## Answer to Your Question

**"Via translations in final output" - What this means:**

**Question:** Should translations discovered VIA intermediate languages (English/French) be included in the main BIG_BIDIX output, or should they be in a separate file?

**My Answer:** 
✅ **Include them in BIG_BIDIX** with clear source tags (`en_wiktionary_via`, `fr_wiktionary_via`)

**Why?**
- Single comprehensive dataset
- Source tags indicate quality/provenance
- Downstream tools can filter as needed
- More translations = better coverage

**But you can filter them out if needed:**
```python
# Only want direct translations?
direct = [e for e in bidix if not any('via' in s for s in e.get('sources', []))]
```

---

## Summary

**Decision needed:**
1. ✅ **Include via in BIG_BIDIX** (recommended)
2. ⬜ **Separate file for via translations**
3. ⬜ **Multiple source-specific files**

**Current setup:** Already using Option 1, just needs renaming (pivot → via)

**No code changes needed** - just renaming for clarity!

