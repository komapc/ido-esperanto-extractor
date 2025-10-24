# Test Fixtures

This directory contains test data and fixtures used by the test suite.

## Structure

- `sample_data/` - Sample JSON data for testing
- `expected_outputs/` - Expected outputs for comparison tests
- `test_dumps/` - Small test dump files (if needed)

## Usage

Tests should use the fixtures defined in `conftest.py` rather than directly accessing files in this directory.
