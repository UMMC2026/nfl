# engine/normalize_picks.py

from datetime import datetime


def normalize_picks(raw_picks):
    """
    Normalize legacy pick formats into canonical schema.
    This is the ONLY place legacy flexibility is allowed.
    """

    run_day = datetime.utcnow().strftime("%Y%m%d")  # TODAY's date, NOT tomorrow
    normalized = []

    for p in raw_picks:
        p = dict(p)

        player = p.get("player", "UNKNOWN_PLAYER")
        team = p.get("team", "UNKNOWN_TEAM")
        league = p.get("league", "NBA")

        # ───────── GAME ID ─────────
        if "game_id" not in p:
            if "opponent" in p:
                game_id = f"{league}_{team}_VS_{p['opponent']}"
            else:
                # TEAM-DAY fallback (truthful, not fake)
                game_id = f"{league}_{team}_{run_day}"

            p["game_id"] = game_id.upper().replace(" ", "_")

        # ───────── EDGE KEY (logical) ─────────
        if "edge_key" not in p:
            p["edge_key"] = (
                f"{p['game_id']}_{player}_{p.get('stat')}_{p.get('direction')}"
            ).upper().replace(" ", "_")

        # ───────── EDGE ID (physical, unique) ─────────
        if "edge_id" not in p:
            line = str(p.get("line", "X")).replace(".", "_")
            p["edge_id"] = f"{p['edge_key']}_LINE_{line}"

        # ───────── DEFAULTS ─────────
        p.setdefault("is_primary", False)

        normalized.append(p)

    return normalized
