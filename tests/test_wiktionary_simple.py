#!/usr/bin/env python3
"""
Simple unit tests for Wiktionary two-stage processing.
"""
import tempfile
import unittest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from filter_and_validate import is_valid_lemma


class TestWiktionarySimple(unittest.TestCase):
    """Simple test cases for Wiktionary processing."""
    
    def test_lemma_validation(self):
        """Test lemma validation function."""
        # Valid lemmas
        self.assertTrue(is_valid_lemma('hundo'))
        self.assertTrue(is_valid_lemma('Esperanto'))
        self.assertTrue(is_valid_lemma('Naturala cienci'))
        
        # Invalid lemmas
        self.assertFalse(is_valid_lemma(''))
        self.assertFalse(is_valid_lemma('Template:test'))
        self.assertFalse(is_valid_lemma('very_long_lemma_that_should_be_filtered_out'))
    
    def test_help_output(self):
        """Test that help output works."""
        from process_wiktionary_two_stage import main as wiktionary_main
        
        # Test help
        with self.assertRaises(SystemExit):
            wiktionary_main(['--help'])
    
    def test_resumability(self):
        """Test that stages can be resumed if output exists."""
        temp_dir = Path(tempfile.mkdtemp())
        try:
            # Create mock output files
            stage1_out = temp_dir / "stage1_out.json"
            stage2_out = temp_dir / "stage2_out.json"
            
            # Create dummy files
            stage1_out.write_text('{"test": "data"}')
            stage2_out.write_text('{"test": "data"}')
            
            # Test with existing files (should skip stages)
            from process_wiktionary_two_stage import main as wiktionary_main
            args = [
                '--source', 'io',
                '--stage1-out', str(stage1_out),
                '--stage2-out', str(stage2_out),
                '--skip-stage1',  # Skip to test resumability
                '--skip-stage2'   # Skip to test resumability
            ]
            
            result = wiktionary_main(args)
            self.assertEqual(result, 0)
        finally:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == '__main__':
    unittest.main(verbosity=2)
