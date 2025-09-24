"""
Insert Data Widget.

Simple form to insert a text snippet into a vector memory collection.
"""
from __future__ import annotations
from typing import Optional, List, Dict, Any
from pathlib import Path
import os

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QPlainTextEdit,
    QPushButton,
    QMessageBox,
    QFileDialog,
)
from PySide6.QtGui import QDragEnterEvent, QDropEvent

from ...application.services.vector_prompt_service import VectorPromptService
from ...application.interfaces.logger import ILogger


class InsertDataWidget(QWidget):
    """Widget providing an input form to insert text into a collection.

    Fields:
      - Collection name (defaults to current env or left empty for user input)
      - Text content to store
      - Insert button
    """

    def __init__(self, service: VectorPromptService, logger: ILogger, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._service = service
        self._logger = logger
        self._build_ui()
        self._connect()
        self.setAcceptDrops(True)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        row = QHBoxLayout()
        row.addWidget(QLabel("Collection:", self))
        self.cmb_collection = QComboBox(self)
        self.cmb_collection.setEditable(True)
        self._populate_collections(os.getenv("MEMORY_COLLECTION_NAME", ""))
        row.addWidget(self.cmb_collection, 1)
        layout.addLayout(row)

        layout.addWidget(QLabel("Text to insert:", self))
        self.txt_text = QPlainTextEdit(self)
        self.txt_text.setPlaceholderText("Enter text snippet to store in vector memory…")
        layout.addWidget(self.txt_text, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        self.btn_insert = QPushButton("Insert", self)
        btn_row.addWidget(self.btn_insert)
        # Placeholder for future: Browse… button for multi-file selection
        self.btn_browse = QPushButton("Browse…", self)
        btn_row.addWidget(self.btn_browse)
        layout.addLayout(btn_row)

    def _connect(self) -> None:
        self.btn_insert.clicked.connect(self._on_insert)
        self.btn_browse.clicked.connect(self._on_browse_clicked)

    def _on_insert(self) -> None:
        collection = self._get_collection_name()
        text = self.txt_text.toPlainText().strip()
        if not collection:
            QMessageBox.warning(self, "Missing Collection", "Please enter a collection name.")
            return
        if not text:
            QMessageBox.warning(self, "Missing Text", "Please enter some text to insert.")
            return
        try:
            self._service.insert_data(collection, text, metadata={"source": "ui:insert"})
            QMessageBox.information(self, "Inserted", f"Inserted text into '{collection}'.")
            self._logger.info(f"Inserted text into collection: {collection}")
            self.txt_text.clear()
        except Exception as e:
            QMessageBox.critical(self, "Insert Failed", f"Error inserting data: {e}")

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # type: ignore[override]
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:  # type: ignore[override]
        urls = event.mimeData().urls() if event.mimeData() else []
        if not urls:
            return
        paths = [Path(u.toLocalFile()) for u in urls if u.isLocalFile()]
        if not paths:
            return
        collection = self._get_collection_name()
        if not collection:
            QMessageBox.warning(self, "Missing Collection", "Please enter a collection name before dropping files.")
            return
        try:
            added = self._ingest_files(collection, paths)
            if added > 0:
                QMessageBox.information(self, "Inserted", f"Inserted {added} item(s) into '{collection}'.")
        except Exception as e:
            QMessageBox.critical(self, "Insert Failed", f"Error inserting from dropped files: {e}")

    def _on_browse_clicked(self) -> None:
        """Open a file dialog to select multiple files for ingestion."""
        collection = self._get_collection_name()
        if not collection:
            QMessageBox.warning(self, "Missing Collection", "Please enter a collection name before selecting files.")
            return
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Select files to insert",
            str(Path.home()),
            "Text/PDF Files (*.txt *.md *.pdf);;All Files (*)",
        )
        if not paths:
            return
        try:
            added = self._ingest_files(collection, [Path(p) for p in paths])
            if added > 0:
                QMessageBox.information(self, "Inserted", f"Inserted {added} item(s) into '{collection}'.")
        except Exception as e:
            QMessageBox.critical(self, "Insert Failed", f"Error inserting from selected files: {e}")

    def _ingest_files(self, collection: str, paths: List[Path]) -> int:
        """Ingest a list of files into the vector store.

        - Supports `.txt` and `.md` as plain text.
        - Supports `.pdf` via optional `pypdf`/`PyPDF2` extraction.
        - Applies simple chunking to large texts for embedding limits.

    Returns number of chunks inserted.
        """
        items: List[Dict[str, Any]] = []
        for p in paths:
            try:
                if not p.exists() or not p.is_file():
                    self._logger.warning(f"Skipping non-file path: {p}")
                    continue
                ext = p.suffix.lower()
                if ext in {".txt", ".md"}:
                    content = p.read_text(encoding="utf-8", errors="ignore").strip()
                    if not content:
                        continue
                    items.extend(
                        {
                            "text": chunk,
                            "meta": {
                                "source": "ui:file",
                                "path": str(p),
                                "kind": ext.lstrip("."),
                                "filename": p.name,
                                "size": p.stat().st_size,
                                "chunk_index": idx,
                            },
                        }
                        for idx, chunk in enumerate(self._chunk_text(content))
                    )
                elif ext == ".pdf":
                    extracted = self._extract_pdf_text(p)
                    if not extracted:
                        continue
                    items.extend(
                        {
                            "text": chunk,
                            "meta": {
                                "source": "ui:file",
                                "path": str(p),
                                "kind": "pdf",
                                "filename": p.name,
                                "size": p.stat().st_size,
                                "chunk_index": idx,
                            },
                        }
                        for idx, chunk in enumerate(self._chunk_text(extracted))
                    )
                else:
                    self._logger.info(f"Unsupported file type (skipped): {p}")
            except Exception as e:
                self._logger.warning(f"Failed to read {p}: {e}")
        if not items:
            self._logger.info("No valid items found to insert from selected/dropped files")
            return 0
        inserted = self._service.insert_items(collection, items)
        self._logger.info(f"Inserted {inserted} items into '{collection}' from files")
        return inserted

    # --- helpers ---
    def _populate_collections(self, preselect: str = "") -> None:
        """Populate the dropdown with collections from service, showing dims."""
        self.cmb_collection.clear()
        cols = []
        try:
            cols = self._service.list_collections()
        except Exception:
            cols = []
        for it in cols:
            name = str(it.get("name", ""))
            dim = it.get("dim")
            label = f"{name} (dim {dim})" if dim else name
            self.cmb_collection.addItem(label, {"name": name, "dim": dim})
        target = (preselect or os.getenv("MEMORY_COLLECTION_NAME", "") or "").strip()
        if target:
            # Try to select existing
            idx = -1
            for i in range(self.cmb_collection.count()):
                data = self.cmb_collection.itemData(i)
                if isinstance(data, dict) and data.get("name") == target:
                    idx = i
                    break
            if idx >= 0:
                self.cmb_collection.setCurrentIndex(idx)
            else:
                self.cmb_collection.insertItem(0, target, {"name": target, "dim": None})
                self.cmb_collection.setCurrentIndex(0)

    def _get_collection_name(self) -> str:
        idx = self.cmb_collection.currentIndex()
        if idx >= 0:
            data = self.cmb_collection.itemData(idx)
            if isinstance(data, dict) and data.get("name"):
                return str(data.get("name")).strip()
        return (self.cmb_collection.currentText() or "").split(" (")[0].strip()

    def _chunk_text(self, text: str, max_len: int = 4000) -> List[str]:
        """Naively chunk text by character length into <=max_len pieces.

        This is a simple, deterministic splitter to avoid embedding overly long inputs.
        It preserves order and does not overlap. Future improvement can switch to a
        token-based splitter if available in the environment.
        """
        s = text.strip()
        if not s:
            return []
        if len(s) <= max_len:
            return [s]
        return [s[i : i + max_len] for i in range(0, len(s), max_len)]

    def _extract_pdf_text(self, path: Path) -> str:
        """Extract text from a PDF using PyPDF2/pypdf if available, else return empty string.

        We avoid adding a hard dependency; if not installed, we log and skip.
        """
        try:
            import pypdf  # type: ignore
        except Exception:
            try:
                import PyPDF2 as pypdf  # type: ignore
            except Exception:
                self._logger.warning("pypdf not installed; skipping PDF extraction")
                return ""
        try:
            text_parts: List[str] = []
            with open(path, "rb") as f:
                reader = pypdf.PdfReader(f)  # type: ignore[attr-defined]
                for page in getattr(reader, "pages", []):
                    try:
                        txt = page.extract_text() or ""
                        if txt:
                            text_parts.append(txt)
                    except Exception:
                        # Log at debug level; skip page and continue naturally
                        self._logger.debug("Failed to extract text from one PDF page; skipping")
            return "\n\n".join(text_parts).strip()
        except Exception as e:
            self._logger.warning(f"PDF read failed for {path}: {e}")
            return ""
