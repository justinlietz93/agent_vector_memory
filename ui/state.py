
from __future__ import annotations
import os, sqlite3, json
from dataclasses import dataclass, field
from typing import Any, Optional

DB_FILE = "shell_prefs.db"

@dataclass
class AppState:
    app_name: str
    db_path: str = field(default_factory=lambda: DB_FILE)
    theme: str = "dark"

    def __post_init__(self) -> None:
        self._ensure_db()

    # --- SQLite minimal persistence (no SQLAlchemy) ---
    def _ensure_db(self) -> None:
        os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
        with sqlite3.connect(self.db_path) as con:
            cur = con.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS recent (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    path TEXT NOT NULL,
                    kind TEXT DEFAULT 'project',
                    ts   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS layouts (
                    name TEXT PRIMARY KEY,
                    geometry BLOB,
                    state    BLOB,
                    meta     TEXT
                )
            """)
            con.commit()

    # Settings
    def get_setting(self, key: str, default: Optional[str]=None) -> Optional[str]:
        with sqlite3.connect(self.db_path) as con:
            cur = con.cursor()
            cur.execute("SELECT value FROM settings WHERE key=?", (key,))
            row = cur.fetchone()
            return row[0] if row else default

    def set_setting(self, key: str, value: str) -> None:
        with sqlite3.connect(self.db_path) as con:
            cur = con.cursor()
            cur.execute("REPLACE INTO settings(key, value) VALUES(?,?)", (key, value))
            con.commit()

    # Recents
    def add_recent(self, path: str, kind: str="project") -> None:
        with sqlite3.connect(self.db_path) as con:
            con.execute("INSERT INTO recent(path, kind) VALUES(?,?)", (path, kind))
            con.commit()

    def get_recent(self, limit: int=15) -> list[tuple[int, str, str, str]]:
        with sqlite3.connect(self.db_path) as con:
            cur = con.cursor()
            cur.execute("SELECT id, path, kind, ts FROM recent ORDER BY ts DESC LIMIT ?", (limit,))
            return cur.fetchall()

    # Layouts
    def save_layout(self, name: str, geometry: bytes, state: bytes, meta: dict[str, Any] | None=None) -> None:
        meta_s = json.dumps(meta or {})
        with sqlite3.connect(self.db_path) as con:
            con.execute("REPLACE INTO layouts(name, geometry, state, meta) VALUES(?,?,?,?)",
                        (name, geometry, state, meta_s))
            con.commit()

    def load_layout(self, name: str) -> tuple[bytes | None, bytes | None, dict | None]:
        with sqlite3.connect(self.db_path) as con:
            cur = con.cursor()
            cur.execute("SELECT geometry, state, meta FROM layouts WHERE name=?", (name,))
            row = cur.fetchone()
            if not row: return None, None, None
            geom, st, meta_s = row
            try:
                meta = json.loads(meta_s) if meta_s else None
            except Exception:
                meta = None
            return geom, st, meta
