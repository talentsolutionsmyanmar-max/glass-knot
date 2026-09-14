"""Nansen API client. Demo mode loads fixtures; live calls bump api_calls.json."""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from app import config
from app.api_counter import record_call

log = logging.getLogger("glass_knot.nansen")


class NansenClient:
    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = (api_key if api_key is not None else config.NANSEN_API_KEY).strip()
        self.demo = not bool(self.api_key)

    def _headers(self) -> dict[str, str]:
        return {
            "apikey": self.api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _post(self, path: str, body: dict[str, Any], *, timeout: float = 45.0) -> dict[str, Any]:
        url = f"{config.NANSEN_BASE}{path}"
        with httpx.Client(timeout=timeout) as client:
            r = client.post(url, headers=self._headers(), json=body)
            record_call(path)
            r.raise_for_status()
            return r.json()

    def fetch_dex_trades(
        self,
        *,
        trade_value_min: float | None = None,
        page: int = 1,
        per_page: int = 100,
    ) -> dict[str, Any]:
        if self.demo:
            path = config.FIXTURES_DIR / "dex_trades.json"
            log.info("demo: load %s", path.name)
            return json.loads(path.read_text())

        body = {
            "chains": ["solana"],
            "filters": {
                "trade_value_usd": {
                    "min": trade_value_min
                    if trade_value_min is not None
                    else config.TRADE_VALUE_USD_MIN
                }
            },
            "pagination": {"page": page, "per_page": per_page},
            "order_by": [{"field": "block_timestamp", "direction": "DESC"}],
        }
        return self._post(config.DEX_TRADES_PATH, body)

    def fetch_related_wallets(
        self,
        address: str,
        *,
        page: int = 1,
        per_page: int = 50,
    ) -> dict[str, Any]:
        if self.demo:
            blob = json.loads((config.FIXTURES_DIR / "related_wallets.json").read_text())
            return blob.get(address) or {
                "data": [],
                "pagination": {"page": 1, "per_page": per_page, "is_last_page": True},
                "source": "fixture_empty",
            }

        body = {
            "address": address,
            "chain": "solana",
            "pagination": {"page": page, "per_page": per_page},
        }
        out = self._post(config.RELATED_WALLETS_PATH, body, timeout=30.0)
        out.setdefault("source", "live")
        return out

    def fetch_counterparties(
        self,
        address: str,
        *,
        date: dict[str, str] | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> dict[str, Any]:
        if self.demo:
            blob = json.loads((config.FIXTURES_DIR / "counterparties.json").read_text())
            return blob.get(address) or {
                "data": [],
                "pagination": {"page": 1, "per_page": per_page, "is_last_page": True},
                "source": "fixture_empty",
            }

        body: dict[str, Any] = {
            "address": address,
            "chain": "solana",
            "group_by": "wallet",
            "pagination": {"page": page, "per_page": per_page},
        }
        if date:
            body["date"] = date
        out = self._post(config.COUNTERPARTIES_PATH, body, timeout=30.0)
        out.setdefault("source", "live")
        return out

    def fetch_labels(self, address: str) -> dict[str, Any]:
        """Free labels by default; premium only if USE_PREMIUM_LABELS=1."""
        if config.SKIP_LABELS and not self.demo:
            return {
                "data": [],
                "pagination": {"page": 1, "per_page": 100, "is_last_page": True},
                "source": "skipped",
            }
        if self.demo:
            blob = json.loads((config.FIXTURES_DIR / "labels.json").read_text())
            return blob.get(address) or {
                "data": [],
                "pagination": {"page": 1, "per_page": 10, "is_last_page": True},
                "source": "fixture",
            }

        body = {
            "address": address,
            "chain": "solana",
            "pagination": {"page": 1, "per_page": 100},
        }
        paths = (
            [config.PREMIUM_LABELS_PATH, config.LABELS_PATH]
            if config.USE_PREMIUM_LABELS
            else [config.LABELS_PATH]
        )
        last_err: Exception | None = None
        with httpx.Client(timeout=30.0) as client:
            for path in paths:
                url = f"{config.NANSEN_BASE}{path}"
                try:
                    r = client.post(url, headers=self._headers(), json=body)
                    record_call(path)
                    if r.status_code in (403, 402):
                        log.warning("labels %s -> %s", path, r.status_code)
                        last_err = httpx.HTTPStatusError(
                            f"{r.status_code}", request=r.request, response=r
                        )
                        continue
                    r.raise_for_status()
                    out = r.json()
                    out["source"] = "premium" if "premium" in path else "free"
                    return out
                except httpx.HTTPError as e:
                    last_err = e
                    log.warning("labels failed on %s: %s", path, e)
        return {
            "data": [],
            "pagination": {"page": 1, "per_page": 100, "is_last_page": True},
            "source": "unavailable",
            "error": str(last_err) if last_err else "unknown",
        }
