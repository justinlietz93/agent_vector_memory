"""
Text Logger Adapter.

Implementation of ILogger that writes to a text widget.
"""

from __future__ import annotations
import contextlib
from datetime import datetime
from typing import Optional

from PySide6.QtWidgets import QTextEdit

from ..application.interfaces.logger import ILogger


class TextLogger(ILogger):
    """Logger that writes to a QTextEdit widget."""

    def __init__(self, text_widget: Optional[QTextEdit] = None):
        """Initialize logger with optional text widget."""
        self._text_widget = text_widget

    def set_widget(self, text_widget: QTextEdit) -> None:
        """Set the text widget for logging."""
        self._text_widget = text_widget

    def info(self, message: str) -> None:
        """Log info level message."""
        self._log("INFO", message)

    def warning(self, message: str) -> None:
        """Log warning level message."""
        self._log("WARN", message)

    def error(self, message: str) -> None:
        """Log error level message."""
        self._log("ERROR", message)

    def _log(self, level: str, message: str) -> None:
        """Write log message to widget."""
        if not self._text_widget:
            return

        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted = f"[{timestamp}] {level}: {message}"

        with contextlib.suppress(RuntimeError):
            self._text_widget.append(formatted)
