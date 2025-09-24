"""
Unit Tests for VectorPromptService.

Tests business logic layer following TDD principles.
"""
from __future__ import annotations
import unittest
from unittest.mock import Mock, MagicMock
import pytest

from ..application.services.vector_prompt_service import VectorPromptService
from ..shared.dto import QueryRequest, QueryResponse, QueryResult


class TestVectorPromptService(unittest.TestCase):
    """Test VectorPromptService business logic."""

    def setUp(self) -> None:
        """Test: Set up test fixtures for VectorPromptService testing."""
        print("Setting up VectorPromptService test with mock dependencies")
        self.mock_memory_service = Mock()
        self.mock_logger = Mock()
        self.service = VectorPromptService(self.mock_memory_service, self.mock_logger)

    def test_execute_query_valid_request_returns_response(self) -> None:
        """Test: Execute query with valid request returns proper QueryResponse."""
        print("Testing valid query execution returns structured response")
        # Arrange
        request = QueryRequest(collection="test_col", prompt="test query", k=5)
        mock_result = Mock()
        mock_result.id = "test_id"
        mock_result.score = 0.95
        mock_result.payload = {"text_preview": "test preview"}

        self.mock_memory_service.query_memory.return_value = [mock_result]

        # Act
        response = self.service.execute_query(request)

        # Assert
        self.assertIsInstance(response, QueryResponse)
        self.assertEqual(response.collection, "test_col")
        self.assertEqual(response.query, "test query")
        self.assertEqual(response.total_found, 1)
        self.assertEqual(len(response.results), 1)

        result = response.results[0]
        self.assertEqual(result.id, "test_id")
        self.assertEqual(result.score, 0.95)
        self.assertEqual(result.text_preview, "test preview")

        self.mock_logger.info.assert_called()

    def test_execute_query_empty_collection_raises_value_error(self) -> None:
        """Test: Execute query with empty collection name raises ValueError."""
        print("Testing empty collection validation raises ValueError")
        # Arrange
        request = QueryRequest(collection="", prompt="test", k=5)

        # Act & Assert
        with self.assertRaises(ValueError) as context:
            self.service.execute_query(request)

        self.assertIn("Collection name cannot be empty", str(context.exception))

    def test_execute_query_empty_prompt_raises_value_error(self) -> None:
        """Test: Execute query with empty prompt raises ValueError."""
        print("Testing empty prompt validation raises ValueError")
        # Arrange
        request = QueryRequest(collection="test", prompt="", k=5)

        # Act & Assert
        with self.assertRaises(ValueError) as context:
            self.service.execute_query(request)

        self.assertIn("Prompt cannot be empty", str(context.exception))

    def test_execute_query_invalid_k_raises_value_error(self) -> None:
        """Test: Execute query with invalid k value raises ValueError."""
        print("Testing invalid k parameter validation raises ValueError")
        # Arrange
        request = QueryRequest(collection="test", prompt="test", k=0)

        # Act & Assert
        with self.assertRaises(ValueError) as context:
            self.service.execute_query(request)

        self.assertIn("K must be between 1 and 50", str(context.exception))

        # Test upper bound
        request_high = QueryRequest(collection="test", prompt="test", k=51)
        with self.assertRaises(ValueError):
            self.service.execute_query(request_high)

    def test_execute_query_memory_service_failure_logs_error_and_raises(self) -> None:
        """Test: Execute query when memory service fails logs error and re-raises."""
        print("Testing memory service failure handling with proper logging")
        # Arrange
        request = QueryRequest(collection="test", prompt="test", k=5)
        self.mock_memory_service.query_memory.side_effect = Exception("Memory service error")

        # Act & Assert
        with self.assertRaises(Exception) as context:
            self.service.execute_query(request)

        self.assertIn("Memory service error", str(context.exception))
        self.mock_logger.error.assert_called_once()
        self.assertIn("Query failed", self.mock_logger.error.call_args[0][0])

    def test_convert_results_handles_missing_attributes_gracefully(self) -> None:
        """Test: Convert results handles missing attributes with default values."""
        print("Testing result conversion handles missing attributes gracefully")
        # Arrange
        mock_result = Mock()
        del mock_result.id  # Simulate missing attribute
        del mock_result.score
        del mock_result.payload

        # Act
        results = self.service._convert_results([mock_result])

        # Assert
        self.assertEqual(len(results), 1)
        result = results[0]
        self.assertEqual(result.id, "")
        self.assertEqual(result.score, 0.0)
        self.assertEqual(result.text_preview, "")
        self.assertEqual(result.metadata, {})

    def test_extract_text_preview_from_various_payload_formats(self) -> None:
        """Test: Extract text preview handles various payload formats correctly."""
        print("Testing text preview extraction from different payload formats")
        # Test with dict payload
        mock_result = Mock()
        mock_result.payload = {"text_preview": "test preview"}

        preview = self.service._extract_text_preview(mock_result)
        self.assertEqual(preview, "test preview")

        preview = self._extracted_from_test_extract_text_preview_from_various_payload_formats_12(
            None, mock_result
        )
        preview = self._extracted_from_test_extract_text_preview_from_various_payload_formats_12(
            "not a dict", mock_result
        )

    # TODO Rename this here and in `test_extract_text_preview_from_various_payload_formats`
    def _extracted_from_test_extract_text_preview_from_various_payload_formats_12(self, arg0, mock_result):
        # Test with missing payload
        mock_result.payload = arg0
        result = self.service._extract_text_preview(mock_result)
        self.assertEqual(result, "")

        return result


if __name__ == "__main__":
    unittest.main()
