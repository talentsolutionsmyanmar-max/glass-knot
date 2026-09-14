"""Grade a wallet knot: FARM_CLUSTER | SOLO_SM | RESEARCH | FAIL."""

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


def grade_knot(knot: dict[str, Any]) -> dict[str, Any]:
    """
    Grading rules (inspect-only):
    - FAIL: bad labels, empty seed, or pipeline error
    - FARM_CLUSTER: dense related-wallet graph (many nodes / edges)
    - SOLO_SM: SM seed with ≤ SOLO_MAX_RELATED related wallets
    - RESEARCH: everything else worth a human look
    """
    notes: list[str] = []
    seed = knot.get("seed_address") or ""
    if not seed:
        return _out("FAIL", notes + ["missing_seed"], knot)

    all_labels = list(knot.get("seed_labels") or [])
    for node in knot.get("nodes") or []:
        all_labels.extend(node.get("labels") or [])
    names = _label_names(all_labels)
    bad = _bad_labels(names)
    if bad:
        notes.append(f"bad_labels:{','.join(bad[:4])}")
        return _out("FAIL", notes + ["volume_is_not_edge", "no_copy_trade"], knot)

    related_count = int(knot.get("related_count") or 0)
    node_count = int(knot.get("node_count") or (related_count + 1))
    edge_count = int(knot.get("edge_count") or 0)
    depth = int(knot.get("bfs_depth_reached") or 0)
    density = edge_count / max(node_count, 1)

    notes.append(f"related={related_count}")
    notes.append(f"nodes={node_count}")
    notes.append(f"edges={edge_count}")
    notes.append(f"bfs_depth={depth}")
    notes.append("volume_is_not_edge")
    notes.append("no_copy_trade")

    # Farm: large related set OR dense multi-hop cluster
    if related_count >= config.FARM_MIN_RELATED or (
        node_count >= config.FARM_MIN_RELATED + 1 and density >= 0.8 and depth >= 1
    ):
        notes.append("dense_related_wallet_cluster")
        return _out("FARM_CLUSTER", notes, knot)

    if related_count <= config.SOLO_MAX_RELATED:
        notes.append("sparse_or_solo_related")
        return _out("SOLO_SM", notes, knot)

    notes.append("ambiguous_cluster_needs_human")
    return _out("RESEARCH", notes, knot)


def _out(grade: str, notes: list[str], knot: dict[str, Any]) -> dict[str, Any]:
    if grade not in ALLOWED:
        grade = "FAIL"
        notes = list(notes) + ["illegal_grade_collapsed_to_FAIL"]
    return {
        "grade": grade,
        "notes": notes,
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
