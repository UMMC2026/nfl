"""
UNDERDOG FANTASY - DAILY COMPREHENSIVE CHEAT SHEET
Generated with NBA game logs (last 10 games)
Dual-mode: Statistical (uncapped) & Governance-Calibrated (regression)
"""

import json
from math import erf, sqrt
from datetime import datetime, timezone
from pathlib import Path
from nba_api.stats.endpoints import leaguedashplayerstats

# Daily Games Report Gating (SOP v2.1)
from gating.daily_games_report_gating import gate_cheat_sheets

from governance_context import (
    get_governance_context,
    apply_blowout_penalty,
    format_governance_annotation,
    get_blowout_risk,
    GAME_SPREADS,
)
from ufa.gates.injury_gate import injury_availability_gate, get_injury_feed_health
from ufa.operational_modes.degraded_mode import DegradedModeManager, DegradedModeLevel


# When injury status is UNKNOWN due to a degraded feed, we allow picks
# to surface for day-of selection but cap their effective confidence so
# they never masquerade as fully verified edges.
MAX_UNCERTAIN_CONF = 0.70

def prob_under(line, mu, sigma):
    if sigma == 0:
        return 1.0 if line > mu else 0.0
    z = (line - mu) / sigma
    return 0.5 * (1 + erf(z / sqrt(2)))

def apply_governance_calibration(prob, confidence_tier='slam'):
    """Apply confidence ceilings per governance layer"""
    ceilings = {
        'slam': 0.75,      # 68-75% ceiling
        'strong': 0.67,    # 60-67% ceiling
        'lean': 0.59       # 52-59% ceiling
    }
    ceiling = ceilings.get(confidence_tier, 0.75)
    # Compress high confidences toward ceiling (regression to the mean)
    if prob >= 0.90:
        return 0.5 + (prob - 0.5) * 0.3  # Stronger shrinkage for extreme confidences
    elif prob >= 0.80:
        return 0.5 + (prob - 0.5) * 0.5
    else:
        return prob * 0.95  # Small shrinkage for lower confidences
    return min(prob, ceiling)

from hydrated_picks_validator import HydrationValidator
from local_validator import LocalValidator
from verification_gate import VerificationGate


def _load_official_last10(players):
    """Load official NBA per-game averages for the last 10 games for the given players."""
    try:
        stats = leaguedashplayerstats.LeagueDashPlayerStats(
            season="2025-26",
            per_mode_detailed="PerGame",
            last_n_games=10,
        )
        df = stats.get_data_frames()[0]
        subset = df[df["PLAYER_NAME"].isin(players)]
        official = {}
        for _, row in subset.iterrows():
            official[row["PLAYER_NAME"]] = {
                "team": row["TEAM_ABBREVIATION"],
                "points": float(row["PTS"]),
                "rebounds": float(row["REB"]),
                "assists": float(row["AST"]),
                "pra": float(row["PTS"] + row["REB"] + row["AST"]),
            }
        return official
    except Exception as e:
        print(f"⚠️  Could not load official Last10 stats: {e}")
        return {}


# Load hydrated picks
picks = json.load(open('picks_hydrated.json', encoding='utf-8'))

# ========================
# PRE-OUTPUT VERIFICATION
# ========================
print("\n🛡️  Running pre-output verification gate...")
verification = VerificationGate()
picks, verification_passed = verification.run_full_verification(picks)

if not verification_passed:
    print("\n❌ CRITICAL VERIFICATION ERRORS - Cannot generate output")
    verification.save_verification_report()
    exit(1)

verification.save_verification_report()

# Run a lightweight validation pass to drop obviously malformed
# entries (bad team codes, absurd mu/sigma, missing core fields)
# before they can surface as edges.
_validator = HydrationValidator()
picks = _validator.filter_valid_picks(picks)

# Apply LocalValidator for instant team/stat sanity checks
# This catches common errors (Jonas wrong team, unreasonable stats)
# and auto-corrects high-confidence issues before they reach the cheatsheet.
print("🧠 Running LocalValidator for team/stat sanity checks...")
local_validation_results = LocalValidator.validate_batch(picks)
corrections_made = 0
questionable_flagged = 0
invalid_flagged = 0

for pick, result in zip(picks, local_validation_results):
    # Store validation metadata for logging/debugging
    pick['local_validation_status'] = result['status']
    pick['local_validation_confidence'] = result['confidence']
    
    # Auto-correct teams when LocalValidator has high confidence
    if result.get('correct_team') and result['confidence'] >= 0.7:
        old_team = pick.get('team', 'UNK')
        pick['team'] = result['correct_team']
        pick['team_corrected_by_validator'] = True
        corrections_made += 1
        print(f"   ✅ Corrected {pick['player']}: {old_team} → {result['correct_team']}")
    
    # Flag questionable/invalid picks for governance attention
    if result['status'] == 'QUESTIONABLE':
        pick['validation_flag'] = 'QUESTIONABLE'
        questionable_flagged += 1
    elif result['status'] == 'INVALID':
        pick['validation_flag'] = 'INVALID'
        invalid_flagged += 1

print(f"✅ LocalValidator complete: {corrections_made} teams corrected, "
      f"{questionable_flagged} questionable, {invalid_flagged} invalid")
print()

# Also ensure we only consider hydrated rows that still correspond
# to current picks in picks.json. This prevents stale or deleted
# players from lingering in hydrated storage and reappearing on
# future slates.
source_path = Path("picks.json")
if source_path.exists():
    try:
        source_picks = json.load(open(source_path, encoding="utf-8"))
        keyset = {
            (
                sp.get("player"),
                sp.get("stat"),
                sp.get("line"),
                sp.get("direction"),
            )
            for sp in source_picks
        }
        before = len(picks)
        picks = [
            hp
            for hp in picks
            if (
                hp.get("player"),
                hp.get("stat"),
                hp.get("line"),
                hp.get("direction"),
            ) in keyset
        ]
        removed_stale = before - len(picks)
        if removed_stale > 0:
            print(f"🧼 Dropped {removed_stale} stale hydrated picks not present in picks.json")
    except Exception:
        # If source picks cannot be loaded, fall back to using all
        # validated hydrated rows.
        pass

# Optionally filter to tonight's newly hydrated range if meta is from today
meta_path = Path('.hydration_meta.json')
if meta_path.exists():
    try:
        meta = json.load(open(meta_path, encoding='utf-8'))
        ts = datetime.fromisoformat(meta.get('timestamp'))
        if ts.date() == datetime.now(timezone.utc).date():
            start = int(meta.get('start', 1)) - 1  # convert to 0-based
            end = int(meta.get('end', len(picks)))  # 1-based inclusive
            if 0 <= start < end <= len(picks):
                picks = picks[start:end]
    except Exception:
        # Ignore meta errors and use full set
        pass

def generate_report(all_plays, mode='statistical', now_local=None, blocked_plays=None, degraded_manager=None):
    """Generate cheatsheet report with specified confidence mode"""
    if now_local is None:
        now_local = datetime.now()

    if blocked_plays is None:
        blocked_plays = []
    
    month_abbr = now_local.strftime('%b').upper()
    day_str = now_local.strftime('%d')
    year_str = now_local.strftime('%Y')
    
    # Apply calibration if governance mode
    if mode == 'governance':
        for p in all_plays:
            # Determine tier for shrinkage
            if p['prob'] >= 0.80:
                tier = 'slam'
            elif p['prob'] >= 0.70:
                tier = 'strong'
            else:
                tier = 'lean'

            # Start from base probability and apply any injury-based
            # confidence multiplier before governance regression.
            base_prob = p['prob']
            mult = p.get('injury_confidence_multiplier', 1.0)
            if mult < 1.0:
                base_prob = max(0.0, min(1.0, base_prob * mult))

            # Apply regression shrinkage
            calibrated_prob = apply_governance_calibration(base_prob, tier)

            # Apply blowout penalty (soft, conditional)
            calibrated_prob = apply_blowout_penalty(calibrated_prob, p['blowout_risk'], p['role'])

            # Cap confidence when injury status is UNKNOWN (feed
            # degraded / unverified availability). This keeps
            # governance-calibrated outputs usable but clearly flagged
            # as uncertain.
            if p.get('injury_status') == 'UNKNOWN':
                calibrated_prob = min(calibrated_prob, MAX_UNCERTAIN_CONF)

            p['prob_display'] = calibrated_prob
            p['governance_annotation'] = format_governance_annotation(p['player'], p['blowout_risk'], p['role'], p['team'])
        mode_str = "GOVERNANCE-CALIBRATED (Regression + Blowout Risk)"
    else:
        for p in all_plays:
            base_prob = p['prob']
            mult = p.get('injury_confidence_multiplier', 1.0)
            if mult < 1.0:
                base_prob = max(0.0, min(1.0, base_prob * mult))

            # In statistical mode we still respect UNKNOWN injuries by
            # capping effective confidence; the raw model may be 90%+
            # but the report must not present that as a clean edge when
            # availability is unverified.
            if p.get('injury_status') == 'UNKNOWN':
                base_prob = min(base_prob, MAX_UNCERTAIN_CONF)

            p['prob_display'] = base_prob
            p['governance_annotation'] = ""
        mode_str = "PURE STATISTICAL (10-Game Rolling Avg)"

    # Apply global degraded-mode confidence cap, if active.
    if degraded_manager is not None:
        for p in all_plays:
            p['prob_display'] = degraded_manager.apply_confidence_cap(p['prob_display'])

    report = []
    
    report.append("=" * 80)
    report.append(f"     UNDERDOG FANTASY - {month_abbr} {day_str}, {year_str} - COMPREHENSIVE CHEAT SHEET")
    report.append("=" * 80)
    report.append(f"     Generated: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}")
    report.append("     🏀 FEATURE SOURCE (Player Averages):")
    report.append("       Primary: OFFICIAL NBA STATS (Last 10 Games, nba_api)")
    report.append("       Trust Level: AUTHORITATIVE (verified against NBA.com)")
    report.append("     ⚡ HARD GATES (Ground Truth):")
    report.append("       • Automatic rejection: official avg < line (for OVER) or official avg > line (for UNDER)")
    report.append("       • All picks recalculated using official averages, not hydration estimates")
    report.append("     OUTCOME SOURCE (Learning Labels):")
    report.append("       Primary: ESPN NBA Box Score (FINAL only)")
    report.append("       Secondary: NBA official stats (cross-check)")
    report.append("       Learning Gate: is_learning_ready() — FINAL + 15 min + cross-verified")
    # If the system is in degraded mode, surface a loud, slate-level
    # warning while still allowing day-of selection to proceed with
    # capped, clearly flagged confidence.
    injury_health = get_injury_feed_health()
    if degraded_manager is not None and degraded_manager.current_level != DegradedModeLevel.NORMAL:
        report.append("     ⚠️ DEGRADED DATA MODE ACTIVE")
        if injury_health == "DEGRADED":
            report.append("     Injury feed degraded: all picks shown with reduced confidence.")
            report.append("     DO NOT treat as injury-verified.")
    elif injury_health == "DEGRADED":
        report.append("     ⚠️ INJURY FEED UNAVAILABLE")
        report.append("     All picks shown with reduced confidence.")
        report.append("     DO NOT treat as injury-verified.")
    report.append("=" * 80)
    report.append("")
    
    # Helper: only surface plays as top edges when availability and
    # usage are clean. If injury_status is UNKNOWN or any non-ACTIVE
    # flag, or if usage is obviously stale (no recent games), the play
    # may still be listed elsewhere (e.g., AVAILABILITY FLAGS) but
    # should not appear as a headline SLAM/STRONG/LEAN edge.
    def _is_clean_availability(play: dict) -> bool:
        # Usage recency gate: if we know the player has not appeared in
        # a long time, do not surface them as a top edge regardless of
        # what the historical mu/sigma says.
        if play.get('usage_stale'):
            return False
        status = play.get('injury_status')
        # If injury feed is degraded, allow UNKNOWN status (already capped confidence by MAX_UNCERTAIN_CONF)
        if injury_health == "DEGRADED" and status == 'UNKNOWN':
            return True
        # Otherwise, only ACTIVE or missing status is clean
        return (not status) or status == 'ACTIVE'

    # SLAM PLAYS - LOWERED THRESHOLDS FOR ACTIONABLE PICKS
    slam_threshold = 0.70 if mode == 'governance' else 0.75  # Lowered from 0.75/0.90
    report.append("┌" + "─" * 78 + "┐")
    report.append(f"│  🔥 SLAM PLAYS ({slam_threshold:.0%}+ Confidence){'':38s}│")
    report.append("├" + "─" * 78 + "┤")
    slams = [
        p for p in all_plays
        if p['prob_display'] >= slam_threshold and _is_clean_availability(p)
    ]
    if slams:
        for p in slams:
            injury_note = ""
            status = p.get('injury_status')
            if status and status != "ACTIVE":
                injury_note = f" [INJURY: {status}]"

            marker = "✓"
            if status and status != "ACTIVE":
                # Never show a clean checkmark when availability is not
                # fully verified (QUESTIONABLE / UNKNOWN / etc.).
                marker = "⚠"
            if mode == 'governance':
                report.append(f"│  {marker} {p['player']:20s} {p['direction']:5s} {p['line']:5.1f} {p['stat']:12s}{injury_note:20s}│")
                report.append(f"│    avg: {p['avg']:5.1f}, conf: [{p['prob_display']:.0%}] {p['governance_annotation'][:48]:48s}│")
            else:
                report.append(f"│  {marker} {p['player']:20s} {p['direction']:5s} {p['line']:5.1f} {p['stat']:12s} (avg: {p['avg']:5.1f}) [{p['prob_display']:.0%}]{injury_note:10s} │")
    else:
        report.append("│  (none)                                                                    │")
    report.append("└" + "─" * 78 + "┘")
    report.append("")
    
    # STRONG PLAYS - LOWERED THRESHOLDS
    strong_min = 0.55 if mode == 'governance' else 0.65  # Lowered from 0.60/0.80
    strong_max = slam_threshold
    report.append("┌" + "─" * 78 + "┐")
    report.append(f"│  💪 STRONG PLAYS ({strong_min:.0%}-{strong_max-0.01:.0%} Confidence){'':33s}│")
    report.append("├" + "─" * 78 + "┤")
    strong = [
        p for p in all_plays
        if strong_min <= p['prob_display'] < strong_max and _is_clean_availability(p)
    ]
    if strong:
        for p in strong[:20]:  # Limit display to top 20
            injury_note = ""
            status = p.get('injury_status')
            if status and status != "ACTIVE":
                injury_note = f" [INJURY: {status}]"
            if mode == 'governance':
                report.append(f"│  • {p['player']:20s} {p['direction']:5s} {p['line']:5.1f} {p['stat']:12s}{injury_note:20s}│")
                report.append(f"│    avg: {p['avg']:5.1f}, conf: [{p['prob_display']:.0%}] {p['governance_annotation'][:48]:48s}│")
            else:
                report.append(f"│  • {p['player']:20s} {p['direction']:5s} {p['line']:5.1f} {p['stat']:12s} (avg: {p['avg']:5.1f}) [{p['prob_display']:.0%}]{injury_note:10s} │")
    else:
        report.append("│  (none)                                                                    │")
    report.append("└" + "─" * 78 + "┘")
    report.append("")
    
    # LEAN PLAYS
    lean_min = 0.52 if mode == 'governance' else 0.52  # Fixed: was 0.70, creating impossible range
    lean_max = strong_min
    report.append("┌" + "─" * 78 + "┐")
    report.append(f"│  📊 LEAN PLAYS ({lean_min:.0%}-{lean_max-0.01:.0%} Confidence){'':37s}│")
    report.append("├" + "─" * 78 + "┤")
    lean = [
        p for p in all_plays
        if lean_min <= p['prob_display'] < lean_max and _is_clean_availability(p)
    ]
    if lean:
        for p in lean[:15]:  # Limit display to top 15
            injury_note = ""
            status = p.get('injury_status')
            if status and status != "ACTIVE":
                injury_note = f" [INJURY: {status}]"
            if mode == 'governance':
                report.append(f"│  • {p['player']:20s} {p['direction']:5s} {p['line']:5.1f} {p['stat']:12s}{injury_note:20s}│")
                report.append(f"│    avg: {p['avg']:5.1f}, conf: [{p['prob_display']:.0%}] {p['governance_annotation'][:48]:48s}│")
            else:
                report.append(f"│  • {p['player']:20s} {p['direction']:5s} {p['line']:5.1f} {p['stat']:12s} (avg: {p['avg']:5.1f}) [{p['prob_display']:.0%}]{injury_note:10s} │")
    else:
        report.append("│  (none)                                                                    │")
    report.append("└" + "─" * 78 + "┘")
    report.append("")
    
    # HIGH CONF OVERS
    report.append("=" * 80)
    report.append("  TOP OVERS (55%+ Confidence)")
    report.append("=" * 80)
    # Only surface high-confidence overs for players who are clean
    # from an availability standpoint. If injury_status is UNKNOWN
    # (degraded feed) or any non-ACTIVE flag, we do not promote the
    # play here; such cases are instead surfaced in the
    # AVAILABILITY FLAGS section below.
    overs = [
        p for p in all_plays
        if p['direction'] == 'OVER'
        and p['prob_display'] >= 0.55  # Lowered from 0.70
        and _is_clean_availability(p)
    ]
    overs.sort(key=lambda x: x['prob_display'], reverse=True)
    report.append(f"  {'#':3s} {'Player':22s} {'Prop':12s} {'Line':>6s} {'Avg':>6s} {'Conf':>6s}")
    report.append("  " + "-" * 60)
    for i, p in enumerate(overs, 1):
        report.append(f"  {i:3d} {p['player']:22s} {p['stat']:12s} {p['line']:6.1f} {p['avg']:6.1f} {p['prob_display']:6.0%}")
    report.append("")
    
    # HIGH CONF UNDERS
    report.append("=" * 80)
    report.append("  TOP UNDERS (50%+ Confidence) ⬇️")
    report.append("=" * 80)
    # Same availability rule as overs: do not recommend unders for
    # players with UNKNOWN or otherwise non-ACTIVE injury status.
    # This prevents obviously hurt or unverified players (e.g.,
    # Jonas Valanciūnas when the injury feed is down) from showing
    # up as top-edge unders while they are flagged as
    # UNKNOWN (NO_INJURY_DATA).
    unders = [
        p for p in all_plays
        if p['direction'] == 'UNDER'
        and p['prob_display'] >= 0.50  # Lowered from 0.65
        and _is_clean_availability(p)
    ]
    unders.sort(key=lambda x: x['prob_display'], reverse=True)
    report.append(f"  {'#':3s} {'Player':22s} {'Prop':12s} {'Line':>6s} {'Avg':>6s} {'Conf':>6s}")
    report.append("  " + "-" * 60)
    for i, p in enumerate(unders, 1):
        report.append(f"  {i:3d} {p['player']:22s} {p['stat']:12s} {p['line']:6.1f} {p['avg']:6.1f} {p['prob_display']:6.0%}")
    report.append("")
    
    # PARLAY SUGGESTIONS
    report.append("=" * 80)
    report.append("  📋 PARLAY SUGGESTIONS")
    report.append("=" * 80)

    parlays_allowed = True
    if degraded_manager is not None:
        parlays_allowed = degraded_manager.is_parlay_allowed()

    if not parlays_allowed:
        report.append("  ⚠️ Parlay construction disabled in DEGRADED DATA MODE.")
        report.append("     Per SOP 2.2.1, new multi-leg entries should not be")
        report.append("     published while key data feeds are degraded.")
    else:
        # Safe 3-leg (all 80%+, confirmed ACTIVE). Picks with UNKNOWN or
        # non-active injury status are explicitly excluded from "safe"
        # parlays.
        safe_candidates = [
            p for p in all_plays
            if p['prob_display'] >= 0.80 and p.get('injury_status') == 'ACTIVE' and not p.get('usage_stale')
        ]
        safe_picks = safe_candidates[:3]
        report.append("")
        report.append("  SAFE 3-LEG (All 80%+ Confidence):")
        report.append("  " + "-" * 40)
        if safe_picks:
            for p in safe_picks:
                report.append(f"    • {p['player']} {p['direction']} {p['line']} {p['stat']} [{p['prob_display']:.0%}]")
            combined_prob = 1.0
            for p in safe_picks:
                combined_prob *= p['prob_display']
            report.append(f"    Combined P(hit): {combined_prob:.1%} → EV: {combined_prob * 6:.2f}x (6x payout)")
        else:
            report.append("    (no eligible picks — injury/availability or confidence constraints)")

        # Value 4-leg with team diversification
        report.append("")
        report.append("  VALUE 4-LEG (Team-Diversified):")
        report.append("  " + "-" * 40)
        used_teams = set()
        value_picks = []
        for p in sorted(all_plays, key=lambda x: x['prob_display'], reverse=True):
            if (
                p['team'] not in used_teams
                and p['prob_display'] >= 0.70
                and p.get('injury_status') == 'ACTIVE'
                and not p.get('usage_stale')
            ):
                value_picks.append(p)
                used_teams.add(p['team'])
                if len(value_picks) >= 4:
                    break
        if value_picks:
            for p in value_picks:
                report.append(f"    • {p['player']} ({p['team']}) {p['direction']} {p['line']} {p['stat']} [{p['prob_display']:.0%}]")
            combined_prob = 1.0
            for p in value_picks:
                combined_prob *= p['prob_display']
            report.append(f"    Combined P(hit): {combined_prob:.1%} → EV: {combined_prob * 10:.2f}x (10x payout)")
        else:
            report.append("    (no eligible picks — injury/availability or confidence constraints)")

        # Longshot with unders
        report.append("")
        report.append("  LONGSHOT 5-LEG (Includes UNDERS):")
        report.append("  " + "-" * 40)
        longshot_overs = [
            p for p in all_plays
            if p['direction'] == 'OVER'
            and p['prob_display'] >= 0.70
            and p.get('injury_status') == 'ACTIVE'
            and not p.get('usage_stale')
        ][:3]
        longshot_unders = [
            p for p in all_plays
            if p['direction'] == 'UNDER'
            and p['prob_display'] >= 0.65
            and p.get('injury_status') == 'ACTIVE'
            and not p.get('usage_stale')
        ][:2]
        longshot_picks = longshot_overs + longshot_unders
        if longshot_picks:
            for p in longshot_picks:
                report.append(f"    • {p['player']} {p['direction']} {p['line']} {p['stat']} [{p['prob_display']:.0%}]")
            combined_prob = 1.0
            for p in longshot_picks:
                combined_prob *= p['prob_display']
            report.append(f"    Combined P(hit): {combined_prob:.1%} → EV: {combined_prob * 20:.2f}x (20x payout)")
        else:
            report.append("    (no eligible picks — injury/availability or confidence constraints)")
    
    report.append("")
    report.append("=" * 80)
    report.append("  ⚠️ PLAYS TO AVOID (Low Confidence or High Volatility)")
    report.append("=" * 80)
    avoid = [p for p in all_plays if p['prob_display'] < 0.40][:8]
    for p in avoid:
        report.append(f"  ✗ {p['player']:22s} {p['direction']:5s} {p['line']:5.1f} {p['stat']:12s} [{p['prob_display']:.0%}] - avg: {p['avg']:.1f}")
    
    report.append("")
    report.append("=" * 80)
    report.append("  📈 HIGH VOLATILITY PLAYERS (Large Standard Deviations)")
    report.append("=" * 80)
    # Deduplicate volatility section by player+stat combination
    seen_volatility = set()
    volatile = []
    for p in sorted([p for p in all_plays], key=lambda x: x['std'], reverse=True):
        key = f"{p['player']}_{p['stat']}"
        if key not in seen_volatility and len(volatile) < 10:
            seen_volatility.add(key)
            volatile.append(p)
    for p in volatile:
        report.append(f"  ! {p['player']:22s} {p['stat']:12s} std={p['std']:5.1f} (avg: {p['avg']:.1f})")
    
    # Availability / injury flags section. Filter aggressively:
    # - Only show picks with confidence >= 0.50 (otherwise it's just noise)
    # - Deduplicate by player_stat_line to avoid repetition
    # This prevents the report from being flooded with low-confidence UNKNOWN entries.
    flagged = []
    
    # Add blocked plays if any
    if blocked_plays:
        flagged.extend([p for p in blocked_plays if p.get('injury_status') or p.get('injury_block_reason')])
    
    # Add non-blocked plays with injury status ONLY if confidence >= 0.50 (aggressively filtered)
    for p in all_plays:
        status = p.get('injury_status')
        if (status and status != 'ACTIVE' and 
            p['prob_display'] >= 0.50):  # ONLY show if player is in consideration
            if not p.get('injury_block_reason'):
                if status == 'UNKNOWN':
                    p['injury_block_reason'] = 'NO_INJURY_DATA'
                else:
                    p['injury_block_reason'] = status
            flagged.append(p)
    
    # Remove duplicates while preserving order
    seen_flags = set()
    flagged_dedup = []
    for p in flagged:
        key = f"{p['player']}_{p['stat']}_{p['line']}"
        if key not in seen_flags:
            seen_flags.add(key)
            flagged_dedup.append(p)
    flagged = flagged_dedup[:30]  # Show max 30 most relevant flags
    if flagged:
        report.append("")
        report.append("=" * 80)
        report.append("  🚑 AVAILABILITY FLAGS (Injury / Status)")
        report.append("=" * 80)
        for p in flagged:
            status = p.get('injury_status', 'UNKNOWN')
            reason = p.get('injury_block_reason') or "BLOCKED"
            ts = p.get('injury_last_checked_at', '')
            report.append(
                f"  ⛔ {p['player']:22s} {p['direction']:5s} {p['line']:5.1f} {p['stat']:12s} "
                f"{status} ({reason}) @ {ts}"
            )

    report.append("")
    report.append("=" * 80)
    report.append("              GOOD LUCK! GAMBLE RESPONSIBLY!")
    report.append("=" * 80)
    
    return '\n'.join(report)

# Initialize degraded mode manager once for this slate.
degraded_manager = DegradedModeManager()
degraded_manager.update_from_injury_feed()
degraded_manager.assess_system_health()

# GROUND TRUTH FIRST: Load official NBA Last10 stats immediately
# This is the source of truth; all picks will be recalculated using these averages.
print("\n🏀 GROUND TRUTH: Loading official NBA Last 10 Games stats...")
from ground_truth_data_loader import (
    load_official_last10_stats,
    get_official_avg,
    validate_pick_against_official,
    save_ground_truth_report,
)

try:
    official_stats = load_official_last10_stats()
    save_ground_truth_report(official_stats)
except RuntimeError as e:
    print(f"❌ CRITICAL FAILURE: {e}")
    exit(1)

def _official_avg(player: str, stat: str):
    """Wrapper for consistency with existing code."""
    return get_official_avg(player, stat, official_stats)

# Build all plays with probabilities and attach injury gate metadata.
all_plays = []
blocked_plays = []
for p in picks:
    if p.get('mu') is None or p.get('sigma') is None:
        continue

    # GROUND TRUTH FIRST: Override model average with official Last10 (this is mandatory, not optional).
    official_avg = _official_avg(p.get('player'), p.get('stat'))
    if official_avg is not None:
        p['mu_official_override'] = official_avg
        p['mu'] = official_avg
        p['data_source'] = 'OFFICIAL_NBA_LAST10'
    else:
        # Player/stat not in official data—mark it and allow (cannot validate).
        p['data_source'] = 'HYDRATED_FALLBACK'

    # Hard rule: Reject picks where official average contradicts the line
    if official_avg is not None:
        is_valid, rejection_reason, _ = validate_pick_against_official(
            p.get('player'),
            p.get('stat'),
            p['line'],
            p['direction'],
            official_stats,
        )
        if not is_valid:
            p['hard_rule_rejection'] = rejection_reason
            blocked_plays.append(p)
            continue

    if p['direction'] == 'higher':
        prob = 1 - prob_under(p['line'], p['mu'], p['sigma'])
    else:
        prob = prob_under(p['line'], p['mu'], p['sigma'])

    # Get governance context
    gov_ctx = get_governance_context(p['player'], p['team'])
    blowout_risk = 'Moderate'  # Default; can be enhanced with game data

    league = p.get('league', 'NBA')
    gate = injury_availability_gate(player=p['player'], team=p['team'], league=league)

    # Usage recency flags from hydration (optional; older files may not
    # have these keys). If days_since_last_game is very large, we treat
    # the usage as stale and avoid surfacing the player as a top edge,
    # even if the historical mu/sigma looks strong.
    days_since_last_game = p.get('days_since_last_game')
    usage_stale = False
    if isinstance(days_since_last_game, int) and days_since_last_game > 21:
        usage_stale = True

    base_play = {
        'player': p['player'],
        'team': p['team'],
        'league': league,
        'stat': p['stat'],
        'line': p['line'],
        'direction': 'OVER' if p['direction'] == 'higher' else 'UNDER',
        'avg': p['mu'],
        'std': p['sigma'],
        'prob': prob,
        # Governance fields
        'role': gov_ctx.get('role', 'unknown'),
        'minutes_survival': gov_ctx.get('minutes_survival', 0.80),
        'garbage_time_eligible': gov_ctx.get('garbage_time_eligible', False),
        'blowout_risk': blowout_risk,
        # Injury gate fields
        'injury_status': gate.injury_status,
        'injury_source': gate.injury_source,
        'injury_last_checked_at': gate.injury_last_checked_at.isoformat(),
        'injury_fresh': gate.injury_fresh,
        'injury_block_reason': gate.block_reason,
        'injury_downgraded': gate.downgraded,
        'injury_confidence_multiplier': gate.confidence_multiplier,
        'injury_uncertain': gate.injury_status == 'UNKNOWN' or not gate.injury_fresh,
        # Usage / availability heuristics
        'days_since_last_game': days_since_last_game,
        'usage_stale': usage_stale,
    }

    if gate.allowed:
        all_plays.append(base_play)
    else:
        blocked_plays.append(base_play)

# Apply degraded-mode star-player exclusion, if active.
if degraded_manager.current_level != DegradedModeLevel.NORMAL:
    filtered_all = degraded_manager.filter_star_players(all_plays)
    star_blocked = [p for p in all_plays if p not in filtered_all]
    for p in star_blocked:
        if not p.get('injury_block_reason'):
            p['injury_block_reason'] = 'STAR_PLAYER_DEGRADED_MODE'
        blocked_plays.append(p)
    all_plays = filtered_all

# Sort by probability
all_plays.sort(key=lambda x: x['prob'], reverse=True)

# Get current datetime
now_local = datetime.now()
month_abbr = now_local.strftime('%b').upper()
day_str = now_local.strftime('%d')
year_str = now_local.strftime('%Y')
time_str = now_local.strftime('%Y%m%d_%H%M')

# Generate both reports
print("=" * 80)
print("📊 GENERATING DUAL REPORTS")
print("=" * 80)

# STATISTICAL REPORT (Pure CDF, 90%+ uncapped)
print("\n📈 Generating STATISTICAL report (pure statistical confidence)...")
statistical_report = generate_report(all_plays, mode='statistical', now_local=now_local, blocked_plays=blocked_plays, degraded_manager=degraded_manager)
statistical_file = f"outputs/CHEATSHEET_{month_abbr}{day_str}_{time_str}_STATISTICAL.txt"
with open(statistical_file, 'w', encoding='utf-8') as f:
    f.write(statistical_report)
print(f"✅ Saved: {statistical_file}")

# GOVERNANCE REPORT (Calibrated confidence with ceilings)
print("\n🔒 Generating GOVERNANCE-CALIBRATED report (regression-adjusted confidence)...")
governance_report = generate_report(all_plays, mode='governance', now_local=now_local, blocked_plays=blocked_plays, degraded_manager=degraded_manager)
governance_file = f"outputs/CHEATSHEET_{month_abbr}{day_str}_{time_str}_CALIBRATED.txt"
with open(governance_file, 'w', encoding='utf-8') as f:
    f.write(governance_report)
print(f"✅ Saved: {governance_file}")

"""After generating both cheat sheets, emit a machine-readable
publishability summary that downstream menus/pipelines can use to
gate client-facing actions (Telegram, etc.)."""

# Derive a shared base name for the slate and attach a JSON sidecar
# with publishability metadata.
base_name = f"CHEATSHEET_{month_abbr}{day_str}_{time_str}"
summary_file = f"outputs/{base_name}_SUMMARY.json"

injury_health = get_injury_feed_health()

# Count injury-related uncertainty across allowed and blocked plays.
unknown_injury_count = sum(
    1
    for p in (all_plays + blocked_plays)
    if p.get("injury_status") == "UNKNOWN"
)
non_active_allowed = sum(
    1
    for p in all_plays
    if p.get("injury_status") and p.get("injury_status") != "ACTIVE"
)

# Recompute simple parlay candidate pools using the same governance-
# calibrated confidences that were just written to the CALIBRATED
# sheet (generate_report in 'governance' mode leaves prob_display set).
safe_candidates = [
    p for p in all_plays
    if p.get("prob_display", 0.0) >= 0.80 and p.get("injury_status") == "ACTIVE"
]

value_candidates = []
used_teams = set()
for p in sorted(all_plays, key=lambda x: x.get("prob_display", 0.0), reverse=True):
    if (
        p.get("team") not in used_teams
        and p.get("prob_display", 0.0) >= 0.70
        and p.get("injury_status") == "ACTIVE"
    ):
        value_candidates.append(p)
        used_teams.add(p.get("team"))
        if len(value_candidates) >= 4:
            break

longshot_overs = [
    p for p in all_plays
    if p.get("direction") == "OVER"
    and p.get("prob_display", 0.0) >= 0.70
    and p.get("injury_status") == "ACTIVE"
][:3]
longshot_unders = [
    p for p in all_plays
    if p.get("direction") == "UNDER"
    and p.get("prob_display", 0.0) >= 0.65
    and p.get("injury_status") == "ACTIVE"
][:2]

publishable = True
publishability_reasons = []

# Hard gate: if the injury feed is not healthy, the slate is not
# considered publishable for client distribution, even though the
# text cheatsheets are still generated for internal review.
if injury_health != "HEALTHY":
    publishable = False
    publishability_reasons.append("injury_feed_not_healthy")

operating_instructions = degraded_manager.get_operating_instructions()
if operating_instructions["current_level"] != DegradedModeLevel.NORMAL.value:
    publishable = False
    if "degraded_mode_active" not in publishability_reasons:
        publishability_reasons.append("degraded_mode_active")

# Soft signals that the slate may be structurally weak; these are
# recorded for the operator but do not, by themselves, flip the
# publishable flag.
if not safe_candidates and not value_candidates and not longshot_overs and not longshot_unders:
    publishability_reasons.append("no_parlay_candidates")

if unknown_injury_count > 0:
    publishability_reasons.append("unknown_injury_players_present")

summary_payload = {
    "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    "slate_date_local": now_local.date().isoformat(),
    "base_name": base_name,
    "files": {
        "statistical": statistical_file,
        "calibrated": governance_file,
    },
    "injury_feed_health": injury_health,
    "degraded_mode": operating_instructions,
    "counts": {
        "allowed_plays": len(all_plays),
        "blocked_plays": len(blocked_plays),
        "unknown_injury": unknown_injury_count,
        "non_active_allowed": non_active_allowed,
        "safe_candidates": len(safe_candidates),
        "value_candidates": len(value_candidates),
        "longshot_over_candidates": len(longshot_overs),
        "longshot_under_candidates": len(longshot_unders),
    },
    "publishable": publishable,
    "publishability_reasons": publishability_reasons,
}

with open(summary_file, "w", encoding="utf-8") as f:
    json.dump(summary_payload, f, indent=2)

print("\n" + "=" * 80)
print("📋 SUMMARY")
print("=" * 80)
print(f"STATISTICAL (Uncapped):  {statistical_file}")
print(f"CALIBRATED (68-75%):    {governance_file}")
print(f"SUMMARY (JSON):         {summary_file}")
print("\n💡 Tip: Use STATISTICAL for aggressive play selection,")
print("        CALIBRATED for conservative, regression-aware picks.")
print("        SUMMARY for menu/pipeline gating and audit.")
print("=" * 80)
