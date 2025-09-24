"""
Application Entry Point.

Composition root for dependency injection and application bootstrap.
"""
from __future__ import annotations
import os
import sys

from PySide6.QtWidgets import QApplication

from .adapters.vector_memory_adapter import VectorMemoryAdapter
from .adapters.text_logger import TextLogger
from .application.services.vector_prompt_service import VectorPromptService
from .presentation.layouts.main_window import MainWindow
from .shared.user_settings import get_ui_scale


class VectorMemoryApp:
    """Vector Memory Application."""

    def __init__(self):
        """Initialize application."""
        self._setup_qt()
        self._wire_dependencies()

    def _setup_qt(self) -> None:
        """Setup Qt application."""
        # Mark UI context so service-layer can gate .env writes to GUI only
        os.environ.setdefault("VM_UI_CONTEXT", "1")
        # In the standalone GUI, default to no thread-level filtering unless explicitly enabled
        # by the user. This ensures queries search across the whole collection by default.
        os.environ.setdefault("VM_THREAD_FILTER", "0")
        # Apply global UI scale before creating the QApplication to enlarge
        # fonts and control sizes across the entire UI. Default from settings
        # (fallback to env var VM_UI_SCALE and then 2.0). We prefer env-based
        # HiDPI controls over deprecated QApplication attributes to avoid warnings.
        self._apply_global_scale_env()
        # Platform selection: respect explicit override only; otherwise let Qt choose.
        platform_override = os.environ.get("VM_UI_FORCE_QT_PLATFORM")
        if platform_override:
            os.environ["QT_QPA_PLATFORM"] = platform_override

        # Reduce noisy QPA plugin messages in some environments
        os.environ.setdefault("QT_LOGGING_RULES", "qt.qpa.*=false;qt.scenegraph.*=false")
        # High-DPI: Defaults are fine on recent Qt; avoid deprecated attributes to prevent warnings.
        self._qt_app = QApplication(sys.argv)

        # Apply dark theme if available
        self._apply_theme()

    def _apply_global_scale_env(self) -> None:
        """Configure Qt environment scaling to enlarge the entire UI.

        This sets process-level Qt environment variables before the QApplication
        is instantiated so that fonts and widget metrics (buttons, inputs, etc.)
        are scaled consistently. Default factor is 2.0, overridable via
        `VM_UI_SCALE` (float). If `QT_SCALE_FACTOR` is already set externally,
        it is respected and not overridden here.
        """
        # Determine desired scale: settings → env VM_UI_SCALE → 2.0 default
        scale_env = os.environ.get("VM_UI_SCALE")
        scale = get_ui_scale(default=float(scale_env) if scale_env else 2.0)

        # Only set QT_SCALE_FACTOR if not provided by the environment already.
        os.environ.setdefault("QT_SCALE_FACTOR", f"{scale:.2f}")
        # Ensure High-DPI scaling is enabled and that rounding preserves our factor.
        os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
        os.environ.setdefault("QT_SCALE_FACTOR_ROUNDING_POLICY", "PassThrough")
        # Avoid double-scaling by disabling automatic screen scaling when we set an explicit factor.
        os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "0")

    def _apply_theme(self) -> None:
        """Apply dark theme stylesheet."""
        from contextlib import suppress
        theme_path = os.path.join(os.path.dirname(__file__), "dark.qss")
        if os.path.exists(theme_path):
            with suppress(OSError, IOError):
                with open(theme_path, "r", encoding="utf-8") as f:
                    self._qt_app.setStyleSheet(f.read())

    def _wire_dependencies(self) -> None:
        """Wire dependencies using dependency injection."""
        # Infrastructure layer
        self._memory_adapter = VectorMemoryAdapter()
        self._logger = TextLogger()

        # Application layer
        self._prompt_service = VectorPromptService(self._memory_adapter, self._logger)

        # Presentation layer
        self._main_window = MainWindow(self._prompt_service, self._logger)

    def run(self) -> int:
        """Run the application."""
        self._main_window.show()
        return self._qt_app.exec()


def main() -> int:
    """Main entry point."""
    try:
        app = VectorMemoryApp()
        return app.run()
    except Exception as e:
        print(f"Application failed to start: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
