# engine/collapse_edges.py

from collections import defaultdict
from typing import List, Dict, Any


def collapse_edges(picks):
    """
    For each logical EDGE (edge_key):
    - Select exactly ONE primary line
    - Mark all others as correlated alternatives
    """

    grouped = defaultdict(list)
    for p in picks:
        grouped[p["edge_key"]].append(p)

    collapsed = []

    for edge_key, group in grouped.items():
        direction = group[0]["direction"].upper()

        if direction == "OVER":
            primary = max(group, key=lambda x: x["line"])
        else:
            primary = min(group, key=lambda x: x["line"])

        primary["is_primary"] = True
        collapsed.append(primary)

        for g in group:
            if g is primary:
                continue
            g["is_primary"] = False
            collapsed.append(g)

    return collapsed


def dedupe_player_props(edges: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Remove duplicate player-stat combinations.

    For same player/stat/line, keep only the highest confidence edge.

    Args:
        edges: List of edge dicts

    Returns:
        Deduplicated edges list

    Raises:
        RuntimeError: If all edges are duped and removed
    """
    seen = {}
    removed_dupes = []

    for e in edges:
        key = (e.get("player"), e.get("stat"), round(e.get("line", 0), 1))

        if key not in seen:
            seen[key] = e
        else:
            # Keep higher confidence edge
            old_conf = seen[key].get("confidence", 0)
            new_conf = e.get("confidence", 0)

            if new_conf > old_conf:
                removed_dupes.append(seen[key])
                seen[key] = e
            else:
                removed_dupes.append(e)

    if not seen:
        raise RuntimeError("DEDUPE: All edges removed (all duplicates)")

    if removed_dupes:
        print(f"⚠️  DEDUPE: Removed {len(removed_dupes)} duplicate edges")

    print(f"✅ DEDUPE: {len(seen)} unique edges retained")
    return list(seen.values())
