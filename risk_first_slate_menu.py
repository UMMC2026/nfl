"""risk_first_slate_menu.py

Interactive ASCII-only menu to "lock in" the Underdog pasted-slate workflow:
  raw text (inputs/*.txt) -> parsed JSON -> risk-first analysis -> outputs + signals

Design goals:
- Deterministic and reproducible: always works from a saved raw file.
- Safe on Windows terminals: no emojis, no rich, no unicode-dependent UI.
- Uses the existing risk-first analyzer + parser.
- Never crashes the session on errors; prints a clear message and returns to menu.

Typical use:
  .venv\\Scripts\\python.exe risk_first_slate_menu.py
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Optional

from parse_underdog_slate import parse_underdog_slate
from risk_first_analyzer import analyze_slate, print_summary
from governance_artifacts import export_governance_artifacts


@dataclass
class RunSettings:
    prob_method: str = "auto"  # auto|empirical|empirical_hybrid|wilson_empirical|normal_cdf|negbin
    force_stats_refresh: bool = False
    generate_ai_report: bool = True
    balanced_report: bool = False
    # HQ Quant options are clamps only (no modes). The menu writes this file each run.
    hq_options_path: str = str(Path("outputs") / "hq_options_last.json")
    injury_return_enabled: bool = False
    injury_return_players: str = ""  # comma-separated names
    injury_return_projection_multiplier: float = 0.92
    injury_return_max_probability: float = 0.58
    player_overrides_path: str = ""  # optional JSON file containing player_overrides


def _safe_int(s: str, default: int) -> int:
    try:
        return int(str(s).strip())
    except Exception:
        return default


def _pause() -> None:
    try:
        input("\nPress Enter to continue...")
    except Exception:
        pass


def _safe_input(prompt: str) -> str:
    """Input wrapper that handles non-interactive stdin.

    When this script is executed in a context without an interactive stdin
    (common with some task runners), plain input() raises EOFError and the
    program can appear to do "nothing". We fail loudly with a clear hint.
    """
    try:
        return input(prompt)
    except EOFError:
        print("\n[MENU] No interactive stdin detected.")
        print("[MENU] Run this from the VS Code integrated terminal (not a non-interactive task runner).")
        print("[MENU] Example (PowerShell):")
        print("        & '.\\.venv\\Scripts\\python.exe' '.\\risk_first_slate_menu.py'")
        raise


def _print_header() -> None:
    print("=" * 70)
    print("RISK-FIRST NBA SLATE MENU")
    print("Raw Underdog paste -> parse -> analyze -> outputs/signals")
    print("=" * 70)


def _list_raw_inputs(inputs_dir: Path) -> list[Path]:
    if not inputs_dir.exists():
        return []
    files = sorted(inputs_dir.glob("*.txt"), key=lambda p: p.stat().st_mtime, reverse=True)
    return [p for p in files if p.is_file()]


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _derive_slug_from_parsed(parsed: dict) -> str:
    """Best-effort slug like NYK_GSW.

    Uses first play's matchup_away/matchup_home when available.
    """
    try:
        plays = parsed.get("plays", [])
        if isinstance(plays, list) and plays:
            p0 = plays[0]
            if isinstance(p0, dict):
                away = (p0.get("matchup_away") or "").strip().upper()
                home = (p0.get("matchup_home") or "").strip().upper()
                if away and home:
                    return f"{away}_{home}"
    except Exception:
        pass
    return "SLATE"


def _stamp_from_date_str(d: Optional[str]) -> str:
    try:
        if isinstance(d, str) and len(d) >= 10:
            return d.replace("-", "")[:8]
    except Exception:
        pass
    return date.today().strftime("%Y%m%d")


def _print_settings(s: RunSettings) -> None:
    print("\nCurrent run settings")
    print("-" * 70)
    print(f"Probability method : {s.prob_method}")
    print(f"Force stats refresh: {'YES' if s.force_stats_refresh else 'NO'}")
    print(f"AI report          : {'YES' if s.generate_ai_report else 'NO'}")
    print(f"Balanced report    : {'YES' if s.balanced_report else 'NO'}")
    print(f"HQ options path    : {s.hq_options_path}")
    print(f"Injury return clamp: {'YES' if s.injury_return_enabled else 'NO'}")
    if s.injury_return_players.strip():
        print(f"Injury return list : {s.injury_return_players.strip()}")
    print(f"Injury mu mult     : {s.injury_return_projection_multiplier:.2f}")
    print(f"Injury p(cap)      : {s.injury_return_max_probability:.2f}")
    if s.player_overrides_path.strip():
        print(f"Player overrides   : {s.player_overrides_path.strip()}")


def _split_csv_names(raw: str) -> list[str]:
    return [p.strip() for p in str(raw).split(",") if p.strip()]


def _show_signals(output_dir: Path) -> None:
    p = output_dir / "signals_latest.json"
    if not p.exists():
        print("\nNo signals found at output/signals_latest.json")
        return
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"\nFailed to read signals_latest.json: {e}")
        return

    if not isinstance(data, list) or not data:
        print("\nNo signals in signals_latest.json")
        return

    print("\nLatest signals (top 10)")
    print("-" * 70)
    for i, s in enumerate(data[:10], 1):
        if not isinstance(s, dict):
            continue
        player = s.get("player", "?")
        team = s.get("team", "?")
        stat = s.get("stat", "?")
        line = s.get("line", "?")
        direction = s.get("direction", "?")
        tier = s.get("tier", "?")
        prob = s.get("probability", None)
        prob_str = f"{float(prob) * 100:.1f}%" if isinstance(prob, (int, float)) else "?"
        print(f"{i}. {tier}: {player} ({team}) {stat} {direction} {line} | p={prob_str}")


def _parse_raw_to_json(raw_path: Path, *, out_json: Optional[Path] = None, override_date: Optional[str] = None) -> Path:
    text = raw_path.read_text(encoding="utf-8", errors="replace")
    parsed = parse_underdog_slate(text)
    if override_date:
        parsed["date"] = override_date

    slug = _derive_slug_from_parsed(parsed)
    if out_json is None:
        out_json = Path(f"{slug.lower()}_full_slate.json")

    _write_json(out_json, parsed)
    return out_json


def _analyze_json_slate(slate_json: Path, settings: RunSettings) -> tuple[Path, Optional[Path]]:
    data = _load_json(slate_json)
    props = data.get("plays", [])

    if not isinstance(props, list) or not props:
        raise ValueError("Slate JSON has no 'plays' array")

    # Apply run settings via environment (only for this process).
    os.environ["RISK_PROB_METHOD"] = settings.prob_method

    os.environ["BALANCED_REPORT"] = "1" if settings.balanced_report else "0"

    # HQ Quant options: deterministic clamps + reporting preferences.
    player_overrides: dict = {}
    if settings.player_overrides_path.strip():
        try:
            player_overrides = json.loads(Path(settings.player_overrides_path.strip()).read_text(encoding="utf-8"))
            if not isinstance(player_overrides, dict):
                player_overrides = {}
        except Exception as e:
            print(f"[HQ] Failed to load player overrides (non-fatal): {e}")
            player_overrides = {}

    hq_payload = {
        "injury_return": {
            "enabled": bool(settings.injury_return_enabled),
            "players": _split_csv_names(settings.injury_return_players),
            "games_back_threshold": 2,
            "stat_window": "last_5",
            "projection_multiplier": float(settings.injury_return_projection_multiplier),
            "max_probability": float(settings.injury_return_max_probability),
        },
        "player_overrides": player_overrides,
        "reporting": {
            "top_n_per_team": 5,
            "include_status": ["PLAY", "LEAN", "ANALYSIS_ONLY"],
        },
    }

    try:
        hq_path = Path(settings.hq_options_path)
        _write_json(hq_path, hq_payload)
        os.environ["HQ_OPTIONS_PATH"] = str(hq_path)
    except Exception as e:
        print(f"[HQ] Failed to write HQ options file (non-fatal): {e}")
        os.environ.pop("HQ_OPTIONS_PATH", None)
    if settings.force_stats_refresh:
        os.environ["FORCE_STATS_REFRESH"] = "1"
    else:
        # Remove to avoid sticky behavior between runs.
        os.environ.pop("FORCE_STATS_REFRESH", None)

    game_context: dict = {}
    results = analyze_slate(props, game_context=game_context)
    print_summary(results)

    slug = _derive_slug_from_parsed(data)
    stamp = _stamp_from_date_str(data.get("date"))

    out_dir = Path("outputs")
    out_dir.mkdir(parents=True, exist_ok=True)

    out_json = out_dir / f"{slug}_RISK_FIRST_{stamp}_FROM_UD.json"
    _write_json(out_json, results)

    # Auto-commit STRONG/SLAM picks to calibration tracking
    try:
        from calibration.commit_mc_picks import commit_picks
        commit_result = commit_picks(out_json, bet_only=True, dry_run=False)
        if commit_result['committed'] > 0:
            print(f"\n[CALIBRATION] ✅ Committed {commit_result['committed']} STRONG/SLAM picks to tracking")
        else:
            print(f"\n[CALIBRATION] ⚠️  No STRONG/SLAM picks to track")
    except Exception as e:
        print(f"\n[CALIBRATION] Commit failed (non-fatal): {e}")

    # Governance exports (stable latest + timestamped copies)
    try:
        exported = export_governance_artifacts(
            results,
            slug=slug,
            stamp=stamp,
            out_dir=out_dir,
            run_settings=settings,
            source={
                "slate_json": str(slate_json),
                "results_json": str(out_json),
                "league": data.get("league", "NBA"),
                "date": data.get("date"),
            },
        )
        print("\n[GOV] Wrote governance artifacts:")
        print(f"      {exported['governance_config']}")
        print(f"      {exported['allowed_edges']}")
        print(f"      {exported['blocked_edges']}")
        if exported.get("governance_summary"):
            print(f"      {exported['governance_summary']}")
    except Exception as e:
        print(f"\n[GOV] Export failed (non-fatal): {e}")

    if settings.balanced_report:
        try:
            from balanced_report import build_balanced_team_report

            rpt = build_balanced_team_report(results, top_n=5)
            rpt_path = out_dir / f"{slug}_BALANCED_{stamp}_FROM_UD.txt"
            rpt_path.write_text(rpt, encoding="utf-8")
        except Exception as e:
            print(f"[BALANCED] Report generation failed (non-fatal): {e}")

    out_txt: Optional[Path] = None
    if settings.generate_ai_report:
        try:
            from ai_commentary import generate_full_report, generate_top20_report

            # Full-slate AI report
            report = generate_full_report(results, game_context=game_context)
            out_txt = out_dir / f"{slug}_AI_REPORT_{stamp}_FROM_UD.txt"
            out_txt.write_text(report, encoding="utf-8")

            # Dedicated Top-20 AI report (by final confidence)
            top20_report = generate_top20_report(results, game_context=game_context, top_n=20)
            top20_path = out_dir / f"{slug}_TOP20_AI_REPORT_{stamp}_FROM_UD.txt"
            top20_path.write_text(top20_report, encoding="utf-8")
        except Exception as e:
            print(f"[AI] Report generation failed (non-fatal): {e}")

    return out_json, out_txt


def main() -> None:
    inputs_dir = Path("inputs")
    output_dir = Path("output")

    settings = RunSettings()
    selected_raw: Optional[Path] = None
    selected_json: Optional[Path] = None

    while True:
        _print_header()

        print("Selected raw :", str(selected_raw) if selected_raw else "(none)")
        print("Selected json:", str(selected_json) if selected_json else "(none)")
        _print_settings(settings)

        print("\nMenu")
        print("-" * 70)
        print("1) Choose raw input file (inputs/*.txt)")
        print("2) Parse selected raw -> JSON")
        print("3) Analyze selected JSON (risk-first)")
        print("4) Quick run: raw -> parse -> analyze")
        print("5) Show latest signals (output/signals_latest.json)")
        print("6) Settings")
        print("7) Run AI Probability Module (new)")
        print("0) Exit")
        if choice == "7":
            if not selected_json:
                print("\nSelect/parse a JSON slate first (option 2).")
                _pause()
                continue
            try:
                from integrations.probability_module_adapter import ProbabilityModuleAdapter
                # Placeholder: replace with your actual feature engine and signal generator
                class DummyFeatureEngine:
                    def compute(self, player_data):
                        return {"dummy_feature": 1}
                class DummySignalGenerator:
                    def create_signal(self, **kwargs):
                        return kwargs
                adapter = ProbabilityModuleAdapter(DummyFeatureEngine(), DummySignalGenerator(), config={})
                data = _load_json(selected_json)
                plays = data.get("plays", [])
                signals = []
                for player in plays:
                    # Map/flatten as needed for your adapter
                    player_data = {
                        "player": player.get("player"),
                        "history": player.get("history", []),
                        "stat": player.get("stat"),
                        "line": player.get("line"),
                        "game_context": player.get("game_context", {}),
                    }
                    signal = adapter.generate_signal(player_data)
                    signals.append(signal)
                out_path = Path("outputs") / "signals_latest.json"
                _write_json(out_path, signals)
                print(f"\n[AI] Probability module signals written to {out_path} ({len(signals)} signals)")
            except Exception as e:
                print(f"\n[AI] Probability module failed: {e}")
            _pause()
            continue

        try:
            choice = _safe_input("\nSelect option: ").strip().lower()
        except EOFError:
            return

        if choice == "0":
            print("\nExiting.")
            return

        if choice == "1":
            raws = _list_raw_inputs(inputs_dir)
            if not raws:
                print("\nNo raw inputs found under inputs/*.txt")
                _pause()
                continue

            print("\nAvailable raw inputs (newest first)")
            print("-" * 70)
            for i, p in enumerate(raws, 1):
                print(f"{i:2d}) {p.name}")

            try:
                idx = _safe_int(_safe_input("\nChoose file number: "), 0)
            except EOFError:
                return
            if idx < 1 or idx > len(raws):
                print("Invalid selection.")
                _pause()
                continue

            selected_raw = raws[idx - 1]
            selected_json = None
            print(f"\nSelected raw: {selected_raw}")
            _pause()
            continue

        if choice == "2":
            if not selected_raw:
                print("\nSelect a raw input first (option 1).")
                _pause()
                continue

            try:
                override_date = _safe_input("Override date (YYYY-MM-DD) or blank: ").strip() or None
            except EOFError:
                return

            try:
                out_json = _parse_raw_to_json(selected_raw, override_date=override_date)
                selected_json = out_json
                parsed = _load_json(out_json)
                print(f"\nParsed props: {len(parsed.get('plays', []))}")
                print(f"Saved JSON: {out_json}")
            except Exception as e:
                print(f"\nParse failed: {e}")

            _pause()
            continue

        if choice == "3":
            if not selected_json:
                print("\nSelect/parse a JSON slate first (option 2).")
                _pause()
                continue

            try:
                out_json, out_txt = _analyze_json_slate(selected_json, settings)
                print(f"\nSaved results: {out_json}")
                if out_txt:
                    print(f"Saved AI report: {out_txt}")
            except Exception as e:
                print(f"\nAnalysis failed: {e}")

            _pause()
            continue

        if choice == "4":
            if not selected_raw:
                print("\nSelect a raw input first (option 1).")
                _pause()
                continue

            try:
                override_date = _safe_input("Override date (YYYY-MM-DD) or blank: ").strip() or None
            except EOFError:
                return

            try:
                selected_json = _parse_raw_to_json(selected_raw, override_date=override_date)
                print(f"\nParsed -> {selected_json}")
                out_json, out_txt = _analyze_json_slate(selected_json, settings)
                print(f"\nSaved results: {out_json}")
                if out_txt:
                    print(f"Saved AI report: {out_txt}")
            except Exception as e:
                print(f"\nQuick run failed: {e}")

            _pause()
            continue

        if choice == "5":
            _show_signals(output_dir)
            _pause()
            continue

        if choice == "6":
            print("\nSettings")
            print("-" * 70)
            print("1) Probability method (auto|empirical|empirical_hybrid|wilson_empirical|normal_cdf|negbin)")
            print("2) Toggle force stats refresh (FORCE_STATS_REFRESH)")
            print("3) Toggle AI report generation")
            print("4) Toggle balanced report (top 5 per team)")
            print("5) Toggle injury return clamp")
            print("6) Set injury-return players (comma-separated)")
            print("7) Set injury projection multiplier (mu multiplier)")
            print("8) Set injury max probability cap (0..1)")
            print("9) Set player_overrides JSON path (dict of overrides)")
            print("10) Set HQ options output path")
            print("0) Back")

            try:
                sub = _safe_input("Select: ").strip().lower()
            except EOFError:
                return
            if sub == "1":
                try:
                    pm = _safe_input("Enter method (auto|empirical|empirical_hybrid|wilson_empirical|normal_cdf|negbin): ").strip().lower()
                except EOFError:
                    return
                if pm in {"auto", "empirical", "empirical_hybrid", "wilson_empirical", "normal_cdf", "negbin"}:
                    settings.prob_method = pm
                else:
                    print("Invalid method.")
                    _pause()
            elif sub == "2":
                settings.force_stats_refresh = not settings.force_stats_refresh
            elif sub == "3":
                settings.generate_ai_report = not settings.generate_ai_report
            elif sub == "4":
                settings.balanced_report = not settings.balanced_report
            elif sub == "5":
                settings.injury_return_enabled = not settings.injury_return_enabled
            elif sub == "6":
                try:
                    raw = _safe_input("Enter players (comma-separated, blank clears): ").strip()
                except EOFError:
                    return
                settings.injury_return_players = raw
            elif sub == "7":
                try:
                    raw = _safe_input("Enter projection multiplier (e.g., 0.92): ").strip()
                except EOFError:
                    return
                try:
                    settings.injury_return_projection_multiplier = float(raw)
                except Exception:
                    print("Invalid number.")
                    _pause()
            elif sub == "8":
                try:
                    raw = _safe_input("Enter max probability cap (0..1, e.g., 0.58): ").strip()
                except EOFError:
                    return
                try:
                    settings.injury_return_max_probability = float(raw)
                except Exception:
                    print("Invalid number.")
                    _pause()
            elif sub == "9":
                try:
                    raw = _safe_input("Enter player_overrides JSON path (blank clears): ").strip()
                except EOFError:
                    return
                settings.player_overrides_path = raw
            elif sub == "10":
                try:
                    raw = _safe_input("Enter HQ options output path (blank keeps current): ").strip()
                except EOFError:
                    return
                if raw:
                    settings.hq_options_path = raw
            continue

        print("\nUnknown option.")
        _pause()


if __name__ == "__main__":
    main()
