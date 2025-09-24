"""
Unit tests for vector memory CLI command dispatch and execution.

Tests command parsing, validation, and integration with use cases.
"""

import json
import tempfile
from pathlib import Path
from unittest import mock
from unittest.mock import Mock, patch, call, ANY
import pytest
from argparse import Namespace

from vector_memory.cli.main import dispatch_commands, run, remember_bulk
from vector_memory.cli.parsers import build_parser
from vector_memory.application.dto import EnsureCollectionRequest, UpsertMemoryRequest, QueryRequest


class TestCommandParsing:
    """Test CLI argument parsing functionality."""

    def test_build_parser_structure(self):
        """Test parser includes all expected subcommands."""
        parser = build_parser()

        # Test basic structure
        assert parser.prog is not None
        assert "Vector memory" in parser.description

        # Test help doesn't raise
        with pytest.raises(SystemExit):
            parser.parse_args(["--help"])

    def test_ensure_collection_args(self):
        """Test ensure-collection argument parsing."""
        parser = build_parser()

        args = parser.parse_args([
            "ensure-collection",
            "--name", "test_collection",
            "--dim", "1024",
            "--distance", "Euclidean",
            "--recreate"
        ])

        assert args.cmd == "ensure-collection"
        assert args.name == "test_collection"
        assert args.dim == 1024
        assert args.distance == "Euclidean"
        assert args.recreate is True

    def test_index_memory_bank_args(self):
        """Test index-memory-bank argument parsing."""
        parser = build_parser()

        args = parser.parse_args([
            "index-memory-bank",
            "--name", "test_collection",
            "--dir", "custom-memory-bank",
            "--idns", "custom",
            "--max-items", "100"
        ])

        assert args.cmd == "index-memory-bank"
        assert args.name == "test_collection"
        assert args.dir == "custom-memory-bank"
        assert args.idns == "custom"
        assert args.max_items == 100

    def test_query_args(self):
        """Test query command argument parsing."""
        parser = build_parser()

        args = parser.parse_args([
            "query",
            "--name", "test_collection",
            "--q", "test query",
            "--k", "10",
            "--with-payload"
        ])

        assert args.cmd == "query"
        assert args.name == "test_collection"
        assert args.q == "test query"
        assert args.k == 10
        assert args.with_payload is True

    def test_recall_args(self):
        """Test recall command argument parsing with score threshold."""
        parser = build_parser()

        args = parser.parse_args([
            "recall",
            "--q", "recall query",
            "--k", "8",
            "--score-threshold", "0.7"
        ])

        assert args.cmd == "recall"
        assert args.q == "recall query"
        assert args.k == 8
        assert args.score_threshold == 0.7

    def test_store_turn_args(self):
        """Test store-turn command argument parsing."""
        parser = build_parser()

        args = parser.parse_args([
            "store-turn",
            "--thread-id", "abc123",
            "--turn-index", "5",
            "--role", "user",
            "--text", "Hello world",
            "--model", "gpt-4",
            "--tool-calls", '{"calls": []}',
            "--files", "file1.py",
            "--files", "file2.py",
            "--chunk-chars", "2000"
        ])

        assert args.cmd == "store-turn"
        assert args.thread_id == "abc123"
        assert args.turn_index == 5
        assert args.role == "user"
        assert args.text == "Hello world"
        assert args.model == "gpt-4"
        assert args.tool_calls == '{"calls": []}'
        assert args.files == ["file1.py", "file2.py"]
        assert args.chunk_chars == 2000

    def test_remember_args(self):
        """Test remember command argument parsing."""
        parser = build_parser()

        args = parser.parse_args([
            "remember",
            "--text", "First memory",
            "--text", "Second memory",
            "--file", "/path/to/file.txt",
            "--tag", "important",
            "--tag", "project",
            "--idns", "convo"
        ])

        assert args.cmd == "remember"
        assert args.text == ["First memory", "Second memory"]
        assert args.file == "/path/to/file.txt"
        assert args.tag == ["important", "project"]
        assert args.idns == "convo"

    def test_remember_bulk_args(self):
        """Test remember-bulk command argument parsing."""
        parser = build_parser()

        args = parser.parse_args([
            "remember-bulk",
            "--input", "./bulk.jsonl",
            "--format", "jsonl",
            "--tag", "cli",
            "--tag", "docs",
            "--idns", "bulk"
        ])

        assert args.cmd == "remember-bulk"
        assert args.input == "./bulk.jsonl"
        assert args.format == "jsonl"
        assert args.tag == ["cli", "docs"]
        assert args.idns == "bulk"


class TestCommandDispatch:
    """Test command dispatch to appropriate handlers."""

    @patch('vector_memory.cli.main.new_project')
    def test_dispatch_new_project(self, mock_new_project):
        """Test new-project command dispatch."""
        mock_emb = Mock()
        mock_store = Mock()
        mock_new_project.return_value = 0

        ns = Namespace(cmd="new-project")
        result = dispatch_commands(ns, mock_emb, mock_store)

        assert result == 0
        mock_new_project.assert_called_once_with(mock_emb, mock_store)

    @patch('vector_memory.cli.main._extracted_from_dispatch_commands_15')
    def test_dispatch_ensure_collection(self, mock_ensure):
        """Test ensure-collection command dispatch."""
        mock_emb = Mock()
        mock_store = Mock()
        mock_ensure.return_value = 0

        ns = Namespace(cmd="ensure-collection", name="test")
        result = dispatch_commands(ns, mock_emb, mock_store)

        assert result == 0
        mock_ensure.assert_called_once_with(ns, mock_emb, mock_store)

    def test_dispatch_unknown_command(self):
        """Test unknown command returns error."""
        mock_emb = Mock()
        mock_store = Mock()

        ns = Namespace(cmd="unknown-command")

        with patch('builtins.print') as mock_print:
            result = dispatch_commands(ns, mock_emb, mock_store)

        assert result == 2
        mock_print.assert_called_once()
        call_args = mock_print.call_args[0][0]
        assert "Unknown command: unknown-command" in call_args

    @patch('vector_memory.cli.main.remember_bulk')
    def test_dispatch_remember_bulk(self, mock_bulk):
        """Test remember-bulk command dispatch."""
        mock_emb = Mock()
        mock_store = Mock()
        mock_bulk.return_value = 0

        ns = Namespace(cmd="remember-bulk")
        result = dispatch_commands(ns, mock_emb, mock_store)

        assert result == 0
        mock_bulk.assert_called_once_with(ns, mock_emb, mock_store)


class TestEnsureCollectionCommand:
    """Test ensure-collection command implementation."""

    @patch('vector_memory.cli.main._allowed_collections')
    @patch('vector_memory.cli.main.EnsureCollectionUseCase')
    def test_ensure_collection_success(self, mock_use_case_class, mock_allowed):
        """Test successful collection creation."""
        # Setup mocks
        mock_allowed.return_value = ["test_collection"]
        mock_use_case = Mock()
        mock_use_case_class.return_value = mock_use_case
        mock_emb = Mock()
        mock_store = Mock()

        # Create namespace
        ns = Namespace(
            cmd="ensure-collection",
            name="test_collection",
            dim=1024,
            distance="Cosine",
            recreate=False
        )

        with patch('builtins.print') as mock_print:
            from vector_memory.cli.main import _extracted_from_dispatch_commands_15
            result = _extracted_from_dispatch_commands_15(ns, mock_emb, mock_store)

        assert result == 0
        mock_use_case_class.assert_called_once_with(mock_emb, mock_store)
        mock_use_case.execute.assert_called_once()

        # Check the request structure
        call_args = mock_use_case.execute.call_args[0][0]
        assert isinstance(call_args, EnsureCollectionRequest)
        assert call_args.collection == "test_collection"
        assert call_args.dim == 1024
        assert call_args.distance == "Cosine"
        assert call_args.recreate is False

    @patch('vector_memory.cli.main._allowed_collections')
    @patch('vector_memory.cli.main._list_qdrant_collections')
    def test_ensure_collection_not_allowed(self, mock_qdrant_collections, mock_allowed):
        """Test collection creation fails when not in allowed list."""
        mock_allowed.return_value = ["allowed_collection"]
        mock_qdrant_collections.return_value = []
        mock_emb = Mock()
        mock_store = Mock()

        ns = Namespace(
            cmd="ensure-collection",
            name="forbidden_collection",
            dim=1024,
            distance="Cosine",
            recreate=False
        )

        with patch('builtins.print') as mock_print:
            from vector_memory.cli.main import _extracted_from_dispatch_commands_15
            result = _extracted_from_dispatch_commands_15(ns, mock_emb, mock_store)

        assert result == 2
        mock_print.assert_called_once()
        call_args = mock_print.call_args[0][0]
        error_data = json.loads(call_args)
        assert error_data["status"] == "error"
        assert "not declared in environment" in error_data["error"]


class TestQueryCommands:
    """Test query and recall command implementations."""

    @patch('vector_memory.cli.main._resolve_collection_name')
    @patch('vector_memory.cli.main._list_qdrant_collections')
    @patch('vector_memory.cli.main.QueryMemoryUseCase')
    def test_query_success(self, mock_use_case_class, mock_collections, mock_resolve):
        """Test successful query execution."""
        # Setup mocks
        mock_resolve.return_value = "test_collection"
        mock_collections.return_value = ["test_collection"]
        mock_use_case = Mock()
        result_stub = Mock()
        result_stub.score = 0.9
        result_stub.text = "result"
        mock_use_case.execute.return_value = [result_stub]
        mock_use_case_class.return_value = mock_use_case

        mock_emb = Mock()
        mock_store = Mock()

        ns = Namespace(
            cmd="query",
            name="test_collection",
            q="test query",
            k=5,
            with_payload=True
        )

        with patch('builtins.print') as mock_print:
            from vector_memory.cli.main import _execute_command
            result = _execute_command(ns, mock_emb, mock_store)

        assert result == 0
        mock_use_case.execute.assert_called_once()

        # Verify request structure
        request = mock_use_case.execute.call_args[0][0]
        assert isinstance(request, QueryRequest)
        assert request.collection == "test_collection"
        assert request.query == "test query"
        assert request.k == 5
        assert request.with_payload is True

    @patch('vector_memory.cli.main._resolve_collection_name')
    @patch('vector_memory.cli.main._list_qdrant_collections')
    def test_query_collection_not_found(self, mock_collections, mock_resolve):
        """Test query fails when collection doesn't exist."""
        mock_resolve.return_value = "missing_collection"
        mock_collections.return_value = ["existing_collection"]

        mock_emb = Mock()
        mock_store = Mock()

        ns = Namespace(name="missing_collection", q="test", k=5, with_payload=True)

        with patch('builtins.print') as mock_print:
            from vector_memory.cli.main import _execute_command
            result = _execute_command(ns, mock_emb, mock_store)

        assert result == 2
        mock_print.assert_called_once()
        call_args = mock_print.call_args[0][0]
        error_data = json.loads(call_args)
        assert error_data["status"] == "error"
        assert "does not exist" in error_data["error"]

    @patch('vector_memory.cli.main._resolve_collection_name')
    @patch('vector_memory.cli.main._list_qdrant_collections')
    @patch('vector_memory.cli.main.QueryMemoryUseCase')
    def test_recall_with_threshold(self, mock_use_case_class, mock_collections, mock_resolve):
        """Test recall command with score threshold."""
        # Setup mocks
        mock_resolve.return_value = "test_collection"
        mock_collections.return_value = ["test_collection"]
        mock_use_case = Mock()
        mock_use_case.execute.return_value = []
        mock_use_case_class.return_value = mock_use_case

        mock_emb = Mock()
        mock_store = Mock()

        ns = Namespace(
            name="test_collection",
            q="recall query",
            k=8,
            with_payload=True,
            score_threshold=0.7
        )

        with patch('builtins.print'):
            from vector_memory.cli.main import _recall
            result = _recall(ns, mock_emb, mock_store)

        assert result == 0

        # Verify score threshold is passed
        request = mock_use_case.execute.call_args[0][0]
        assert request.score_threshold == 0.7


class TestStoreTurnCommand:
    """Test store-turn command implementation."""

    @patch('vector_memory.cli.main._resolve_collection_name')
    @patch('vector_memory.cli.main._list_qdrant_collections')
    @patch('vector_memory.cli.main.UpsertMemoryUseCase')
    @patch('vector_memory.cli.main.chat_chunk_chars')
    def test_store_turn_success(self, mock_chunk_chars, mock_use_case_class,
                               mock_collections, mock_resolve):
        """Test successful turn storage."""
        # Setup mocks
        mock_resolve.return_value = "test_collection"
        mock_collections.return_value = ["test_collection"]
        mock_chunk_chars.return_value = 1000
        mock_use_case = Mock()
        mock_use_case.execute.return_value = Mock(raw={})
        mock_use_case_class.return_value = mock_use_case

        mock_emb = Mock()
        mock_store = Mock()

        ns = Namespace(
            name="test_collection",
            thread_id="thread123",
            turn_index=5,
            role="user",
            text="This is a test message",
            model=None,
            tool_calls=None,
            files=[],
            idns="chat",
            chunk_chars=None
        )

        with patch('builtins.print') as mock_print:
            from vector_memory.cli.main import store_turn
            result = store_turn(ns, mock_emb, mock_store)

        assert result == 0
        mock_use_case.execute.assert_called_once()

        # Verify request structure
        request = mock_use_case.execute.call_args[0][0]
        assert isinstance(request, UpsertMemoryRequest)
        assert request.collection == "test_collection"
        assert request.id_namespace == "chat"
        assert len(request.items) == 1  # Single chunk for short message

        # Verify item metadata
        item = request.items[0]
        assert item.text == "This is a test message"
        assert item.meta["thread_id"] == "thread123"
        assert item.meta["turn_index"] == 5
        assert item.meta["role"] == "user"
        assert item.meta["chunk_index"] == 0

    @patch('vector_memory.cli.main._resolve_collection_name')
    @patch('vector_memory.cli.main._list_qdrant_collections')
    def test_store_turn_collection_missing(self, mock_collections, mock_resolve):
        """Test store-turn fails when collection doesn't exist."""
        mock_resolve.return_value = "missing_collection"
        mock_collections.return_value = []

        mock_emb = Mock()
        mock_store = Mock()

        ns = Namespace(
            thread_id="thread123",
            turn_index=5,
            role="user",
            text="test message"
        )

        with patch('builtins.print') as mock_print:
            from vector_memory.cli.main import store_turn
            result = store_turn(ns, mock_emb, mock_store)

        assert result == 2
        mock_print.assert_called_once()
        call_args = mock_print.call_args[0][0]
        error_data = json.loads(call_args)
        assert error_data["status"] == "error"


class TestRememberBulkCommand:
    """Test remember-bulk command implementation."""

    @patch('vector_memory.cli.main._resolve_collection_name')
    @patch('vector_memory.cli.main.UpsertMemoryUseCase')
    def test_remember_bulk_jsonl(self, mock_use_case_class, mock_resolve, tmp_path):
        """Test bulk remember with JSONL input."""
        mock_resolve.return_value = "test_collection"
        mock_use_case = Mock()
        mock_use_case.execute.return_value = Mock(raw={})
        mock_use_case_class.return_value = mock_use_case

        bulk_file = tmp_path / "memories.jsonl"
        bulk_file.write_text(
            "\n".join(
                [
                    json.dumps({"text": "Alpha", "meta": {"topic": "A"}}),
                    json.dumps({"text": "Beta", "tags": ["extra"]}),
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        ns = Namespace(
            name=None,
            input=str(bulk_file),
            format="jsonl",
            tag=["cli"],
            idns="bulk"
        )

        with patch('builtins.print') as mock_print:
            result = remember_bulk(ns, Mock(), Mock())

        assert result == 0
        mock_use_case.execute.assert_called_once()
        request = mock_use_case.execute.call_args[0][0]
        assert isinstance(request, UpsertMemoryRequest)
        assert request.collection == "test_collection"
        assert request.id_namespace == "bulk"
        assert len(request.items) == 2
        assert any("Alpha" in item.text for item in request.items)
        for item in request.items:
            assert "cli" in item.meta.get("tags", [])

        mock_print.assert_called()

    @patch('vector_memory.cli.main._resolve_collection_name')
    def test_remember_bulk_missing_file(self, mock_resolve, tmp_path):
        """Test bulk remember handles missing input files."""
        mock_resolve.return_value = "test_collection"
        missing = tmp_path / "missing.jsonl"

        ns = Namespace(
            name=None,
            input=str(missing),
            format="jsonl",
            tag=[],
            idns="bulk"
        )

        with patch('builtins.print') as mock_print:
            result = remember_bulk(ns, Mock(), Mock())

        assert result == 2
        mock_print.assert_called_once()
        error_data = json.loads(mock_print.call_args[0][0])
        assert error_data["status"] == "error"
        assert "not found" in error_data["error"]


class TestCLIIntegration:
    """Integration tests for CLI entry point."""

    @patch('vector_memory.cli.main.OllamaEmbeddingService')
    @patch('vector_memory.cli.main.QdrantVectorStore')
    @patch('vector_memory.cli.main.dispatch_commands')
    def test_run_success(self, mock_dispatch, mock_store_class, mock_emb_class):
        """Test successful CLI run."""
        mock_emb = Mock()
        mock_store = Mock()
        mock_emb_class.return_value = mock_emb
        mock_store_class.return_value = mock_store
        mock_dispatch.return_value = 0

        result = run(["query", "--q", "test"])

        assert result == 0
        mock_emb_class.assert_called_once()
        mock_store_class.assert_called_once()
        mock_dispatch.assert_called_once_with(mock.ANY, mock_emb, mock_store)

    @patch('vector_memory.cli.main.OllamaEmbeddingService')
    @patch('vector_memory.cli.main.QdrantVectorStore')
    @patch('vector_memory.cli.main.dispatch_commands')
    def test_run_exception_handling(self, mock_dispatch, mock_store_class, mock_emb_class):
        """Test CLI exception handling."""
        mock_emb_class.return_value = Mock()
        mock_store_class.return_value = Mock()
        mock_dispatch.side_effect = RuntimeError("Test error")

        with patch('builtins.print') as mock_print:
            result = run(["query", "--q", "test"])

        assert result == 3
        mock_print.assert_called_once()
        call_args = mock_print.call_args[0][0]
        error_data = json.loads(call_args)
        assert error_data["status"] == "error"
        assert "RuntimeError: Test error" in error_data["error"]
