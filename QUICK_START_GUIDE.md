# Quick Start Guide - Ido Wikipedia Vocabulary

## ✅ What's Done

You now have **5,172 ultra-clean vocabulary candidates** extracted from Ido Wikipedia, all with verified Esperanto translations.

---

## 📁 Files to Review (in order)

### 1. Core Vocabulary ⭐ **START HERE**
```bash
ido_wiki_vocab_vocabulary_final.csv
```
- **4,230 entries**
- Common nouns, verbs, adjectives, compounds
- 100% have Ido grammatical endings
- Examples: Aborto, Acensilo, Acelero, Administrerio

### 2. Geographic Names
```bash
ido_wiki_vocab_geographic_final.csv
```
- **67 entries**
- Cities, countries, regions
- Examples: Abuja, Acapulco, Accra, Abhazia

### 3. Other/Specialized
```bash
ido_wiki_vocab_other_final.csv
```
- **875 entries**
- Technical terms, specialized vocabulary
- Review selectively

---

## 🔍 How to Review

### Option A: Spreadsheet (Recommended)
```bash
libreoffice ido_wiki_vocab_vocabulary_final.csv
# or
gnumeric ido_wiki_vocab_vocabulary_final.csv
```

### Option B: Command Line
```bash
# View file
less ido_wiki_vocab_vocabulary_final.csv

# Search for specific patterns
grep "linguo" ido_wiki_vocab_vocabulary_final.csv
grep "ar,.*False" ido_wiki_vocab_vocabulary_final.csv  # Find verbs

# Count entries
wc -l ido_wiki_vocab_vocabulary_final.csv
```

### Option C: Python Script
Create a review script to filter by criteria (word length, POS, etc.)

---

## 🎯 What to Look For

### High Priority (add to dictionary)
- ✅ Common everyday words
- ✅ Basic vocabulary (food, colors, objects)
- ✅ Common verbs (actions)
- ✅ Descriptive adjectives
- ✅ Scientific/technical terms that appear frequently

### Medium Priority
- 🟡 Geographic names (major cities, countries)
- 🟡 Specialized vocabulary for specific domains
- 🟡 Less common but useful terms

### Low Priority (skip)
- 🔴 Very obscure terms
- 🔴 Proper names of people
- 🔴 Place names of tiny villages
- 🔴 Technical jargon unlikely to be used

---

## 📝 Adding Words to Dictionary

Once you've selected words, you can:

### Manual Addition
Edit `dictionary_merged.json` directly:
```json
{
  "ido_word": "acensilo",
  "esperanto_words": ["lifto"],
  "morfologio": ["acensil", ".o"]
}
```

### Batch Addition (create script)
Create a script to add selected words from CSV:
```python
# Read selected words from vocabulary_to_add.csv
# Add to dictionary_merged.json
# Run create_ido_monolingual.py and create_ido_epo_bilingual.py
```

---

## 🔄 Regenerate Dictionary Files

After adding words:

```bash
cd /home/mark/apertium-ido-epo/ido-esperanto-extractor

# Regenerate Apertium dictionaries
python3 create_ido_monolingual.py
python3 create_ido_epo_bilingual.py

# Rebuild translation system
cd ../../apertium/apertium-ido-epo
make clean && make
make test
```

---

## 📊 Statistics Summary

| Metric | Value |
|--------|-------|
| **Ido Wikipedia articles** | 60,138 |
| **Has Esperanto equivalent** | 31,016 (52%) |
| **Valid word titles** | 19,279 |
| **After all filtering** | **5,172** |
| **Vocabulary** | 4,230 |
| **Geographic** | 67 |
| **Other** | 875 |

---

## 🛠️ Pipeline Scripts (Already Created)

All scripts are in `/home/mark/apertium-ido-epo/ido-esperanto-extractor/`:

1. **`extract_ido_wiki_via_langlinks.py`** - Main extractor
2. **`filter_vocabulary.py`** - Basic filtering
3. **`categorize_vocabulary.py`** - Categorization
4. **`clean_vocabulary.py`** - Deep cleaning
5. **`apply_final_filters.py`** - Final ultra-clean
6. **`analyze_clean_vocab.py`** - Analysis tool

---

## 💡 Tips

- **Start small**: Review first 100 entries, add ~20-30 high-value words
- **Test frequently**: After adding 50-100 words, regenerate and test
- **Document decisions**: Note why certain words were added/rejected
- **Check for duplicates**: Some words might have alternate forms already in dictionary
- **Verify translations**: Not all Wikipedia links are perfect - double-check meanings

---

## 🎯 Recommended First Batch

Add these common, useful words first:
- Aborto (abortion/abortion)
- Acensilo (elevator)
- Acelero (acceleration)
- Abreviuro (abbreviation)
- Acento (accent)
- Administrerio (administration)

Then test the system before adding more.

---

## ✨ Success!

You now have a **comprehensive, filtered, categorized vocabulary** of 5,172 words ready for review. This can potentially **double your dictionary size** and significantly improve translation quality!

**Next step**: Open `ido_wiki_vocab_vocabulary_final.csv` and start reviewing! 🎉

