#!/usr/bin/env python3
"""
Common template parsing utilities for Wiktionary and Wikipedia processing.

This module consolidates template parsing logic that was duplicated across
multiple scripts, providing consistent template handling for:
- French Wiktionary templates ({{trad-début}}, {{T|io}}, {{T|eo}})
- English Wiktionary templates ({{t|lang|word}}, {{t+|lang|word}}, etc.)
- General MediaWiki template patterns
"""
import re
from typing import Dict, List, Optional, Pattern, Set

# Pre-compiled regex patterns for performance
class TemplatePatterns:
    """Pre-compiled regex patterns for common template parsing."""
    
    def __init__(self):
        # French Wiktionary patterns
        self.fr_trad_section = re.compile(r'\{\{trad-début\|([^}]+)\}\}(.*?)\{\{trad-fin\}\}', re.DOTALL)
        self.fr_io_trans = re.compile(r'\{\{T\|io\}\}\s*:\s*\{\{trad\+?\|io\|([^}|]+)')
        self.fr_eo_trans = re.compile(r'\{\{T\|eo\}\}\s*:\s*\{\{trad\+?\|eo\|([^}|]+)')
        
        # English Wiktionary patterns (language-specific)
        self.en_patterns_cache: Dict[str, Dict[str, Pattern]] = {}
        
        # General MediaWiki patterns
        self.wikilink = re.compile(r'\[\[(?:[^\]|]*\|)?([^\]]+)\]\]')
        self.template_simple = re.compile(r'\{\{([^}]+)\}\}')
        self.template_param = re.compile(r'\{\{([^|]+)\|([^}]+)\}\}')
        self.template_multi = re.compile(r'\{\{([^|]+)\|([^|]+)\|([^}]+)\}\}')
        
        # Language code patterns
        self.lang_code = re.compile(r'\{\{[a-z]{2,3}\}\}')
        self.translation_template = re.compile(r'\{\{tr\|[^|]+\|([^}]+)\}\}')
        
        # Quality markers
        self.low_quality = re.compile(r'\{\{t-check|\{\{t-needed')
    
    def get_english_patterns(self, target_lang: str) -> Dict[str, Pattern]:
        """Get or create compiled patterns for English Wiktionary target language."""
        if target_lang not in self.en_patterns_cache:
            self.en_patterns_cache[target_lang] = {
                # Translation templates
                't_plus': re.compile(rf'\{{{{t\+\|{target_lang}\|([^|}}]+?)(?:\|[^}}]*)?\}}}}', re.IGNORECASE),
                't': re.compile(rf'\{{{{t\|{target_lang}\|([^|}}]+?)(?:\|[^}}]*)?\}}}}', re.IGNORECASE),
                'tt': re.compile(rf'\{{{{tt\+?\|{target_lang}\|([^|}}]+?)(?:\|[^}}]*)?\}}}}', re.IGNORECASE),
                'link': re.compile(rf'\{{{{[lm]\|{target_lang}\|([^|}}]+?)(?:\|[^}}]*)?\}}}}', re.IGNORECASE),
                # Language name pattern for line matching
                'lang_line': re.compile(
                    rf'^\s*\*\s*\{\{{{target_lang.upper()}\}}\}\s*[:\.-]\s*(.+)$', 
                    re.MULTILINE | re.IGNORECASE
                ),
            }
        return self.en_patterns_cache[target_lang]


# Global instance
PATTERNS = TemplatePatterns()


def extract_french_via_translations(text: str) -> List[Dict[str, any]]:
    """Extract via translations from French Wiktionary text."""
    via_translations = []
    
    # Look for numbered list items in French section
    meaning_pattern = r'^#\s+(.+?)(?=^#|^===|^==|\Z)'
    
    meaning_num = 1
    for match in re.finditer(meaning_pattern, text, re.MULTILINE | re.DOTALL):
        definition = match.group(1).strip()
        
        # Clean up definition (remove examples, citations, etc.)
        definition = re.sub(r'{{exemple[^}]*}}', '', definition)  # Remove examples
        definition = re.sub(r'{{[^}]*}}', '', definition)  # Remove templates
        definition = re.sub(r'\[\[[^]]*\]\]', '', definition)  # Remove links
        definition = re.sub(r'[#*]', '', definition)  # Remove bullets
        definition = re.sub(r'\s+', ' ', definition).strip()  # Normalize whitespace
        
        if len(definition) < 3:
            continue
            
        # Extract translations for this meaning
        translations = extract_translations_for_meaning(text, meaning_num)
        
        if translations['io'] and translations['eo']:
            via_translations.append({
                'via_num': meaning_num,
                'definition': definition,
                'io_translations': translations['io'],
                'eo_translations': translations['eo']
            })
        meaning_num += 1
    
    return via_translations


def extract_translations_for_meaning(text: str, meaning_num: int) -> Dict[str, List[str]]:
    """Extract Ido and Esperanto translations for a specific meaning."""
    translations = {'io': [], 'eo': []}
    
    # Look for trad-début sections
    trad_sections = PATTERNS.fr_trad_section.findall(text)
    
    for via_desc, section_text in trad_sections:
        # Look for Ido and Esperanto translations in this section
        io_matches = PATTERNS.fr_io_trans.findall(section_text)
        eo_matches = PATTERNS.fr_eo_trans.findall(section_text)
        
        for match in io_matches:
            translation = match.strip()
            if translation and len(translation) > 1:
                translations['io'].append(translation)
        
        for match in eo_matches:
            translation = match.strip()
            if translation and len(translation) > 1:
                translations['eo'].append(translation)
    
    return translations


def extract_english_translations_from_templates(line: str, target_lang: str) -> List[str]:
    """
    Extract translations from English Wiktionary MediaWiki templates.
    
    Templates we PARSE (extract word):
        {{t|eo|word}}        - unchecked translation
        {{t+|eo|word}}       - verified translation (best quality)
        {{tt|eo|word}}       - translation variant
        {{tt+|eo|word}}      - verified translation with transliteration
        {{l|eo|word}}        - link to word
        {{m|eo|word}}        - mention word
    """
    translations = []
    
    # SKIP: Check for low-quality templates
    if PATTERNS.low_quality.search(line):
        return []
    
    patterns = PATTERNS.get_english_patterns(target_lang)
    
    # Extract {{t+|lang|word}} (verified - highest quality)
    for match in patterns['t_plus'].finditer(line):
        word = match.group(1).strip()
        if word and len(word) > 1:
            translations.append(word)
    
    # Extract {{t|lang|word}} (unchecked)
    for match in patterns['t'].finditer(line):
        word = match.group(1).strip()
        if word and len(word) > 1:
            translations.append(word)
    
    # Extract {{tt+|lang|word}}, {{tt|lang|word}} (transliteration variants)
    for match in patterns['tt'].finditer(line):
        word = match.group(1).strip()
        if word and len(word) > 1:
            translations.append(word)
    
    # Extract {{l|lang|word}}, {{m|lang|word}} (links/mentions)
    for match in patterns['link'].finditer(line):
        word = match.group(1).strip()
        if word and len(word) > 1:
            translations.append(word)
    
    return translations


def extract_bare_words_from_line(line: str, target_lang: str) -> List[str]:
    """
    Extract bare words (not in templates) from a line.
    
    Args:
        line: Text line to process
        target_lang: Target language code (e.g., 'io', 'eo')
    
    Returns:
        List of bare words found
    """
    # Remove all templates using precompiled pattern
    line_no_templates = PATTERNS.template_simple.sub('', line)
    
    # Extract wikilinks: [[word]] or [[link|word]] → word
    wikilink_matches = PATTERNS.wikilink.findall(line_no_templates)
    
    # Filter for target language context and clean
    words = []
    for match in wikilink_matches:
        word = match.strip()
        if word and len(word) > 1 and not any(x in word for x in ['|', '{', '}', ':', '=']):
            words.append(word)
    
    return words


def clean_translation_line(line: str) -> str:
    """
    Clean a translation line by removing metadata templates.
    
    IGNORE templates (remove entirely):
        {{qualifier|...}}, {{q|...}}, {{sense|...}}, {{lb|...}}
        Gender markers: {{m}}, {{f}}, {{n}}, {{c}}
        Number markers: {{p}}, {{s}}
    """
    # Remove metadata templates
    line = re.sub(r'\{\{(?:qualifier|q|sense|lb|m|f|n|c|p|s)(?:\|[^}]*)?\}\}', '', line)
    
    # Remove other common metadata
    line = re.sub(r'\{\{[^|}]+\}\}', '', line)  # Simple templates
    line = re.sub(r'\[\[[^]]*\]\]', '', line)  # Links
    line = re.sub(r'[#*]', '', line)  # Bullets
    line = re.sub(r'\s+', ' ', line).strip()  # Normalize whitespace
    
    return line


def clean_lemma_from_templates(lemma: str) -> str:
    """
    Clean Wiktionary markup from lemmas while preserving actual content.
    
    This is a more aggressive version of template cleaning specifically
    for lemmas that may contain various markup patterns.
    """
    if not lemma:
        return ""
    
    original = lemma
    
    # 1. WIKILINKS: [[text]] or [[link|text]] → text
    lemma = PATTERNS.wikilink.sub(r'\1', lemma)
    
    # 2. BOLD/ITALIC: '''text''' → text, ''text'' → text
    lemma = re.sub(r"'''([^']+)'''", r"\1", lemma)
    lemma = re.sub(r"''([^']+)''", r"\1", lemma)
    
    # 3. TEMPLATES: Handle common template types {{...}}
    #    Language codes: {{io}}, {{eo}}, {{en}} etc. → remove entirely
    #    Translation: {{tr|io|word}} → extract word
    #    General: {{template|param}} → extract param or remove
    
    # Remove language code templates (standalone)
    lemma = PATTERNS.lang_code.sub("", lemma)
    
    # Extract content from translation templates: {{tr|lang|word}} → word
    lemma = PATTERNS.translation_template.sub(r"\1", lemma)
    
    # Extract content from parameterized templates: {{template|content}} → content
    lemma = PATTERNS.template_param.sub(r"\2", lemma)
    
    # Remove remaining simple templates: {{template}} → (removed)
    lemma = PATTERNS.template_simple.sub("", lemma)
    
    # 4. LANGUAGE CODES: word (io) → word
    lemma = re.sub(r"\s*\([a-z]{2,3}\)\s*", "", lemma)
    
    # 5. NUMBERED DEFINITIONS: '''1.''' word → word
    lemma = re.sub(r"'''\d+\.'''\s*", "", lemma)
    
    # 6. CLEANUP: Remove extra whitespace and normalize
    lemma = re.sub(r"\s+", " ", lemma).strip()
    
    return lemma


def is_french_page(text: str) -> bool:
    """Check if text represents a French Wiktionary page."""
    return '{{langue|fr}}' in text or 'Français' in text


def has_io_eo_translations(text: str) -> bool:
    """Check if text contains both Ido and Esperanto translations."""
    return '{{T|io}}' in text and '{{T|eo}}' in text


def extract_categories_from_text(text: str) -> List[str]:
    """Extract category names from article text."""
    category_pattern = r'\[\[Kategorio:([^]]+)\]\]'
    return re.findall(category_pattern, text, re.IGNORECASE)
