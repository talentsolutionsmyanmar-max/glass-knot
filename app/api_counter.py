"""Persist live API call counts to data/api_calls.json."""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app import config

_lock = threading.Lock()


def _empty() -> dict[str, Any]:
    return {
        "total": 0,
        "by_endpoint": {},
        "last_call_at": None,
        "updated_at": None,
        "target": 1000,
        "note": "Counts every live Nansen request (demo/fixture loads do not increment).",
    }


def read_counter(path: Path | None = None) -> dict[str, Any]:
    path = path or config.API_CALLS_PATH
    if not path.exists():
        return _empty()
    try:
        data = json.loads(path.read_text())
        if not isinstance(data, dict):
            return _empty()
        data.setdefault("total", 0)
        data.setdefault("by_endpoint", {})
        data.setdefault("target", 1000)
        return data
    except (json.JSONDecodeError, OSError):
        return _empty()


def record_call(endpoint: str, *, path: Path | None = None) -> dict[str, Any]:
    """Increment counter for one live HTTP request. Thread-safe."""
    path = path or config.API_CALLS_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    with _lock:
        data = read_counter(path)
        data["total"] = int(data.get("total") or 0) + 1
        by = data.setdefault("by_endpoint", {})
        by[endpoint] = int(by.get(endpoint) or 0) + 1
        now = datetime.now(timezone.utc).isoformat()
        data["last_call_at"] = now
        data["updated_at"] = now
        data["target"] = 1000
        path.write_text(json.dumps(data, indent=2) + "\n")
        return data
