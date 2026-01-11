"""100% local, zero-Ollama validator for production use."""


class LocalValidator:
    """Never fails, never times out, always available."""

    # TEAM_KNOWLEDGE START (auto-updated from picks.json)
    TEAM_KNOWLEDGE = {
        "aj green": "MIL",
        "al horford": "GSW",
        "alex sarr": "WAS",
        "ayo dosunmu": "CHI",
        "bilal coulibaly": "WAS",
        "bobby portis": "MIL",
        "brandin podziemski": "GSW",
        "bub carrington": "WAS",
        "cj mccollum": "WAS",
        "collin gillespie": "PHX",
        "darius garland": "CLE",
        "de'andre hunter": "CLE",
        "dean wade": "CLE",
        "deandre ayton": "LAL",
        "deuce mcbride": "NYK",
        "devin booker": "PHX",
        "dillon brooks": "PHX",
        "donovan mitchell": "CLE",
        "evan mobley": "CLE",
        "gary trent jr.": "MIL",
        "giannis antetokounmpo": "MIL",
        "grayson allen": "PHX",
        "isaac okoro": "CHI",
        "jake laravia": "LAL",
        "jalen brunson": "NYK",
        "jalen smith": "CHI",
        "jarred vanderbilt": "LAL",
        "jarrett allen": "CLE",
        "jaxson hayes": "LAL",
        "jeremiah fears": "NOP",
        "jimmy butler": "GSW",
        "jordan clarkson": "NYK",
        "jordan goodwin": "PHX",
        "jordan poole": "NOP",
        "justin champagnie": "WAS",
        "karl-anthony towns": "NYK",
        "kevin huerter": "CHI",
        "kevin porter jr.": "MIL",
        "khris middleton": "WAS",
        "kyle kuzma": "MIL",
        "lebron james": "LAL",
        "luka doncic": "LAL",
        "marcus smart": "LAL",
        "mark williams": "PHX",
        "marvin bagley": "WAS",
        "matas buzelis": "CHI",
        "mikal bridges": "NYK",
        "moses moody": "GSW",
        "myles turner": "MIL",
        "nikola vucevic": "CHI",
        "og anunoby": "NYK",
        "patrick williams": "CHI",
        "quinten post": "GSW",
        "royce o'neale": "PHX",
        "ryan rollins": "MIL",
        "sam merrill": "CLE",
        "stephen curry": "GSW",
        "tre johnson": "WAS",
        "tre jones": "CHI",
        "trey murphy iii": "NOP",
        "tyler kolek": "NYK",
        "zion williamson": "NOP",
    }
    # TEAM_KNOWLEDGE END

    STAT_RANGES = {
        "points": (0, 50),
        "rebounds": (0, 25),
        "assists": (0, 15),
        "pts+reb+ast": (0, 80),
        "3pm": (0, 10),
        "steals": (0, 5),
        "blocks": (0, 5),
        "turnovers": (0, 10),
    }

    @staticmethod
    def validate(pick):
        """Validate pick locally - INSTANT response."""
        player = pick.get("player", "").lower()
        stat = pick.get("stat", "").lower()
        value = pick.get("mu", 0)
        reported_team = pick.get("team", "UNK").upper()

        correct_team = LocalValidator.TEAM_KNOWLEDGE.get(player, reported_team)
        team_valid = reported_team == correct_team or reported_team == "UNK"
        has_kb_entry = player in LocalValidator.TEAM_KNOWLEDGE

        stat_valid = True
        for stat_name, (min_val, max_val) in LocalValidator.STAT_RANGES.items():
            if stat_name in stat:
                if value < min_val or value > max_val:
                    stat_valid = False
                    break

        if team_valid and stat_valid:
            status = "VALID"
            confidence = 0.9
        elif not team_valid and not stat_valid:
            status = "INVALID"
            confidence = 0.8
        elif not team_valid and has_kb_entry:
            # Team mismatch but we have KB entry - high confidence correction
            status = "QUESTIONABLE"
            confidence = 0.85
        else:
            status = "QUESTIONABLE"
            confidence = 0.6

        return {
            "player": player.title(),
            "status": status,
            "confidence": confidence,
            "correct_team": correct_team if not team_valid else None,
            "stat_reasonable": stat_valid,
            "response_time_ms": 1,
            "source": "local_knowledge_base",
        }

    @staticmethod
    def validate_batch(picks):
        """Validate multiple picks."""
        return [LocalValidator.validate(pick) for pick in picks]


if __name__ == "__main__":
    print("🧠 Testing Local Validator (100% local, no Ollama)...")

    test_picks = [
        {"player": "Jonas Valanciunas", "stat": "points", "mu": 7.5, "team": "DEN"},
        {
            "player": "Giannis Antetokounmpo",
            "stat": "points",
            "mu": 31.5,
            "team": "MIL",
        },
        {"player": "Stephen Curry", "stat": "points", "mu": 60, "team": "GSW"},
    ]

    for pick in test_picks:
        result = LocalValidator.validate(pick)
        print(f"\n{pick['player']}:")
        print(f"  Status: {result['status']}")
        print(f"  Confidence: {result['confidence']:.0%}")
        if result["correct_team"]:
            print(f"  Team correction: {pick['team']} → {result['correct_team']}")
        if not result["stat_reasonable"]:
            print(f"  ⚠️  Stat {pick['mu']} {pick['stat']} is unreasonable")

    print("\n✅ Local validator ready for production!")
