import json

from quant_modules.monte_carlo_optimizer import _infer_league_from_picks, optimize_entries


def test_infer_league_detects_cbb_from_non_nba_team_abbrs():
    picks = [
        {
            "player": "A",
            "team": "WOF",
            "opponent": "SAM",
            "stat": "rebounds",
            "decision": "PLAY",
            "effective_confidence": 70.0,
            "line": 5.5,
            "direction": "higher",
        },
        {
            "player": "B",
            "team": "WOF",
            "opponent": "SAM",
            "stat": "assists",
            "decision": "PLAY",
            "effective_confidence": 70.0,
            "line": 2.5,
            "direction": "higher",
        },
    ]
    assert _infer_league_from_picks(picks) == "CBB"


def test_infer_league_prefers_explicit_league_field_when_present():
    picks = [{"player": "A", "team": "BOS", "opponent": "NYK", "stat": "points"}]
    assert _infer_league_from_picks(picks, meta={"league": "CBB"}) == "CBB"


def test_infer_league_still_detects_nfl_from_stat_signature():
    picks = [{"player": "A", "stat": "pass_yds", "team": "BUF"}]
    assert _infer_league_from_picks(picks) == "NFL"


def test_optimize_entries_cbb_does_not_apply_nba_fragile_filters(tmp_path, capsys):
    # These stats would be excluded by NBA strict (assists/3pm), but should pass CBB filtering.
    picks = [
        {
            "player": "A",
            "team": "WOF",
            "opponent": "SAM",
            "stat": "assists",
            "decision": "PLAY",
            "effective_confidence": 70.0,
            "line": 2.5,
            "direction": "higher",
        },
        {
            "player": "B",
            "team": "WOF",
            "opponent": "SAM",
            "stat": "3pm",
            "decision": "PLAY",
            "effective_confidence": 70.0,
            "line": 1.5,
            "direction": "higher",
        },
    ]

    out = tmp_path / "mc_report.txt"
    res = optimize_entries(picks, output_path=out)

    captured = capsys.readouterr().out
    assert "[MC][CBB]" in captured
    assert "Found 2 qualifying picks" in captured
    assert out.exists()
    # OptimizationResult is returned even if not enough legs to build entries.
    assert res is not None
