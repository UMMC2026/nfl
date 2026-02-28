"""
AI-Powered Sports Commentary Generator
REFACTORED: Math-Only Reporting (No Confabulation)

Principle: Report ONLY what the model actually computed.
- NO speculation ("may face foul trouble")
- NO unfalsifiable claims ("market overcorrecting")  
- NO invented explanations ("defensive assignment")
- YES: distributions, factors, historical rates
"""

import os
import requests
import json
from typing import Dict, List, Optional


def _as_percent(value, default: float = 0.0) -> float:
    """Normalize probability/confidence to a 0-100 percent scale."""
    try:
        if value is None:
            return float(default)
        v = float(value)
        # Accept either decimal [0,1] or percent [0,100]
        if 0.0 <= v <= 1.0:
            v *= 100.0
        # Clamp to sane bounds for reporting
        return float(max(0.0, min(100.0, v)))
    except Exception:
        return float(default)


def _pick_model_confidence_percent(pick: dict) -> float:
    """Best-effort 'model' confidence (pre-penalty) in percent."""
    try:
        ed = pick.get("edge_diagnostics")
        if isinstance(ed, dict):
            pens = ed.get("penalties")
            if isinstance(pens, dict) and pens.get("raw_probability") is not None:
                return _as_percent(pens.get("raw_probability"), default=0.0)
    except Exception:
        pass
    return _as_percent(pick.get("model_confidence"), default=_as_percent(pick.get("probability"), default=50.0))


def _pick_final_confidence_percent(pick: dict) -> float:
    """Best-effort 'final' confidence (post-penalty) in percent.

    Preference order:
    - effective_confidence (canonical engine output)
    - edge_diagnostics.penalties.final_probability (fallback for legacy outputs)
    - probability (fallback)
    """
    eff = pick.get("effective_confidence")
    if eff is not None:
        return _as_percent(eff, default=50.0)
    try:
        ed = pick.get("edge_diagnostics")
        if isinstance(ed, dict):
            pens = ed.get("penalties")
            if isinstance(pens, dict) and pens.get("final_probability") is not None:
                return _as_percent(pens.get("final_probability"), default=50.0)
    except Exception:
        pass
    return _as_percent(pick.get("probability"), default=50.0)


def _is_hybrid_veto(pick: dict) -> bool:
    try:
        if str(pick.get("hybrid_tier") or "").upper() == "VETO":
            return True
        notes = pick.get("context_notes")
        if isinstance(notes, list):
            for n in notes:
                if "HYBRID VETO" in str(n).upper():
                    return True
    except Exception:
        return False
    return False


def _decision_from_final_confidence(final_conf_percent: float, *, sport: str = "NBA") -> tuple[str, str]:
    """Return (tier, engine_decision) from final confidence using canonical thresholds."""
    try:
        from config.thresholds import implied_tier

        tier = implied_tier(max(0.0, min(1.0, float(final_conf_percent) / 100.0)), sport=str(sport or "NBA"))
        t = str(tier or "").upper()
        if t == "SLAM":
            return t, "PLAY"
        if t == "STRONG":
            return t, "STRONG"
        if t == "LEAN":
            return t, "LEAN"
        return (t or "NO_PLAY"), "NO_PLAY"
    except Exception:
        # Fail-soft fallback: never claim actionable if we can't determine tier.
        return "NO_PLAY", "NO_PLAY"

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "").strip()
OLLAMA_URL = "http://localhost:11434/api/generate"


def generate_pick_commentary(pick: dict, game_context: dict = None) -> str:
    """
    Generate MATH-ONLY commentary explaining the pick.
    
    Reports ONLY what the model actually computed:
    - Projection vs line gap
    - Factors that were applied (pace, matchup, situation)
    - Probability and edge calculations
    
    NO speculation, NO invented explanations.
    """
    player = pick.get('player', 'Unknown')
    stat = pick.get('stat', '').upper()
    direction = pick.get('direction', 'higher').upper()
    line = pick.get('line', 0)
    
    # FIX: Support multiple field names for mean (mu, mu_raw, player_mean, decision_trace.mean.lambda)
    mu = pick.get('mu', pick.get('mu_raw', pick.get('player_mean', 0)))
    
    # Try to extract from decision_trace if mu is still 0
    if mu == 0:
        decision_trace = pick.get('decision_trace', {})
        mean_trace = decision_trace.get('mean', {})
        mu = mean_trace.get('lambda', 0)
    
    mu_raw = pick.get('mu_raw', mu)
    sigma = pick.get('sigma', 2.0)
    edge = pick.get('edge', 0)
    
    # Compute z_score if not provided
    z_score = pick.get('z_score', 0)
    if z_score == 0 and mu > 0 and sigma > 0:
        z_score = (line - mu) / sigma
    
    # Confidence (keep model vs final distinct to prevent contradictions)
    model_conf_pct = _pick_model_confidence_percent(pick)
    final_conf_pct = _pick_final_confidence_percent(pick)
    
    edge_quality = pick.get('edge_quality', 'UNKNOWN')
    
    # Extract actual factors that were applied
    pace_factor = pick.get('pace_factor', 1.0)
    matchup_factor = pick.get('matchup_factor', 1.0)
    defense_factor = pick.get('defense_factor', 1.0)
    situation_factor = pick.get('situation_factor', 1.0)
    
    # Calculate projection gap
    gap = line - mu
    gap_pct = (gap / mu * 100) if mu > 0 else 0
    
    # Build MATH-ONLY commentary
    lines = []
    
    # Line 1: Core projection
    lines.append(f"Model projects {mu:.1f} {stat.lower()} (line: {line})")
    
    # Line 2: Gap analysis
    if direction == "HIGHER":
        if gap > 0:
            lines.append(f"Line is {abs(gap):.1f} ABOVE projection ({abs(gap_pct):.0f}% gap)")
        else:
            lines.append(f"Line is {abs(gap):.1f} BELOW projection ({abs(gap_pct):.0f}% gap)")
    else:  # LOWER
        if gap > 0:
            lines.append(f"Line is {abs(gap):.1f} ABOVE projection ({abs(gap_pct):.0f}% gap)")
        else:
            lines.append(f"Line is {abs(gap):.1f} BELOW projection ({abs(gap_pct):.0f}% gap)")
    
    # Line 3: Applied factors (ONLY what was actually computed)
    factors_applied = []
    if pace_factor != 1.0:
        pct = (pace_factor - 1) * 100
        factors_applied.append(f"pace {pct:+.0f}%")
    if matchup_factor != 1.0:
        pct = (matchup_factor - 1) * 100
        factors_applied.append(f"matchup {pct:+.0f}%")
    if defense_factor != 1.0:
        pct = (defense_factor - 1) * 100
        factors_applied.append(f"defense {pct:+.0f}%")
    if situation_factor != 1.0:
        pct = (situation_factor - 1) * 100
        factors_applied.append(f"situation {pct:+.0f}%")
    
    if factors_applied:
        lines.append(f"Adjustments: {', '.join(factors_applied)}")
    
    # Line 4: Probability statement (model vs final) with edge diagnostics
    edge_diag = pick.get('edge_diagnostics', {})
    z_info = edge_diag.get('z_score', {})
    if z_info:
        z_val = z_info.get('z_score', z_score)
        if abs(final_conf_pct - model_conf_pct) >= 0.6:
            lines.append(
                f"Model P({direction.lower()} {line}) = {model_conf_pct:.1f}% | Final confidence = {final_conf_pct:.1f}% | z = {z_val:+.2f}σ"
            )
        else:
            lines.append(f"P({direction.lower()} {line}) = {final_conf_pct:.1f}% | z = {z_val:+.2f}σ")
    else:
        if abs(final_conf_pct - model_conf_pct) >= 0.6:
            lines.append(
                f"Model P({direction.lower()} {line}) = {model_conf_pct:.1f}% | Final confidence = {final_conf_pct:.1f}% | z = {z_score:+.2f}σ"
            )
        else:
            lines.append(f"P({direction.lower()} {line}) = {final_conf_pct:.1f}% | z = {z_score:+.2f}σ")
    
    # Line 5: Penalty breakdown (only when internally consistent)
    penalties = edge_diag.get('penalties', {}) if isinstance(edge_diag, dict) else {}
    if isinstance(penalties, dict) and penalties.get('total_penalty_pct', 0) > 0:
        raw_p = _as_percent(penalties.get('raw_probability'), default=model_conf_pct)
        final_p = _as_percent(penalties.get('final_probability'), default=final_conf_pct)
        total_pen = _as_percent(penalties.get('total_penalty_pct'), default=0.0)
        # If legacy outputs have mismatched penalty.final vs pick.effective_confidence, avoid printing a contradictory line.
        if abs(final_p - final_conf_pct) <= 1.0:
            lines.append(f"Raw {raw_p:.0f}% → Final {final_p:.0f}% (−{total_pen:.0f}% penalty)")

    # If we didn't print a penalty breakdown but model != final, show a net adjustment line.
    if abs(final_conf_pct - model_conf_pct) >= 0.6:
        delta = final_conf_pct - model_conf_pct
        lines.append(f"Adjustment: {model_conf_pct:.1f}% → {final_conf_pct:.1f}% ({delta:+.1f} pts)")
    
    # Line 6: Kelly metrics if available
    kelly = pick.get('kelly_metrics', {})
    if kelly:
        edge_pct = kelly.get('edge_pct', 0)
        kelly_bet = kelly.get('kelly_bet', 0) * 100
        if kelly_bet > 0:
            lines.append(f"Edge: {edge_pct:+.1f}% | Kelly stake: {kelly_bet:.1f}%")
    
    # Line 7: Tier label + engine decision from FINAL confidence (canonical thresholds)
    sport = pick.get("sport") or "NBA"
    tier_final, decision_final = _decision_from_final_confidence(final_conf_pct, sport=str(sport))
    if tier_final:
        lines.append(f"Tier: [{tier_final}]")
    if decision_final:
        lines.append(f"Engine decision: [{decision_final}]")
    
    return " | ".join(lines[:3]) + "\n" + " | ".join(lines[3:])


def generate_distributional_context(pick: dict) -> str:
    """
    Generate distributional context - historical patterns, NOT speculation.
    """
    mu = pick.get('mu', 0)
    sigma = pick.get('sigma', 2.0)
    line = pick.get('line', 0)
    sample_n = pick.get('sample_n', 0)
    prob_details = pick.get('prob_method_details', {})
    edge_diag = pick.get('edge_diagnostics', {})
    
    lines = []
    
    # Sample size context
    if sample_n > 0:
        lines.append(f"Based on {sample_n} games")
    
    # Empirical hit rate if available (already stored as percentage 0-100)
    emp_rate = prob_details.get('empirical_hit_rate')
    if emp_rate is not None:
        lines.append(f"Historical hit rate: {emp_rate:.0f}%")
    
    # Distribution spread
    cv = (sigma / mu * 100) if mu > 0 else 0
    if cv > 30:
        lines.append(f"High variance player (CV={cv:.0f}%)")
    elif cv > 20:
        lines.append(f"Moderate variance (CV={cv:.0f}%)")
    else:
        lines.append(f"Consistent performer (CV={cv:.0f}%)")
    
    return " | ".join(lines) if lines else ""


def generate_coaching_insight(pick: dict, game_context: dict = None) -> str:
    """
    DEPRECATED: Returns empty string.
    
    Previous version used LLM to speculate about coaching tendencies.
    This violates the math-only principle - coaching data should be 
    in the model's factors, not invented by an LLM.
    """
    return ""


def generate_block_reasoning(pick: dict) -> str:
    """
    Generate FACTUAL explanation for why a pick was blocked.
    
    Reports ONLY the gate that failed and the actual values.
    NO speculation about what "might" happen.
    """
    player = pick.get('player', 'Unknown')
    stat = pick.get('stat', '').upper()
    line = pick.get('line', 0)
    direction = str(pick.get('direction', '') or '').strip().lower()
    dir_label = "OVER" if direction == "higher" else "UNDER" if direction == "lower" else ""
    try:
        line_val = float(line)
    except Exception:
        line_val = None

    prop_suffix = ""
    if dir_label and line_val is not None:
        prop_suffix = f" {dir_label} {line_val:g}"
    elif dir_label:
        prop_suffix = f" {dir_label}"
    elif line_val is not None:
        prop_suffix = f" {line_val:g}"
    block_reason = pick.get('block_reason', 'Unknown')
    gate = pick.get('gate_failed', block_reason)
    
    # Map gate failures to factual explanations (no speculation)
    gate_lower = gate.lower() if gate else ''
    
    if "elite defense" in gate_lower or "elite_defense" in gate_lower:
        return f"[BLOCK] {player} {stat}{prop_suffix}: Elite defense gate - opponent in bottom-5 for allowing {stat.lower()}"
    
    elif "bench" in gate_lower:
        return f"[BLOCK] {player} {stat}{prop_suffix}: Bench gate - starter minutes not guaranteed"
    
    elif "blowout" in gate_lower:
        return f"[BLOCK] {player} {stat}{prop_suffix}: Blowout gate - game spread suggests reduced minutes risk"
    
    elif "role" in gate_lower:
        return f"[BLOCK] {player} {stat}{prop_suffix}: Role gate - historical usage doesn't support this stat"
    
    elif "banned" in gate_lower:
        return f"[BLOCK] {player} {stat}{prop_suffix}: Ban list - recent failures on this prop type"
    
    elif "composite" in gate_lower:
        return f"[BLOCK] {player} {stat}{prop_suffix}: Composite stat - multi-category fragility"
    
    elif "back-to-back" in gate_lower or "b2b" in gate_lower:
        return f"[BLOCK] {player} {stat}{prop_suffix}: B2B gate - second night of back-to-back"
    
    elif "injury" in gate_lower:
        return f"[BLOCK] {player} {stat}{prop_suffix}: Injury gate - player on injury report"
    
    elif "variance" in gate_lower or "cv" in gate_lower:
        return f"[BLOCK] {player} {stat}{prop_suffix}: Variance gate - stat too unpredictable"
    
    elif "ceiling" in gate_lower:
        return f"[BLOCK] {player} {stat}{prop_suffix}: Ceiling gate - upside insufficient for line"
    
    else:
        return f"[BLOCK] {player} {stat}{prop_suffix}: {block_reason}"


def generate_full_report(analysis_results: dict, game_context: dict = None) -> str:
    """Generate complete slate report with MATH-ONLY commentary.

    No LLM speculation - just computed values and factual context.
    """
    results = analysis_results.get('results', [])
    
    # Deduplicate results by (player, stat, line, direction)
    seen_keys = set()
    unique_results = []
    for r in results:
        key = (
            str(r.get('player', r.get('player_name', ''))).lower().strip(),
            str(r.get('stat', r.get('market', ''))).lower().strip(),
            float(r.get('line', 0)),
            str(r.get('direction', '')).lower().strip()
        )
        if key not in seen_keys:
            seen_keys.add(key)
            unique_results.append(r)
    results = unique_results
    
    # QUALIFIED = actionable tiers for humans (PLAY + STRONG) AFTER final-confidence normalization.
    # Also: hybrid VETO'd picks can never be qualified.
    decorated = []
    for r in results:
        sport = r.get("sport") or analysis_results.get("sport") or "NBA"
        final_conf = _pick_final_confidence_percent(r)
        model_conf = _pick_model_confidence_percent(r)
        veto = _is_hybrid_veto(r)
        tier_final, decision_final = _decision_from_final_confidence(final_conf, sport=str(sport))
        decorated.append(
            {
                "pick": r,
                "sport": str(sport),
                "final_conf": float(final_conf),
                "model_conf": float(model_conf),
                "hybrid_veto": bool(veto),
                "tier_final": tier_final,
                "decision_final": decision_final,
            }
        )

    qualified = [d for d in decorated if (not d["hybrid_veto"]) and d["decision_final"] in ("PLAY", "STRONG")]

    # BLOCKED sample: show engine-blocked picks only (avoid mixing NO_PLAY/VETO into a "BLOCKED" section).
    blocked_engine = [d for d in decorated if str(d["pick"].get("decision") or "").upper() == "BLOCKED"]

    # De-duplicate sample output by full prop identity so the sample doesn't look spammy.
    seen_block_keys = set()
    blocked_engine_unique = []
    for d in blocked_engine:
        p = d["pick"]
        try:
            k = (
                str(p.get('player', p.get('player_name', ''))).lower().strip(),
                str(p.get('stat', p.get('market', ''))).lower().strip(),
                float(p.get('line', 0) or 0),
            )
        except Exception:
            k = (id(p),)
        if k in seen_block_keys:
            continue
        seen_block_keys.add(k)
        blocked_engine_unique.append(p)

    blocked_sample_size = min(10, len(blocked_engine_unique))
    blocked_picks = blocked_engine_unique[:blocked_sample_size]
    
    # Reconciliation helpers for the common question: "why do counts differ?"
    total_props = int(analysis_results.get("total_props") or len(results) or 0)
    stat_meta = analysis_results.get("stat_ranking_meta")
    if not isinstance(stat_meta, dict):
        stat_meta = {}
    total_analyzed = stat_meta.get("total_analyzed")
    try:
        total_analyzed = int(total_analyzed) if total_analyzed is not None else None
    except Exception:
        total_analyzed = None

    veto_count = sum(1 for d in decorated if d.get("hybrid_veto"))
    play_noveto = sum(1 for d in decorated if (not d.get("hybrid_veto")) and d.get("decision_final") == "PLAY")
    strong_noveto = sum(1 for d in decorated if (not d.get("hybrid_veto")) and d.get("decision_final") == "STRONG")
    lean_noveto = sum(1 for d in decorated if (not d.get("hybrid_veto")) and d.get("decision_final") == "LEAN")

    raw_play = int(analysis_results.get("play") or 0)
    raw_strong = int(analysis_results.get("strong") or 0)
    raw_lean = int(analysis_results.get("lean") or 0)
    raw_blocked = int(analysis_results.get("blocked") or 0)

    report = []
    report.append("\n" + "="*80)
    report.append("RISK-FIRST ANALYSIS REPORT (Math-Only)")
    report.append("="*80 + "\n")

    # Quick reconciliation line so users don't have to mentally diff reports.
    if total_analyzed is not None and total_props:
        skipped = max(0, total_props - total_analyzed)
        report.append(f"Coverage: {total_analyzed}/{total_props} props with modelable stat windows ({skipped} skipped)\n")
    
    def _extract_role(pick: dict) -> str:
        # Prefer explicit field if present
        role = str(pick.get("role", "")).strip()
        if role:
            return role
        # Try to parse gate details (ROLE_MAP gate)
        try:
            gates = pick.get("gate_details") or []
            for g in gates:
                if str(g.get("gate", "")).upper() == "ROLE_MAP":
                    reason = str(g.get("reason", ""))
                    # e.g., "PASS: BIG → 'points' allowed"
                    # Extract token before the arrow
                    for token in ["PASS:", "FAIL:", "BLOCKED:"]:
                        if token in reason:
                            reason = reason.split(token, 1)[-1].strip()
                            break
                    # Role is the first word
                    role_token = reason.split(" ")[0].strip()
                    # Some upstream strings are warnings like "WARNING:"; don't treat them as roles.
                    if role_token.upper().startswith("WARNING"):
                        return "UNKNOWN"
                    return role_token
        except Exception:
            pass
        return "UNKNOWN"

    def _format_info_line(pick: dict) -> str:
        team = pick.get("team")
        opp = pick.get("opponent")
        away = pick.get("matchup_away") or pick.get("away_team")
        home = pick.get("matchup_home") or pick.get("home_team")
        role = _extract_role(pick)
        minutes_cv = pick.get("minutes_cv")
        # Rough bucket for volatility
        if isinstance(minutes_cv, (int, float)):
            if minutes_cv >= 0.35:
                minutes_band = "HIGH VAR"
            elif minutes_cv >= 0.2:
                minutes_band = "MED VAR"
            elif minutes_cv > 0:
                minutes_band = "LOW VAR"
            else:
                minutes_band = "UNKNOWN"
        else:
            minutes_band = "UNKNOWN"

        ctx_notes = []
        for k in ("situation_notes", "context_notes"):
            vals = pick.get(k)
            if isinstance(vals, list):
                for v in vals:
                    vstr = str(v).strip()
                    if vstr and vstr not in ctx_notes:
                        ctx_notes.append(vstr)

        injury_verified = pick.get("injury_verified")
        sources = pick.get("data_sources")
        src_str = ",".join(sources) if isinstance(sources, list) else ""
        inj_str = "YES" if injury_verified else ("NO" if injury_verified is False else "UNKNOWN")

        parts = []
        # Prefer team/opponent when known; otherwise fall back to matchup home/away if present.
        team_norm = str(team or "").strip().upper()
        opp_norm = str(opp or "").strip().upper()
        if (team_norm and team_norm != "UNK") or (opp_norm and opp_norm != "UNK"):
            parts.append(f"{team or 'UNK'} vs {opp or 'UNK'}")
        else:
            if away or home:
                parts.append(f"{away or 'UNK'} @ {home or 'UNK'}")
        # Tennis fallback: use player vs opponent when no team context is available.
        if not parts:
            sport = str(pick.get("sport") or "").upper()
            if sport == "TENNIS":
                p_name = pick.get("player") or pick.get("player_name")
                opp_name = pick.get("opponent")
                if p_name or opp_name:
                    parts.append(f"{p_name or 'UNK'} vs {opp_name or 'UNK'}")
        if role and role != "UNKNOWN":
            parts.append(f"role={role}")
        if minutes_band and minutes_band != "UNKNOWN":
            parts.append(f"minutes={minutes_band}")
        if ctx_notes:
            parts.append(" | ".join(ctx_notes))
        if inj_str != "UNKNOWN":
            parts.append(f"injury_verified={inj_str}")
        if src_str:
            parts.append(f"sources={src_str}")
        return "INFO: " + ("; ".join(parts) if parts else "(no additional context)")

    # QUALIFIED PICKS with math-only commentary
    if qualified:
        report.append(f"✅ QUALIFIED PICKS ({len(qualified)})\n")
        report.append("="*80 + "\n")
        
        for i, d in enumerate(qualified, 1):
            pick = d["pick"]
            player = pick.get('player', 'Unknown')
            stat = pick.get('stat', '').upper()
            direction = pick.get('direction', 'higher').upper()
            line = pick.get('line', 0)
            edge = pick.get('edge', 0)
            z_score = pick.get('z_score', 0)
            edge_quality = pick.get('edge_quality', 'UNKNOWN')
            confidence = d["final_conf"]
            mu = pick.get('mu', 0)
            sigma = pick.get('sigma', 2.0)
            
            report.append(f"#{i} | {player} - {stat} {direction} {line}")
            report.append(f"Edge: {edge:+.1f} ({z_score:+.2f} sd) {edge_quality} | Confidence: {confidence:.1f}%")
            report.append(f"Stats: μ={mu:.1f}, σ={sigma:.1f}\n")
            
            # Math-only commentary (no LLM)
            commentary = generate_pick_commentary(pick, game_context)
            report.append(f"ANALYSIS:\n{commentary}\n")
            # Context info line
            report.append(_format_info_line(pick) + "\n")
            
            # Distributional context
            dist_ctx = generate_distributional_context(pick)
            if dist_ctx:
                report.append(f"CONTEXT: [{dist_ctx}]\n")
            
            report.append("-" * 80 + "\n")
    
    # BLOCKED PICKS with factual explanations
    if blocked_picks:
        total_blocked = analysis_results.get('blocked', len(blocked_engine))
        report.append(f"\n❌ BLOCKED PICKS (showing {len(blocked_picks)} of {total_blocked})\n")
        report.append("="*80 + "\n")
        
        for pick in blocked_picks:
            explanation = generate_block_reasoning(pick)
            report.append(explanation)
            # Context info line for blocked picks as well
            report.append(_format_info_line(pick))
            report.append("")
    
    report.append("="*80)
    report.append(
        f"SUMMARY (post-veto tiers): {play_noveto} PLAY | {strong_noveto} STRONG | {lean_noveto} LEAN | {raw_blocked} BLOCKED | {veto_count} VETO"
    )
    report.append(
        f"SUMMARY (raw analyzer counters): {raw_play} PLAY | {raw_strong} STRONG | {raw_lean} LEAN | {raw_blocked} BLOCKED"
    )
    report.append("Commentary: Math-only (no LLM speculation)")
    report.append("="*80)

    return "\n".join(report)


def generate_top20_report(analysis_results: dict, game_context: dict = None, top_n: int = 20) -> str:
    """Generate a MATH-ONLY report focused on the top-N highest-confidence picks.

    This is a thin wrapper around :func:`generate_full_report` that filters the
    input ``results`` down to the top ``top_n`` entries by final confidence
    (after penalties / governance), then delegates to the standard reporter.
    """
    try:
        results = list(analysis_results.get("results", []))
    except Exception:
        results = []

    if not results or top_n <= 0:
        return generate_full_report(analysis_results, game_context=game_context)

    # Sort by final confidence (post-penalty) and keep top N
    scored = []
    for r in results:
        try:
            conf = _pick_final_confidence_percent(r)
        except Exception:
            conf = 0.0
        scored.append((conf, r))

    scored.sort(key=lambda t: t[0], reverse=True)
    top_results = [r for _, r in scored[:top_n]]

    trimmed = dict(analysis_results)
    trimmed["results"] = top_results
    return generate_full_report(trimmed, game_context=game_context)
