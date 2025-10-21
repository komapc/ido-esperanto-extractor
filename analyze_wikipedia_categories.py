#!/usr/bin/env python3
"""
Analyze Wikipedia categories to classify vocabulary words.

This helps us distinguish:
- Geographic proper nouns (cities, countries, regions)
- People/biographies  
- Organizations
- Common vocabulary words
"""

import json
import bz2
import re
from collections import defaultdict
from pathlib import Path

# Category patterns for filtering
CATEGORY_PATTERNS = {
    'geography': [
        'landi', 'urbi', 'citat', 'komunumi', 'provinc', 'region', 'stato',
        'Afrika', 'Amerika', 'Europa', 'Oceania', 'Azia', 'Antarktika',
        'geografio', 'topografio', 'kapitali', 'insuli', 'monto', 'riveri',
        'laki', 'oceani', 'mari'
    ],
    'people': [
        'person', 'homo', 'kompozist', 'skriptist', 'autor', 'poeta',
        'biciklis', 'futbalis', 'prezidant', 'aktris', 'aktoro', 'kantisto',
        'direktoro', 'filozofo', 'scientisto', 'matematikisto', 'fizikisto',
        'naskita', 'mortinta', 'biografio'
    ],
    'organizations': [
        'organizaji', 'kompanio', 'firmao', 'klubo', 'asocio',
        'universitati', 'skoli', 'governo'
    ],
    'temporal': [
        'yari', 'monati', 'tagi', 'horai', 'sekli', 'eventi', 'historio'
    ]
}

def matches_category_pattern(category, pattern_list):
    """Check if category matches any pattern."""
    cat_lower = category.lower()
    return any(pattern.lower() in cat_lower for pattern in pattern_list)

def classify_by_category(categories):
    """Classify a word based on its Wikipedia categories."""
    if not categories:
        return 'unknown'
    
    # Check each category type
    for cat in categories:
        if matches_category_pattern(cat, CATEGORY_PATTERNS['geography']):
            return 'geography'
        if matches_category_pattern(cat, CATEGORY_PATTERNS['people']):
            return 'people'
        if matches_category_pattern(cat, CATEGORY_PATTERNS['organizations']):
            return 'organization'
        if matches_category_pattern(cat, CATEGORY_PATTERNS['temporal']):
            return 'temporal'
    
    # If no proper noun patterns, likely vocabulary
    return 'vocabulary'

def extract_categories_from_wikipedia(wiki_dump, word_set, limit=None):
    """Extract categories for words from Wikipedia dump."""
    print(f"📖 Extracting categories from {wiki_dump.name}...")
    print(f"   Looking for {len(word_set):,} words")
    
    word_categories = {}
    found_count = 0
    page_count = 0
    
    with bz2.open(wiki_dump, 'rt', encoding='utf-8') as f:
        current_title = None
        current_text = []
        in_text = False
        
        for line in f:
            if '<title>' in line:
                match = re.search(r'<title>(.*?)</title>', line)
                if match:
                    current_title = match.group(1).strip()
                    # Skip special pages
                    if current_title.startswith(('Wikipedia:', 'Kategorio:', 'Helpo:', 'Template:')):
                        current_title = None
            
            if current_title and '<text' in line:
                in_text = True
                current_text = [line]
            elif in_text:
                current_text.append(line)
            
            if '</text>' in line and in_text:
                in_text = False
                page_count += 1
                
                # Check if this title is in our vocabulary
                if current_title and current_title in word_set:
                    found_count += 1
                    
                    # Extract categories
                    text = ''.join(current_text)
                    cats = re.findall(r'\[\[Kategorio:([^\]|]+)', text)
                    word_categories[current_title] = cats
                    
                    if found_count % 100 == 0:
                        print(f'   Progress: {found_count:,} words found, {page_count:,} pages scanned...', end='\r')
                
                current_title = None
                current_text = []
                in_text = False
            
            if limit and page_count >= limit:
                break
    
    print(f'\n   ✅ Found categories for {found_count:,} words (scanned {page_count:,} pages)')
    return word_categories

def main():
    print("=" * 70)
    print("📚 Wikipedia Category Analysis")
    print("=" * 70)
    print()
    
    # Load Wikipedia vocabulary
    vocab_file = Path('wikipedia_vocabulary_merge_ready.json')
    if not vocab_file.exists():
        print(f"❌ Vocabulary file not found: {vocab_file}")
        return 1
    
    print(f"📖 Loading {vocab_file}...")
    with open(vocab_file, 'r') as f:
        vocab_data = json.load(f)
    
    # Extract Ido words
    words_list = vocab_data.get('words', [])
    word_set = {entry['ido_word'] for entry in words_list if 'ido_word' in entry}
    
    print(f"   ✅ Loaded {len(word_set):,} words")
    print()
    
    # Extract categories from Wikipedia
    wiki_dump = Path('iowiki-latest-pages-articles.xml.bz2')
    if not wiki_dump.exists():
        print(f"❌ Wikipedia dump not found: {wiki_dump}")
        return 1
    
    word_categories = extract_categories_from_wikipedia(wiki_dump, word_set)
    
    # Classify words
    print()
    print("📊 Classifying words by category...")
    classifications = defaultdict(list)
    category_stats = defaultdict(int)
    
    for word, cats in word_categories.items():
        classification = classify_by_category(cats)
        classifications[classification].append((word, cats))
        
        for cat in cats:
            category_stats[cat] += 1
    
    # Also classify words without Wikipedia articles
    for word in word_set:
        if word not in word_categories:
            classifications['no_wikipedia_article'].append((word, []))
    
    # Print classification summary
    print()
    print("=" * 70)
    print("📊 Classification Summary")
    print("=" * 70)
    print()
    
    for classification, words in sorted(classifications.items(), key=lambda x: len(x[1]), reverse=True):
        print(f"  {classification:25s}: {len(words):,} words")
    
    # Show examples from each category
    print()
    print("=" * 70)
    print("📝 Examples from Each Category")
    print("=" * 70)
    
    for classification in ['geography', 'people', 'organization', 'temporal', 'vocabulary', 'unknown']:
        if classification not in classifications:
            continue
        
        print(f"\n🏷️  {classification.upper()}:")
        examples = classifications[classification][:10]
        for word, cats in examples:
            cats_str = ', '.join(cats[:3]) if cats else '(no categories)'
            print(f"   {word:30s} → {cats_str}")
        if len(classifications[classification]) > 10:
            print(f"   ... and {len(classifications[classification]) - 10:,} more")
    
    # Show most common categories
    print()
    print("=" * 70)
    print("📊 Most Common Wikipedia Categories")
    print("=" * 70)
    print()
    
    for cat, count in sorted(category_stats.items(), key=lambda x: x[1], reverse=True)[:30]:
        print(f"   {count:4d}x  {cat}")
    
    # Save classification results
    output_file = Path('wikipedia_classifications.json')
    output_data = {
        'metadata': {
            'total_words': len(word_set),
            'words_with_categories': len(word_categories),
            'classification_date': '2025-10-22'
        },
        'classifications': {
            key: [{'word': w, 'categories': c} for w, c in words]
            for key, words in classifications.items()
        },
        'category_stats': dict(category_stats)
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    
    print()
    print(f"✅ Saved classification results to: {output_file}")
    
    # Recommendation
    print()
    print("=" * 70)
    print("💡 Recommendation")
    print("=" * 70)
    print()
    
    vocab_count = len(classifications.get('vocabulary', []))
    unknown_count = len(classifications.get('unknown', []))
    geo_count = len(classifications.get('geography', []))
    people_count = len(classifications.get('people', []))
    
    print(f"Based on category analysis:")
    print(f"  • {vocab_count:,} likely VOCABULARY words (no proper noun categories)")
    print(f"  • {unknown_count:,} UNKNOWN (have categories but don't match patterns)")
    print(f"  • {geo_count:,} GEOGRAPHIC proper nouns")
    print(f"  • {people_count:,} PEOPLE/biography entries")
    print()
    print("Suggested approach:")
    print("  1. Include 'vocabulary' + 'unknown' in dictionary (~common words)")
    print("  2. Tag 'geography' and 'people' as proper nouns (np)")
    print("  3. Keep all in database but mark their type")
    print()
    
    return 0

if __name__ == '__main__':
    import sys
    sys.exit(main())

