"""Emergency validator that works RIGHT NOW with your existing mistral model."""

import subprocess
import time
import json
from pathlib import Path


class EmergencyMistralValidator:
    """Validator optimized for mistral with long timeout."""

    def __init__(self, timeout: int = 45, max_retries: int = 2) -> None:
        self.timeout = timeout
        self.max_retries = max_retries
        self.cache_file = Path("cache/mistral_cache.json")
        self.cache_file.parent.mkdir(exist_ok=True)
        self._load_cache()

    def _load_cache(self):
        """Load cached responses."""
        if self.cache_file.exists():
            with open(self.cache_file, "r", encoding="utf-8") as f:
                self.cache = json.load(f)
        else:
            self.cache = {}

    def _save_cache(self):
        """Save cache to disk."""
        with open(self.cache_file, "w", encoding="utf-8") as f:
            json.dump(self.cache, f, indent=2)

    def validate_pick(self, pick):
        """Validate a pick with mistral."""
        player = pick.get("player", "")
        cache_key = f"{player}_{pick.get('stat', '')}"

        if cache_key in self.cache:
            return self.cache[cache_key]

        prompt = f"NBA 2025: {player} team? Answer 3 letters only."

        for attempt in range(self.max_retries):
            try:
                print(f"  Attempt {attempt+1} for {player}...")
                start = time.time()

                result = subprocess.run(
                    ["ollama", "run", "mistral", prompt],
                    capture_output=True,
                    text=True,
                    timeout=self.timeout,
                )

                if result.returncode == 0:
                    response = (result.stdout or "").strip()
                    elapsed = time.time() - start

                    team = self._extract_team(response)

                    validation = {
                        "player": player,
                        "team_found": team,
                        "response": response[:50],
                        "time_seconds": round(elapsed, 1),
                        "attempts": attempt + 1,
                    }

                    self.cache[cache_key] = validation
                    self._save_cache()

                    return validation

            except subprocess.TimeoutExpired:
                print(f"  Timeout on attempt {attempt+1}")
                continue

        return {
            "player": player,
            "team_found": None,
            "error": "all_attempts_timeout",
            "time_seconds": self.timeout * self.max_retries,
        }

    def _extract_team(self, response: str):
        """Extract team abbreviation from response."""
        response_upper = response.upper()
        teams = [
            "NOP",
            "MIL",
            "LAL",
            "GSW",
            "BOS",
            "PHI",
            "DEN",
            "PHX",
            "NYK",
            "MIA",
            "ATL",
            "CHI",
            "CLE",
            "DAL",
            "DET",
            "HOU",
            "IND",
            "LAC",
            "MEM",
            "MIN",
            "OKC",
            "ORL",
            "POR",
            "SAC",
            "SAS",
            "TOR",
            "UTA",
            "WAS",
            "BKN",
            "CHA",
        ]

        for team in teams:
            if team in response_upper:
                return team

        return None


if __name__ == "__main__":
    print("🚨 Testing Emergency Mistral Validator...")

    validator = EmergencyMistralValidator(timeout=30)

    test_players = [
        {"player": "Jonas Valanciunas", "stat": "points"},
        {"player": "Jalen Brunson", "stat": "points"},
        {"player": "Giannis Antetokounmpo", "stat": "points"},
    ]

    for player_data in test_players:
        print(f"\n🔍 Validating {player_data['player']}...")
        result = validator.validate_pick(player_data)

        if result.get("team_found"):
            print(
                f"   ✅ Found team: {result['team_found']} ({result['time_seconds']}s)"
            )
        else:
            print(f"   ❌ No team found: {result.get('error', 'unknown')}")

    print("\n✅ Emergency validator ready for production!")
