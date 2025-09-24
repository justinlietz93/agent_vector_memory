"""
Vector Prompt Input Widget.

Widget for entering prompts and displaying formatted output.
"""

from __future__ import annotations
import contextlib
import os
from typing import Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSpinBox, QPushButton, QPlainTextEdit, QMessageBox, QApplication, QInputDialog, QComboBox
from PySide6.QtGui import QClipboard

from ...application.services.vector_prompt_service import VectorPromptService
from ...application.interfaces.logger import ILogger
from ...shared.dto import QueryRequest


class VectorPromptWidget(QWidget):
    """Widget for vector memory prompt input and output."""

    # Signal emitted when query is executed
    query_executed = Signal(object)  # QueryResponse

    def __init__(self, service: VectorPromptService, logger: ILogger, parent: Optional[QWidget] = None):
        """Initialize widget with service dependencies."""
        super().__init__(parent)
        self._service = service
        self._logger = logger
        self._build_ui()
        self._connect_signals()

    def _build_ui(self) -> None:
        """Build the user interface."""
        layout = QVBoxLayout(self)

        # Configuration row
        config_layout = self._create_config_row()
        layout.addLayout(config_layout)

        # Prompt input
        layout.addWidget(QLabel("Your Prompt:", self))
        self._create_prompt_input()
        layout.addWidget(self.txt_prompt, 1)

        # Output area
        layout.addWidget(QLabel("Formatted Prompt (with vector memory):", self))
        self._create_output_area()
        layout.addWidget(self.txt_output, 1)

    def _create_config_row(self) -> QHBoxLayout:
        """Create configuration controls row."""
        layout = QHBoxLayout()

        layout.addWidget(QLabel("Collection:", self))
        self.cmb_collection = QComboBox(self)
        self.cmb_collection.setEditable(True)  # allow custom names too
        self._populate_collections(self._get_default_collection())
        layout.addWidget(self.cmb_collection, 1)
        self.btn_new_collection = QPushButton("+", self)
        self.btn_new_collection.setToolTip("Create new collection")
        layout.addWidget(self.btn_new_collection)

        layout.addWidget(QLabel("K:", self))
        self.spin_k = QSpinBox(self)
        self.spin_k.setRange(1, 50)
        self.spin_k.setValue(8)
        layout.addWidget(self.spin_k)

        self.btn_generate = QPushButton("Generate", self)
        layout.addWidget(self.btn_generate)

        self.btn_copy = QPushButton("Copy", self)
        layout.addWidget(self.btn_copy)

        return layout

    def _create_prompt_input(self) -> None:
        """Create prompt input area."""
        self.txt_prompt = QPlainTextEdit(self)
        self.txt_prompt.setPlaceholderText("Type your prompt here…")
        self.txt_prompt.setTabChangesFocus(True)

    def _create_output_area(self) -> None:
        """Create output display area."""
        self.txt_output = QPlainTextEdit(self)
        self.txt_output.setReadOnly(True)

    def _connect_signals(self) -> None:
        """Connect widget signals."""
        self.btn_generate.clicked.connect(self._on_generate_clicked)
        self.btn_copy.clicked.connect(self._on_copy_clicked)
        self.btn_new_collection.clicked.connect(self._on_create_collection_clicked)

    def _get_default_collection(self) -> str:
        """Get default collection name from environment."""
        return os.getenv("MEMORY_COLLECTION_NAME", "roo_project_mem").strip()

    def _on_generate_clicked(self) -> None:
        """Handle generate button click."""
        try:
            request = self._create_query_request()
            response = self._service.execute_query(request)

            formatted_output = self._format_output(request, response)
            self.txt_output.setPlainText(formatted_output)

            # Emit signal for other components
            self.query_executed.emit(response)

        except ValueError as e:
            QMessageBox.warning(self, "Invalid Input", str(e))
        except Exception as e:
            QMessageBox.critical(self, "Query Failed", f"Error: {e}")

    def _create_query_request(self) -> QueryRequest:
        """Create query request from UI inputs."""
        collection = self.get_collection() or self._get_default_collection()
        prompt = self.txt_prompt.toPlainText().strip()
        k = self.spin_k.value()
        return QueryRequest(collection=collection, prompt=prompt, k=k)

    def _format_output(self, request: QueryRequest, response) -> str:
        """Format the complete output with prompt and vector memory."""
        from ...application.services.prompt_formatter import PromptFormatter
        formatter = PromptFormatter()
        return formatter.format_with_vector_memory(request, response)

    def _on_copy_clicked(self) -> None:
        """Handle copy button click."""
        text = self.txt_output.toPlainText()
        if not text:
            QMessageBox.information(self, "Nothing to copy", "Generate a formatted prompt first.")
            return

        clipboard = QApplication.clipboard()
        clipboard.setText(text, QClipboard.Clipboard)

        # Also set selection clipboard on X11
        with contextlib.suppress(Exception):
            clipboard.setText(text, QClipboard.Selection)
        self._logger.info("Formatted prompt copied to clipboard")
        QMessageBox.information(self, "Copied", "Formatted prompt copied to clipboard.")

    def _on_create_collection_clicked(self) -> None:
        """Create a new collection and set it as active in the input field."""
        preset = self.get_collection()
        name, ok = QInputDialog.getText(self, "Create Collection", "Collection name:", text=preset)
        if not ok:
            return
        name = (name or "").strip()
        if not name:
            QMessageBox.warning(self, "Invalid Name", "Collection name cannot be empty.")
            return
        try:
            # Prefer explicit API if available
            if hasattr(self._service, "create_collection"):
                self._service.create_collection(name)
            else:
                raise NotImplementedError("Service does not support collection creation.")
            self.set_collection(name)
            QMessageBox.information(self, "Collection Created", f"Collection '{name}' is ready.")
            self._logger.info(f"Collection created: {name}")
        except NotImplementedError as e:
            QMessageBox.warning(self, "Create Not Supported", str(e))
        except Exception as e:
            QMessageBox.critical(self, "Create Failed", f"Error creating collection: {e}")

    # Convenience helpers used by the main window
    def set_collection(self, name: str) -> None:
        """Set/select the current collection in the dropdown."""
        name = (name or "").strip()
        if not name:
            return
        # Try to find existing item
        idx = -1
        for i in range(self.cmb_collection.count()):
            data = self.cmb_collection.itemData(i)
            if isinstance(data, dict) and data.get("name") == name:
                idx = i
                break
            if self.cmb_collection.itemText(i).split(" (")[0] == name:
                idx = i
                break
        if idx >= 0:
            self.cmb_collection.setCurrentIndex(idx)
        else:
            # Add new at top with unknown dim
            label = name
            self.cmb_collection.insertItem(0, label, {"name": name, "dim": None})
            self.cmb_collection.setCurrentIndex(0)

    def get_collection(self) -> str:
        """Get the current collection name from the dropdown (or text)."""
        idx = self.cmb_collection.currentIndex()
        if idx >= 0:
            data = self.cmb_collection.itemData(idx)
            if isinstance(data, dict) and data.get("name"):
                return str(data.get("name")).strip()
        # Editable text fallback
        return (self.cmb_collection.currentText() or "").split(" (")[0].strip()

    # --- helpers ---
    def _populate_collections(self, preselect: Optional[str] = None) -> None:
        """Populate the dropdown with collections from service, showing dims."""
        self.cmb_collection.clear()
        cols = []
        try:
            cols = self._service.list_collections()
        except Exception:
            cols = []
        # If none found, still allow typing
        for it in cols:
            name = str(it.get("name", ""))
            dim = it.get("dim")
            label = f"{name} (dim {dim})" if dim else name
            self.cmb_collection.addItem(label, {"name": name, "dim": dim})
        # Ensure default/preselect visible
        target = (preselect or self._get_default_collection() or "").strip()
        if target:
            self.set_collection(target)
