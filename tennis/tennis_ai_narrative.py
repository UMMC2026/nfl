"""tennis/tennis_ai_narrative.py

AI narrative generator for tennis match edges.

Uses DeepSeek API (same as NBA/CBB) to generate contextual one-liners
from the MatchContext data. Falls back gracefully if API unavailable.

Architecture:
  Layer 2 (LLM Adapter) — produces language, never overrides probabilities.
  Language rules: "data suggests", "may indicate" — NO imperatives.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional


def _call_deepseek(prompt: str, max_tokens: int = 80) -> Optional[str]:
    """Call DeepSeek API. Returns None on failure."""
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        return None

    try:
        import requests
        resp = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "temperature": 0.3,
            },
            timeout=10,
        )
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception:
        pass
    return None


def generate_tennis_narrative(
    edge: Dict[str, Any],
    *,
    use_ai: bool = False,
) -> str:
    """
    Generate a narrative for a tennis edge.

    If use_ai=True and DEEPSEEK_API_KEY is set, uses the LLM to expand
    the narrative_seed into a polished one-liner.

    Otherwise generates a math-only factual narrative from the context.
    """
    ctx = edge.get("match_context") or {}
    player_ctx = ctx.get("player") or {}
    opponent_ctx = ctx.get("opponent") or {}
    h2h = ctx.get("head_to_head") or {}
    sim = edge.get("simulation") or {}

    player = edge.get("player", "?")
    stat = edge.get("stat", "?")
    line = edge.get("line", 0)
    direction = edge.get("direction", "?")
    prob = edge.get("probability", 0)
    tier = edge.get("tier", "?")
    sim_mean = sim.get("mean", 0)

    # ── BUILD FACTUAL NARRATIVE ──────────────────────────────────
    parts: List[str] = []

    # Core projection
    gap = sim_mean - line
    if stat == "total_games":
        parts.append(f"MC projects {sim_mean:.1f} total games (line {line})")
        if abs(gap) >= 1.0:
            parts.append(f"{'above' if gap > 0 else 'below'} line by {abs(gap):.1f}")
    elif stat == "game_spread":
        opp_name = opponent_ctx.get("name", "opponent")
        parts.append(f"{player} projected spread {sim_mean:.1f} vs {opp_name} (line {line:+.1f})")
    else:
        parts.append(f"MC projects {sim_mean:.1f} {stat} (line {line})")

    # Ranking context
    p_rank = player_ctx.get("ranking")
    o_rank = opponent_ctx.get("ranking")
    if p_rank and o_rank:
        parts.append(f"#{p_rank} vs #{o_rank}")

    # H2H
    if h2h.get("total_matches", 0) > 0:
        parts.append(f"H2H {h2h.get('p1_wins', 0)}-{h2h.get('p2_wins', 0)}")

    # Serve edge
    p_hold = player_ctx.get("serve_hold_rate")
    o_hold = opponent_ctx.get("serve_hold_rate")
    if p_hold and o_hold and abs(p_hold - o_hold) > 0.05:
        leader = player if p_hold > o_hold else opponent_ctx.get("name", "opp")
        parts.append(f"{leader} serve edge ({max(p_hold, o_hold):.0%} hold)")

    # Style
    p_style = player_ctx.get("player_style")
    o_style = opponent_ctx.get("player_style")
    if p_style and o_style and p_style != o_style:
        parts.append(f"{p_style} vs {o_style}")

    # Surface Elo
    p_elo = player_ctx.get("elo_surface")
    o_elo = opponent_ctx.get("elo_surface")
    if p_elo and o_elo and abs(p_elo - o_elo) > 50:
        parts.append(f"Elo gap: {abs(p_elo - o_elo):.0f}")

    factual = " | ".join(parts)

    # ── OPTIONAL AI EXPANSION ────────────────────────────────────
    if use_ai:
        narrative_seed = ctx.get("narrative_seed", "")
        prompt = (
            f"You are a tennis analyst. Write ONE concise sentence (max 25 words) "
            f"explaining this edge. Use language like 'data suggests' — never 'bet' or 'lock'.\n\n"
            f"Edge: {player} {stat} {direction} {line} ({prob:.0%} prob, {tier})\n"
            f"Context: {narrative_seed}\n"
            f"Facts: {factual}\n"
            f"One sentence:"
        )
        ai_result = _call_deepseek(prompt, max_tokens=60)
        if ai_result:
            return ai_result

    return factual


def enrich_edges_with_narrative(
    edges: List[Dict[str, Any]],
    *,
    use_ai: bool = False,
) -> List[Dict[str, Any]]:
    """Add 'narrative' field to each edge in-place."""
    for edge in edges:
        try:
            edge["narrative"] = generate_tennis_narrative(edge, use_ai=use_ai)
        except Exception:
            edge["narrative"] = None
    return edges
