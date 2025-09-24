"""
Unit Tests for TextLogger.

Tests logging adapter functionality.
"""
from __future__ import annotations
import unittest
from unittest.mock import Mock

from ..adapters.text_logger import TextLogger


class TestTextLogger(unittest.TestCase):
    """Test TextLogger adapter."""

    def setUp(self) -> None:
        """Test: Set up TextLogger test with mock widget."""
        print("Setting up TextLogger test with mock text widget")
        self.mock_widget = Mock()
        self.logger = TextLogger(self.mock_widget)

    def test_info_logs_with_proper_format(self) -> None:
        """Test: Info logging formats message with timestamp and level."""
        print("Testing info logging formats message with INFO level and timestamp")
        # Act
        self.logger.info("test info message")

        # Assert
        self.mock_widget.append.assert_called_once()
        call_args = self.mock_widget.append.call_args[0][0]
        self.assertIn("INFO:", call_args)
        self.assertIn("test info message", call_args)
        # Check timestamp format (HH:MM:SS)
        self.assertRegex(call_args, r'\[\d{2}:\d{2}:\d{2}\]')

    def test_warning_logs_with_proper_format(self) -> None:
        """Test: Warning logging formats message with WARN level."""
        print("Testing warning logging formats message with WARN level")
        # Act
        self.logger.warning("test warning")

        # Assert
        call_args = self.mock_widget.append.call_args[0][0]
        self.assertIn("WARN:", call_args)
        self.assertIn("test warning", call_args)

    def test_error_logs_with_proper_format(self) -> None:
        """Test: Error logging formats message with ERROR level."""
        print("Testing error logging formats message with ERROR level")
        # Act
        self.logger.error("test error")

        # Assert
        call_args = self.mock_widget.append.call_args[0][0]
        self.assertIn("ERROR:", call_args)
        self.assertIn("test error", call_args)

    def test_set_widget_updates_internal_reference(self) -> None:
        """Test: Set widget updates internal widget reference correctly."""
        print("Testing widget reference update via set_widget method")
        # Arrange
        new_widget = Mock()

        # Act
        self.logger.set_widget(new_widget)
        self.logger.info("test message")

        # Assert
        new_widget.append.assert_called_once()
        self.mock_widget.append.assert_not_called()

    def test_logging_without_widget_does_not_crash(self) -> None:
        """Test: Logging without widget reference does not raise exception."""
        print("Testing logging without widget gracefully handles missing reference")
        # Arrange
        logger = TextLogger()  # No widget provided

        # Act & Assert (should not raise)
        logger.info("test message")
        logger.warning("test warning")
        logger.error("test error")

    def test_logging_with_deleted_widget_handles_runtime_error(self) -> None:
        """Test: Logging with deleted widget handles RuntimeError gracefully."""
        print("Testing logging with deleted widget handles RuntimeError gracefully")
        # Arrange
        self.mock_widget.append.side_effect = RuntimeError("Widget deleted")

        # Act & Assert (should not raise)
        self.logger.info("test message")


if __name__ == "__main__":
    unittest.main()
