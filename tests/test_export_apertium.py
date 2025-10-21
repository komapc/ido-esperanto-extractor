#!/usr/bin/env python3
"""
Tests for export_apertium.py to ensure it handles both old and new JSON formats.

Bug fixes tested:
1. Export script crashes when entries don't have 'language' field (new format)
2. Export script doesn't recognize 'eo_translations' field (new format)
3. Export script produces empty .dix files with new standardized JSON
"""

import sys
import json
import tempfile
from pathlib import Path
from xml.etree import ElementTree as ET

# Add parent directory to path to import the module
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'scripts'))

from export_apertium import build_monodix, build_bidix


def test_new_format_entries_without_language_field():
    """Test that entries without 'language' field are processed (new format)."""
    entries = [
        {"lemma": "hundo", "pos": "n"},
        {"lemma": "bela", "pos": "adj"},
    ]
    
    result = build_monodix(entries)
    assert result is not None
    
    # Check that XML contains entries
    xml_str = ET.tostring(result, encoding='unicode')
    assert 'hundo' in xml_str
    assert 'bela' in xml_str
    

def test_old_format_entries_with_language_field():
    """Test that entries with 'language' field are still processed (old format)."""
    entries = [
        {"lemma": "hundo", "pos": "n", "language": "io"},
        {"lemma": "kato", "pos": "n", "language": "eo"},  # Should be skipped
    ]
    
    result = build_monodix(entries)
    xml_str = ET.tostring(result, encoding='unicode')
    
    assert 'hundo' in xml_str
    assert 'kato' not in xml_str  # Non-io entries should be filtered


def test_new_format_eo_translations_field():
    """Test that new format 'eo_translations' field is recognized."""
    entries = [
        {
            "lemma": "hundo",
            "pos": "n",
            "eo_translations": ["hundo", "hundego"]
        }
    ]
    
    result = build_bidix(entries)
    xml_str = ET.tostring(result, encoding='unicode')
    
    assert 'hundo' in xml_str
    # Should have at least one eo translation
    assert '<r>' in xml_str


def test_old_format_senses_translations():
    """Test that old format with senses/translations still works."""
    entries = [
        {
            "lemma": "hundo",
            "pos": "n",
            "language": "io",
            "senses": [
                {
                    "translations": [
                        {"lang": "eo", "term": "hundo"}
                    ]
                }
            ]
        }
    ]
    
    result = build_bidix(entries)
    xml_str = ET.tostring(result, encoding='unicode')
    
    assert 'hundo' in xml_str
    assert '<r>' in xml_str


def test_mixed_format_entries():
    """Test that both old and new formats can be processed together."""
    entries = [
        # New format
        {"lemma": "hundo", "eo_translations": ["hundo"]},
        # Old format
        {
            "lemma": "kato",
            "language": "io",
            "senses": [{"translations": [{"lang": "eo", "term": "kato"}]}]
        }
    ]
    
    result = build_bidix(entries)
    xml_str = ET.tostring(result, encoding='unicode')
    
    assert 'hundo' in xml_str
    assert 'kato' in xml_str


def test_entries_with_null_lemma_are_skipped():
    """Test that entries with null or missing lemma are skipped."""
    entries = [
        {"lemma": None, "eo_translations": ["test"]},
        {"eo_translations": ["test2"]},  # No lemma field
        {"lemma": "validword", "eo_translations": ["valid"]},
    ]
    
    result = build_bidix(entries)
    xml_str = ET.tostring(result, encoding='unicode')
    
    assert 'validword' in xml_str
    # Invalid entries should not cause crash


def test_entries_without_translations_are_skipped():
    """Test that entries without EO translations are skipped in bidix."""
    entries = [
        {"lemma": "notr", "eo_translations": []},  # Empty
        {"lemma": "hundo", "eo_translations": ["hundo"]},  # Valid
        {"lemma": "test"},  # No translations field
    ]
    
    result = build_bidix(entries)
    xml_str = ET.tostring(result, encoding='unicode')
    
    assert 'hundo' in xml_str
    # Entries without translations should be skipped
    assert xml_str.count('<e>') >= 1  # At least one valid entry


def test_large_entry_set():
    """Test that export handles large number of entries (regression for production data)."""
    # Simulate production-scale data: 14,481 entries
    entries = [
        {"lemma": f"word{i}", "eo_translations": [f"vorto{i}"]}
        for i in range(14481)
    ]
    
    result = build_bidix(entries)
    assert result is not None
    
    xml_str = ET.tostring(result, encoding='unicode')
    # Should have created entries
    assert xml_str.count('<e>') >= 14480


def test_monodix_with_morphology():
    """Test monodix generation with morphology information."""
    entries = [
        {
            "lemma": "hundo",
            "pos": "n",
            "morphology": {"paradigm": "o__n"}
        }
    ]
    
    result = build_monodix(entries)
    xml_str = ET.tostring(result, encoding='unicode')
    
    assert 'hundo' in xml_str
    assert 'o__n' in xml_str


def test_dict_with_entries_key():
    """Test that dict format with 'entries' key is handled (standardized format)."""
    # This tests the wrapper function's handling, but we can test the core functions
    entries_data = {
        "metadata": {"source": "test"},
        "entries": [
            {"lemma": "hundo", "eo_translations": ["hundo"]}
        ]
    }
    
    # In actual usage, the export_apertium function extracts the entries
    # Here we test that the entries themselves are handled correctly
    result = build_bidix(entries_data["entries"])
    xml_str = ET.tostring(result, encoding='unicode')
    
    assert 'hundo' in xml_str


if __name__ == "__main__":
    print("Running export_apertium tests...")
    
    tests = [
        ("New format without language field", test_new_format_entries_without_language_field),
        ("Old format with language field", test_old_format_entries_with_language_field),
        ("New format eo_translations field", test_new_format_eo_translations_field),
        ("Old format senses/translations", test_old_format_senses_translations),
        ("Mixed format entries", test_mixed_format_entries),
        ("Null lemma handling", test_entries_with_null_lemma_are_skipped),
        ("Empty translations handling", test_entries_without_translations_are_skipped),
        ("Large entry set (14,481)", test_large_entry_set),
        ("Monodix with morphology", test_monodix_with_morphology),
        ("Dict with entries key", test_dict_with_entries_key),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        try:
            test_func()
            print(f"✅ PASS: {name}")
            passed += 1
        except AssertionError as e:
            print(f"❌ FAIL: {name}")
            print(f"   Error: {e}")
            failed += 1
        except Exception as e:
            print(f"❌ ERROR: {name}")
            print(f"   Error: {e}")
            failed += 1
    
    print(f"\n{'='*60}")
    print(f"Results: {passed} passed, {failed} failed")
    print(f"{'='*60}")
    
    sys.exit(0 if failed == 0 else 1)

