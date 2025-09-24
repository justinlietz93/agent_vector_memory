"""
Main Window Layout with Docking.

Primary application window using ``QMainWindow`` with dockable side panels.
For stability on Linux compositors, the layout is pinned by default:
- Vector prompt (central) occupies the top portion
- Data panel anchored bottom-left
- Logs panel anchored bottom-right

The layout is fixed in placement (no move/float/close), but users can adjust the
bottom row height and the splitter between Data and Logs. A View menu item lets
you reset the layout if anything changes programmatically.
"""
from __future__ import annotations
import os
from typing import Optional
from contextlib import suppress

from PySide6.QtCore import Qt
from PySide6.QtGui import QFontDatabase, QAction
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QTableWidget,
    QTextEdit,
    QTableWidgetItem,
    QDockWidget,
    QMenuBar,
    QMenu,
    QTabWidget,
    QSizePolicy,
    QInputDialog,
    QMessageBox,
)

from ...application.services.vector_prompt_service import VectorPromptService
from ...application.interfaces.logger import ILogger
from ...shared.dto import QueryResponse
from ..widgets.vector_prompt_widget import VectorPromptWidget
from ..widgets.insert_data_widget import InsertDataWidget
from ...shared.user_settings import set_ui_scale, get_ui_scale
import sys
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication


class MainWindow(QMainWindow):
    """Main application window with dockable side panels.

    - Central widget: :class:`VectorPromptWidget`
    - Dock widgets: Data (left/right/bottom), Logs (left/right/bottom)
    - Docks are movable, floatable, and can be tabbed together
    """

    def __init__(self, service: VectorPromptService, logger: ILogger, parent: Optional[QWidget] = None):
        """Initialize main window."""
        super().__init__(parent)
        self._service = service
        self._logger = logger
    # Fixed bottom row height (pixels) for initial sizing only (user-adjustable later)
        self._bottom_row_px = 220
        self._setup_window()
        self._build_layout()

    def _setup_window(self) -> None:
        """Configure window properties."""
        self.setWindowTitle("Vector Memory UI")
        self.resize(1400, 800)
        self._load_fonts()
        # Baseline font size for simple scaling (pt). If 0, fallback to 10pt.
        app = QApplication.instance()
        base_size = (app.font().pointSizeF() if app else self.font().pointSizeF())
        self._baseline_point_size = base_size if base_size and base_size > 0 else 10.0
        # Docking behavior (keep simple; no animations implied)
        self.setDockOptions(QMainWindow.DockOption.AllowNestedDocks)
        self.setDockNestingEnabled(True)
        # Preferred tab position if ever used
        self.setTabPosition(Qt.AllDockWidgetAreas, QTabWidget.North)

    def _load_fonts(self) -> None:
        """Load custom fonts if available."""
        font_path = os.path.join(os.path.dirname(__file__), "..", "..", "resources", "Inter.ttf")
        if os.path.exists(font_path):
            QFontDatabase.addApplicationFont(font_path)

    def _build_layout(self) -> None:
        """Build central widget and dockable side panels."""
        # Central widget: Tabbed interface (Formatter | Insert Data)
        self.tabs = QTabWidget(self)
        self.prompt_panel = self._create_prompt_panel()
        self.insert_panel = self._create_insert_panel()
        self.tabs.addTab(self.prompt_panel, "Formatter")
        self.tabs.addTab(self.insert_panel, "Insert Data")
        self.setCentralWidget(self.tabs)

        # Data dock
        self.data_panel = self._create_data_panel()
        self.data_dock = QDockWidget("Data", self)
        self.data_dock.setObjectName("dock_data")
        self.data_dock.setWidget(self.data_panel)
        # Fully fixed: no move/float/close buttons
        self.data_dock.setFeatures(QDockWidget.DockWidgetFeature.NoDockWidgetFeatures)
        self.data_dock.setAllowedAreas(
            Qt.DockWidgetArea.BottomDockWidgetArea
        )
        # Place Data dock in bottom area
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.data_dock)

        # Log dock
        self.log_panel = self._create_log_panel()
        self.log_dock = QDockWidget("Logs", self)
        self.log_dock.setObjectName("dock_logs")
        self.log_dock.setWidget(self.log_panel)
        # Fully fixed: no move/float/close buttons
        self.log_dock.setFeatures(QDockWidget.DockWidgetFeature.NoDockWidgetFeatures)
        self.log_dock.setAllowedAreas(
            Qt.DockWidgetArea.BottomDockWidgetArea
        )
        # Also bottom area; will be split to the right of Data
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.log_dock)

        # Split bottom horizontally: Data (left) | Logs (right)
        self.splitDockWidget(self.data_dock, self.log_dock, Qt.Horizontal)
        # Initial sizing only (user can adjust afterwards)
        with suppress(Exception):
            self.resizeDocks([self.data_dock], [self._bottom_row_px], Qt.Vertical)
            self.resizeDocks([self.data_dock, self.log_dock], [1, 1], Qt.Horizontal)

        # Corner preferences: both bottom corners map to bottom area
        self.setCorner(Qt.Corner.BottomLeftCorner, Qt.DockWidgetArea.BottomDockWidgetArea)
        self.setCorner(Qt.Corner.BottomRightCorner, Qt.DockWidgetArea.BottomDockWidgetArea)

        self.data_dock.show()
        self.log_dock.show()

        # Menus
        self._build_menus()

        # Connect signals
        self._connect_signals()

        # Welcome messages
        self._show_welcome_message()

    def _build_menus(self) -> None:
        """Create File and View menus.

        - File: Create Collection
        - View: Reset to Fixed Layout
        - Settings: UI Size (Small/Medium/Large) and Thread Filter toggle
        """
        menubar: QMenuBar = self.menuBar() or QMenuBar(self)
        if self.menuBar() is None:
            self.setMenuBar(menubar)

        file_menu: QMenu = menubar.addMenu("File")
        action_create = file_menu.addAction("Create Collection…")
        action_create.triggered.connect(self._on_create_collection)

        view_menu: QMenu = menubar.addMenu("View")

        # Reset to fixed layout
        action_reset = view_menu.addAction("Reset to Fixed Layout")
        action_reset.triggered.connect(self._layout_fixed_bottom)

        # Settings menu for UI Size
        settings_menu: QMenu = menubar.addMenu("Settings")
        ui_size_menu: QMenu = settings_menu.addMenu("UI Size")

        # Create exclusive actions
        self._ui_size_actions = {
            "Small (1.0x)": (1.0, QAction("Small (1.0x)", self, checkable=True)),
            "Medium (1.5x)": (1.5, QAction("Medium (1.5x)", self, checkable=True)),
            "Large (2.0x)": (2.0, QAction("Large (2.0x)", self, checkable=True)),
        }
        # Determine current scale and check corresponding action
        current_scale = float(get_ui_scale(default=1.0))
        def _on_select(scale: float) -> None:
            # Persist first, then apply runtime scale without restart
            if not set_ui_scale(scale):
                QMessageBox.warning(self, "Settings", "Failed to save UI scale.")
                return
            self._apply_scale(scale)
            # Update checked states to reflect the active choice
            for _, (s, act) in self._ui_size_actions.items():
                act.setChecked(abs(s - scale) < 0.01)
            self._logger.info(f"Applied UI scale {scale:.1f}x without restart")

        for _, (scale, action) in self._ui_size_actions.items():
            action.setChecked(abs(current_scale - scale) < 0.01)
            action.triggered.connect(lambda checked, s=scale: _on_select(s))
            ui_size_menu.addAction(action)

        # Thread Filter toggle
        self._thread_filter_action = QAction("Filter by current thread", self, checkable=True)
        # Reflect current env (default set in app.py to 0 for GUI)
        current_tf = str(os.environ.get("VM_THREAD_FILTER", "0")).lower() in {"1", "true", "yes"}
        self._thread_filter_action.setChecked(current_tf)
        def _on_toggle_thread_filter(checked: bool) -> None:
            os.environ["VM_THREAD_FILTER"] = "1" if checked else "0"
            state = "enabled" if checked else "disabled"
            self._logger.info(f"Thread filter {state}; subsequent queries will {'only include current thread' if checked else 'include all threads'}.")
            QMessageBox.information(
                self,
                "Thread Filter",
                f"Thread filter {state}. New queries will {('be limited to the current thread.' if checked else 'search across all threads.')}"
            )
        self._thread_filter_action.triggered.connect(_on_toggle_thread_filter)
        settings_menu.addAction(self._thread_filter_action)

    def _on_create_collection(self) -> None:
        """Prompt for a collection name, create it, and set it active in the UI.

        Uses the central prompt panel to reflect the new selection.
        """
        current = ""
        with suppress(Exception):
            current = self.prompt_panel.get_collection().strip()  # type: ignore[attr-defined]
        name, ok = QInputDialog.getText(self, "Create Collection", "Collection name:", text=current)
        if not ok:
            return
        name = (name or "").strip()
        if not name:
            QMessageBox.warning(self, "Invalid Name", "Collection name cannot be empty.")
            return
        try:
            self._service.create_collection(name)
            # Update the prompt panel input
            if hasattr(self.prompt_panel, "set_collection"):
                self.prompt_panel.set_collection(name)
            QMessageBox.information(self, "Collection Created", f"Collection '{name}' is ready.")
            self._logger.info(f"Collection created: {name}")
        except NotImplementedError as e:
            QMessageBox.warning(self, "Create Not Supported", str(e))
        except Exception as e:
            QMessageBox.critical(self, "Create Failed", f"Error creating collection: {e}")

    def _create_data_panel(self) -> QTableWidget:
        """Create data results panel (used inside a dock widget)."""
        table = QTableWidget(self)
        # Let docks control width equally; avoid internal width caps
        table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        return table

    def _create_prompt_panel(self) -> VectorPromptWidget:
        """Create vector prompt panel (central widget)."""
        return VectorPromptWidget(self._service, self._logger, self)

    def _create_insert_panel(self) -> InsertDataWidget:
        """Create insert data panel (central tab)."""
        return InsertDataWidget(self._service, self._logger, self)

    def _create_log_panel(self) -> QTextEdit:
        """Create logs panel (used inside a dock widget)."""
        log_widget = QTextEdit(self)
        log_widget.setReadOnly(True)
        # Let docks control width equally; avoid internal width caps
        log_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        log_widget.setPlaceholderText("UI activity logs will appear here...")
        return log_widget

    def _connect_signals(self) -> None:
        """Connect widget signals."""
        self.prompt_panel.query_executed.connect(self._on_query_executed)

        # Connect logger to log panel
        if hasattr(self._logger, 'set_widget'):
            self._logger.set_widget(self.log_panel)

    # ----- Dock layout helper -----
    def _layout_fixed_bottom(self) -> None:
        """Pin Data bottom-left and Logs bottom-right under the central widget.

        This re-applies the intended fixed layout, splitting the bottom dock area
        horizontally with Data on the left and Logs on the right.
        """
        # Ensure docks are allowed and visible
        if self.data_dock.isHidden():
            self.data_dock.show()
        if self.log_dock.isHidden():
            self.log_dock.show()

        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.data_dock)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.log_dock)
        self.splitDockWidget(self.data_dock, self.log_dock, Qt.Horizontal)
        with suppress(Exception):
            self.resizeDocks([self.data_dock], [self._bottom_row_px], Qt.Vertical)
            self.resizeDocks([self.data_dock, self.log_dock], [1, 1], Qt.Horizontal)

    # No showEvent override; allow user to adjust splitters freely after initial sizing

    def _show_welcome_message(self) -> None:
        """Show initial welcome messages."""
        collection = os.getenv("MEMORY_COLLECTION_NAME", "roo_project_mem")
        self._logger.info("Vector Memory UI initialized")
        self._logger.info(f"Collection: {collection}")

    def _apply_scale(self, scale: float) -> None:
        """Apply simple, deterministic UI scaling: new_pt = baseline_pt × scale.

        This avoids complex ratio logic and CSS tweaks. It sets the app font and
        updates key containers so layouts recompute immediately.
        """
        app = QApplication.instance()
        if not app:
            return
        base = getattr(self, "_baseline_point_size", 10.0)
        new_pt = max(6.0, base * max(0.5, scale))
        f = QFont(app.font())
        f.setPointSizeF(new_pt)
        app.setFont(f)
        # Update key widgets and trigger layout updates
        if self.centralWidget() and self.centralWidget().layout():
            self.centralWidget().layout().invalidate()
        if hasattr(self, "tabs") and self.tabs is not None:
            self.tabs.setFont(f)
            self.tabs.updateGeometry()
        if hasattr(self, "data_dock"):
            self.data_dock.setFont(f)
            self.data_dock.update()
        if hasattr(self, "log_dock"):
            self.log_dock.setFont(f)
            self.log_dock.update()
        app.processEvents()

    # Note: no runtime stylesheet or per-widget refresh is required in this
    # simplified approach. Qt will recompute metrics based on the new app font.

    def _prompt_restart(self, scale: float) -> None:
        """Ask the user to restart the app to apply the new UI scale.

        We rely on process-level environment vars set before QApplication is created,
        so a restart is the cleanest approach. We offer an immediate restart option.
        """
        res = QMessageBox.question(
            self,
            "Apply UI Size",
            f"UI size set to {scale:.1f}x. Restart now to apply?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if res == QMessageBox.StandardButton.Yes:
            # Best-effort: re-exec current python process
            try:
                self._logger.info("Restarting application to apply UI scale...")
                python = sys.executable
                os.execv(python, [python, "-m", "vector_memory.ui.app"])  # nosec - fixed arg list
            except Exception as e:
                QMessageBox.warning(self, "Restart Failed", f"Please restart manually. Error: {e}")

    def _on_query_executed(self, response: QueryResponse) -> None:
        """Handle query execution results."""
        self._update_data_panel(response)

    def _update_data_panel(self, response: QueryResponse) -> None:
        """Update data panel with query results."""
        table = self.data_panel
        table.setRowCount(len(response.results))
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels(["Score", "ID", "Preview"])

        for i, result in enumerate(response.results):
            table.setItem(i, 0, QTableWidgetItem(f"{result.score:.4f}"))
            table.setItem(i, 1, QTableWidgetItem(result.id[:20]))

            preview = result.text_preview
            if len(preview) > 100:
                preview = f"{preview[:97]}..."
            table.setItem(i, 2, QTableWidgetItem(preview))

        table.resizeColumnsToContents()
