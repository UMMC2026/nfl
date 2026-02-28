"""
CBB Output Formatter — Ensures all required fields, caps, badges, and diagnostics are present in output schema.
"""
from sports.cbb.probability_caps import cap_probability, assign_confidence_badge
from calibration.log_writer import log_pick_result

def format_cbb_pick_output(
        # --- Fallback recall for missing player stats ---
        import os, json
        fallback_stats = {}
        fallback_path = os.path.join(os.path.dirname(__file__), 'data', 'player_stats.json')
        if os.path.exists(fallback_path):
            with open(fallback_path) as f:
                fallback_stats = json.load(f)
        player_key = player.lower().replace(' ', '_')
        if player_key in fallback_stats:
            fallback = fallback_stats[player_key]
            output['fallback_stats'] = fallback
            # Partial stat recall: fill only missing fields from fallback
            filled_from_fallback = []
            for k, v in fallback.items():
                if k not in output or output[k] in (None, '', '-', 0):
                    output[k] = v
                    filled_from_fallback.append(k)
            output['stat_source'] = 'fallback' if filled_from_fallback else 'live'
            output['fallback_flag'] = bool(filled_from_fallback)
            output['fallback_filled_fields'] = filled_from_fallback
        else:
            output['stat_source'] = 'live'
            output['fallback_flag'] = False
            output['fallback_filled_fields'] = []
    edge_id: str,
    player: str,
    stat: str,
    line: float,
    direction: str,
    raw_probability: float,
    sample_n: int,
    variance: float,
    tier: str,
    pick_state: str,
    extra_fields: dict = None
) -> dict:
    """
    Formats a CBB pick output object with all required diagnostics and governance fields.
    """
    probability = cap_probability(stat, raw_probability, sample_n, variance)
    badge = assign_confidence_badge(probability, sample_n, variance)

    # Always anchor output to filtered mean/variance if present
    filtered_mean = None
    filtered_var = None
    if extra_fields:
        filtered_mean = extra_fields.get('filtered_points_mean')
        filtered_var = extra_fields.get('kalman_points_var')


    # --- RSI Momentum Calculation ---
    rsi_momentum = None
    if extra_fields and 'game_logs' in extra_fields:
        logs = extra_fields['game_logs']
        pts = [g.get('points', 0) for g in logs][-10:]
        gains = [max(pts[i+1] - pts[i], 0) for i in range(len(pts)-1)]
        losses = [max(pts[i] - pts[i+1], 0) for i in range(len(pts)-1)]
        avg_gain = sum(gains) / len(gains) if gains else 0.0
        avg_loss = sum(losses) / len(losses) if losses else 0.0
        if avg_loss == 0:
            rsi_momentum = 100.0
        else:
            rs = avg_gain / avg_loss if avg_loss else 0.0
            rsi_momentum = 100 - (100 / (1 + rs))

    # --- Web Narrative Integration ---
    def generate_narrative(player, stat, line, direction, probability, sample_n, opponent=None, splits=None, next_game=None):
        dir_word = "exceed" if direction.upper() == "HIGHER" else "fall below"
        opp_str = f" against {opponent}" if opponent else ""
        conf = "high confidence" if probability >= 0.7 else ("moderate confidence" if probability >= 0.6 else "cautious outlook")
        split_str = f"Splits: {splits}" if splits else ""
        next_game_str = f"Next Game: {next_game}" if next_game else ""
        return (
            f"Based on Monte Carlo simulations and recent performance, {player} is projected to {dir_word} {line} {stat}{opp_str} with {conf} (n={sample_n}). "
            f"{split_str} {next_game_str}"
        )

    opponent = extra_fields.get('opponent') if extra_fields else None
    splits = extra_fields.get('splits') if extra_fields else None
    next_game = extra_fields.get('next_game') if extra_fields else None
    narrative = generate_narrative(player, stat, line, direction, probability, sample_n, opponent, splits, next_game)

    # Always include model mean for points/PTS
    player_mean = None
    if extra_fields:
        # Try all possible keys for mean
        player_mean = (
            extra_fields.get("player_mean")
            or extra_fields.get("mu")
            or extra_fields.get("mean")
            or extra_fields.get("lambda")
            or extra_fields.get("filtered_points_mean")
        )
    # Fallback: if stat is points/PTS and still missing, set to line (neutral)
    if player_mean is None and stat.lower() in ("pts", "points"):
        player_mean = line

    output = {
        "edge_id": edge_id,
        "sport": "CBB",
        "entity": player,
        "market": stat,
        "line": line,
        "direction": direction,
        "probability": round(probability, 4),
        "tier": tier,
        "pick_state": pick_state,
        "sample_n": sample_n,
        "variance": round(variance, 3),
        "confidence_badge": badge,
        # Anchor fields for reporting and audit
        "filtered_mean": filtered_mean,
        "filtered_variance": filtered_var,
        "narrative": narrative,
        "rsi_momentum": round(rsi_momentum, 2) if rsi_momentum is not None else None,
    }
    if player_mean is not None and stat.lower() in ("pts", "points"):
        output["player_mean"] = round(player_mean, 2) if isinstance(player_mean, (int, float)) else player_mean
    if extra_fields:
        output.update(extra_fields)

    # --- Calibration logging: log every live probability ---
    log_pick_result(
        edge_id=edge_id,
        player=player,
        stat=stat,
        line=line,
        direction=direction,
        probability=round(probability, 4),
        tier=tier,
        pick_state=pick_state,
        result=None
    )

    return output
