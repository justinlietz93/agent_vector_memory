"""
Unit Tests for PromptFormatter.

Tests prompt formatting business logic.
"""
from __future__ import annotations
import unittest

from ..application.services.prompt_formatter import PromptFormatter
from ..shared.dto import QueryRequest, QueryResponse, QueryResult


class TestPromptFormatter(unittest.TestCase):
    """Test PromptFormatter service."""

    def setUp(self) -> None:
        """Test: Set up PromptFormatter test fixtures."""
        print("Setting up PromptFormatter test with sample data")
        self.formatter = PromptFormatter()

    def test_format_with_vector_memory_includes_prompt_and_envelope(self) -> None:
        """Test: Format with vector memory includes both original prompt and XML envelope."""
        print("Testing formatted output contains prompt and vector memory envelope")
        # Arrange
        request = QueryRequest(collection="test_col", prompt="test prompt", k=2)
        results = [
            QueryResult(id="id1", score=0.95, text_preview="preview1", metadata={"key": "value"}),
            QueryResult(id="id2", score=0.85, text_preview="preview2", metadata={})
        ]
        response = QueryResponse(results=results, collection="test_col", query="test prompt", total_found=2)

        # Act
        output = self.formatter.format_with_vector_memory(request, response)

        # Assert
        self.assertIn("test prompt", output)
        self.assertIn("<vector_memory>", output)
        self.assertIn("</vector_memory>", output)
        self.assertIn('collection="test_col"', output)
        self.assertIn('k="2"', output)

    def test_create_vector_memory_envelope_contains_proper_xml_structure(self) -> None:
        """Test: Vector memory envelope contains proper XML structure with metadata."""
        print("Testing XML envelope structure with proper tags and attributes")
        # Arrange
        request = QueryRequest(collection="test", prompt="test", k=1)
        results = [QueryResult(id="test_id", score=0.9, text_preview="test text", metadata={"meta": "data"})]
        response = QueryResponse(results=results, collection="test", query="test", total_found=1)

        # Act
        envelope = self.formatter._create_vector_memory_envelope(request, response)

        # Assert
        self.assertIn("<vector_memory>", envelope)
        self.assertIn("<relevance", envelope)
        self.assertIn("<item", envelope)
        self.assertIn("<text>test text</text>", envelope)
        self.assertIn("<other_metadata>", envelope)
        self.assertIn("</item>", envelope)
        self.assertIn("</relevance>", envelope)
        self.assertIn("</vector_memory>", envelope)

    def test_format_result_item_handles_empty_text_gracefully(self) -> None:
        """Test: Format result item handles empty text with self-closing tag."""
        print("Testing result item formatting handles empty text with self-closing XML tag")
        # Arrange
        result = QueryResult(id="test", score=0.5, text_preview="", metadata={})

        # Act
        lines = self.formatter._format_result_item(1, result, "")
        output = "\n".join(lines)

        # Assert
        self.assertIn("<text />", output)
        self.assertIn('index="1"', output)
        self.assertIn('score="0.5000"', output)

    def test_escape_xml_handles_special_characters(self) -> None:
        """Test: XML escaping handles all special characters correctly."""
        print("Testing XML character escaping for security and validity")
        # Arrange
        text_with_specials = '<test>value & "quoted" \'single\' chars'

        # Act
        escaped = self.formatter._escape_xml(text_with_specials)

        # Assert
        self.assertEqual(escaped, "&lt;test&gt;value &amp; &quot;quoted&quot; &apos;single&apos; chars")

    def test_character_limit_truncates_long_text_properly(self) -> None:
        """Test: Character limit enforcement truncates text and adds ellipsis."""
        print("Testing character limit truncation with ellipsis indicator")
        # Arrange
        request = QueryRequest(collection="test", prompt="test", k=1)
        long_text = "a" * 2000  # Exceeds 1500 char limit
        results = [QueryResult(id="test", score=0.9, text_preview=long_text, metadata={})]
        response = QueryResponse(results=results, collection="test", query="test", total_found=1)

        # Act
        envelope = self.formatter._create_vector_memory_envelope(request, response)

        # Assert
        self.assertIn("...", envelope)
        # Verify it's not the full 2000 characters
        self.assertLess(len(envelope), 2000)

    def test_only_top1_result_is_injected(self) -> None:
        """Test: Only the top-1 result is included in the envelope."""
        print("Testing policy: inject only the top-1 memory into formatted output")
        # Arrange
        request = QueryRequest(collection="test", prompt="test", k=3)
        results = [
            QueryResult(id="id1", score=0.9, text_preview="short1", metadata={}),
            QueryResult(id="id2", score=0.8, text_preview="short2", metadata={}),
            QueryResult(id="id3", score=0.7, text_preview="short3", metadata={})
        ]
        response = QueryResponse(results=results, collection="test", query="test", total_found=3)

        # Act
        envelope = self.formatter._create_vector_memory_envelope(request, response)

        # Assert
        self.assertIn("short1", envelope)
        self.assertNotIn("short2", envelope)
        self.assertNotIn("short3", envelope)
        self.assertIn('index="1"', envelope)
        self.assertNotIn('index="2"', envelope)
        self.assertNotIn('index="3"', envelope)

    def test_metadata_excludes_text_preview_in_other_metadata(self) -> None:
        """Test: Metadata section excludes text_preview key from other_metadata."""
        print("Testing metadata filtering excludes text_preview from other_metadata")
        # Arrange
        metadata = {"text_preview": "should_be_excluded", "other_key": "should_be_included"}
        result = QueryResult(id="test", score=0.9, text_preview="preview", metadata=metadata)

        # Act
        lines = self.formatter._format_result_item(1, result, "preview")
        output = "\n".join(lines)

        # Assert
        self.assertIn('<other_metadata>{"other_key":"should_be_included"}</other_metadata>', output)
        self.assertNotIn('"text_preview":"should_be_excluded"', output)
        self.assertNotIn("should_be_excluded", output)
        self.assertIn('"other_key":"should_be_included"', output)


if __name__ == "__main__":
    unittest.main()
