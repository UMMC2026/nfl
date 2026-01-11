# engine/render_gate.py

from collections import defaultdict


class RenderGateError(Exception):
    pass


REQUIRED_FIELDS = {
    "edge_id",
    "edge_key",
    "game_id",
    "player",
    "stat",
    "direction",
    "line",
    "probability",
    "confidence_tier",
    "is_primary",
}


TIER_THRESHOLDS = {
    "SLAM": 0.75,
    "STRONG": 0.65,
    "LEAN": 0.55,
}


def render_gate(picks):
    if not picks:
        raise RenderGateError("No picks supplied to render gate.")

    for p in picks:
        missing = REQUIRED_FIELDS - p.keys()
        if missing:
            raise RenderGateError(f"Missing fields {missing}")

        if not (0 <= p["probability"] <= 1):
            raise RenderGateError(f"Invalid probability for {p['player']}")

        if p["probability"] < TIER_THRESHOLDS[p["confidence_tier"]]:
            raise RenderGateError(f"Tier mismatch for {p['player']}")

    # One primary per EDGE
    edge_primary = defaultdict(int)
    for p in picks:
        if p["is_primary"]:
            edge_primary[p["edge_key"]] += 1

    offenders = {k: v for k, v in edge_primary.items() if v != 1}
    if offenders:
        raise RenderGateError(f"EDGE_KEY primary violation: {offenders}")

    # One primary per PLAYER per GAME
    player_game = defaultdict(int)
    for p in picks:
        if p["is_primary"]:
            key = (p["player"], p["game_id"])
            player_game[key] += 1

    offenders = {k: v for k, v in player_game.items() if v > 1}
    if offenders:
        raise RenderGateError(f"Multiple primaries per player/game: {offenders}")

    return picks
