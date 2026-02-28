from soccer.ingest.parse_soccer_underdog_paste import parse_text


def test_parse_soccer_goalie_saves_less_more():
    sample = """
Rodrigo Rey
Independiente - Goalkeeper
Rodrigo Rey
@ Newell's Tue 7:15pm
2.5
Goalie Saves
Less
More
""".strip()

    plays = parse_text(sample)
    assert len(plays) == 2

    players = {p["player"] for p in plays}
    assert players == {"Rodrigo Rey"}

    stats = {p["stat"] for p in plays}
    assert stats == {"goalie_saves"}

    dirs = {p["direction"] for p in plays}
    assert dirs == {"higher", "lower"}

    assert all(p["team"] == "Independiente" for p in plays)
    assert all(p["opponent"] == "Newell's" for p in plays)

    # Defensive placeholders for future hydration/modeling
    assert all("starter_assumed" in p and p["starter_assumed"] is None for p in plays)
    assert all("minutes_projection" in p and p["minutes_projection"] is None for p in plays)
    assert all("risk_flags" in p and isinstance(p["risk_flags"], list) for p in plays)


def test_parse_soccer_badge_attached_to_name_more_only():
    sample = """
Diego BarreraDemon
Córdoba SdE - Attacker
Diego Barrera
@ Atl. Tucumán Tue 7:15pm
3.5
Shots
More
""".strip()

    plays = parse_text(sample)
    assert len(plays) == 1
    assert plays[0]["player"] == "Diego Barrera"
    assert plays[0]["stat"] == "shots"
    assert plays[0]["direction"] == "higher"
    assert plays[0].get("demon") is True

    assert plays[0].get("starter_assumed") is None
    assert plays[0].get("minutes_projection") is None
    assert isinstance(plays[0].get("risk_flags"), list)
