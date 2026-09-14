#!/usr/bin/env python3
"""One-shot Glass Knot poll → data/latest.json (+ api_calls.json if live)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.api_counter import read_counter  # noqa: E402
from app.nansen import NansenClient  # noqa: E402
from app.pipeline import run_pipeline  # noqa: E402


def main() -> int:
    client = NansenClient()
    payload = run_pipeline(client)
    grades = {
        k.get("grade"): k.get("seed_short")
        for k in (payload.get("knots") or [])
    }
    print(
        json.dumps(
            {
                "ok": True,
                "product": "Glass Knot",
                "demo_mode": payload.get("demo_mode"),
                "generated_at": payload.get("generated_at"),
                "stats": payload.get("stats"),
                "demo_grades": grades,
                "api_calls": read_counter(),
                "path": str(ROOT / "data" / "latest.json"),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
