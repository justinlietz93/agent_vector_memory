"""
Unit tests for vector memory operations: indexing, remembering, and chunking.

Tests the memory bank loading and chat turn storage functionality.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, call
import pytest
from argparse import Namespace

from vector_memory.cli.main import index_memory, remember_memory, store_turn, _chunk
from vector_memory.domain.models import MemoryItem


class TestMemoryBankIndexing:
    """Test memory-bank indexing functionality."""

    @patch('vector_memory.cli.main.load_memory_items')
    @patch('vector_memory.cli.main.UpsertMemoryUseCase')
    @patch('vector_memory.cli.main._resolve_collection_name')
    def test_index_memory_success(self, mock_resolve, mock_use_case_class, mock_loader):
        """Test successful memory bank indexing."""
        # Setup mocks
        mock_resolve.return_value = "test_collection"
        mock_items = [
            MemoryItem(text="Memory 1", meta={"source": "file1.md"}),
            MemoryItem(text="Memory 2", meta={"source": "file2.md"}),
        ]
        mock_loader.return_value = mock_items
        mock_use_case = Mock()
        mock_use_case.execute.return_value = Mock(raw={"indexed": 2})
        mock_use_case_class.return_value = mock_use_case

        mock_emb = Mock()
        mock_store = Mock()

        ns = Namespace(
            name="test_collection",
            dir="memory-bank",
            idns="mem",
            max_items=None
        )

        with patch('builtins.print') as mock_print:
            result = index_memory(ns, mock_emb, mock_store)

        assert result == 0
        mock_loader.assert_called_once_with(Path("memory-bank"))
        mock_use_case.execute.assert_called_once()

        # Verify request structure
        request = mock_use_case.execute.call_args[0][0]
        assert request.collection == "test_collection"
        assert request.items == mock_items
        assert request.id_namespace == "mem"

    @patch('vector_memory.cli.main.load_memory_items')
    @patch('vector_memory.cli.main.UpsertMemoryUseCase')
    @patch('vector_memory.cli.main._resolve_collection_name')
    def test_index_memory_with_max_items(self, mock_resolve, mock_use_case_class, mock_loader):
        """Test indexing with max items limit."""
        mock_resolve.return_value = "test_collection"
        mock_items = [MemoryItem(text=f"Memory {i}", meta={}) for i in range(10)]
        mock_loader.return_value = mock_items
        mock_use_case = Mock()
        mock_use_case.execute.return_value = Mock(raw={})
        mock_use_case_class.return_value = mock_use_case

        ns = Namespace(
            name="test_collection",
            dir="memory-bank",
            idns="mem",
            max_items=3
        )

        with patch('builtins.print'):
            result = index_memory(ns, Mock(), Mock())

        assert result == 0

        # Verify only first 3 items are indexed
        request = mock_use_case.execute.call_args[0][0]
        assert len(request.items) == 3

    @patch('vector_memory.cli.main.load_memory_items')
    @patch('vector_memory.cli.main._resolve_collection_name')
    def test_index_memory_empty_directory(self, mock_resolve, mock_loader):
        """Test indexing empty directory."""
        mock_resolve.return_value = "test_collection"
        mock_loader.return_value = []

        ns = Namespace(
            name="test_collection",
            dir="empty-dir",
            idns="mem",
            max_items=None
        )

        with patch('vector_memory.cli.main.UpsertMemoryUseCase') as mock_use_case_class:
            mock_use_case = Mock()
            mock_use_case.execute.return_value = Mock(raw={})
            mock_use_case_class.return_value = mock_use_case

            with patch('builtins.print'):
                result = index_memory(ns, Mock(), Mock())

        assert result == 0

        # Verify empty list is processed
        request = mock_use_case.execute.call_args[0][0]
        assert len(request.items) == 0


class TestRememberCommand:
    """Test remember command functionality."""

    @patch('vector_memory.cli.main.UpsertMemoryUseCase')
    @patch('vector_memory.cli.main._resolve_collection_name')
    def test_remember_text_args(self, mock_resolve, mock_use_case_class):
        """Test remembering from --text arguments."""
        mock_resolve.return_value = "test_collection"
        mock_use_case = Mock()
        mock_use_case.execute.return_value = Mock(raw={})
        mock_use_case_class.return_value = mock_use_case

        ns = Namespace(
            name="test_collection",
            text=["First memory", "Second memory", "  ", "Third memory"],  # Include whitespace
            file=None,
            tag=["important", "project"],
            idns="convo"
        )

        with patch('builtins.print') as mock_print:
            result = remember_memory(ns, Mock(), Mock())

        assert result == 0
        mock_use_case.execute.assert_called_once()

        # Verify request structure
        request = mock_use_case.execute.call_args[0][0]
        assert len(request.items) == 3  # Whitespace-only filtered out
        assert request.id_namespace == "convo"

        # Check memory items
        texts = [item.text for item in request.items]
        assert "First memory" in texts
        assert "Second memory" in texts
        assert "Third memory" in texts

        # Check metadata
        for item in request.items:
            assert item.meta["kind"] == "conversational"
            assert item.meta["tags"] == ["important", "project"]

    @patch('vector_memory.cli.main.UpsertMemoryUseCase')
    @patch('vector_memory.cli.main._resolve_collection_name')
    def test_remember_from_file(self, mock_resolve, mock_use_case_class):
        """Test remembering from file contents."""
        mock_resolve.return_value = "test_collection"
        mock_use_case = Mock()
        mock_use_case.execute.return_value = Mock(raw={})
        mock_use_case_class.return_value = mock_use_case

        # Create temporary file with content
        file_content = """
# This is a comment
First line of memories

Second line of memories

Third line of memories
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(file_content)
            temp_path = Path(f.name)

        try:
            ns = Namespace(
                name="test_collection",
                text=[],
                file=str(temp_path),
                tag=[],
                idns="file"
            )

            with patch('builtins.print'):
                result = remember_memory(ns, Mock(), Mock())

            assert result == 0

            # Verify non-empty lines are captured
            request = mock_use_case.execute.call_args[0][0]
            texts = [item.text for item in request.items]
            assert "# This is a comment" in texts
            assert "First line of memories" in texts
            assert "Second line of memories" in texts
            assert "Third line of memories" in texts
            assert len(request.items) == 4  # Empty lines filtered

        finally:
            temp_path.unlink()

    @patch('vector_memory.cli.main.UpsertMemoryUseCase')
    @patch('vector_memory.cli.main._resolve_collection_name')
    def test_remember_combined_sources(self, mock_resolve, mock_use_case_class):
        """Test remembering from both text args and file."""
        mock_resolve.return_value = "test_collection"
        mock_use_case = Mock()
        mock_use_case.execute.return_value = Mock(raw={})
        mock_use_case_class.return_value = mock_use_case

        # Create file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("File memory line")
            temp_path = Path(f.name)

        try:
            ns = Namespace(
                name="test_collection",
                text=["Text arg memory"],
                file=str(temp_path),
                tag=[],
                idns="combined"
            )

            with patch('builtins.print'):
                result = remember_memory(ns, Mock(), Mock())

            assert result == 0

            # Verify both sources are included
            request = mock_use_case.execute.call_args[0][0]
            texts = [item.text for item in request.items]
            assert "Text arg memory" in texts
            assert "File memory line" in texts
            assert len(request.items) == 2

        finally:
            temp_path.unlink()

    @patch('vector_memory.cli.main._resolve_collection_name')
    def test_remember_empty_input(self, mock_resolve):
        """Test remember with no text or file produces empty result."""
        mock_resolve.return_value = "test_collection"

        ns = Namespace(
            name="test_collection",
            text=None,
            file=None,
            tag=[],
            idns="empty"
        )

        with patch('builtins.print') as mock_print:
            result = remember_memory(ns, Mock(), Mock())

        assert result == 0
        mock_print.assert_called_once()
        call_args = mock_print.call_args[0][0]
        result_data = json.loads(call_args)
        assert result_data["status"] == "ok"
        assert result_data["result"]["indexed"] == 0

    @patch('vector_memory.cli.main._resolve_collection_name')
    def test_remember_nonexistent_file(self, mock_resolve):
        """Test remember handles nonexistent file gracefully."""
        mock_resolve.return_value = "test_collection"

        ns = Namespace(
            name="test_collection",
            text=["Text memory"],
            file="/nonexistent/file.txt",
            tag=[],
            idns="missing"
        )

        with patch('vector_memory.cli.main.UpsertMemoryUseCase') as mock_use_case_class:
            mock_use_case = Mock()
            mock_use_case.execute.return_value = Mock(raw={})
            mock_use_case_class.return_value = mock_use_case

            with patch('builtins.print'):
                result = remember_memory(ns, Mock(), Mock())

        assert result == 0

        # Should only include text arg, file silently ignored
        request = mock_use_case.execute.call_args[0][0]
        assert len(request.items) == 1
        assert request.items[0].text == "Text memory"


class TestChunkingFunction:
    """Test text chunking functionality."""

    def test_chunk_short_text(self):
        """Test chunking text shorter than chunk size."""
        text = "Short text"
        result = _chunk(text, 100)

        assert result == ["Short text"]

    def test_chunk_exact_size(self):
        """Test chunking text exactly equal to chunk size."""
        text = "12345"
        result = _chunk(text, 5)

        assert result == ["12345"]

    def test_chunk_multiple_chunks(self):
        """Test chunking text into multiple chunks."""
        text = "123456789"
        result = _chunk(text, 3)

        assert result == ["123", "456", "789"]

    def test_chunk_uneven_division(self):
        """Test chunking text with remainder."""
        text = "1234567"
        result = _chunk(text, 3)

        assert result == ["123", "456", "7"]

    def test_chunk_zero_size(self):
        """Test chunking with zero size uses minimum of 1."""
        text = "test"
        result = _chunk(text, 0)

        assert result == ["t", "e", "s", "t"]

    def test_chunk_negative_size(self):
        """Test chunking with negative size uses minimum of 1."""
        text = "test"
        result = _chunk(text, -5)

        assert result == ["t", "e", "s", "t"]

    def test_chunk_empty_text(self):
        """Test chunking empty text."""
        text = ""
        result = _chunk(text, 10)

        assert result == []

    def test_chunk_large_text(self):
        """Test chunking larger text maintains character boundaries."""
        text = "A" * 1000
        result = _chunk(text, 333)

        assert len(result) == 4  # 333, 333, 333, 1
        assert result[0] == "A" * 333
        assert result[1] == "A" * 333
        assert result[2] == "A" * 333
        assert result[3] == "A" * 1
        assert "".join(result) == text


class TestStoreTurnIntegration:
    """Integration tests for store-turn functionality."""

    @patch('vector_memory.cli.main._resolve_collection_name')
    @patch('vector_memory.cli.main._list_qdrant_collections')
    @patch('vector_memory.cli.main.UpsertMemoryUseCase')
    @patch('vector_memory.cli.main.chat_chunk_chars')
    def test_store_turn_with_chunking(self, mock_chunk_chars, mock_use_case_class,
                                     mock_collections, mock_resolve):
        """Test store-turn with text chunking."""
        mock_resolve.return_value = "test_collection"
        mock_collections.return_value = ["test_collection"]
        mock_chunk_chars.return_value = 10  # Small chunks for testing
        mock_use_case = Mock()
        mock_use_case.execute.return_value = Mock(raw={})
        mock_use_case_class.return_value = mock_use_case

        # Long text that will be chunked
        long_text = "This is a very long message that will be split into multiple chunks."

        ns = Namespace(
            name="test_collection",
            thread_id="thread123",
            turn_index=1,
            role="assistant",
            text=long_text,
            model="gpt-4",
            tool_calls='{"function": "test"}',
            files=["file1.py", "file2.py"],
            idns="chat",
            chunk_chars=None
        )

        with patch('builtins.print'):
            result = store_turn(ns, Mock(), Mock())

        assert result == 0

        # Verify multiple chunks were created
        request = mock_use_case.execute.call_args[0][0]
        assert len(request.items) > 1

        # Verify chunk metadata
        for i, item in enumerate(request.items):
            assert item.meta["thread_id"] == "thread123"
            assert item.meta["turn_index"] == 1
            assert item.meta["role"] == "assistant"
            assert item.meta["chunk_index"] == i
            assert item.meta["model"] == "gpt-4"
            assert item.meta["tool_calls"] == {"function": "test"}
            assert item.meta["files_touched"] == ["file1.py", "file2.py"]
            assert "ts" in item.meta
            assert "message_id" in item.meta

        # Verify text reconstruction
        reconstructed = "".join(item.text for item in request.items)
        assert reconstructed == long_text

    @patch('vector_memory.cli.main._resolve_collection_name')
    @patch('vector_memory.cli.main._list_qdrant_collections')
    @patch('vector_memory.cli.main.UpsertMemoryUseCase')
    def test_store_turn_user_minimal(self, mock_use_case_class, mock_collections, mock_resolve):
        """Test store-turn for user with minimal metadata."""
        mock_resolve.return_value = "test_collection"
        mock_collections.return_value = ["test_collection"]
        mock_use_case = Mock()
        mock_use_case.execute.return_value = Mock(raw={})
        mock_use_case_class.return_value = mock_use_case

        ns = Namespace(
            thread_id="thread456",
            turn_index=0,
            role="user",
            text="Hello, world!",
            model=None,  # Users don't have models
            tool_calls=None,
            files=[],
            idns="chat",
            chunk_chars=1000
        )

        with patch('builtins.print'):
            result = store_turn(ns, Mock(), Mock())

        assert result == 0

        request = mock_use_case.execute.call_args[0][0]
        assert len(request.items) == 1

        item = request.items[0]
        assert item.text == "Hello, world!"
        assert item.meta["role"] == "user"
        assert item.meta["turn_index"] == 0
        assert "model" not in item.meta  # None values filtered out
        assert "tool_calls" not in item.meta

    def test_store_turn_invalid_json_tool_calls(self):
        """Test store-turn handles invalid JSON in tool_calls gracefully."""
        ns = Namespace(
            thread_id="thread789",
            turn_index=1,
            role="assistant",
            text="Test message",
            tool_calls='{"invalid": json}',  # Invalid JSON
            files=[],
            idns="chat"
        )

        with patch('vector_memory.cli.main._resolve_collection_name', return_value="test"):
            with patch('vector_memory.cli.main._list_qdrant_collections', return_value=["test"]):
                with patch('vector_memory.cli.main.UpsertMemoryUseCase') as mock_use_case_class:
                    mock_use_case = Mock()
                    mock_use_case.execute.return_value = Mock(raw={})
                    mock_use_case_class.return_value = mock_use_case

                    with patch('builtins.print'):
                        result = store_turn(ns, Mock(), Mock())

        assert result == 0

        # Should succeed with tool_calls as None due to JSON parse failure
        request = mock_use_case.execute.call_args[0][0]
        item = request.items[0]
        assert "tool_calls" not in item.meta  # Invalid JSON filtered out
