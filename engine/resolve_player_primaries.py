# engine/resolve_player_primaries.py

from collections import defaultdict

TIER_RANK = {
    "SLAM": 3,
    "STRONG": 2,
    "LEAN": 1,
}


def resolve_player_primaries(picks):
    """
    Enforce exactly ONE primary edge per (player, game_id).
    Selection is deterministic:
      1) Highest confidence tier
      2) Highest probability
    """

    grouped = defaultdict(list)

    for p in picks:
        grouped[(p["player"], p["game_id"])].append(p)

    resolved = []

    for (player, game_id), group in grouped.items():
        if len(group) == 1:
            group[0]["is_primary"] = True
            resolved.extend(group)
            continue

        # Sort strongest first
        group_sorted = sorted(
            group,
                key=lambda p: (
                    TIER_RANK.get(p.get("confidence_tier"), 0),
                    p.get("probability", 0),
                ),
            reverse=True,
        )

        # Select ONE primary
        primary = group_sorted[0]
        primary["is_primary"] = True
        resolved.append(primary)

        # All others are correlated alternatives
        for g in group_sorted[1:]:
            g["is_primary"] = False
            resolved.append(g)

    return resolved
