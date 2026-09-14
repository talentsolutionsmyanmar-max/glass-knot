"""Grade a wallet knot: FARM_CLUSTER | SOLO_SM | RESEARCH | FAIL.

Inspect-only. Volume is not edge. Never copy-trade, never size.
"""

from __future__ import annotations

from typing import Any

from app import config

ALLOWED = frozenset(config.GRADES)


def _label_names(labels: list[Any]) -> list[str]:
    names: list[str] = []
    for item in labels or []:
        if isinstance(item, str):
            names.append(item)
        elif isinstance(item, dict):
            for key in ("label", "name", "type", "category"):
                if item.get(key):
                    names.append(str(item[key]))
                    break
    return names


def _bad_labels(names: list[str]) -> list[str]:
    bad_needles = (
        "scam",
        "hack",
        "exploit",
        "phish",
        "drain",
        "mixer",
        "sanction",
        "rug",
        "honeypot",
    )
    hits = []
    for n in names:
        low = n.lower()
        if any(b in low for b in bad_needles):
            hits.append(n)
    return hits


def _unique(seq: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in seq:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def mint_stats_from_tape(knot: dict[str, Any], tape: list[dict[str, Any]] | None) -> dict[str, Any]:
    """Supporting signal: who else on this tape bought the same mint.

    Honest and inspect-only — uses the current SM tape, not invented fills.
    """
    sample = knot.get("sample_trade") or {}
    mint = sample.get("bought_address")
    seed = knot.get("seed_address")
    related = set(knot.get("related_addresses") or [])
    traders: set[str] = set()
    hits = 0
    timestamps: list[str] = []
    for t in tape or []:
        if mint and t.get("bought_address") == mint:
            hits += 1
            trader = t.get("trader") or t.get("trader_address")
            if trader:
                traders.add(trader)
            if t.get("ts"):
                timestamps.append(str(t["ts"]))
    related_on = related & traders
    rel_count = int(knot.get("related_count") or 0)
    other_sm = {a for a in traders if a != seed}
    return {
        "mint": mint,
        "token_symbol": sample.get("bought"),
        "tape_hits": hits,
        "traders_on_mint": len(traders),
        "related_on_mint": len(related_on),
        "shared_mint_density": round(len(related_on) / max(rel_count, 1), 3),
        "other_sm_on_mint": len(other_sm),
        "first_ts": min(timestamps) if timestamps else sample.get("ts"),
        "last_ts": max(timestamps) if timestamps else sample.get("ts"),
        "token_age_days": sample.get("age_days"),
    }


def _confidence(
    grade: str,
    *,
    related_count: int,
    density: float,
    depth: int,
    bad: list[str],
    mint: dict[str, Any],
) -> int:
    if grade == "FAIL":
        return 92 if bad else 99
    if grade == "FARM_CLUSTER":
        c = 68
        c += min(18, related_count * 2)
        if density >= 0.8:
            c += 8
        if depth >= 2:
            c += 4
        if int(mint.get("related_on_mint") or 0) >= 2:
            c += 5
        return int(min(96, c))
    if grade == "SOLO_SM":
        c = 90 if related_count == 0 else 74
        if int(mint.get("other_sm_on_mint") or 0) >= 3:
            c -= 8  # other SM on mint, but no related edges — less sure it's truly solo
        return int(max(62, min(94, c)))
    # RESEARCH
    c = 50 + min(14, related_count * 2)
    return int(max(45, min(68, c)))


def _plain_reason(
    grade: str,
    *,
    related_count: int,
    node_count: int,
    edge_count: int,
    density: float,
    token: str,
    bad: list[str],
) -> str:
    tok = token or "this mint"
    if grade == "FAIL":
        if bad:
            return (
                f"Risk labels ({', '.join(_unique(bad)[:3])}) sit on this knot. "
                "Grade is FAIL — inspect only, never a trade."
            )
        return "This knot is missing a seed address, so it cannot be graded."
    if grade == "FARM_CLUSTER":
        dense = "dense" if density >= 0.8 else "multi-wallet"
        return (
            f"This buyer is not sitting alone. {related_count} related wallets "
            f"form a {dense} knot ({node_count} nodes, {edge_count} edges) around "
            f"the seed. The structure reads as a farm cluster on {tok}, not a solo "
            "Smart Money touch."
        )
    if grade == "SOLO_SM":
        if related_count == 0:
            return (
                f"The related-wallet graph is empty. This looks like a solo Smart "
                f"Money wallet touching {tok}, not a farm of linked wallets."
            )
        return (
            f"The related-wallet graph is sparse ({related_count} related, "
            f"{node_count} nodes). This looks like a solo Smart Money touch on {tok}, "
            "not a farm cluster."
        )
    return (
        f"Related count is {related_count} — between the solo and farm thresholds. "
        f"The knot on {tok} is worth a human look; structure is not decisive."
    )


def _reasons(
    grade: str,
    *,
    related_count: int,
    node_count: int,
    edge_count: int,
    density: float,
    depth: int,
    names: list[str],
    bad: list[str],
    mint: dict[str, Any],
) -> list[str]:
    reasons: list[str] = []
    if grade == "FAIL" and bad:
        reasons.append(f"Risk labels: {', '.join(_unique(bad)[:4])}.")
    reasons.append(
        f"Related wallets: {related_count} "
        f"(farm ≥ {config.FARM_MIN_RELATED}, solo ≤ {config.SOLO_MAX_RELATED})."
    )
    reasons.append(
        f"Graph: {node_count} nodes, {edge_count} edges, density {density:.2f} edges/node."
    )
    reasons.append(f"BFS depth reached: {depth}.")
    if names:
        reasons.append(f"Labels: {', '.join(_unique(names)[:6])}.")
    else:
        reasons.append("Labels: none on the wallets we tagged (free labels only).")
    rel_on = int(mint.get("related_on_mint") or 0)
    others = int(mint.get("other_sm_on_mint") or 0)
    density_m = float(mint.get("shared_mint_density") or 0)
    if rel_on:
        reasons.append(
            f"Shared-mint: {rel_on} related wallet(s) also bought this mint on the current tape "
            f"(density {density_m:.2f})."
        )
    elif others:
        reasons.append(
            f"Shared-mint: {others} other SM trader(s) bought this mint on the tape, "
            "but they are not in this related-wallet knot."
        )
    else:
        reasons.append(
            "Shared-mint: this mint appears only from this seed on the current tape."
        )
    age = mint.get("token_age_days")
    if age is not None:
        reasons.append(
            f"Timing: token age {age} day(s) at the sample trade"
            + (f" ({mint.get('last_ts')})." if mint.get("last_ts") else ".")
            + " Age is context, not size or edge."
        )
    elif mint.get("last_ts"):
        reasons.append(f"Timing: sample Smart Money touch at {mint.get('last_ts')}.")
    reasons.append("Volume is not edge. No copy-trade, no orders, no size.")
    return reasons


def grade_knot(
    knot: dict[str, Any],
    *,
    mint_stats: dict[str, Any] | None = None,
    tape: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    Grading rules (inspect-only):
    - FAIL: bad labels, empty seed, or pipeline error
    - FARM_CLUSTER: dense related-wallet graph (many nodes / edges)
    - SOLO_SM: SM seed with ≤ SOLO_MAX_RELATED related wallets
    - RESEARCH: everything else worth a human look
    """
    notes: list[str] = []
    seed = knot.get("seed_address") or ""
    mint = mint_stats if mint_stats is not None else mint_stats_from_tape(knot, tape)

    if not seed:
        reasons = ["Missing seed address — cannot inspect a knot."]
        return _out(
            "FAIL",
            notes + ["missing_seed"],
            knot,
            reasons=reasons,
            reason_plain="This knot is missing a seed address, so it cannot be graded.",
            confidence=99,
            signals={"related_count": 0, "bad_labels": [], **mint},
        )

    all_labels = list(knot.get("seed_labels") or [])
    for node in knot.get("nodes") or []:
        all_labels.extend(node.get("labels") or [])
    names = _label_names(all_labels)
    bad = _bad_labels(names)

    related_count = int(knot.get("related_count") or 0)
    node_count = int(knot.get("node_count") or (related_count + 1))
    edge_count = int(knot.get("edge_count") or 0)
    depth = int(knot.get("bfs_depth_reached") or 0)
    density = edge_count / max(node_count, 1)
    token = str(mint.get("token_symbol") or (knot.get("sample_trade") or {}).get("bought") or "")

    notes.append(f"related={related_count}")
    notes.append(f"nodes={node_count}")
    notes.append(f"edges={edge_count}")
    notes.append(f"bfs_depth={depth}")
    notes.append(f"shared_mint_density={mint.get('shared_mint_density')}")
    notes.append("volume_is_not_edge")
    notes.append("no_copy_trade")

    signals = {
        "related_count": related_count,
        "node_count": node_count,
        "edge_count": edge_count,
        "bfs_depth": depth,
        "density": round(density, 3),
        "labels": _unique(names)[:8],
        "bad_labels": bad,
        "shared_mint_density": mint.get("shared_mint_density"),
        "related_on_mint": mint.get("related_on_mint"),
        "other_sm_on_mint": mint.get("other_sm_on_mint"),
        "tape_hits": mint.get("tape_hits"),
        "token_age_days": mint.get("token_age_days"),
        "sample_ts": mint.get("last_ts"),
        "token_symbol": token or None,
        "mint": mint.get("mint"),
    }

    if bad:
        notes.append(f"bad_labels:{','.join(bad[:4])}")
        reasons = _reasons(
            "FAIL",
            related_count=related_count,
            node_count=node_count,
            edge_count=edge_count,
            density=density,
            depth=depth,
            names=names,
            bad=bad,
            mint=mint,
        )
        return _out(
            "FAIL",
            notes,
            knot,
            reasons=reasons,
            reason_plain=_plain_reason(
                "FAIL",
                related_count=related_count,
                node_count=node_count,
                edge_count=edge_count,
                density=density,
                token=token,
                bad=bad,
            ),
            confidence=_confidence(
                "FAIL",
                related_count=related_count,
                density=density,
                depth=depth,
                bad=bad,
                mint=mint,
            ),
            signals=signals,
        )

    if related_count >= config.FARM_MIN_RELATED or (
        node_count >= config.FARM_MIN_RELATED + 1 and density >= 0.8 and depth >= 1
    ):
        grade = "FARM_CLUSTER"
        notes.append("dense_related_wallet_cluster")
    elif related_count <= config.SOLO_MAX_RELATED:
        grade = "SOLO_SM"
        notes.append("sparse_or_solo_related")
    else:
        grade = "RESEARCH"
        notes.append("ambiguous_cluster_needs_human")

    reasons = _reasons(
        grade,
        related_count=related_count,
        node_count=node_count,
        edge_count=edge_count,
        density=density,
        depth=depth,
        names=names,
        bad=bad,
        mint=mint,
    )
    return _out(
        grade,
        notes,
        knot,
        reasons=reasons,
        reason_plain=_plain_reason(
            grade,
            related_count=related_count,
            node_count=node_count,
            edge_count=edge_count,
            density=density,
            token=token,
            bad=bad,
        ),
        confidence=_confidence(
            grade,
            related_count=related_count,
            density=density,
            depth=depth,
            bad=bad,
            mint=mint,
        ),
        signals=signals,
    )


def _out(
    grade: str,
    notes: list[str],
    knot: dict[str, Any],
    *,
    reasons: list[str] | None = None,
    reason_plain: str | None = None,
    confidence: int | None = None,
    signals: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if grade not in ALLOWED:
        grade = "FAIL"
        notes = list(notes) + ["illegal_grade_collapsed_to_FAIL"]
        reasons = list(reasons or []) + ["Illegal grade collapsed to FAIL."]
        reason_plain = reason_plain or "Illegal grade collapsed to FAIL."
        confidence = 99
    return {
        "grade": grade,
        "notes": notes,
        "reasons": reasons or notes,
        "reason_plain": reason_plain
        or (reasons[0] if reasons else "Graded from related-wallet structure."),
        "confidence": int(confidence if confidence is not None else 50),
        "signals": signals or {},
        "seed_address": knot.get("seed_address"),
        "seed_short": knot.get("seed_short"),
        "related_count": knot.get("related_count"),
        "node_count": knot.get("node_count"),
        "edge_count": knot.get("edge_count"),
        "policy": {
            "mode": "PAPER_INSPECT_ONLY",
            "forbids": ["COPY_TRADE", "PLACE_ORDER", "SIZE_RECOMMENDATION"],
        },
    }
