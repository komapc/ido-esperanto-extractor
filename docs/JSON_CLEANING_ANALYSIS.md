# JSON Cleaning Issues & Fixes

## 5 Problem Examples

### 1. **Wiktionary Markup Not Stripped**
```json
{
  "lemma": "'''1.''' tu (io)",
  "translation": "vi"
}
```
**Issue:** Bold markup `'''` and language codes `(io)` from Wiktionary source  
**Should be:** `"lemma": "tu"`

### 2. **Numbered Definitions as Lemmas**
```json
{
  "lemma": "'''2.''' vi (io)",
  "translation": "vi"
}
```
**Issue:** Definition numbering `'''2.'''` included in lemma  
**Should be:** `"lemma": "vi"`

### 3. **Language Codes in Lemma**
```json
{
  "lemma": "damzelo (io)",
  "translation": "fraŭlino"
}
```
**Issue:** `(io)` language indicator not removed  
**Should be:** `"lemma": "damzelo"`

### 4. **Gender Symbols**
```json
{
  "lemma": "(''♀'')",
  "translation": "tigro"
}
```
**Issue:** Gender symbol with wiki markup as entire lemma  
**Should be:** Skip this entry or extract context

### 5. **Article/Song Titles**
```json
{
  "lemma": "(Ghost) Riders in the Sky: A Cowboy Legend",
  "translation": null
}
```
**Issue:** Full titles from Wikipedia, not dictionary words  
**Should be:** Filter out or mark as proper noun phrase

## Root Causes

### 1. **Insufficient Wiktionary Cleaning**
Location: `scripts/wiktionary_parser.py` → `clean_translation_text()`

Current cleaning:
```python
def clean_translation_text(text: str) -> str:
    text = html.unescape(text)
    text = re.sub(r"\{\{[^}]*\}\}", "", text)  # templates
    text = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]+)\]\]", r"\1", text)  # links
    text = re.sub(r"\[\[(?:Category|Kategorio):[^\]]*\]\]", "", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\|\s*\}.*$", "", text)
    text = re.sub(r"\s+", " ", text).strip(" \t\n\r\f\v:;,.–-|")
    return text
```

**Missing:**
- Bold/italic removal: `'''text'''` → `text`
- Language code removal: `word (io)` → `word`
- Numbered definitions: `'''1.''' word` → `word`
- Gender symbols: `(''♀'')` → skip

### 2. **Title Extraction Without Filtering**
Location: `scripts/extract_wikipedia_io.py`

Wikipedia titles are added as-is without checking if they're:
- Song/book titles
- Multi-word phrases
- Already quoted strings

### 3. **No Lemma Validation in Final Step**
Location: `scripts/filter_and_validate.py`

Should reject entries where:
- Lemma starts with special chars: `'''`, `(`, `[`, `%`
- Lemma contains Wiki markup
- Lemma is empty or just whitespace

## Suggested Fixes

### Fix 1: Enhanced Lemma Cleaning

Add to `scripts/_common.py`:
```python
import re

def clean_lemma(lemma: str) -> str:
    """Clean Wiktionary markup from lemmas."""
    if not lemma:
        return ""
    
    # Remove bold/italic markup
    lemma = re.sub(r"'{2,}", "", lemma)
    
    # Remove language codes in parentheses
    lemma = re.sub(r"\s*\([a-z]{2,3}\)\s*$", "", lemma)
    
    # Remove numbered definitions
    lemma = re.sub(r"^'{0,3}\d+\.'{0,3}\s*", "", lemma)
    
    # Remove gender symbols
    lemma = re.sub(r"\s*\(['']*[♀♂]['']*\)\s*", "", lemma)
    
    # Strip whitespace and punctuation
    lemma = lemma.strip(" \t\n\r\f\v:;,.–-|'\"")
    
    return lemma
```

### Fix 2: Lemma Validation

Add to `scripts/filter_and_validate.py`:
```python
def is_valid_lemma(lemma: str) -> bool:
    """Check if lemma is a valid dictionary word."""
    if not lemma or len(lemma) < 2:
        return False
    
    # Reject if starts with special chars
    if lemma[0] in "'''([{%#*":
        return False
    
    # Reject if contains unresolved markup
    if any(x in lemma for x in ["'''", "''", "[[", "]]", "{{", "}}"]):
        return False
    
    # Reject obvious titles/phrases
    if ":" in lemma and len(lemma) > 30:
        return False
    
    return True
```

### Fix 3: Apply Cleaning in normalize_entries.py

```python
from _common import clean_lemma, is_valid_lemma

for entry in entries:
    # Clean the lemma
    raw_lemma = entry.get('lemma', '')
    cleaned = clean_lemma(raw_lemma)
    
    # Skip if invalid after cleaning
    if not is_valid_lemma(cleaned):
        continue
    
    entry['lemma'] = cleaned
    entry['_original_lemma'] = raw_lemma  # Keep for debugging
```

### Fix 4: Filter Wikipedia Titles

In `scripts/extract_wikipedia_io.py`:
```python
def is_valid_wikipedia_title(title: str) -> bool:
    """Check if Wikipedia title is a valid dictionary entry."""
    # Skip song/book titles (have colons usually)
    if ":" in title and not title.startswith("Category:"):
        return False
    
    # Skip parenthetical disambiguations for multi-word phrases
    if " (" in title and len(title.split()) > 2:
        return False
    
    # Skip quoted strings
    if title.startswith('"') or title.startswith("'"):
        return False
    
    return True
```

### Fix 5: Add Cleaning to Final Preparation

Update `scripts/final_preparation.py` to:
1. Apply `clean_lemma()` to all entries
2. Filter out invalid lemmas
3. Log what was removed for review

## Implementation Priority

1. **HIGH**: Add `clean_lemma()` function (Fix 1)
2. **HIGH**: Add `is_valid_lemma()` validation (Fix 2)
3. **HIGH**: Apply in `normalize_entries.py` (Fix 3)
4. **MEDIUM**: Filter Wikipedia titles better (Fix 4)  
5. **MEDIUM**: Final validation pass (Fix 5)

## Expected Impact

- Remove ~5,000-10,000 malformed entries
- Keep ~110,000-115,000 clean entries
- Dictionaries will be smaller but much higher quality
- Better translation accuracy

## Testing

After fixes, verify with:
```bash
grep "'''" dist/bidix_big.json  # Should be empty
grep "(io)" dist/apertium-ido-epo.ido-epo.dix  # Should be empty
grep "♀\|♂" dist/bidix_big.json  # Should be empty
```
