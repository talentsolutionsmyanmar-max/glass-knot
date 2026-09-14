"""Runtime config — never hardcode secrets."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

NANSEN_API_KEY = (os.getenv("NANSEN_API_KEY") or "").strip()
TRADE_VALUE_USD_MIN = float(os.getenv("TRADE_VALUE_USD_MIN") or "1000")
POLL_INTERVAL_SEC = int(os.getenv("POLL_INTERVAL_SEC") or "60")
HOST = os.getenv("HOST") or "0.0.0.0"
PORT = int(os.getenv("PORT") or "8765")

# BFS / grading knobs
BFS_MAX_DEPTH = int(os.getenv("BFS_MAX_DEPTH") or "2")
BFS_MAX_RELATED_PER_NODE = int(os.getenv("BFS_MAX_RELATED_PER_NODE") or "8")
BFS_MAX_WALLETS = int(os.getenv("BFS_MAX_WALLETS") or "24")
FARM_MIN_RELATED = int(os.getenv("FARM_MIN_RELATED") or "4")
SOLO_MAX_RELATED = int(os.getenv("SOLO_MAX_RELATED") or "1")
INCLUDE_COUNTERPARTIES = (os.getenv("INCLUDE_COUNTERPARTIES") or "0").strip() in (
    "1",
    "true",
    "True",
    "yes",
)
USE_PREMIUM_LABELS = (os.getenv("USE_PREMIUM_LABELS") or "0").strip() in (
    "1",
    "true",
    "True",
    "yes",
)
# Free plan returns 403 on /labels — skip unless SKIP_LABELS=0
SKIP_LABELS = (os.getenv("SKIP_LABELS") or "1").strip() not in (
    "0",
    "false",
    "False",
    "no",
)

DATA_DIR = ROOT / "data"
FIXTURES_DIR = ROOT / "fixtures"
LATEST_PATH = DATA_DIR / "latest.json"
API_CALLS_PATH = DATA_DIR / "api_calls.json"
STATIC_DIR = ROOT / "static"

NANSEN_BASE = "https://api.nansen.ai"
DEX_TRADES_PATH = "/api/v1/smart-money/dex-trades"
RELATED_WALLETS_PATH = "/api/v1/profiler/address/related-wallets"
COUNTERPARTIES_PATH = "/api/v1/profiler/address/counterparties"
LABELS_PATH = "/api/v1/profiler/address/labels"
PREMIUM_LABELS_PATH = "/api/v1/profiler/address/premium-labels"

DEMO_MODE = not bool(NANSEN_API_KEY)

POLICY_BANNER = "PAPER · INSPECT ONLY · NO COPY-TRADE · NO ORDERS · NO SIZE"
GRADES = ("FARM_CLUSTER", "SOLO_SM", "RESEARCH", "FAIL")
