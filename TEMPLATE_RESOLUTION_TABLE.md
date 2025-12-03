# Template Resolution Strategy: English Wiktionary

## Template Inventory & Resolution Plan

Based on analysis of 1000 English Wiktionary pages with IO/EO translations.

---

## Translation Templates

These are the core translation templates in English Wiktionary. All use format: `{{template|lang|word|additional-params}}`

| Template | Count | Format | Content | Resolution | Rationale |
|----------|-------|--------|---------|------------|-----------|
| `{{t\|eo\|...}}` | ~120 | `{{t\|eo\|hundo}}` | Unchecked translation | **PARSE** | Core translation data - highest value |
| `{{t+\|eo\|...}}` | ~150 | `{{t+\|eo\|hundo}}` | Verified translation (exists in target Wiktionary) | **PARSE** | High quality, verified by community |
| `{{tt\|eo\|...}}` | ~15 | `{{tt\|eo\|hundo}}` | Translation variant | **PARSE** | Same as `{{t}}`, variant notation |
| `{{tt+\|eo\|...}}` | ~30 | `{{tt+\|eo\|hundo\|tr=...}}` | Translation with transliteration | **PARSE** | Extract word, ignore transliteration |
| `{{t-check\|eo\|...}}` | ~8 | `{{t-check\|eo\|hundo}}` | Translation needs verification | **SKIP** | Low quality, unverified |
| `{{t-needed\|eo}}` | ~7 | `{{t-needed\|eo}}` | Translation missing | **SKIP** | No translation content |

### Parsing Strategy

For templates we want to **PARSE**, extract the word using:

```python
# Pattern: {{t|lang|word}} or {{t+|lang|word|extra}}
pattern = r'\{\{tt?\+?\|eo\|([^|}\]]+?)(?:\|[^}]*)?\}\}'
```

**What to extract:**
- `{{t|eo|hundo}}` → `hundo`
- `{{t+|eo|hundo|m}}` → `hundo`
- `{{tt+|eo|hundo|tr=hun.do}}` → `hundo` (ignore transliteration)

**What to skip:**
- `{{t-check|eo|...}}` - Unverified
- `{{t-needed|eo}}` - No content

---

## Context/Qualifier Templates

These add context or qualifiers to translations. They don't contain translation words.

| Template | Count | Format | Content | Resolution | Rationale |
|----------|-------|--------|---------|------------|-----------|
| `{{qualifier\|...}}` | ~10 | `{{qualifier\|archaic}}` | Context marker | **IGNORE** | Not translation data, just metadata |
| `{{q\|...}}` | ~5 | `{{q\|informal}}` | Short qualifier | **IGNORE** | Metadata only |
| `{{sense\|...}}` | ~3 | `{{sense\|animal}}` | Sense grouping | **IGNORE** | Organizational, not data |
| `{{lb\|eo\|...}}` | ~2 | `{{lb\|eo\|formal}}` | Label/context | **IGNORE** | Context only |

### Ignore Strategy

**Simply remove these templates entirely:**

```python
# Remove all qualifier/context templates
text = re.sub(r'\{\{(?:qualifier|q|sense|lb)\|[^}]*\}\}', '', text)
```

They're not translation data, just markup for human readers.

---

## Gender/Grammar Templates

Used to mark grammatical gender or number.

| Template | Count | Format | Content | Resolution | Rationale |
|----------|-------|--------|---------|------------|-----------|
| `{{m}}`, `{{f}}`, `{{n}}` | ~8 | `{{m}}` | Gender markers | **IGNORE** | Esperanto has no grammatical gender |
| `{{p}}`, `{{s}}` | ~3 | `{{p}}` | Number markers | **IGNORE** | Number is morphologically encoded |
| `{{c}}` | ~2 | `{{c}}` | Common gender | **IGNORE** | Not applicable to Esperanto |

### Why Ignore

Esperanto doesn't have grammatical gender, and number is handled via `-j` suffix. These markers are for other languages in the same translation list.

---

## Cross-Reference Templates

Link to other entries or external references.

| Template | Count | Format | Content | Resolution | Rationale |
|----------|-------|--------|---------|------------|-----------|
| `{{l\|eo\|...}}` | ~12 | `{{l\|eo\|hundo}}` | Link to entry | **PARSE** | Contains valid translation word |
| `{{m\|eo\|...}}` | ~6 | `{{m\|eo\|hundo}}` | Mention (link) | **PARSE** | Same as `{{l}}`, contains word |
| `{{gloss\|...}}` | ~4 | `{{gloss\|dog}}` | English gloss | **IGNORE** | English text, not translation |

### Parsing Strategy

```python
# {{l|eo|word}} and {{m|eo|word}} contain translation words
pattern = r'\{\{[lm]\|eo\|([^|}\]]+?)(?:\|[^}]*)?\}\}'
```

---

## Formatting Templates

Control text appearance or structure.

| Template | Count | Format | Content | Resolution | Rationale |
|----------|-------|--------|---------|------------|-----------|
| `{{...}}` (generic) | ~15 | Various | Formatting | **REMOVE** | Visual markup only |
| `{{sup}}`, `{{sub}}` | ~2 | `{{sup\|1}}` | Superscript/subscript | **REMOVE** | Formatting only |

---

## Problem: Current Parser Can't Handle These

### Why Parser Fails

**Current extraction pattern:**
```python
r"\*[ \t]*Esperanto:[ \t]*([^\n]+?)(?=\n|\|\}|\Z)"
                                       ^^^
                            Stops at | (pipe character)
```

**What happens:**
```
Input:  * Esperanto: {{t|eo|hundo}}, {{t+|eo|kato}}
Stops:  * Esperanto: {{t         ❌ (at first |)
```

**Result:** Templates are truncated BEFORE we can parse them.

---

## Fix Required: Two-Stage Parsing

### Stage 1: Extract Full Line

```python
# New pattern: capture everything until newline
pattern = r"\*[ \t]*Esperanto:[ \t]*([^\n]+)"
```

**Result:** `{{t|eo|hundo}}, {{t+|eo|kato}}` ✅ (full content)

### Stage 2: Parse Templates

```python
# Extract all translation templates
translations = []

# {{t|eo|word}}, {{t+|eo|word}}, {{tt|eo|word}}, {{tt+|eo|word}}
for match in re.finditer(r'\{\{tt?\+?\|eo\|([^|}\]]+?)(?:\|[^}]*)?\}\}', line):
    translations.append(match.group(1))

# {{l|eo|word}}, {{m|eo|word}}
for match in re.finditer(r'\{\{[lm]\|eo\|([^|}\]]+?)(?:\|[^}]*)?\}\}', line):
    translations.append(match.group(1))

# Remove qualifiers, gender markers, etc.
for match in re.finditer(r'\{\{(?:qualifier|q|sense|lb|[mfnps]|sup|sub|gloss)\|[^}]*\}\}', line):
    line = line.replace(match.group(0), '')

# Also capture bare words (not in templates)
bare_words = re.findall(r'\b([a-zA-ZĉĝĥĵŝŭĈĜĤĴŜŬ]+)\b', line)
```

---

## Resolution Summary Table

| Action | Templates | Count | Priority |
|--------|-----------|-------|----------|
| **PARSE** | `{{t}}`, `{{t+}}`, `{{tt}}`, `{{tt+}}`, `{{l}}`, `{{m}}` | ~330 | HIGH ⭐ |
| **SKIP** | `{{t-check}}`, `{{t-needed}}` | ~15 | LOW |
| **IGNORE** | `{{qualifier}}`, `{{q}}`, `{{sense}}`, `{{lb}}`, gender/number markers | ~40 | MEDIUM |
| **REMOVE** | Generic formatting templates | ~15 | MEDIUM |

---

## Implementation Plan

### Option A: Fix Parser (If We Want English Via)

**Effort:** 4-6 hours
**Files to modify:**
- `scripts/parse_wiktionary_en.py`
- `scripts/wiktionary_parser.py`

**Steps:**
1. Change extraction pattern to capture full line (don't stop at `|`)
2. Add template parsing logic for `{{t}}`, `{{t+}}`, etc.
3. Add template filtering for `{{qualifier}}`, gender markers, etc.
4. Test on 1000 pages
5. Verify quality > 90%

**Expected yield:** ~600-800 clean translation pairs

### Option B: Keep Disabled (Current Decision)

**Effort:** 0 hours ✅
**Rationale:**
- Only ~0.6% of total entries
- Medium quality (via intermediate language)
- High maintenance cost
- Direct translations are better quality

**Current status:** ✅ **Disabled in Makefile**

---

## Same Analysis Needed for French

**Next task:** Analyze `fr_wiktionary_via` the same way:

1. Parse 1000 French Wiktionary pages
2. Build template inventory
3. Check if French uses same MediaWiki templates
4. Assess truncation issues
5. Create resolution table

**Expected:** Similar issues (MediaWiki standard templates across languages)

---

## Recommendation

✅ **Keep pivoting disabled** until we have:
- Specific user need for via-translations
- Confirmed parser fix works (>90% quality)
- Better sources exhausted (IO Wiktionary, IO Wikipedia, etc.)

**Focus instead on:**
- Improving direct translation sources
- Better morphology inference
- More Wikipedia vocabulary extraction


