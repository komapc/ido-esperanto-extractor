#!/usr/bin/env python3
"""
Test runner for Ido-Esperanto extractor tests.
"""
import sys
import unittest
import tempfile
import shutil
from pathlib import Path

# Add scripts directory to path
scripts_dir = Path(__file__).parent / "scripts"
sys.path.insert(0, str(scripts_dir))

# Add tests directory to path
tests_dir = Path(__file__).parent / "tests"
sys.path.insert(0, str(tests_dir))

def setup_test_environment():
    """Set up test environment with temporary directories."""
    # Create temporary test directory
    test_temp_dir = Path(tempfile.mkdtemp(prefix="extractor_test_"))
    
    # Set environment variables for tests
    import os
    os.environ['TEST_TEMP_DIR'] = str(test_temp_dir)
    os.environ['TEST_DATA_DIR'] = str(tests_dir / "fixtures")
    
    return test_temp_dir

def cleanup_test_environment(temp_dir):
    """Clean up test environment."""
    if temp_dir.exists():
        shutil.rmtree(temp_dir, ignore_errors=True)

def run_tests():
    """Run all tests."""
    temp_dir = setup_test_environment()
    
    try:
        # Discover and run tests
        loader = unittest.TestLoader()
        start_dir = str(tests_dir)
        suite = loader.discover(start_dir, pattern='test_*.py')
        
        runner = unittest.TextTestRunner(verbosity=2)
        result = runner.run(suite)
        
        # Return exit code
        return 0 if result.wasSuccessful() else 1
    finally:
        cleanup_test_environment(temp_dir)

if __name__ == '__main__':
    sys.exit(run_tests())
