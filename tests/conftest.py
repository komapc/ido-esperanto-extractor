"""
Pytest configuration and shared fixtures for tests.
"""
import tempfile
import pytest
from pathlib import Path


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test artifacts."""
    temp_path = Path(tempfile.mkdtemp())
    yield temp_path
    # Cleanup after test
    import shutil
    shutil.rmtree(temp_path, ignore_errors=True)


@pytest.fixture
def test_data_dir():
    """Path to test data directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_wiktionary_data():
    """Sample Wiktionary data for testing."""
    return {
        'metadata': {
            'source_name': 'io_wiktionary',
            'version': '2.0',
            'dump_file': 'test_dump.xml.bz2'
        },
        'entries': [
            {
                'lemma': 'hundo',
                'pos': 'n',
                'language': 'io',
                'senses': [
                    {
                        'translations': [
                            {'lang': 'eo', 'term': 'hundo'}
                        ]
                    }
                ],
                'morphology': {'paradigm': 'o__n'},
                'provenance': [{'source': 'io_wiktionary'}]
            },
            {
                'lemma': 'kato',
                'pos': 'n',
                'language': 'io',
                'senses': [],
                'morphology': {},
                'provenance': [{'source': 'io_wiktionary'}]
            }
        ]
    }


@pytest.fixture
def sample_wikipedia_data():
    """Sample Wikipedia data for testing."""
    return {
        'metadata': {
            'source_name': 'io_wikipedia',
            'version': '2.0'
        },
        'entries': [
            {
                'lemma': 'Esperanto',
                'pos': 'propn',
                'language': 'io',
                'provenance': [{'source': 'io_wikipedia', 'page': 'Esperanto'}],
                'categories': ['kategorio:lingui'],
                'text_length': 11042
            },
            {
                'lemma': 'Ido',
                'pos': 'propn',
                'language': 'io',
                'provenance': [{'source': 'io_wikipedia', 'page': 'Ido'}],
                'categories': ['kategorio:lingui'],
                'text_length': 17237
            }
        ]
    }
