"""
Unit tests for environment variable resolution in vector memory CLI.

Tests the environment-based collection policy and configuration loading.
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch, mock_open
import pytest

from vector_memory.cli.main import (
    _parse_dotenv,
    _env_get,
    _resolve_collection_name,
    _list_additional_collections,
    _allowed_collections,
)


class TestDotenvParsing:
    """Test .env file parsing functionality."""

    def test_parse_empty_dotenv(self):
        """Test parsing an empty .env file returns empty dict."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            f.write("")
            temp_path = Path(f.name)

        try:
            result = _parse_dotenv(temp_path)
            assert result == {}
        finally:
            temp_path.unlink()

    def test_parse_simple_dotenv(self):
        """Test parsing basic KEY=VALUE pairs."""
        content = """
# Comment line
MEMORY_COLLECTION_NAME=test_collection
QDRANT_URL=http://localhost:6333
EMBED_MODEL="mxbai-embed-large"
OLLAMA_URL='http://localhost:11434'

# Another comment
MEMORY_COLLECTION_NAME_2=secondary_mem
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            f.write(content)
            temp_path = Path(f.name)

        try:
            result = _parse_dotenv(temp_path)
            expected = {
                'MEMORY_COLLECTION_NAME': 'test_collection',
                'QDRANT_URL': 'http://localhost:6333',
                'EMBED_MODEL': 'mxbai-embed-large',
                'OLLAMA_URL': 'http://localhost:11434',
                'MEMORY_COLLECTION_NAME_2': 'secondary_mem'
            }
            assert result == expected
        finally:
            temp_path.unlink()

    def test_parse_malformed_lines_ignored(self):
        """Test that malformed lines are silently ignored."""
        content = """
VALID_KEY=valid_value
invalid line without equals
=MISSING_KEY
EMPTY_VALUE=
KEY_WITH_SPACES = spaced value
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            f.write(content)
            temp_path = Path(f.name)

        try:
            result = _parse_dotenv(temp_path)
            expected = {
                'VALID_KEY': 'valid_value',
                'EMPTY_VALUE': '',
                'KEY_WITH_SPACES': 'spaced value'
            }
            assert result == expected
        finally:
            temp_path.unlink()

    def test_parse_nonexistent_file(self):
        """Test parsing nonexistent file returns empty dict."""
        result = _parse_dotenv(Path("/nonexistent/path/.env"))
        assert result == {}


class TestEnvironmentGet:
    """Test environment variable retrieval with .env fallback."""

    @patch.dict(os.environ, {'TEST_VAR': 'from_env'})
    def test_env_get_from_process_env(self):
        """Test retrieval from process environment takes precedence."""
        with patch('vector_memory.cli.main._parse_dotenv') as mock_parse:
            mock_parse.return_value = {'TEST_VAR': 'from_dotenv'}

            result = _env_get('TEST_VAR')
            assert result == 'from_env'

    @patch.dict(os.environ, {}, clear=True)
    def test_env_get_from_dotenv_fallback(self):
        """Test fallback to .env when not in process environment."""
        with patch('vector_memory.cli.main._parse_dotenv') as mock_parse:
            mock_parse.return_value = {'TEST_VAR': 'from_dotenv'}

            result = _env_get('TEST_VAR')
            assert result == 'from_dotenv'

    @patch.dict(os.environ, {}, clear=True)
    def test_env_get_missing_key(self):
        """Test missing key returns None."""
        with patch('vector_memory.cli.main._parse_dotenv') as mock_parse:
            mock_parse.return_value = {}

            result = _env_get('MISSING_KEY')
            assert result is None

    @patch.dict(os.environ, {'EMPTY_VAR': '   '})
    def test_env_get_strips_whitespace(self):
        """Test whitespace stripping and empty string handling."""
        result = _env_get('EMPTY_VAR')
        assert result is None  # Should return None for whitespace-only values


class TestCollectionNameResolution:
    """Test collection name resolution from explicit args or environment."""

    def test_resolve_explicit_name(self):
        """Test explicit name takes precedence over environment."""
        result = _resolve_collection_name("explicit_collection")
        assert result == "explicit_collection"

    def test_resolve_explicit_name_strips_whitespace(self):
        """Test explicit name whitespace is stripped."""
        result = _resolve_collection_name("  spaced_collection  ")
        assert result == "spaced_collection"

    @patch('vector_memory.cli.main._env_get')
    def test_resolve_from_environment(self, mock_env_get):
        """Test fallback to MEMORY_COLLECTION_NAME environment variable."""
        mock_env_get.return_value = "env_collection"

        result = _resolve_collection_name(None)
        assert result == "env_collection"
        mock_env_get.assert_called_once_with("MEMORY_COLLECTION_NAME")

    @patch('vector_memory.cli.main._env_get')
    def test_resolve_missing_environment_raises(self, mock_env_get):
        """Test ValueError when environment variable not set."""
        mock_env_get.return_value = None

        with pytest.raises(ValueError, match="MEMORY_COLLECTION_NAME not set"):
            _resolve_collection_name(None)

    @patch('vector_memory.cli.main._env_get')
    def test_resolve_empty_explicit_fallback(self, mock_env_get):
        """Test empty explicit name falls back to environment."""
        mock_env_get.return_value = "env_collection"

        result = _resolve_collection_name("")
        assert result == "env_collection"

    @patch('vector_memory.cli.main._env_get')
    def test_resolve_whitespace_explicit_fallback(self, mock_env_get):
        """Test whitespace-only explicit name falls back to environment."""
        mock_env_get.return_value = "env_collection"

        result = _resolve_collection_name("   ")
        assert result == "env_collection"


class TestAdditionalCollections:
    """Test listing additional collections from environment."""

    @patch('vector_memory.cli.main._parse_dotenv')
    @patch.dict(os.environ, {
        'MEMORY_COLLECTION_NAME_2': 'second_collection',
        'MEMORY_COLLECTION_NAME_3': 'third_collection',
        'OTHER_VAR': 'should_be_ignored'
    })
    def test_list_additional_from_env(self, mock_parse):
        """Test listing additional collections from process environment."""
        mock_parse.return_value = {}

        result = _list_additional_collections()
        expected = ['second_collection', 'third_collection']
        assert sorted(result) == sorted(expected)

    @patch('vector_memory.cli.main._parse_dotenv')
    @patch.dict(os.environ, {}, clear=True)
    def test_list_additional_from_dotenv(self, mock_parse):
        """Test listing additional collections from .env file."""
        mock_parse.return_value = {
            'MEMORY_COLLECTION_NAME_2': 'dotenv_second',
            'MEMORY_COLLECTION_NAME_4': 'dotenv_fourth',
            'REGULAR_VAR': 'ignored'
        }

        result = _list_additional_collections()
        expected = ['dotenv_second', 'dotenv_fourth']
        assert sorted(result) == sorted(expected)

    @patch('vector_memory.cli.main._parse_dotenv')
    @patch.dict(os.environ, {
        'MEMORY_COLLECTION_NAME_2': 'env_override'
    })
    def test_env_overrides_dotenv(self, mock_parse):
        """Test process environment overrides .env values."""
        mock_parse.return_value = {
            'MEMORY_COLLECTION_NAME_2': 'dotenv_value'
        }

        result = _list_additional_collections()
        assert result == ['env_override']

    @patch('vector_memory.cli.main._parse_dotenv')
    @patch.dict(os.environ, {
        'MEMORY_COLLECTION_NAME_2': '  whitespace_collection  ',
        'MEMORY_COLLECTION_NAME_3': '',  # Empty should be filtered
        'MEMORY_COLLECTION_NAME_4': '   '  # Whitespace-only should be filtered
    })
    def test_filters_empty_and_strips_whitespace(self, mock_parse):
        """Test filtering empty values and whitespace stripping."""
        mock_parse.return_value = {}

        result = _list_additional_collections()
        assert result == ['whitespace_collection']

    @patch('vector_memory.cli.main._parse_dotenv')
    @patch.dict(os.environ, {
        'MEMORY_COLLECTION_NAME_2': 'duplicate',
        'MEMORY_COLLECTION_NAME_3': 'unique',
        'MEMORY_COLLECTION_NAME_4': 'duplicate'  # Should be deduped
    })
    def test_deduplicates_preserving_order(self, mock_parse):
        """Test deduplication while preserving declaration order."""
        mock_parse.return_value = {}

        result = _list_additional_collections()
        assert result == ['duplicate', 'unique']


class TestAllowedCollections:
    """Test building list of allowed collections from environment."""

    @patch('vector_memory.cli.main._env_get')
    @patch('vector_memory.cli.main._list_additional_collections')
    def test_allowed_collections_primary_only(self, mock_additional, mock_env_get):
        """Test with only primary collection configured."""
        mock_env_get.return_value = "primary_collection"
        mock_additional.return_value = []

        result = _allowed_collections()
        assert result == ["primary_collection"]

    @patch('vector_memory.cli.main._env_get')
    @patch('vector_memory.cli.main._list_additional_collections')
    def test_allowed_collections_with_additional(self, mock_additional, mock_env_get):
        """Test with primary and additional collections."""
        mock_env_get.return_value = "primary"
        mock_additional.return_value = ["second", "third"]

        result = _allowed_collections()
        assert result == ["primary", "second", "third"]

    @patch('vector_memory.cli.main._env_get')
    @patch('vector_memory.cli.main._list_additional_collections')
    def test_allowed_collections_deduplication(self, mock_additional, mock_env_get):
        """Test deduplication when primary appears in additional list."""
        mock_env_get.return_value = "primary"
        mock_additional.return_value = ["primary", "second"]  # Duplicate primary

        result = _allowed_collections()
        assert result == ["primary", "second"]  # Primary appears only once

    @patch('vector_memory.cli.main._env_get')
    @patch('vector_memory.cli.main._list_additional_collections')
    def test_allowed_collections_no_primary(self, mock_additional, mock_env_get):
        """Test with no primary collection but additional collections exist."""
        mock_env_get.return_value = None
        mock_additional.return_value = ["second", "third"]

        result = _allowed_collections()
        assert result == ["second", "third"]

    @patch('vector_memory.cli.main._env_get')
    @patch('vector_memory.cli.main._list_additional_collections')
    def test_allowed_collections_empty(self, mock_additional, mock_env_get):
        """Test with no collections configured."""
        mock_env_get.return_value = None
        mock_additional.return_value = []

        result = _allowed_collections()
        assert result == []


class TestIntegrationScenarios:
    """Integration tests for realistic environment scenarios."""

    def test_typical_project_setup(self):
        """Test typical project environment setup."""
        env_vars = {
            'MEMORY_COLLECTION_NAME': 'project_main',
            'MEMORY_COLLECTION_NAME_2': 'project_research',
            'QDRANT_URL': 'http://localhost:6333',
            'OLLAMA_URL': 'http://localhost:11434'
        }

        with patch.dict(os.environ, env_vars):
            # Test primary collection resolution
            primary = _resolve_collection_name(None)
            assert primary == 'project_main'

            # Test additional collections
            additional = _list_additional_collections()
            assert additional == ['project_research']

            # Test allowed collections
            allowed = _allowed_collections()
            assert allowed == ['project_main', 'project_research']

    def test_override_scenarios(self):
        """Test environment variable override scenarios."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            f.write("""
MEMORY_COLLECTION_NAME=dotenv_primary
MEMORY_COLLECTION_NAME_2=dotenv_secondary
""")
            dotenv_path = Path(f.name)

        try:
            # Mock the dotenv path resolution
            with patch('vector_memory.cli.main.Path') as mock_path:
                mock_path.return_value = dotenv_path

                # Test .env values used when no process env
                with patch.dict(os.environ, {}, clear=True):
                    primary = _resolve_collection_name(None)
                    assert primary == 'dotenv_primary'

                # Test process env overrides .env
                with patch.dict(os.environ, {'MEMORY_COLLECTION_NAME': 'env_override'}):
                    primary = _resolve_collection_name(None)
                    assert primary == 'env_override'

        finally:
            dotenv_path.unlink()

    def test_error_conditions(self):
        """Test various error conditions and edge cases."""
        with patch.dict(os.environ, {}, clear=True):
            with patch('vector_memory.cli.main._parse_dotenv', return_value={}):
                # Test missing primary collection
                with pytest.raises(ValueError):
                    _resolve_collection_name(None)

                # Test empty allowed collections
                allowed = _allowed_collections()
                assert allowed == []
