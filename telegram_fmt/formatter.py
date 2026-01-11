"""
Telegram message formatter for GOVERNED, VALIDATED signal output.
Only consumes validated_primary_edges.json schema.
"""

from engine.tiers import tier_emoji


def _dir_symbol(direction: str) -> str:
    return "O" if direction == "higher" else "U"


def format_signal(signal: dict) -> str:
    """
    Full detailed format for a single validated primary signal.
    """
    tier = signal.get("confidence_tier", "UNKNOWN")
    emoji = tier_emoji(tier)

    league = signal.get("league", "SPORT")
    player = signal.get("player", "Unknown")
    team = signal.get("team", "?")
    stat = signal.get("stat", "")
    line = signal.get("line", 0)
    direction = _dir_symbol(signal.get("direction"))
    prob = signal.get("probability", 0) * 100

    notes = signal.get("notes")

    body = f"""
{emoji} {league} | PRIMARY EDGE

{player} ({team})
{direction} {line} {stat}

📊 Probability: {prob:.1f}%
🏷️ Tier: {tier}
""".strip()

    if notes:
        body += f"\n\n📝 Notes:\n{notes}"

    return body


def format_signal_compact(signal: dict) -> str:
    """
    Compact one-line format for lists.
    """
    tier = signal.get("confidence_tier", "?")
    emoji = tier_emoji(tier)

    player = signal.get("player", "Unknown")
    stat = signal.get("stat", "")
    line = signal.get("line", 0)
    direction = _dir_symbol(signal.get("direction"))
    prob = signal.get("probability", 0) * 100

    return f"{emoji} {player} {direction}{line} {stat} | {prob:.0f}%"


def format_signal_batch(
    signals: list,
    title: str = "Validated Signals",
) -> str:
    """
    Batch formatter for Telegram.
    Expects validated PRIMARY signals only.
    """
    header = f"""
🏀 {title}
{'=' * 36}
""".strip()

    # group by tier
    tiers = ["SLAM", "STRONG", "LEAN"]
    sections = []

    for tier in tiers:
        group = [s for s in signals if s.get("confidence_tier") == tier]
        if not group:
            continue

        sections.append(f"{tier_emoji(tier)} {tier} PLAYS")
        for s in group:
            sections.append(format_signal_compact(s))
        sections.append("")

    footer = f"""
{'=' * 36}
⚠️ Validated primary edges only.
""".strip()

    return "\n".join([header, *sections, footer])


def format_parlay_suggestion(signals: list, legs: int = 3) -> str:
    """
    Parlay suggestion from top-probability validated signals.
    """
    from math import prod

    top = signals[:legs]
    combined_prob = prod([s.get("probability", 0) for s in top])

    # Underdog multipliers
    payouts = {2: 3, 3: 6, 4: 10, 5: 20, 6: 35, 7: 50, 8: 100}
    payout = payouts.get(legs, legs * 2)

    ev = combined_prob * payout - 1

    lines = [
        f"🎰 {legs}-LEG PARLAY (PRIMARY EDGES)",
        f"Combined: {combined_prob*100:.1f}% | EV: {ev:+.2f}",
        "",
    ]

    for s in top:
        player = s.get("player")
        stat = s.get("stat")
        line = s.get("line")
        direction = _dir_symbol(s.get("direction"))
        prob = s.get("probability", 0) * 100

        lines.append(f"  • {player} {direction}{line} {stat} ({prob:.0f}%)")

    return "\n".join(lines)
