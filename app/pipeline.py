"""Pipeline: SM dex-trades → BFS related-wallets (+ optional counterparties) → grade → latest.json."""

from __future__ import annotations

import json
import logging
from collections import deque
from datetime import datetime, timezone
from typing import Any

from app import config
from app.api_counter import read_counter
from app.grader import grade_knot, mint_stats_from_tape
from app.nansen import NansenClient

log = logging.getLogger("glass_knot.pipeline")

HISTORY_KEEP = 200
HISTORY_UI = 16


def _short(addr: str | None, n: int = 4) -> str:
    if not addr:
        return "?"
    if len(addr) <= n * 2 + 2:
        return addr
    return f"{addr[:n]}…{addr[-n:]}"


def _related_addrs(resp: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalize related-wallets payload into [{address, ...meta}]."""
    rows = resp.get("data") or []
    out: list[dict[str, Any]] = []
    for row in rows:
        if isinstance(row, str):
            out.append({"address": row})
            continue
        if not isinstance(row, dict):
            continue
        addr = (
            row.get("address")
            or row.get("related_address")
            or row.get("wallet_address")
            or row.get("wallet")
        )
        if not addr:
            continue
        out.append({**row, "address": addr})
    return out


def bfs_related(
    client: NansenClient,
    seed: str,
    *,
    max_depth: int | None = None,
    max_wallets: int | None = None,
    max_per_node: int | None = None,
) -> dict[str, Any]:
    """BFS over profiler related-wallets from an SM seed address."""
    max_depth = config.BFS_MAX_DEPTH if max_depth is None else max_depth
    max_wallets = config.BFS_MAX_WALLETS if max_wallets is None else max_wallets
    max_per_node = config.BFS_MAX_RELATED_PER_NODE if max_per_node is None else max_per_node

    visited: set[str] = {seed}
    edges: list[dict[str, str]] = []
    nodes: dict[str, dict[str, Any]] = {
        seed: {
            "address": seed,
            "address_short": _short(seed),
            "depth": 0,
            "role": "seed",
            "labels": [],
        }
    }
    q: deque[tuple[str, int]] = deque([(seed, 0)])
    depth_reached = 0

    while q and len(visited) < max_wallets:
        addr, depth = q.popleft()
        if depth >= max_depth:
            continue
        try:
            resp = client.fetch_related_wallets(addr, per_page=max_per_node)
        except Exception as e:  # noqa: BLE001
            log.warning("related-wallets failed for %s: %s", addr, e)
            continue
        related = _related_addrs(resp)[:max_per_node]
        for rel in related:
            child = rel["address"]
            edges.append({"from": addr, "to": child})
            if child in visited:
                continue
            visited.add(child)
            depth_reached = max(depth_reached, depth + 1)
            nodes[child] = {
                "address": child,
                "address_short": _short(child),
                "depth": depth + 1,
                "role": "related",
                "labels": [],
                "meta": {
                    k: v
                    for k, v in rel.items()
                    if k not in ("address",) and not isinstance(v, (dict, list))
                },
            }
            if depth + 1 < max_depth and len(visited) < max_wallets:
                q.append((child, depth + 1))
            if len(visited) >= max_wallets:
                break

    related_only = [a for a in visited if a != seed]
    return {
        "seed_address": seed,
        "seed_short": _short(seed),
        "related_count": len(related_only),
        "node_count": len(nodes),
        "edge_count": len(edges),
        "bfs_depth_reached": depth_reached,
        "nodes": list(nodes.values()),
        "edges": edges,
        "related_addresses": related_only,
    }


def enrich_labels(client: NansenClient, knot: dict[str, Any], *, max_label: int = 6) -> None:
    addrs = [knot["seed_address"]] + list(knot.get("related_addresses") or [])
    labeled = 0
    seed_labels: list[Any] = []
    by_addr: dict[str, list[Any]] = {}
    for addr in addrs:
        if labeled >= max_label:
            break
        try:
            resp = client.fetch_labels(addr)
            labs = resp.get("data") or []
        except Exception as e:  # noqa: BLE001
            log.warning("labels failed for %s: %s", addr, e)
            labs = []
        by_addr[addr] = labs
        if addr == knot["seed_address"]:
            seed_labels = labs
        labeled += 1
    knot["seed_labels"] = seed_labels
    for node in knot.get("nodes") or []:
        node["labels"] = by_addr.get(node["address"], node.get("labels") or [])


def maybe_counterparties(client: NansenClient, knot: dict[str, Any]) -> None:
    if not config.INCLUDE_COUNTERPARTIES:
        knot["counterparties"] = []
        knot["counterparties_included"] = False
        return
    try:
        resp = client.fetch_counterparties(knot["seed_address"])
        knot["counterparties"] = resp.get("data") or []
        knot["counterparties_included"] = True
    except Exception as e:  # noqa: BLE001
        log.warning("counterparties failed: %s", e)
        knot["counterparties"] = []
        knot["counterparties_included"] = False
        knot["counterparties_error"] = str(e)


def build_tape(trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    tape = []
    for t in trades:
        tape.append(
            {
                "ts": t.get("block_timestamp"),
                "chain": t.get("chain") or "solana",
                "trader": t.get("trader_address"),
                "trader_short": _short(t.get("trader_address")),
                "trader_label": t.get("trader_address_label"),
                "bought": t.get("token_bought_symbol"),
                "bought_address": t.get("token_bought_address"),
                "sold": t.get("token_sold_symbol"),
                "value_usd": t.get("trade_value_usd"),
                "age_days": t.get("token_bought_age_days"),
                "tx": t.get("transaction_hash"),
            }
        )
    tape.sort(key=lambda x: x.get("ts") or "", reverse=True)
    return tape


def select_seeds(trades: list[dict[str, Any]], *, limit: int = 6) -> list[dict[str, Any]]:
    """Distinct SM traders from the tape, preserving first-seen order (newest first)."""
    seen: set[str] = set()
    seeds: list[dict[str, Any]] = []
    ordered = sorted(trades, key=lambda t: t.get("block_timestamp") or "", reverse=True)
    for t in ordered:
        addr = t.get("trader_address")
        if not addr or addr in seen:
            continue
        seen.add(addr)
        seeds.append(
            {
                "address": addr,
                "address_short": _short(addr),
                "label_from_trade": t.get("trader_address_label"),
                "sample_trade": {
                    "bought": t.get("token_bought_symbol"),
                    "bought_address": t.get("token_bought_address"),
                    "value_usd": t.get("trade_value_usd"),
                    "ts": t.get("block_timestamp"),
                    "tx": t.get("transaction_hash"),
                    "age_days": t.get("token_bought_age_days"),
                },
            }
        )
        if len(seeds) >= limit:
            break
    return seeds


def read_history(*, limit: int = HISTORY_UI) -> list[dict[str, Any]]:
    path = config.HISTORY_PATH
    if not path.exists():
        return []
    items: list[dict[str, Any]] = []
    try:
        lines = path.read_text().splitlines()
    except OSError:
        return []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(rec, dict):
            items.append(rec)
    return items[-limit:]


def append_history(knots: list[dict[str, Any]], generated_at: str) -> list[dict[str, Any]]:
    """Append one inspect-only grade row per knot. No PnL, no size."""
    path = config.HISTORY_PATH
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    existing: list[str] = []
    if path.exists():
        try:
            existing = [ln for ln in path.read_text().splitlines() if ln.strip()]
        except OSError:
            existing = []
    new_lines: list[str] = []
    for k in knots:
        rec = {
            "ts": generated_at,
            "grade": k.get("grade"),
            "confidence": k.get("confidence"),
            "seed_short": k.get("seed_short"),
            "seed_address": k.get("seed_address"),
            "token": k.get("token_symbol"),
            "mint": k.get("token_mint"),
            "mint_short": k.get("token_mint_short"),
            "related_count": k.get("related_count"),
            "node_count": k.get("node_count"),
            "edge_count": k.get("edge_count"),
            "reason": (k.get("reason_plain") or "")[:240],
        }
        new_lines.append(json.dumps(rec, separators=(",", ":")))
    kept = (existing + new_lines)[-HISTORY_KEEP:]
    path.write_text("\n".join(kept) + "\n")
    parsed: list[dict[str, Any]] = []
    for ln in kept[-HISTORY_UI:]:
        try:
            parsed.append(json.loads(ln))
        except json.JSONDecodeError:
            continue
    return parsed


def _featured_knot(knots: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not knots:
        return None
    for g in ("FARM_CLUSTER", "SOLO_SM", "RESEARCH", "FAIL"):
        for k in knots:
            if k.get("grade") == g:
                return k
    return knots[0]


def run_pipeline(client: NansenClient | None = None) -> dict[str, Any]:
    client = client or NansenClient()
    raw = client.fetch_dex_trades()
    trades = list(raw.get("data") or [])
    seeds = select_seeds(trades)
    tape = build_tape(trades)

    knots: list[dict[str, Any]] = []
    for seed in seeds:
        knot = bfs_related(client, seed["address"])
        knot["seed_trade_label"] = seed.get("label_from_trade")
        knot["sample_trade"] = seed.get("sample_trade")
        sample = knot.get("sample_trade") or {}
        knot["token_symbol"] = sample.get("bought")
        knot["token_mint"] = sample.get("bought_address")
        knot["token_mint_short"] = _short(sample.get("bought_address"))
        enrich_labels(client, knot)
        maybe_counterparties(client, knot)
        mint = mint_stats_from_tape(knot, tape)
        graded = grade_knot(knot, mint_stats=mint, tape=tape)
        knot["grade"] = graded["grade"]
        knot["grade_notes"] = graded["notes"]
        knot["reasons"] = graded["reasons"]
        knot["reason_plain"] = graded["reason_plain"]
        knot["confidence"] = graded["confidence"]
        knot["signals"] = graded["signals"]
        knot["grade_detail"] = graded
        knots.append(knot)

    grade_counts = {g: 0 for g in config.GRADES}
    for k in knots:
        grade_counts[k["grade"]] = grade_counts.get(k["grade"], 0) + 1

    # Stable demo order: farms first, then solo, research, fail
    order = {g: i for i, g in enumerate(("FARM_CLUSTER", "SOLO_SM", "RESEARCH", "FAIL"))}
    knots.sort(key=lambda k: (order.get(k["grade"], 99), -int(k.get("related_count") or 0)))
    for i, k in enumerate(knots):
        k["featured"] = i == 0

    generated_at = datetime.now(timezone.utc).isoformat()
    history = append_history(knots, generated_at)
    featured = _featured_knot(knots)
    featured_card = None
    if featured:
        featured_card = {
            "seed_address": featured.get("seed_address"),
            "seed_short": featured.get("seed_short"),
            "grade": featured.get("grade"),
            "confidence": featured.get("confidence"),
            "reason_plain": featured.get("reason_plain"),
            "reasons": featured.get("reasons"),
            "token_symbol": featured.get("token_symbol"),
            "token_mint": featured.get("token_mint"),
            "token_mint_short": featured.get("token_mint_short"),
            "related_count": featured.get("related_count"),
            "node_count": featured.get("node_count"),
            "edge_count": featured.get("edge_count"),
            "signals": featured.get("signals"),
        }

    api_calls = read_counter()
    payload = {
        "product": "Glass Knot",
        "question": "Is this Smart Money touch a farm or solo?",
        "generated_at": generated_at,
        "demo_mode": client.demo,
        "policy": {
            "mode": "PAPER_INSPECT_ONLY",
            "banner": config.POLICY_BANNER,
            "grades": list(config.GRADES),
            "forbids": ["COPY_TRADE", "PLACE_ORDER", "SIZE_RECOMMENDATION", "KEEP_TRADE"],
        },
        "filters": {
            "chains": ["solana"],
            "trade_value_usd_min": config.TRADE_VALUE_USD_MIN,
            "bfs_max_depth": config.BFS_MAX_DEPTH,
            "include_counterparties": config.INCLUDE_COUNTERPARTIES,
            "use_premium_labels": config.USE_PREMIUM_LABELS,
        },
        "stats": {
            "trade_count": len(trades),
            "seed_count": len(seeds),
            "knot_count": len(knots),
            "grades": grade_counts,
        },
        "api_calls": api_calls,
        "tape": tape,
        "knots": knots,
        "featured": featured_card,
        "history": history,
        "pagination": raw.get("pagination"),
    }

    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    config.LATEST_PATH.write_text(json.dumps(payload, indent=2) + "\n")
    log.info(
        "wrote %s demo=%s trades=%d knots=%d grades=%s api_calls=%s",
        config.LATEST_PATH,
        client.demo,
        len(trades),
        len(knots),
        grade_counts,
        api_calls.get("total"),
    )
    return payload
