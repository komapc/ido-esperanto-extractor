# Markup Cleaning Examples

## Overview

The `clean_lemma()` function in `scripts/_common.py` handles three main types of Wiktionary markup:
1. **Bold/Italic** (`'''`, `''`)
2. **Wiki Links** (`[[...]]`)
3. **Templates** (`{{...}}`)

After cleaning, `is_valid_lemma()` checks if any unresolved markup remains. Entries with remaining markup are rejected as malformed.

---

## 1. Bold/Italic Markup (`'''`, `''`)

**Purpose:** MediaWiki uses quotes for text formatting. We remove the quotes but **keep the content**.

### Examples:

```
BEFORE              →  AFTER
'''abelo'''         →  abelo          (bold word)
''femino''          →  femino         (italic word)
'''1.''' homo       →  homo           (numbered definition)
'''[[altra]]'''     →  altra          (bold + link)
'''Bonveno'''       →  Bonveno        (bold text)
```

**Rule:** Strip all `''` and `'''` characters, preserve the text inside.

---

## 2. Wiki Links (`[[...]]`)

**Purpose:** MediaWiki uses `[[...]]` for internal links. We extract the text, discard the link syntax.

### Patterns:

#### Simple links: `[[word]]` → `word`
```
BEFORE              →  AFTER
[[kavalo]]          →  kavalo         (link to page)
[[Ido]]             →  Ido            (language name)
[[helpo]]           →  helpo          (help)
```

#### Piped links: `[[target|display]]` → `display`
```
BEFORE                  →  AFTER
[[altra|ALTRA]]         →  ALTRA          (display text used)
[[helpo|HELPO]]         →  HELPO          (uppercase display)
[[linguo|LINGUI]]       →  LINGUI         (plural display)
```

#### Combined with bold: `'''[[word]]'''` → `word`
```
BEFORE                  →  AFTER
'''[[altra|ALTRA]]'''   →  ALTRA          (bold + piped link)
'''[[helpo|HELPO]]'''   →  HELPO          (bold + link)
```

**Rule:** Extract display text from piped links, otherwise extract link target. Discard all `[[` and `]]`.

---

## 3. Templates (`{{...}}`)

**Purpose:** MediaWiki uses templates for structured content. Different template types need different handling.

### Common Template Types

Based on analysis of Ido Wiktionary (7.4M pages):

| Template | Count | Purpose | Handling |
|----------|-------|---------|----------|
| `{{en}}`, `{{fr}}`, `{{de}}` | 98K+ each | Language codes | Remove entirely |
| `{{io}}`, `{{eo}}` | 68K, 50K | Ido/Esperanto markers | Remove entirely |
| `{{vartas}}` | 50K | "Awaits" marker | Remove entirely |
| `{{Fonto}}` | 47K | Source citation | Remove entirely |
| `{{tr\|lang\|word}}` | varies | Translation template | **Extract word** |

### Extraction Rules:

#### Language code templates: `{{lang}}` → (removed)
```
BEFORE              →  AFTER
{{io}}              →  (empty)        (language marker)
{{eo}}              →  (empty)        (language marker)
{{en}}              →  (empty)        (language marker)
{{fr}}              →  (empty)        (language marker)
```

#### Translation templates: `{{tr|lang|word}}` → `word`
```
BEFORE                      →  AFTER
{{tr|io|hundo}}             →  hundo          (extract word)
{{tr|eo|hundo}}             →  hundo          (extract word)
{{trad|io|kavalo}}          →  kavalo         (extract word)
```

#### Parameterized templates: `{{template|content}}` → `content`
```
BEFORE                      →  AFTER
{{contexte|géographie}}     →  géographie     (extract parameter)
{{qualifier|informal}}      →  informal       (extract qualifier)
{{template|value}}          →  value          (generic: extract first param)
```

#### Simple templates: `{{template}}` → (removed)
```
BEFORE              →  AFTER
{{Fonto}}           →  (empty)        (source template)
{{vartas}}          →  (empty)        (awaits template)
{{Aktivo}}          →  (empty)        (active template)
```

### Complex Examples:

```
BEFORE                                          →  AFTER
'''{{Fonto}}'''                                 →  (empty)
{{io}} [[kavalo]]                               →  kavalo
{{tr|eo|hundo}} {{qualifier|common}}            →  hundo common
text {{contexte|géographie}} more               →  text géographie more
```

**Rules:**
1. Language codes (`{{io}}`, `{{en}}`, etc.) → remove
2. Translation templates (`{{tr|lang|word}}`) → extract word (3rd parameter)
3. Parameterized (`{{template|param}}`) → extract param (1st parameter)
4. Simple (`{{template}}`) → remove entirely
5. Cleanup leftover `{`, `}`, `[`, `]` characters

---

## Validation After Cleaning

After cleaning, `is_valid_lemma()` checks:

### ✅ PASS (properly cleaned):
```
abelo           ✓  (all markup removed)
kavalo          ✓  (from [[kavalo]])
hundo           ✓  (from {{tr|io|hundo}})
Afriko          ✓  (from '''Afriko''')
```

### ❌ FAIL (unresolved markup):
```
'''abelo        ✗  (incomplete quote removal)
[[kavalo        ✗  (unclosed bracket)
{{template      ✗  (unclosed brace)
text'''more     ✗  (quotes in middle)
```

**Why validation matters:** If markup remains after cleaning, the entry is malformed and should be rejected rather than included in the dictionary.

---

## Implementation

### Clean Function
Location: `scripts/_common.py::clean_lemma()`

Order of operations:
1. Strip bold/italic quotes (`'''`, `''`)
2. Extract content from wiki links (`[[...]]`)
3. Process templates (`{{...}}`)
4. Remove numbered definitions
5. Remove language codes in parentheses
6. Remove gender symbols
7. Strip punctuation artifacts
8. Normalize whitespace

### Validation Function
Location: `scripts/_common.py::is_valid_lemma()`

Checks:
- Not empty, minimum 2 characters
- Doesn't start with special chars
- No unresolved markup (`'''`, `[[`, `{{`, etc.)
- Not obviously a title (long + contains `:`)
- Contains at least one alphabetic character

---

## Statistics

From Ido Wiktionary processing:

- **Before normalization**: 75,288 raw entries
- **After cleaning**: 7,167 normalized entries  
- **Invalid lemmas removed**: 68,117 (90.5%)
  - Wikipedia titles without translations: 68,015
  - Malformed markup: ~102
  - Other issues: varies

**Result:** Only high-quality, properly formatted entries remain in the final dictionary.

