"""analyze_from_underdog_json.py

Generic risk-first runner for a parsed Underdog JSON slate.

- Reads a JSON file with schema: {"plays": [...]}
- Runs `risk_first_analyzer.analyze_slate`
- Writes outputs/<LABEL>_RISK_FIRST_<YYYYMMDD>_FROM_UD.json
- Optional balanced report via BALANCED_REPORT=1
- Optional AI report via GENERATE_AI_REPORT=1 (renderer only; does not affect decisions)

Usage (example):
  .venv\\Scripts\\python.exe analyze_from_underdog_json.py --slate nyk_gsw_full_slate_20260115.json --label NYK_GSW
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import date
from pathlib import Path

from balanced_report import build_balanced_team_report
from risk_first_analyzer import analyze_slate, print_summary
try:
    from menu import _env_preflight  # diagnostics helper
except Exception:
    _env_preflight = None
try:
    from analysis.nba.stat_rank_explainer import inject_rankings_into_report
except ImportError:
    inject_rankings_into_report = None  # Graceful degradation


def main() -> None:
    ap = argparse.ArgumentParser(description="Analyze a parsed Underdog slate JSON with risk-first pipeline")
    ap.add_argument("--slate", required=True, help="Path to parsed slate JSON (expects {'plays': [...]})")
    ap.add_argument("--label", required=True, help="Label used in output filenames (e.g., NYK_GSW)")
    ap.add_argument("--date", default=None, help="Override date stamp (YYYY-MM-DD)")
    ap.add_argument("--hq-options", default=None, help="Path to HQ options JSON (injury clamp / overrides / reporting)")
    ap.add_argument("--ai", action="store_true", help="Generate AI report (renderer only)")
    # Game situation flags
    ap.add_argument("--away-b2b", action="store_true", help="Away team is on back-to-back")
    ap.add_argument("--home-b2b", action="store_true", help="Home team is on back-to-back")
    ap.add_argument("--away-rest", type=int, default=1, help="Away team days rest (0=B2B, 1=normal, 2+=extra)")
    ap.add_argument("--home-rest", type=int, default=1, help="Home team days rest (0=B2B, 1=normal, 2+=extra)")
    args = ap.parse_args()

    if args.hq_options:
        os.environ["HQ_OPTIONS_PATH"] = str(args.hq_options)

    slate_path = Path(args.slate)
    slate = json.loads(slate_path.read_text(encoding="utf-8"))
    props = slate.get("plays", [])

    if not isinstance(props, list) or not props:
        raise SystemExit("Slate JSON contains no plays")

    # Auto-detect teams from slate filename and set up game situations
    try:
        from setup_game_situation import detect_home_team_from_slate
        from nba_game_situation import set_game_situation
        
        teams = detect_home_team_from_slate(str(slate_path))
        if teams:
            away_team, home_team = teams
            game_date = date.today().strftime("%Y-%m-%d")
            
            # Set away team situation
            set_game_situation(
                team=away_team,
                game_date=game_date,
                is_home=False,
                days_rest=args.away_rest if not args.away_b2b else 0,
                is_back_to_back=args.away_b2b,
                opponent=home_team,
                opponent_b2b=args.home_b2b,
                opponent_days_rest=args.home_rest if not args.home_b2b else 0
            )
            
            # Set home team situation
            set_game_situation(
                team=home_team,
                game_date=game_date,
                is_home=True,
                days_rest=args.home_rest if not args.home_b2b else 0,
                is_back_to_back=args.home_b2b,
                opponent=away_team,
                opponent_b2b=args.away_b2b,
                opponent_days_rest=args.away_rest if not args.away_b2b else 0
            )
            
            # Print situation summary
            from nba_game_situation import get_situation_summary
            if args.away_b2b or args.home_b2b or args.away_rest != 1 or args.home_rest != 1:
                print(f"[SITUATION] {away_team}: {get_situation_summary(away_team, game_date)}")
                print(f"[SITUATION] {home_team}: {get_situation_summary(home_team, game_date)}")
                print()
    except ImportError:
        pass  # Situation modules not available

    game_context: dict = {}

    # Environment preflight diagnostics (nba_api / ESPN / config availability)
    try:
        if _env_preflight:
            _env_preflight()
    except Exception:
        pass

    print("=" * 70)
    print(f"{args.label} - RISK-FIRST ANALYSIS")
    print("=" * 70)
    print(f"Total props in slate: {len(props)}")
    
    # Show active config
    try:
        from analysis_config import get_config_summary, apply_config_to_environment, load_config
        config = load_config()
        apply_config_to_environment(config)
        print(f"Config: {get_config_summary(config)}")
    except ImportError:
        print("Config: Default (analysis_config.py not loaded)")
    
    print("=" * 70)
    print()

    results = analyze_slate(props, game_context=game_context)
    print_summary(results)

    # STAT-WISE TOP-5 EXPLANATION ENGINE (inject rankings into results)
    if inject_rankings_into_report is not None:
        try:
            picks_list = results.get("results", []) if isinstance(results, dict) else results
            results = inject_rankings_into_report(results, picks_list)
            if "top_5_by_stat" in results:
                print(f"[STAT-RANKINGS] Injected Top-5 rankings for {len(results['top_5_by_stat'])} stats")
        except Exception as e:
            print(f"[STAT-RANKINGS] Skipped (non-fatal): {e}")

    if args.date:
        stamp = str(args.date).replace("-", "")[:8]
    else:
        stamp = date.today().strftime("%Y%m%d")

    out_dir = Path("outputs")
    out_dir.mkdir(parents=True, exist_ok=True)

    out_json = out_dir / f"{args.label}_RISK_FIRST_{stamp}_FROM_UD.json"
    out_json.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nFull results saved to: {out_json}\n")

    # Optional balanced report
    try:
        if os.getenv("BALANCED_REPORT", "0").strip() == "1":
            rpt = build_balanced_team_report(results, top_n=5)
            rpt_path = out_dir / f"{args.label}_BALANCED_{stamp}_FROM_UD.txt"
            rpt_path.write_text(rpt, encoding="utf-8")
            print(f"Balanced report saved to: {rpt_path}")
    except Exception:
        pass

    # Optional AI report (renderer only)
    if args.ai or os.getenv("GENERATE_AI_REPORT", "0").strip() == "1":
        try:
            from ai_commentary import generate_full_report

            report = generate_full_report(results, game_context=game_context)
            out_txt = out_dir / f"{args.label}_AI_REPORT_{stamp}_FROM_UD.txt"
            out_txt.write_text(report, encoding="utf-8")
            print(f"AI analysis report saved to: {out_txt}")
        except Exception as e:
            print(f"[AI] Report generation failed (non-fatal): {e}")
    else:
        print("AI report: disabled (set GENERATE_AI_REPORT=1 to enable).")

    # ============================================================
    # QUANT MODULES: Backtest, Monte Carlo, Bayesian Tuning
    # Enable with QUANT_MODULES=1
    # ============================================================
    if os.getenv("QUANT_MODULES", "0").strip() == "1":
        try:
            from quant_modules import (
                run_calibration_report,
                optimize_entries,
                optimize_entries_unfiltered,
                run_bayesian_tuning,
            )

            print("\n" + "=" * 70)
            print("QUANT MODULES - ADVANCED ANALYSIS")
            print("=" * 70)

            # 1. Calibration Backtest (requires history)
            try:
                # run_calibration_report takes optional output_path, not picks data
                calib_result = run_calibration_report()
            except Exception as e:
                print(f"[BACKTEST] Skipped: {e}")

            # 2. Monte Carlo Entry Optimization
            try:
                # results is a dict with "results" key containing the picks list
                picks_list = results.get("results", []) if isinstance(results, dict) else results
                mc_result = optimize_entries(picks_list)
            except Exception as e:
                print(f"[MONTE CARLO] Skipped: {e}")

            # Unfiltered fallback: if strict MC yields too few picks, also run raw comparator
            try:
                # Read mc_settings if available
                mc_settings_path = Path("config/mc_settings.json")
                mc_min_conf = 55.0
                mc_exclude_composites = True
                if mc_settings_path.exists():
                    try:
                        mc_cfg = json.loads(mc_settings_path.read_text(encoding="utf-8"))
                        mc_min_conf = float(mc_cfg.get("unfiltered_min_conf", mc_min_conf))
                        mc_exclude_composites = bool(mc_cfg.get("exclude_composites", mc_exclude_composites))
                    except Exception:
                        pass

                # Always run the unfiltered comparator to generate UNDER-first baseline
                _ = optimize_entries_unfiltered(
                    picks_list,
                    min_confidence=mc_min_conf,
                    exclude_composites=mc_exclude_composites,
                )
            except Exception as e:
                print(f"[MONTE CARLO][RAW] Fallback skipped: {e}")

            # 3. Bayesian Gate Tuning
            try:
                bayes_result = run_bayesian_tuning()
            except Exception as e:
                print(f"[BAYESIAN] Skipped: {e}")

        except ImportError as e:
            print(f"[QUANT] Modules not available: {e}")
    else:
        print("\nQuant modules: disabled (set QUANT_MODULES=1 to enable).")


if __name__ == "__main__":
    main()
