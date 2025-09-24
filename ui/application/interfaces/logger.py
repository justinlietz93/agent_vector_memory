"""
Logger Interface.

Defines contract for logging operations.
"""
from __future__ import annotations
from abc import ABC, abstractmethod


class ILogger(ABC):
    """Interface for logging operations."""

    @abstractmethod
    def info(self, message: str) -> None:
        """Log info level message."""
        ...

    @abstractmethod
    def warning(self, message: str) -> None:
        """Log warning level message."""
        ...

    @abstractmethod
    def error(self, message: str) -> None:
        """Log error level message."""
        ...
