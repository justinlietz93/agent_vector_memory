"""
User Settings utilities.

Provides a minimal XDG-backed settings helper for persisting UI preferences,
currently focusing on the UI scale factor for the Qt application.

Module Purpose:
- Persist and retrieve UI scale between runs using `$XDG_CONFIG_HOME` or
  `~/.config` fallback under `vector_memory/ui/settings.json`.
- No external dependencies; JSON-based storage.

Timeout/Retries:
- Pure local file I/O; no network. No timeouts are involved.

Failure Modes:
- On read/parse errors, defaults are returned and errors are logged (if logger
  provided) but not raised.
- On write errors, a boolean False is returned.
"""
from __future__ import annotations
import json
import os
from contextlib import suppress
from pathlib import Path

_XDG_APP_DIR = "vector_memory"
_SETTINGS_FILE = "ui/settings.json"
_DEFAULT_SCALE = 2.0


def _xdg_config_dir() -> Path:
    """Resolve the base XDG config directory.

    Returns:
        Path: The configuration directory (guaranteed to exist on return if
        possible).
    """
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(Path.home(), ".config")
    path = Path(base) / _XDG_APP_DIR
    with suppress(Exception):
        path.mkdir(parents=True, exist_ok=True)
    return path


def _settings_path() -> Path:
    """Full path to the settings JSON file."""
    return _xdg_config_dir() / _SETTINGS_FILE


def get_ui_scale(default: float = _DEFAULT_SCALE) -> float:
    """Load the UI scale factor from settings.

    Args:
        default: Value to use when no setting is found or parsing fails.

    Returns:
        float: The configured UI scale factor.
    """
    path = _settings_path()
    with suppress(Exception):
        if path.exists():
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            scale = data.get("ui_scale", default)
            return max(0.5, min(4.0, float(scale)))
    return default


def set_ui_scale(value: float) -> bool:
    """Persist the UI scale factor to settings.

    Args:
        value: New scale factor to set.

    Returns:
        bool: True on success, False on failure.
    """
    # Normalize value to a numeric type without unnecessary cast complaints
    scale_num: float
    if isinstance(value, (int, float)):
        scale_num = value  # type: ignore[assignment]
    else:
        with suppress(Exception):
            # Best effort parse from string-like
            scale_num = float(str(value))
        if not isinstance(locals().get("scale_num"), (int, float)):
            scale_num = _DEFAULT_SCALE
    scale = max(0.5, min(4.0, scale_num))
    path = _settings_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"ui_scale": scale}
        with path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False
