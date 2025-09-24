"""
Unit tests for project initialization and MCP integration functionality.

Tests new-project command, MCP shim generation, and Qdrant collection management.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, mock_open
import pytest
from argparse import Namespace

from vector_memory.cli.main import (
    new_project,
    _write_file_if_missing,
    _generate_doc,
    _list_qdrant_collections,
    _fetch_collections,
    _SHIM_CONTENT
)


class TestWriteFileIfMissing:
    """Test conditional file writing utility."""

    def test_write_new_file(self):
        """Test writing to nonexistent file returns True."""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "new_file.txt"
            content = "Test content"

            result = _write_file_if_missing(file_path, content)

            assert result is True
            assert file_path.exists()
            assert file_path.read_text() == content

    def test_skip_existing_file(self):
        """Test skipping existing file returns False."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write("Existing content")
            file_path = Path(f.name)

        try:
            result = _write_file_if_missing(file_path, "New content")

            assert result is False
            assert file_path.read_text() == "Existing content"  # Unchanged
        finally:
            file_path.unlink()

    def test_create_parent_directories(self):
        """Test automatic parent directory creation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            nested_path = Path(temp_dir) / "subdir" / "nested" / "file.txt"
            content = "Nested content"

            result = _write_file_if_missing(nested_path, content)

            assert result is True
            assert nested_path.exists()
            assert nested_path.read_text() == content


class TestDocumentGeneration:
    """Test MCP documentation generation."""

    @patch('vector_memory.cli.main._list_additional_collections')
    def test_generate_doc_with_additional_collections(self, mock_additional):
        """Test documentation generation with additional collections."""
        mock_additional.return_value = ["secondary_mem", "research_mem"]

        doc = _generate_doc("primary_collection")

        assert "primary_collection" in doc
        assert "secondary_mem" in doc
        assert "research_mem" in doc
        assert "MEMORY_COLLECTION_NAME" in doc
        assert "vector-memory ensure-collection" in doc

    @patch('vector_memory.cli.main._list_additional_collections')
    def test_generate_doc_no_additional(self, mock_additional):
        """Test documentation generation without additional collections."""
        mock_additional.return_value = []

        doc = _generate_doc("solo_collection")

        assert "solo_collection" in doc
        assert "(none configured)" in doc
        assert "Additional:" in doc

    def test_generate_doc_structure(self):
        """Test generated documentation contains required sections."""
        with patch('vector_memory.cli.main._list_additional_collections', return_value=[]):
            doc = _generate_doc("test_collection")

        # Check for required sections
        assert "# Vector Memory MCP Usage" in doc
        assert "Collections" in doc
        assert "Environment variables" in doc
        assert "CLI" in doc
        assert "MCP shim" in doc
        assert "Policy" in doc

        # Check for specific commands
        assert "ensure-collection" in doc
        assert "remember" in doc
        assert "recall" in doc


class TestQdrantCollectionListing:
    """Test Qdrant collection listing functionality."""

    @patch('vector_memory.cli.main.requests.get')
    @patch('vector_memory.cli.main.operation_timeout')
    def test_fetch_collections_success(self, mock_timeout, mock_get):
        """Test successful collection fetching from Qdrant."""
        mock_timeout.__enter__ = Mock()
        mock_timeout.__exit__ = Mock()

        # Mock response
        mock_response = Mock()
        mock_response.json.return_value = {
            "result": {
                "collections": [
                    {"name": "collection_a"},
                    {"name": "collection_b"},
                    {"name": "collection_c"},
                ]
            }
        }
        mock_get.return_value = mock_response

        result = _fetch_collections("http://localhost:6333", 30)

        assert result == ["collection_a", "collection_b", "collection_c"]
        mock_get.assert_called_once_with("http://localhost:6333/collections", timeout=30)
        mock_response.raise_for_status.assert_called_once()

    @patch('vector_memory.cli.main.requests.get')
    def test_fetch_collections_deduplication(self, mock_get):
        """Test collection name deduplication and sorting."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "result": {
                "collections": [
                    {"name": "zebra_collection"},
                    {"name": "alpha_collection"},
                    {"name": "zebra_collection"},  # Duplicate
                    {"name": "beta_collection"},
                ]
            }
        }
        mock_get.return_value = mock_response

        result = _fetch_collections("http://localhost:6333", 30)

        assert result == ["alpha_collection", "beta_collection", "zebra_collection"]

    @patch('vector_memory.cli.main.requests.get')
    def test_fetch_collections_filters_invalid(self, mock_get):
        """Test filtering of invalid collection entries."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "result": {
                "collections": [
                    {"name": "valid_collection"},
                    {"name": ""},  # Empty name
                    {"name": None},  # None name
                    {"name": "  "},  # Whitespace only
                    {"invalid": "no_name_field"},
                    {"name": "another_valid"},
                ]
            }
        }
        mock_get.return_value = mock_response

        result = _fetch_collections("http://localhost:6333", 30)

        assert result == ["another_valid", "valid_collection"]

    @patch('vector_memory.cli.main.requests.get')
    def test_fetch_collections_empty_response(self, mock_get):
        """Test handling of empty or malformed responses."""
        mock_response = Mock()
        mock_response.json.return_value = None
        mock_get.return_value = mock_response

        result = _fetch_collections("http://localhost:6333", 30)

        assert result == []

    @patch('vector_memory.cli.main.requests.get')
    def test_fetch_collections_missing_result(self, mock_get):
        """Test handling of response missing result field."""
        mock_response = Mock()
        mock_response.json.return_value = {"status": "ok"}  # No result field
        mock_get.return_value = mock_response

        result = _fetch_collections("http://localhost:6333", 30)

        assert result == []

    @patch('vector_memory.cli.main._fetch_collections')
    @patch('vector_memory.cli.main.operation_timeout')
    @patch('vector_memory.cli.main.http_timeout_seconds')
    @patch('vector_memory.cli.main.qdrant_url')
    def test_list_qdrant_collections_success(self, mock_url, mock_timeout_seconds,
                                           mock_operation_timeout, mock_fetch):
        """Test successful collection listing with timeout."""
        mock_url.return_value = "http://localhost:6333"
        mock_timeout_seconds.return_value = 30
        mock_operation_timeout.__enter__ = Mock()
        mock_operation_timeout.__exit__ = Mock()
        mock_fetch.return_value = ["collection1", "collection2"]

        result = _list_qdrant_collections()

        assert result == ["collection1", "collection2"]
        mock_fetch.assert_called_once_with("http://localhost:6333", 30)

    @patch('vector_memory.cli.main._fetch_collections')
    @patch('vector_memory.cli.main.operation_timeout')
    def test_list_qdrant_collections_exception(self, mock_operation_timeout, mock_fetch):
        """Test collection listing handles exceptions gracefully."""
        mock_operation_timeout.__enter__ = Mock()
        mock_operation_timeout.__exit__ = Mock()
        mock_fetch.side_effect = Exception("Network error")

        result = _list_qdrant_collections()

        assert result == []  # Should return empty list on error


class TestNewProjectCommand:
    """Test new-project command functionality."""

    @patch('vector_memory.cli.main._env_get')
    @patch('vector_memory.cli.main.EnsureCollectionUseCase')
    @patch('vector_memory.cli.main._write_file_if_missing')
    @patch('vector_memory.cli.main._generate_doc')
    @patch('vector_memory.cli.main._list_additional_collections')
    def test_new_project_success(self, mock_additional, mock_generate_doc,
                                mock_write_file, mock_use_case_class, mock_env_get):
        """Test successful new project initialization."""
        # Setup mocks
        mock_env_get.return_value = "project_collection"
        mock_additional.return_value = ["secondary_collection"]
        mock_generate_doc.return_value = "Generated documentation"
        mock_write_file.side_effect = [True, True]  # Both files created

        mock_emb = Mock()
        mock_emb.get_dimension.return_value = 1024
        mock_store = Mock()

        mock_use_case = Mock()
        mock_use_case_class.return_value = mock_use_case

        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('vector_memory.cli.main.Path') as mock_path_class:
                mock_cwd = Mock()
                mock_cwd.resolve.return_value = Path(temp_dir)
                mock_path_class.return_value = mock_cwd

                with patch('builtins.print') as mock_print:
                    result = new_project(mock_emb, mock_store)

        assert result == 0

        # Verify collection creation
        mock_use_case.execute.assert_called_once()
        request = mock_use_case.execute.call_args[0][0]
        assert request.collection == "project_collection"
        assert request.dim == 1024
        assert request.distance == "Cosine"
        assert request.recreate is False

        # Verify file creation attempts
        assert mock_write_file.call_count == 2
        shim_call, doc_call = mock_write_file.call_args_list
        assert "mcp_vector_memory.py" in str(shim_call[0][0])
        assert shim_call[0][1] == _SHIM_CONTENT
        assert "VECTOR_MEMORY_MCP.md" in str(doc_call[0][0])
        assert doc_call[0][1] == "Generated documentation"

    @patch('vector_memory.cli.main._env_get')
    def test_new_project_missing_env(self, mock_env_get):
        """Test new project fails when MEMORY_COLLECTION_NAME not set."""
        mock_env_get.return_value = None

        with patch('builtins.print') as mock_print:
            result = new_project(Mock(), Mock())

        assert result == 2
        mock_print.assert_called_once()
        call_args = mock_print.call_args[0][0]
        error_data = json.loads(call_args)
        assert error_data["status"] == "error"
        assert "MEMORY_COLLECTION_NAME is not set" in error_data["error"]

    @patch('vector_memory.cli.main._env_get')
    @patch('vector_memory.cli.main.EnsureCollectionUseCase')
    @patch('vector_memory.cli.main._write_file_if_missing')
    @patch('vector_memory.cli.main._generate_doc')
    @patch('vector_memory.cli.main._list_additional_collections')
    def test_new_project_files_exist(self, mock_additional, mock_generate_doc,
                                    mock_write_file, mock_use_case_class, mock_env_get):
        """Test new project when files already exist."""
        mock_env_get.return_value = "existing_project"
        mock_additional.return_value = []
        mock_generate_doc.return_value = "Doc content"
        mock_write_file.side_effect = [False, False]  # Both files already exist

        mock_emb = Mock()
        mock_emb.get_dimension.return_value = 512
        mock_use_case_class.return_value = Mock()

        with tempfile.TemporaryDirectory():
            with patch('vector_memory.cli.main.Path'):
                with patch('builtins.print') as mock_print:
                    result = new_project(mock_emb, Mock())

        assert result == 0

        # Verify output indicates files were not created
        call_args = mock_print.call_args[0][0]
        output_data = json.loads(call_args)
        assert output_data["mcp_shim_created"] is False
        assert output_data["doc_created"] is False

    @patch('vector_memory.cli.main._env_get')
    @patch('vector_memory.cli.main.EnsureCollectionUseCase')
    @patch('vector_memory.cli.main._write_file_if_missing')
    def test_new_project_chmod_handling(self, mock_write_file, mock_use_case_class, mock_env_get):
        """Test new project handles chmod operations gracefully."""
        mock_env_get.return_value = "test_project"
        mock_write_file.side_effect = [True, False]  # Shim created, doc exists

        mock_emb = Mock()
        mock_emb.get_dimension.return_value = 768
        mock_use_case_class.return_value = Mock()

        with tempfile.TemporaryDirectory() as temp_dir:
            shim_path = Path(temp_dir) / "mcp_vector_memory.py"
            shim_path.write_text("#!/usr/bin/env python3")  # Create actual file for chmod

            with patch('vector_memory.cli.main.Path') as mock_path_class:
                mock_cwd = Mock()
                mock_cwd.resolve.return_value = Path(temp_dir)
                mock_cwd.__truediv__ = lambda self, other: shim_path if "mcp_vector_memory.py" in str(other) else Path(temp_dir) / str(other)
                mock_path_class.return_value = mock_cwd

                with patch('builtins.print'):
                    result = new_project(mock_emb, Mock())

        assert result == 0
        # Should complete successfully even if chmod fails


class TestMCPShimContent:
    """Test MCP shim template content."""

    def test_shim_content_structure(self):
        """Test shim contains required structure and imports."""
        content = _SHIM_CONTENT

        # Check required imports
        assert "from vector_memory.mcp.api import" in content
        assert "vector_create_collection" in content
        assert "vector_index_memory_bank" in content
        assert "vector_query" in content
        assert "vector_delete" in content

        # Check CLI structure
        assert "def run(" in content
        assert "argparse.ArgumentParser" in content
        assert "add_subparsers" in content

        # Check subcommands
        assert 'sub.add_parser("ensure")' in content
        assert 'sub.add_parser("index")' in content
        assert 'sub.add_parser("query")' in content
        assert 'sub.add_parser("delete")' in content

        # Check main entry point
        assert "def main():" in content
        assert 'if __name__ == "__main__":' in content
        assert "SystemExit(main())" in content

    def test_shim_content_executable(self):
        """Test shim content starts with shebang."""
        content = _SHIM_CONTENT

        assert content.startswith("#!/usr/bin/env python3")

    def test_shim_content_error_handling(self):
        """Test shim includes error handling."""
        content = _SHIM_CONTENT

        assert "try:" in content
        assert "except Exception as ex:" in content
        assert "json.dumps" in content
        assert '"status":"error"' in content


class TestProjectInitIntegration:
    """Integration tests for project initialization workflow."""

    @patch.dict('os.environ', {
        'MEMORY_COLLECTION_NAME': 'integration_test',
        'MEMORY_COLLECTION_NAME_2': 'integration_secondary'
    })
    @patch('vector_memory.cli.main.EnsureCollectionUseCase')
    def test_complete_initialization_workflow(self, mock_use_case_class):
        """Test complete project initialization from environment setup to file creation."""
        mock_emb = Mock()
        mock_emb.get_dimension.return_value = 1024
        mock_store = Mock()
        mock_use_case_class.return_value = Mock()

        with tempfile.TemporaryDirectory() as temp_dir:
            # Change to temp directory for file creation
            original_cwd = Path.cwd()
            temp_path = Path(temp_dir)

            try:
                import os
                os.chdir(temp_dir)

                with patch('builtins.print') as mock_print:
                    result = new_project(mock_emb, mock_store)

                assert result == 0

                # Verify files were created
                shim_path = temp_path / "mcp_vector_memory.py"
                doc_path = temp_path / "VECTOR_MEMORY_MCP.md"

                assert shim_path.exists()
                assert doc_path.exists()

                # Verify content quality
                shim_content = shim_path.read_text()
                assert shim_content == _SHIM_CONTENT

                doc_content = doc_path.read_text()
                assert "integration_test" in doc_content
                assert "integration_secondary" in doc_content

                # Verify output
                output_data = json.loads(mock_print.call_args[0][0])
                assert output_data["status"] == "ok"
                assert output_data["collection"] == "integration_test"
                assert output_data["dimension"] == 1024
                assert output_data["mcp_shim_created"] is True
                assert output_data["doc_created"] is True
                assert "integration_secondary" in output_data["additional_collections"]

            finally:
                os.chdir(original_cwd)
