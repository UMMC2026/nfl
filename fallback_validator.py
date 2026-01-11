"""Fallback validator when Ollama is slow or unavailable.

This is intentionally simple, fast, and deterministic. It never calls
Ollama and returns immediately with conservative flags.
"""


class FallbackValidator:
    """Always-available validator with conservative defaults."""

    @staticmethod
    def quick_validate(pick):
        """Cheap validation that never times out.

        Returns a small dict with status/confidence/corrected_team.
        """

        player = pick.get("player", "").lower()
        stat = pick.get("stat", "").lower()
        value = pick.get("mu", 0)
        team = pick.get("team", "").upper()

        team_map = {
            "jonas valanciunas": "NOP",
            "giannis antetokounmpo": "MIL",
            "jalen brunson": "NYK",
            "joel embiid": "PHI",
            "nikola jokic": "DEN",
            "stephen curry": "GSW",
            "lebron james": "LAL",
        }

        correct_team = team_map.get(player, team)
        team_valid = team == correct_team or team == "UNK"

        stat_ranges = {
            "points": (0, 50),
            "rebounds": (0, 25),
            "assists": (0, 15),
            "pts+reb+ast": (0, 80),
        }

        stat_valid = True
        for stat_name, (min_val, max_val) in stat_ranges.items():
            if stat_name in stat:
                if value < min_val or value > max_val:
                    stat_valid = False
                    break

        if not team_valid and not stat_valid:
            status = "INVALID"
            confidence = 0.8
        elif not team_valid or not stat_valid:
            status = "QUESTIONABLE"
            confidence = 0.6
        else:
            status = "VALID"
            confidence = 0.9

        return {
            "status": status,
            "confidence": confidence,
            "corrected_team": correct_team if not team_valid else None,
            "source": "fallback_validator",
            "response_time_ms": 1,
        }
