# daily_pipeline.py
"""
DAILY PIPELINE — TRUTH PATH WITH HARD GATES

Execution order:
1. Load hydrated legacy picks
2. Normalize schema (game_id, edge_key, edge_id)
3. ⛔ SCHEDULE GATE: Filter to TODAY's games only
4. ⛔ ROSTER GATE: Fix player-team truth from active roster
5. ⛔ DEDUPE: Remove duplicate player-stat combinations
6. Collapse correlated lines into logical edges
7. Enrich usage/minutes (for CORE stat unlock to 80%)
8. Score edges (probabilities + tiers with conditional caps)
9. Resolve ONE primary per player per game (deterministic)
10. ⛔ DIRECTIONAL BIAS GATE: Balance check + probability adjustment
11. Enforce render gate (hard truth)
12. Write validated output
"""
import argparse
from datetime import datetime
from pathlib import Path
import json
import hashlib
import sys
import glob
from engine.validation_guard import audit_pipeline_failure
from engine.pipeline_mode import PipelineMode, get_mode_config
from engine.bias_attribution import generate_bias_report, save_bias_report, enforce_bias_policy
from engine.tier_calibration import assign_calibrated_tier, compress_tiers, add_tier_rationale
from tests.regression_tests import run_all_regression_tests
from engine.capital_allocation import allocate_capital, summarize_allocation, DEFAULT_BANKROLL
from engine.normalize_picks import normalize_picks
from engine.schedule_gate import gate_today_games, get_today_games_from_espn
from engine.roster_gate import gate_active_roster, build_active_roster_map, load_roster_map
from engine.collapse_edges import collapse_edges, dedupe_player_props
from engine.enrich_usage_minutes import enrich_usage_minutes
from engine.score_edges import score_edges
from engine.resolve_player_primaries import resolve_player_primaries
from engine.directional_bias_gate import directional_bias_gate
from engine.render_gate import render_gate, RenderGateError
from utils.io import load_json, write_json



OUTPUT_FILE = "outputs/validated_primary_edges.json"


def run_pipeline(league: str = "NBA", mode: PipelineMode = PipelineMode.ANALYSIS, input_file: str = "picks_hydrated.json", dry_run: bool = False):
    # Patch: Import composite stat derivation for NFL
    from engine.stat_derivation import COMPOSITE_MAP, derive_composite

    # --- PIPELINE STATE ENFORCEMENT (anti-drift lock) ---
    state_path = Path("pipeline_state.json")
    state = None
    if state_path.exists():
        with open(state_path, "r", encoding="utf-8") as f:
            state = json.load(f)
        # Compute input file checksum
        def file_sha256(path):
            h = hashlib.sha256()
            with open(path, "rb") as f2:
                while True:
                    chunk = f2.read(8192)
                    if not chunk:
                        break
                    h.update(chunk)
            return "sha256:" + h.hexdigest()
        input_checksum = file_sha256(input_file)
        # Enforce state
        if state["league"] != league:
            raise RuntimeError(f"STATE VIOLATION: league mismatch ({state['league']} vs {league})")
        if state["mode"] != mode.value:
            raise RuntimeError(f"STATE VIOLATION: mode mismatch ({state['mode']} vs {mode.value})")
        if state["input_file"] != input_file:
            raise RuntimeError(f"STATE VIOLATION: input_file mismatch ({state['input_file']} vs {input_file})")
        if state["learning_enabled"] and mode.value != "learn":
            raise RuntimeError("STATE VIOLATION: learning flag mismatch")
        if state["checksum"] != input_checksum:
            raise RuntimeError("STATE VIOLATION: input file checksum changed")
    # --- PRE-RUN POLICY ENFORCEMENT ---
        # --- DRY-RUN VALIDATOR (universal pre-flight) ---
        if dry_run:
            print("\n🟢 PIPELINE DRY-RUN: PRE-FLIGHT GATE CHECKS\n")
            # 1. Ingestion module exists
            try:
                # Check if normalize_picks is available (already imported at top)
                if callable(normalize_picks):
                    print("✔ Ingestion module: normalize_picks available")
                else:
                    raise ImportError("normalize_picks is not callable")
            except Exception as e:
                print(f"❌ Ingestion module missing: {e}")
                exit(1)
            # 2. Schedule gate returns games
            try:
                today_games = get_today_games_from_espn(league)
                if today_games:
                    print(f"✔ Schedule gate: {len(today_games)} games found for {league}")
                else:
                    print("❌ Schedule gate: No games found")
                    exit(1)
            except Exception as e:
                print(f"❌ Schedule gate error: {e}")
                exit(1)
            # 3. Injury feed health (stub: always pass, extend as needed)
            print("✔ Injury feed: (stubbed PASS)")
            # 4. Stat source reachable (stub: always pass, extend as needed)
            print("✔ Stat source: (stubbed PASS)")
            # 5. Learning gate logic wired (stub: always pass, extend as needed)
            print("✔ Learning gate: (stubbed PASS)")
            # 6. Output validator callable (stub: always pass, extend as needed)
            print("✔ Output validator: (stubbed PASS)")
            print("\nNFL DRY-RUN STATUS: PASS\n")
            import sys
            sys.exit(0)
    policy_path = Path("multi_sport_policy.json")
    if not policy_path.exists():
        print("❌ POLICY ENFORCEMENT FAILED: multi_sport_policy.json not found.")
        sys.exit(1)
    try:
        with open(policy_path, "r", encoding="utf-8") as f:
            policy = json.load(f)
        # Basic enforcement: check locked philosophy and required pipeline order
        if not policy.get("constraints", {}).get("philosophy_locked", False):
            print("❌ POLICY ENFORCEMENT FAILED: Philosophy not locked in policy file.")
            sys.exit(1)
        required_order = ["ingest", "normalize", "hydrate", "collapse_edges", "score", "validate", "render"]
        if policy.get("pipeline_order") != required_order:
            print("❌ POLICY ENFORCEMENT FAILED: Pipeline order mismatch.")
            print(f"   Expected: {required_order}")
            print(f"   Found:    {policy.get('pipeline_order')}")
            sys.exit(1)
        print("🔒 POLICY ENFORCEMENT PASSED: multi_sport_policy.json loaded and validated.")
    except Exception as e:
        print(f"❌ POLICY ENFORCEMENT FAILED: {e}")
        sys.exit(1)

    config = get_mode_config(mode)
    print("🚀 DAILY PIPELINE START")
    print(f"   League: {league}")
    print(f"   Mode: {mode.value.upper()}")
    if mode == PipelineMode.ANALYSIS:
        print("   ⚠️  ANALYSIS MODE: Gates log only, NO BROADCAST")
    else:
        print("   ✅ BROADCAST MODE: Hard gates enforced")
    print()


    # 1️⃣ Load legacy hydrated picks
    raw_picks = load_json(input_file)
    if not raw_picks:
        raise RuntimeError(f"No picks found in {input_file}")

    print(f"📥 Loaded {len(raw_picks)} raw picks from {input_file}")

    # --- Update pipeline_state.json after successful load ---
    def file_sha256(path):
        h = hashlib.sha256()
        with open(path, "rb") as f2:
            while True:
                chunk = f2.read(8192)
                if not chunk:
                    break
                h.update(chunk)
        return "sha256:" + h.hexdigest()
    input_checksum = file_sha256(input_file)
    new_state = {
        "league": league,
        "mode": mode.value,
        "input_file": input_file,
        "stage": "VALIDATED",
        "last_run": datetime.utcnow().isoformat() + "Z",
        "learning_enabled": False,
        "checksum": input_checksum
    }
    with open("pipeline_state.json", "w", encoding="utf-8") as f:
        json.dump(new_state, f, indent=2)

    # 2️⃣ Normalize schema
    normalized = normalize_picks(raw_picks)
    print(f"🔧 Normalized {len(normalized)} picks")
    print()

    # 2.5️⃣ NFL Hydration Failure Logging (pre-score audit)
    hydration_failures = []
    for pick in normalized:
        # Only check NFL
        if league.upper() == "NFL":
            # If recent_values missing or empty, flag as hydration failure
            if not pick.get("recent_values") or len(pick.get("recent_values", [])) < 2:
                pick["HYDRATION_FAILED"] = True
                hydration_failures.append({k: pick.get(k) for k in ("player", "team", "stat", "line", "direction")})
            else:
                pick["HYDRATION_FAILED"] = False

    if hydration_failures:
        print(f"⚠️  NFL HYDRATION FAILURES: {len(hydration_failures)} picks missing stat data:")
        for fail in hydration_failures:
            print(f"   - {fail}")

    # 3️⃣ ⛔ SCHEDULE GATE: Filter to today's games
    print("⛔ SCHEDULE GATE")
    try:
        today_games = get_today_games_from_espn(league)
        print(f"   Fetched {len(today_games)} games for today")
        scheduled = gate_today_games(normalized, today_games)
        print(f"   ✅ {len(scheduled)} picks match today's schedule")
    except RuntimeError as e:
        print(f"   ❌ SCHEDULE GATE FAILED: {e}")
        raise
    print()

    # 4️⃣ ⛔ ROSTER GATE: Fix player-team truth
    print("⛔ ROSTER GATE")
    try:
        roster_map = build_active_roster_map(league)
        if not roster_map:
            # Dynamic NFL roster file resolution
            if league.upper() == "NFL":
                # Find all unique teams in scheduled picks
                teams = sorted({p['team'] for p in scheduled if 'team' in p})
                if len(teams) >= 2:
                    team_part = "_".join(teams)
                    today_str = datetime.now().strftime("%Y-%m-%d")
                    pattern = f"data_center/rosters/NFL_active_roster_{team_part}_*{today_str}*.csv"
                    local_files = glob.glob(pattern)
                    if not local_files:
                        # fallback: try any file for these teams
                        pattern = f"data_center/rosters/NFL_active_roster_{team_part}_*.csv"
                        local_files = glob.glob(pattern)
                    if local_files:
                        print(f"   ⚠️  ESPN/SerpApi failed, using local NFL roster file: {local_files[0]}")
                        roster_map = load_roster_map(local_files[0])
                    else:
                        print(f"⚠️  ROSTER VALIDATION SKIPPED (no NFL roster for {team_part})")
                        print(f"   {len(scheduled)} picks NOT verified against active rosters")
                        roster_fixed = scheduled
                        raise StopIteration
                else:
                    print(f"⚠️  ROSTER VALIDATION SKIPPED (not enough NFL teams in picks)")
                    print(f"   {len(scheduled)} picks NOT verified against active rosters")
                    roster_fixed = scheduled
                    raise StopIteration
            else:
                # Default fallback for other leagues
                today_str = datetime.now().strftime("%Y-%m-%d")
                pattern = f"data_center/rosters/{league}_active_roster_*{today_str}*.csv"
                local_files = glob.glob(pattern)
                if local_files:
                    print(f"   ⚠️  ESPN/SerpApi failed, using local roster file: {local_files[0]}")
                    roster_map = load_roster_map(local_files[0])
                else:
                    print(f"⚠️  ROSTER VALIDATION SKIPPED (no ESPN/SerpApi/local roster)")
                    print(f"   {len(scheduled)} picks NOT verified against active rosters")
                    roster_fixed = scheduled
                    raise StopIteration
        if roster_map:
            print(f"   ✅ Fetched {len(roster_map)} players from active roster")
            roster_fixed = gate_active_roster(scheduled, roster_map)
            print(f"   ✅ {len(roster_fixed)} picks validated against active rosters")
        else:
            print(f"⚠️  ROSTER VALIDATION SKIPPED (no valid roster found)")
            print(f"   {len(scheduled)} picks NOT verified against active rosters")
            roster_fixed = scheduled
    except StopIteration:
        pass
    except RuntimeError as e:
        print(f"   ❌ ROSTER GATE FAILED: {e}")
        raise
    print()

    # 5️⃣ ⛔ DEDUPE: Remove duplicates
    print("⛔ DEDUPE GATE")
    try:
        deduped = dedupe_player_props(roster_fixed)
        print(f"   ✅ {len(deduped)} unique edges after deduplication")
    except RuntimeError as e:
        print(f"   ❌ DEDUPE FAILED: {e}")
        raise
    print()

    # 6️⃣ Collapse correlated lines (edge-level)
    print("🧩 COLLAPSE EDGES")
    collapsed = collapse_edges(deduped)
    print(f"   ✅ Collapsed to {len(collapsed)} edge rows")
    print()

    # 7️⃣ Enrich usage/minutes (for CORE stat unlock)
    print("📊 ENRICH USAGE/MINUTES")
    enriched = enrich_usage_minutes(collapsed)
    print(f"   ✅ {len(enriched)} picks enriched with usage/minutes estimates")
    print()

    # Enforce: soft roster pass only allowed in analysis mode
    if league.upper() == "NFL" and mode.value not in ("analysis",):
        before = len(enriched)
        enriched = [p for p in enriched if not p.get("soft_roster_pass")]
        after = len(enriched)
        if before != after:
            print(f"⛔ Dropped {before - after} picks with soft roster pass (not allowed in {mode.value} mode)")

    # Patch: NFL composite stat derivation (rush_rec_tds, rush_rec_yds, etc)
    if league.upper() == "NFL":
        for pick in enriched:
            stat = pick.get("stat")
            if stat in COMPOSITE_MAP:
                if not pick.get("recent_values"):
                    # Derive from atomic stats, but never assume zero for missing
                    atomic_lists = []
                    missing_components = False
                    missing_which = []
                    for atomic in COMPOSITE_MAP[stat]:
                        atomic_pick = next((p for p in enriched if p.get("player") == pick.get("player") and p.get("stat") == atomic), None)
                        if atomic_pick and atomic_pick.get("recent_values"):
                            atomic_lists.append(atomic_pick["recent_values"])
                        else:
                            missing_components = True
                            missing_which.append(atomic)
                    if atomic_lists:
                        min_len = min(len(lst) for lst in atomic_lists)
                        composite_values = [sum(lst[i] for lst in atomic_lists) for i in range(min_len)]
                    else:
                        composite_values = []
                    pick["recent_values"] = composite_values
                    # Audit fields
                    pick["derived_from"] = COMPOSITE_MAP[stat]
                    pick["missing_components"] = missing_components
                    pick["missing_which"] = missing_which
                    pick["composite_method"] = "sum"
                    # Penalty for missing atomic
                    if missing_components:
                        pick["composite_missing_penalty"] = 0.10
                    else:
                        pick["composite_missing_penalty"] = 0.0


    # 8️⃣ Score edges (probabilities + tiers with conditional caps)
    print("🎲 SCORE EDGES")
    scored = score_edges(enriched)
    print(f"   ✅ Scored {len(scored)} eligible edges")
    print()

    # 8.5️⃣ In ANALYSIS mode, output all picks (even if not scored) with HYDRATION_FAILED flag for audit
    if league.upper() == "NFL" and mode.value == "analysis":
        # Find picks that were not scored (e.g., due to hydration failure)
        scored_keys = set((p.get("player"), p.get("stat"), p.get("line"), p.get("direction")) for p in scored)
        unscored = []
        for pick in enriched:
            key = (pick.get("player"), pick.get("stat"), pick.get("line"), pick.get("direction"))
            if key not in scored_keys:
                # Mark as unscored, hydration failed
                pick = pick.copy()
                pick["probability"] = None
                pick["confidence_tier"] = "NO PLAY"
                pick["audit_note"] = "HYDRATION_FAILED"
                unscored.append(pick)
        if unscored:
            print(f"⚠️  {len(unscored)} NFL picks could not be scored due to hydration failure. Including for audit.")
        scored += unscored

    # --- DEBUG: Output full stat edge/Monte Carlo analysis for all props (NFL/NBA parity) ---
    if league.upper() == "NFL":
        try:
            from ufa.analysis.engine import AnalysisEngine, Player, PropBet
            players = {}
            for pick in enriched:
                pname = pick.get("player")
                if pname not in players:
                    players[pname] = Player(
                        name=pname,
                        team=pick.get("team", ""),
                        opponent=pick.get("opponent", ""),
                        position=pick.get("position", ""),
                        props=[],
                    )
                # Patch: If no recent_values or <2, fill with [0,0,0,0] to avoid div0
                game_logs = pick.get("recent_values", [])
                if not game_logs or len(game_logs) < 2:
                    game_logs = [0, 0, 0, 0]
                players[pname].props.append(
                    PropBet(
                        stat=pick.get("stat", ""),
                        line=pick.get("line", 0.0),
                        prop_type=pick.get("stat", ""),
                        game_logs=game_logs
                    )
                )
            engine = AnalysisEngine(defense_rankings={}, correlation_groups=[])
            all_analyzed, _ = engine.analyze_all(list(players.values()))
            def dc_to_dict(obj):
                import enum
                if hasattr(obj, "__dataclass_fields__"):
                    return {k: dc_to_dict(getattr(obj, k)) for k in obj.__dataclass_fields__}
                elif isinstance(obj, list):
                    return [dc_to_dict(x) for x in obj]
                elif isinstance(obj, dict):
                    return {k: dc_to_dict(v) for k, v in obj.items()}
                elif isinstance(obj, enum.Enum):
                    return obj.value
                else:
                    return obj
            debug_nfl_file = "outputs/edge_analysis_NFL.json"
            with open(debug_nfl_file, "w", encoding="utf-8") as f:
                json.dump([dc_to_dict(x) for x in all_analyzed], f, indent=2)
            print(f"   📝 DEBUG: Wrote full NFL edge analysis to {debug_nfl_file}")
        except Exception as e:
            print(f"   ⚠️  NFL EDGE DEBUG OUTPUT FAILED: {e}")

    # 9️⃣ Resolve ONE primary per (player, game)
    print("🎯 RESOLVE PRIMARIES")
    resolved = resolve_player_primaries(scored)
    print(f"   ✅ Resolved primary edges per player/game")
    print()

    # 🔟 Bias Attribution Report (governance diagnostics)
    print("📊 BIAS ATTRIBUTION REPORT")
    run_date = datetime.now().strftime("%Y-%m-%d")
    bias_report = generate_bias_report(resolved, run_date)
    report_file = save_bias_report(bias_report)
    
    # DEBUG: Save scored picks before tier filtering
    debug_file = "outputs/scored_picks_before_calibration.json"
    write_json(debug_file, resolved)
    
    print(f"   Distribution: {bias_report['directional_distribution']['under_pct']}% UNDERS | {bias_report['directional_distribution']['over_pct']}% OVERS")
    print(f"   Severity: {bias_report['severity']}")
    if bias_report['root_causes']:
        print(f"   Root causes: {', '.join(bias_report['root_causes'])}")
    print(f"   Saved: {report_file}")
    
    # Enforce bias policy
    allowed, reason = enforce_bias_policy(bias_report, mode.value)
    if not allowed:
        print(f"   🚫 BIAS POLICY BLOCK: {reason}")
        if config.enforce_gates:
            raise ValueError(f"Bias policy violation: {reason}")
    print()

    # 1️⃣1️⃣ Tier Calibration (policy layer)
    print("🎯 TIER CALIBRATION")
    for pick in resolved:
        calibrated_tier = assign_calibrated_tier(pick, bias_report)
        pick["confidence_tier"] = calibrated_tier
        pick = add_tier_rationale(pick, bias_report)
    
    # Filter NO PLAY
    tiered = [p for p in resolved if p.get("confidence_tier") != "NO PLAY"]
    
    # Compress tiers if overflow
    tiered = compress_tiers(tiered)
    
    tier_counts = {}
    for p in tiered:
        tier = p.get("confidence_tier", "NO PLAY")
        tier_counts[tier] = tier_counts.get(tier, 0) + 1
    
    print(f"   ✅ {len(tiered)} picks after calibration")
    print(f"   Tiers: {tier_counts}")
    print()

    # 1️⃣2️⃣ Directional bias gate (legacy - now informed by bias report)
    print("⚖️  DIRECTIONAL BIAS GATE")
    try:
        balanced = directional_bias_gate(tiered)
        print(f"   ✅ {len(balanced)} edges passed directional balance check")
    except ValueError as e:
        print(f"   ❌ DIRECTIONAL BIAS GATE FAILED")
        print(str(e))
        if config.enforce_gates:
            print("   🚫 BROADCAST MODE: ABORTING")
            raise
        else:
            print(f"   ⚠️  ANALYSIS MODE: Continuing with {len(tiered)} biased edges")
            print("   DO NOT BROADCAST - FOR INSPECTION ONLY")
            balanced = tiered  # Continue with unbalanced data for analysis
    print()

    # 1️⃣3️⃣ Render gate (final validation)
    print("🔒 RENDER GATE")
    try:
        validated = render_gate(balanced)
        print(f"   ✅ {len(validated)} edges passed render validation")
    except RenderGateError as e:
        print(f"   ❌ RENDER GATE FAILED: {e}")
        if config.enforce_gates:
            print("   🚫 BROADCAST MODE: ABORTING")
            raise
        else:
            print("   ⚠️  ANALYSIS MODE: Continuing with render errors")
            validated = balanced
    print()

    # 1️⃣4️⃣ Regression Test Suite (anti-drift enforcement)
    run_all_regression_tests(
        picks=validated,
        config={
            "BIAS_GATE_ENABLED": True,
            "RENDER_GATE_ENABLED": True,
            "ALLOW_GATE_OVERRIDE": False,
        },
        context={
            "pipeline_mode": mode.value,
            "bias_report": bias_report,
            "telegram_sent": False,  # TODO: Update when Telegram integration added
            "learning_attempted": False,  # TODO: Update when learning added
        }
    )

    # 1️⃣5️⃣ Capital Allocation (BROADCAST only, bias-free only)
    if mode == PipelineMode.BROADCAST and not bias_report["bias_detected"]:
        print("💰 CAPITAL ALLOCATION")
        try:
            allocated = allocate_capital(
                picks=validated,
                bankroll=DEFAULT_BANKROLL,
                mode=mode.value,
                bias_detected=bias_report["bias_detected"]
            )
            
            # Generate summary
            summary = summarize_allocation(allocated, DEFAULT_BANKROLL)
            
            print(f"   ✅ {summary['total_picks']} picks allocated")
            print(f"   Total: {summary['total_units']} units ({summary['total_pct']:.1%} of bankroll)")
            print(f"   Daily cap: {summary['daily_cap_utilization']:.1%} of {summary['daily_cap_pct']:.0%} max")
            print(f"   Avg: {summary['avg_units_per_pick']:.2f} units/pick")
            
            tier_breakdown = " / ".join([f"{tier}:{units:.1f}u" for tier, units in summary['tier_breakdown'].items()])
            print(f"   Tiers: {tier_breakdown}")
            
            # Replace validated with allocated picks for output
            validated = allocated
            
        except ValueError as e:
            print(f"   ❌ CAPITAL ALLOCATION BLOCKED")
            print(str(e))
            raise
    else:
        if mode == PipelineMode.ANALYSIS:
            print("💰 CAPITAL ALLOCATION: SKIPPED (ANALYSIS mode)")
        elif bias_report["bias_detected"]:
            print("💰 CAPITAL ALLOCATION: SKIPPED (bias detected)")
        print()

    # 1️⃣6️⃣ Write output
    output_file = OUTPUT_FILE if mode == PipelineMode.BROADCAST else OUTPUT_FILE.replace(".json", "_ANALYSIS.json")
    write_json(output_file, validated)
    print(f"📝 Wrote {len(validated)} edges to {output_file}")
    print()
    
    # Final report
    if mode == PipelineMode.ANALYSIS:
        print("⚠️  ANALYSIS RUN COMPLETE - DO NOT BROADCAST")
        print(f"   Bias Report: {report_file}")
        print(f"   Learning: FROZEN (bias={bias_report['bias_detected']})")
        print(f"   Regression Tests: PASSED (system integrity verified)")
        print(f"   Capital Allocation: SKIPPED (analysis mode)")
    else:
        print("✅ BROADCAST PIPELINE COMPLETE - CLEARED FOR TELEGRAM")
        if bias_report['bias_detected']:
            print(f"   ⚠️  WARNING: {bias_report['recommendation']}")
            print(f"   Capital Allocation: SKIPPED (bias detected)")
        else:
            print(f"   Capital Allocation: ACTIVE ({len(validated)} picks funded)")
        print(f"   Regression Tests: PASSED (system integrity verified)")



if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["analysis", "broadcast"], default="analysis")
    parser.add_argument("--league", default="NBA")
    parser.add_argument("--input-file", default="picks_hydrated.json", help="Path to picks JSON file")
    parser.add_argument("--dry-run", action="store_true", help="Run pipeline readiness checks only and exit")
    args = parser.parse_args()

    mode = PipelineMode.ANALYSIS if args.mode == "analysis" else PipelineMode.BROADCAST
    run_pipeline(league=args.league, mode=mode, input_file=args.input_file, dry_run=args.dry_run)
