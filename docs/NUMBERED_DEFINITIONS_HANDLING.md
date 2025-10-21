# Handling Numbered Definitions in Wiktionary

## Problem Example

Wiktionary often has entries like:
```
hundo (Ido)
  Esperanto:
  '''1.''' ĥundo (domestic animal)
  '''2.''' hundredo (unit of 100)
```

Currently extracted as ONE entry:
```json
{
  "lemma": "'''1.''' hundo (io)",
  "senses": [
    {"translations": [{"term": "ĥundo", "lang": "eo"}]}
  ]
}
```

## Correct Approach

### Step 1: Parse Numbered Definitions

In `scripts/wiktionary_parser.py`, the `parse_meanings()` function already handles this:

```python
def parse_meanings(blob: str) -> List[List[str]]:
    # Finds numbered patterns like (1) x; (2) y
    numbered = re.findall(r"\((\d+)\)\s*([^;()]+)", t)
    if numbered:
        out: List[List[str]] = []
        for _, meaning in numbered:
            syns = [s.strip() for s in meaning.split(',') if s.strip()]
            if syns:
                out.append(syns)  # Each number becomes separate sense
        return out
```

This creates **multiple senses** for one lemma.

### Step 2: JSON Representation

The JSON should look like:
```json
{
  "lemma": "hundo",
  "language": "io",
  "pos": "noun",
  "senses": [
    {
      "senseId": "1",
      "gloss": "domestic animal",
      "translations": [
        {"term": "ĥundo", "lang": "eo", "confidence": 0.6}
      ]
    },
    {
      "senseId": "2",
      "gloss": "hundred",
      "translations": [
        {"term": "hundredo", "lang": "eo", "confidence": 0.6}
      ]
    }
  ]
}
```

**Key point:** ONE lemma, MULTIPLE senses

### Step 3: Apertium .dix Export

Apertium format doesn't support multiple senses per entry directly. We have TWO options:

#### Option A: Multiple Entries (Current - CORRECT for Apertium)

Generate **separate `<e>` entries** for each sense:

```xml
<e>
  <p>
    <l>hundo<s n="n" /></l>
    <r>ĥundo<s n="n" /></r>
  </p>
</e>
<e>
  <p>
    <l>hundo<s n="n" /></l>
    <r>hundredo<s n="n" /></r>
  </p>
</e>
```

**How Apertium handles this:**
- When translating "hundo", Apertium finds BOTH matches
- Returns first match by default: `ĥundo`
- User can see alternatives with `-a` (ambiguity mode): `ĥundo|hundredo`

**Advantage:** All meanings available, simple format  
**Disadvantage:** No sense disambiguation (picks first)

#### Option B: Comments (Less useful)

```xml
<e r="LR">  <!-- sense 1: domestic animal -->
  <p>
    <l>hundo<s n="n" /></l>
    <r>ĥundo<s n="n" /></r>
  </p>
</e>
<e r="LR">  <!-- sense 2: hundred -->
  <p>
    <l>hundo<s n="n" /></l>
    <r>hundredo<s n="n" /></r>
  </p>
</e>
```

**Advantage:** Documentation  
**Disadvantage:** Apertium ignores comments at runtime

### Step 4: Implementation in export_apertium.py

Current code in `build_bidix()` (lines 107-157):

```python
for e in sorted_entries:
    lemma = e.get("lemma")
    
    # Collect EO translations from ALL senses
    eo_terms = []
    for s in e.get("senses", []):
        for tr in s.get("translations", []):
            if tr.get("lang") == "eo":
                eo_terms.append(tr.get("term"))
    
    # Create ONE entry per translation
    for epo in eo_terms:
        en = ET.SubElement(section, "e")
        p = ET.SubElement(en, "p")
        l = ET.SubElement(p, "l")
        l.text = lemma
        # Add POS tag
        r = ET.SubElement(p, "r")
        r.text = epo
        # Add POS tag
```

**This is CORRECT!** It already creates multiple `<e>` entries for multi-sense words.

## The Real Problems to Fix

### Problem 1: Lemma Cleaning

**Before export**, clean the lemma in `normalize_entries.py`:

```python
def clean_lemma(lemma: str) -> str:
    if not lemma:
        return ""
    
    # Remove bold/italic markup
    lemma = re.sub(r"'{2,}", "", lemma)
    
    # Remove numbered definitions
    lemma = re.sub(r"^'{0,3}\d+\.'{0,3}\s*", "", lemma)
    
    # Remove language codes
    lemma = re.sub(r"\s*\([a-z]{2,3}\)\s*$", "", lemma, flags=re.IGNORECASE)
    
    # Remove gender symbols
    lemma = re.sub(r"\s*\(['']*[♀♂]['']*\)\s*", "", lemma)
    
    # Strip markup artifacts
    lemma = lemma.strip(" \t\n\r\f\v:;,.–-|'\"")
    
    return lemma

# Apply to all entries
for entry in entries:
    entry['lemma'] = clean_lemma(entry['lemma'])
```

### Problem 2: Validation

```python
def is_valid_lemma(lemma: str) -> bool:
    if not lemma or len(lemma) < 2:
        return False
    if lemma[0] in "'''([{%#*":
        return False
    if any(x in lemma for x in ["'''", "[[", "]]", "{{", "}}"]):
        return False
    return True

# Filter entries
entries = [e for e in entries if is_valid_lemma(e['lemma'])]
```

## Example Transformation

### Input (from Wiktionary):
```
Wikitext: 
  Esperanto:
  '''1.''' ĥundo (dog)
  '''2.''' hundredo (hundred)
```

### After Parsing (wiktionary_parser.py):
```json
{
  "lemma": "'''1.''' hundo (io)",
  "senses": [
    {"translations": [{"term": "ĥundo", "lang": "eo"}]},
    {"translations": [{"term": "hundredo", "lang": "eo"}]}
  ]
}
```

### After Cleaning (normalize_entries.py):
```json
{
  "lemma": "hundo",
  "senses": [
    {"translations": [{"term": "ĥundo", "lang": "eo"}]},
    {"translations": [{"term": "hundredo", "lang": "eo"}]}
  ]
}
```

### After Export (export_apertium.py):
```xml
<e>
  <p>
    <l>hundo<s n="n" /></l>
    <r>ĥundo<s n="n" /></r>
  </p>
</e>
<e>
  <p>
    <l>hundo<s n="n" /></l>
    <r>hundredo<s n="n" /></r>
  </p>
</e>
```

### Apertium Translation:
```bash
$ echo "hundo" | apertium ido-epo
ĥundo

$ echo "hundo" | apertium -a ido-epo  # With ambiguity
^hundo/ĥundo$|^hundo/hundredo$
```

## Summary

✅ **Numbered definitions are ALREADY creating multiple senses**  
✅ **Export ALREADY creates multiple entries per sense**  
❌ **PROBLEM: Lemmas have markup that needs cleaning**

**Fix:** Clean lemmas in `normalize_entries.py` BEFORE export, preserving the multiple senses structure.
