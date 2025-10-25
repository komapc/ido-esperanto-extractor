# Historical Rules Analysis

## 🔍 Analysis Summary

After analyzing 48 commits in the git history of `apertium-ido.ido.dix`, I've identified several critical morphological improvements that are **MISSING** from the current rules file.

## 🚨 Missing Critical Paradigms

### 1. **Verb Participles** (Commit: a69ddaa)
**Status**: ❌ **MISSING** from current rules

The `ar__vblex` paradigm is missing all participle forms:

```xml
<!-- MISSING: Verb participles -->
<e><p><l>anta</l><r><s n="adj"/></r></p></e>  <!-- Present active participle -->
<e><p><l>ante</l><r><s n="adv"/></r></p></e>  <!-- Present active participle (adv) -->
<e><p><l>inta</l><r><s n="adj"/></r></p></e>  <!-- Past active participle -->
<e><p><l>inte</l><r><s n="adv"/></r></p></e>  <!-- Past active participle (adv) -->
<e><p><l>onta</l><r><s n="adj"/></r></p></e>  <!-- Future active participle -->
<e><p><l>onte</l><r><s n="adv"/></r></p></e>  <!-- Future active participle (adv) -->
<e><p><l>ata</l><r><s n="adj"/></r></p></e>   <!-- Present passive participle -->
<e><p><l>ate</l><r><s n="adv"/></r></p></e>   <!-- Present passive participle (adv) -->
<e><p><l>ita</l><r><s n="adj"/></r></p></e>   <!-- Past passive participle -->
<e><p><l>ite</l><r><s n="adv"/></r></p></e>   <!-- Past passive participle (adv) -->
<e><p><l>ota</l><r><s n="adj"/></r></p></e>   <!-- Future passive participle -->
<e><p><l>ote</l><r><s n="adv"/></r></p></e>   <!-- Future passive participle (adv) -->
```

### 2. **Additional Adjective Paradigms** (Commit: ea1f218)
**Status**: ❌ **MISSING** from current rules

```xml
<!-- MISSING: Additional adjective paradigms -->
<pardef n="oza__adj">
  <e><p><l>oza</l><r><s n="adj"/></r></p></e>
  <e><p><l>oze</l><r><s n="adv"/></r></p></e>
</pardef>

<pardef n="iva__adj">
  <e><p><l>iva</l><r><s n="adj"/></r></p></e>
  <e><p><l>ive</l><r><s n="adv"/></r></p></e>
</pardef>
```

### 3. **Noun Paradigm for -ajo** (Commit: ea1f218)
**Status**: ❌ **MISSING** from current rules

```xml
<!-- MISSING: -ajo noun paradigm -->
<pardef n="ajo__n">
  <e><p><l>ajo</l><r><s n="n"/><s n="sg"/><s n="nom"/></r></p></e>
  <e><p><l>aji</l><r><s n="n"/><s n="pl"/><s n="nom"/></r></p></e>
  <e><p><l>ajon</l><r><s n="n"/><s n="sg"/><s n="acc"/></r></p></e>
  <e><p><l>ajin</l><r><s n="n"/><s n="pl"/><s n="acc"/></r></p></e>
</pardef>
```

### 4. **Enhanced Number Recognition** (Commit: f4347cd)
**Status**: ❌ **MISSING** from current rules

The current `num_regex` paradigm is incomplete. It should include:

```xml
<!-- MISSING: Complete number recognition -->
<pardef n="num_regex">
  <e>
    <re>[0-9]+([.,][0-9]+)*</re>
    <p>
      <l/>
      <r><s n="num"/><s n="ciph"/><s n="sp"/><s n="nom"/></r>
    </p>
  </e>
  <e>
    <re>[0-9]+([.,][0-9]+)*</re>
    <p>
      <l/>
      <r><s n="num"/><s n="ciph"/><s n="sp"/><s n="acc"/></r>
    </p>
  </e>
  <e>
    <re>[0-9]+([.,][0-9]+)*%</re>
    <p>
      <l/>
      <r><s n="num"/><s n="percent"/><s n="sp"/><s n="nom"/></r>
    </p>
  </e>
  <e>
    <re>[0-9]+([.,][0-9]+)*%</re>
    <p>
      <l/>
      <r><s n="num"/><s n="percent"/><s n="sp"/><s n="acc"/></r>
    </p>
  </e>
</pardef>
```

### 5. **Missing Symbol Definitions**
**Status**: ❌ **MISSING** from current rules

```xml
<!-- MISSING: Symbol definitions -->
<sdef n="percent" />
```

## 📊 Impact Analysis

### Current Rules File Status
- ✅ **Basic paradigms**: `o__n`, `a__adj`, `e__adv`, `ar__vblex` (basic)
- ✅ **Function words**: `__pr`, `__det`, `__cnjcoo`, etc.
- ✅ **Basic number**: `num_regex` (incomplete)
- ❌ **Verb participles**: Missing all 12 participle forms
- ❌ **Additional adjectives**: Missing `oza__adj`, `iva__adj`
- ❌ **Noun variants**: Missing `ajo__n`
- ❌ **Complete numbers**: Missing percentage support

### Translation Quality Impact
Based on commit messages, these missing paradigms caused:

1. **Verb Participles**: Reduced morphological coverage for verb forms
2. **Adjective Paradigms**: Limited adjective derivation capabilities  
3. **Number Recognition**: Numbers showing '*' prefix in translations
4. **Noun Variants**: Missing support for -ajo noun forms

## 🎯 Recommended Actions

### Priority 1: Critical Missing Paradigms
1. **Add verb participles** to `ar__vblex` paradigm
2. **Add missing adjective paradigms** (`oza__adj`, `iva__adj`)
3. **Add `ajo__n` noun paradigm**
4. **Complete number recognition** with percentage support

### Priority 2: Symbol Definitions
1. **Add missing symbols** (`percent`, etc.)

### Priority 3: Validation
1. **Test all paradigms** with sample words
2. **Validate XML syntax** after updates
3. **Test translation quality** improvements

## 🔧 Implementation Plan

1. **Extract missing paradigms** from historical commits
2. **Update rules file** with missing paradigms
3. **Test merge script** with updated rules
4. **Validate translation quality** improvements
5. **Document changes** in commit message

## 📈 Expected Improvements

After adding these missing paradigms:

- ✅ **Verb participles** will work correctly
- ✅ **Adjective derivation** will be more complete
- ✅ **Number recognition** will handle percentages
- ✅ **Noun variants** will support -ajo forms
- ✅ **Translation quality** will improve significantly

---

**Status**: 🚨 **CRITICAL UPDATES NEEDED**

The current rules file is missing several important morphological paradigms that were developed and tested in the historical commits. These should be restored to maintain full translation quality.
