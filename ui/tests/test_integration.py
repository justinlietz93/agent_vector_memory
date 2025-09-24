"""
Integration Tests for Vector Memory UI.

Tests component integration following Clean Architecture.
"""
from __future__ import annotations
import unittest
from unittest.mock import Mock, patch

from ..application.services.vector_prompt_service import VectorPromptService
from ..adapters.text_logger import TextLogger
from ..adapters.vector_memory_adapter import VectorMemoryAdapter
from ..shared.dto import QueryRequest


class TestIntegration(unittest.TestCase):
    """Integration tests for UI components."""

    def test_end_to_end_query_flow_with_mocked_dependencies(self) -> None:
        """Test: End-to-end query flow integrates all components correctly."""
        print("Testing end-to-end integration of service, adapter, and logger")

        # Arrange - Mock external dependencies
        with patch.object(VectorMemoryAdapter, '_setup_imports'):
            adapter = VectorMemoryAdapter()

        # Mock the vector memory components
        mock_use_case = Mock()
        mock_result = Mock()
        mock_result.id = "test_id"
        mock_result.score = 0.95
        mock_result.payload = {"text_preview": "test preview"}

        mock_use_case.execute.return_value = [mock_result]

        # Mock the adapter's internals
        adapter._QueryRequest = Mock()
        adapter._QueryMemoryUseCase = Mock(return_value=mock_use_case)
        adapter._OllamaEmbeddingService = Mock()
        adapter._QdrantVectorStore = Mock()

        logger = TextLogger()
        service = VectorPromptService(adapter, logger)

        # Act
        request = QueryRequest(collection="test", prompt="test query", k=5)
        response = service.execute_query(request)

        # Assert
        self.assertEqual(response.collection, "test")
        self.assertEqual(response.query, "test query")
        self.assertEqual(len(response.results), 1)
        self.assertEqual(response.results[0].id, "test_id")
        self.assertEqual(response.results[0].score, 0.95)

    def test_dependency_injection_wiring_works_correctly(self) -> None:
        """Test: Dependency injection wiring connects components properly."""
        print("Testing dependency injection connects interface implementations")

        # Arrange
        logger = TextLogger()

        with patch.object(VectorMemoryAdapter, '_setup_imports'):
            adapter = VectorMemoryAdapter()

        # Act
        service = VectorPromptService(adapter, logger)

        # Assert
        self.assertIsInstance(service._memory_service, VectorMemoryAdapter)
        self.assertIsInstance(service._logger, TextLogger)

    def test_error_propagation_through_layers(self) -> None:
        """Test: Error propagation works correctly through architectural layers."""
        print("Testing error propagation maintains proper exception handling")

        # Arrange
        adapter = Mock()
        adapter.query_memory.side_effect = Exception("Infrastructure error")
        logger = Mock()
        service = VectorPromptService(adapter, logger)

        # Act & Assert
        request = QueryRequest(collection="test", prompt="test", k=5)

        with self.assertRaises(Exception) as context:
            service.execute_query(request)

        self.assertIn("Infrastructure error", str(context.exception))
        logger.error.assert_called_once()


if __name__ == "__main__":
    unittest.main()
