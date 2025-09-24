from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator
import os


try:
    # Prefer central policy source
    from crux_providers.base.timeouts import (  # type: ignore
        get_timeout_config as _get_timeout_config,
        operation_timeout as _operation_timeout,
    )

    def get_timeout_config():
        return _get_timeout_config()

    def operation_timeout(seconds: float):
        return _operation_timeout(seconds)

except Exception:
    class _TimeoutCfg:
        def __init__(self, default: float = 15.0) -> None:
            try:
                self.start_timeout_seconds = float(os.getenv("MEMORY_START_TIMEOUT", str(default)))
            except Exception:
                self.start_timeout_seconds = default

    def get_timeout_config() -> _TimeoutCfg:
        return _TimeoutCfg()

    @contextmanager
    def operation_timeout(_: float) -> Iterator[None]:
        yield


def http_timeout_seconds() -> float:
    return float(get_timeout_config().start_timeout_seconds or 15.0)
