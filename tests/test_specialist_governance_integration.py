from core.decision_governance import EligibilityGate, PickState
from quant_modules.monte_carlo_optimizer import MonteCarloOptimizer, Pick


def test_eligibility_rejects_bench_microwave_pts_and_3pm():
    gate = EligibilityGate()

    pick_pts = {
        "player": "Test Guy",
        "stat": "PTS",
        "line": 18.5,
        "direction": "higher",
        "final_probability": 70.0,
        "stat_specialist_type": "BENCH_MICROWAVE",
    }
    r1 = gate.evaluate(pick_pts)
    assert r1.state == PickState.REJECTED

    pick_3pm = dict(pick_pts)
    pick_3pm["stat"] = "3PM"
    pick_3pm["line"] = 2.5
    r2 = gate.evaluate(pick_3pm)
    assert r2.state == PickState.REJECTED


def test_eligibility_rejects_off_dribble_low_confidence():
    gate = EligibilityGate()
    pick = {
        "player": "OD Guy",
        "stat": "3PM",
        "line": 2.5,
        "direction": "higher",
        "final_probability": 57.9,
        "stat_specialist_type": "OFF_DRIBBLE_SCORER",
    }
    r = gate.evaluate(pick)
    assert r.state == PickState.REJECTED


def test_eligibility_rejects_big_man_3pm_line_35_plus():
    gate = EligibilityGate()
    pick = {
        "player": "Big Shooter",
        "stat": "3PM",
        "line": 3.5,
        "direction": "higher",
        "final_probability": 70.0,
        "stat_specialist_type": "BIG_MAN_3PM",
    }
    r = gate.evaluate(pick)
    assert r.state == PickState.REJECTED


def test_optimizer_blocks_volatile_specialists_from_flex():
    # With a volatile specialist in the only 3-leg combo, FLEX should produce no entries.
    picks = [
        Pick(player="A", stat="PTS", line=20.5, direction="higher", p_hit=0.70, specialist="BENCH_MICROWAVE"),
        Pick(player="B", stat="REB", line=7.5, direction="higher", p_hit=0.69, specialist=""),
        Pick(player="C", stat="STL", line=1.5, direction="higher", p_hit=0.68, specialist=""),
    ]

    opt = MonteCarloOptimizer(method="exact")
    res = opt.find_best_entries(
        picks,
        legs_options=[3],
        entry_types=["power", "flex"],
        max_entries=10,
        max_same_game=99,
        max_picks_to_consider=10,
        league="NBA",
    )

    assert any(e.entry_type == "power" for e in res.entries)
    assert all(e.entry_type != "flex" for e in res.entries)


def test_optimizer_excludes_big_man_3pm_from_3_leg_combos():
    picks = [
        Pick(player="Big", stat="3PM", line=2.5, direction="higher", p_hit=0.80, specialist="BIG_MAN_3PM"),
        Pick(player="A", stat="PTS", line=20.5, direction="higher", p_hit=0.70, specialist=""),
        Pick(player="B", stat="REB", line=7.5, direction="higher", p_hit=0.69, specialist=""),
        Pick(player="C", stat="STL", line=1.5, direction="higher", p_hit=0.68, specialist=""),
    ]

    opt = MonteCarloOptimizer(method="exact")
    res = opt.find_best_entries(
        picks,
        legs_options=[3],
        entry_types=["power"],
        max_entries=20,
        max_same_game=99,
        max_picks_to_consider=10,
        league="NBA",
    )

    # Any 3-leg entry should have skipped BIG_MAN_3PM.
    assert res.entries, "Expected at least one entry from non-big-man picks"
    for e in res.entries:
        assert all((p.specialist or "").strip().upper() != "BIG_MAN_3PM" for p in e.picks)
