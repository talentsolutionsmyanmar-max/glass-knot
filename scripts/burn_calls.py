#!/usr/bin/env python3
"""
Pace live Nansen requests toward the Meridian 1k call budget.

Safe defaults: small batches, sleep between calls, hard stop at --target (default 1000).
Demo mode (no NANSEN_API_KEY) exits without burning.

Usage:
  python scripts/burn_calls.py                 # report only if already near target
  python scripts/burn_calls.py --budget 50     # burn up to 50 more calls
  python scripts/burn_calls.py --budget 200 --sleep 1.5
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import config  # noqa: E402
from app.api_counter import read_counter  # noqa: E402
from app.nansen import NansenClient  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description="Pace Glass Knot live API calls toward 1000")
    p.add_argument("--target", type=int, default=1000, help="Hard ceiling for total calls")
    p.add_argument("--budget", type=int, default=0, help="Max additional calls this run")
    p.add_argument("--sleep", type=float, default=1.25, help="Seconds between live requests")
    p.add_argument(
        "--endpoint",
        choices=("dex", "related", "labels"),
        default="dex",
        help="Which endpoint to exercise when burning",
    )
    args = p.parse_args()

    client = NansenClient()
    state = read_counter()
    total = int(state.get("total") or 0)

    report = {
        "product": "Glass Knot",
        "demo_mode": client.demo,
        "api_calls_before": total,
        "target": args.target,
        "remaining_to_target": max(0, args.target - total),
    }

    if client.demo:
        report["ok"] = True
        report["burned"] = 0
        report["note"] = "No NANSEN_API_KEY — demo mode; refusing to burn. Set key to pace live calls."
        print(json.dumps(report, indent=2))
        return 0

    if total >= args.target:
        report["ok"] = True
        report["burned"] = 0
        report["note"] = "Already at/above target — stop."
        print(json.dumps(report, indent=2))
        return 0

    if args.budget <= 0:
        report["ok"] = True
        report["burned"] = 0
        report["note"] = "Pass --budget N to burn calls. Report-only this run."
        report["api_calls"] = state
        print(json.dumps(report, indent=2))
        return 0

    room = min(args.budget, args.target - total)
    burned = 0
    seed = "So11111111111111111111111111111111111111112"  # wrapped SOL — probe only
    errors: list[str] = []

    for i in range(room):
        try:
            if args.endpoint == "dex":
                client.fetch_dex_trades(per_page=1)
            elif args.endpoint == "related":
                client.fetch_related_wallets(seed, per_page=1)
            else:
                client.fetch_labels(seed)
            burned += 1
        except Exception as e:  # noqa: BLE001
            errors.append(str(e))
            break
        if i + 1 < room:
            time.sleep(max(0.0, args.sleep))

    after = read_counter()
    report.update(
        {
            "ok": True,
            "burned": burned,
            "api_calls_after": after.get("total"),
            "api_calls": after,
            "errors": errors[:3],
            "note": "Paced burn complete. Re-run with --budget to continue toward target.",
        }
    )
    print(json.dumps(report, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
