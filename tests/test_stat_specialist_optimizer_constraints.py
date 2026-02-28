from quant_modules.monte_carlo_optimizer import MonteCarloOptimizer, Pick


def test_flex_excludes_volatile_specialists():
    opt = MonteCarloOptimizer(method="exact", n_sims=100)

    picks = [
        Pick(player="A", stat="PTS", line=10, direction="OVER", p_hit=0.70, specialist="BENCH_MICROWAVE"),
        Pick(player="B", stat="REB", line=5, direction="OVER", p_hit=0.70, specialist="GENERIC"),
        Pick(player="C", stat="AST", line=4, direction="OVER", p_hit=0.70, specialist="GENERIC"),
    ]

    res = opt.find_best_entries(
        picks,
        legs_options=[2],
        entry_types=["flex"],
        max_same_game=99,
        max_entries=10,
        max_picks_to_consider=30,
        league="NBA",
    )

    # The only valid 2-leg FLEX entry should be B+C (no BENCH_MICROWAVE leg).
    assert res.entries, "Expected at least one FLEX entry"
    for entry in res.entries:
        assert all((p.specialist or "").upper() not in {"BENCH_MICROWAVE", "OFF_DRIBBLE_SCORER"} for p in entry.picks)


def test_big_man_3pm_caps_max_legs_to_2():
    opt = MonteCarloOptimizer(method="exact", n_sims=100)

    picks = [
        Pick(player="A", stat="3PM", line=2.5, direction="OVER", p_hit=0.70, specialist="BIG_MAN_3PM"),
        Pick(player="B", stat="REB", line=5, direction="OVER", p_hit=0.70, specialist="GENERIC"),
        Pick(player="C", stat="AST", line=4, direction="OVER", p_hit=0.70, specialist="GENERIC"),
    ]

    res = opt.find_best_entries(
        picks,
        legs_options=[3],
        entry_types=["power"],
        max_same_game=99,
        max_entries=10,
        max_picks_to_consider=30,
        league="NBA",
    )

    # The only 3-leg combo includes BIG_MAN_3PM; it should be skipped.
    assert not res.entries
