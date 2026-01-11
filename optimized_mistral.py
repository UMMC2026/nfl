"""Use mistral with optimized settings for quick testing."""

import json
import subprocess
import time


def validate_with_mistral():
    """Use mistral with optimized settings."""

    with open("picks_hydrated.json", "r", encoding="utf-8") as f:
        picks = json.load(f)

    test_picks = picks[:2]

    results = []

    for pick in test_picks:
        player = pick.get("player", "Unknown")

        print(f"\n🔍 Validating {player} with mistral...")

        prompt = f"Q: {player} NBA team 2025-26? A:"

        try:
            start = time.time()

            result = subprocess.run(
                ["ollama", "run", "mistral", prompt],
                capture_output=True,
                text=True,
                timeout=30,
            )

            elapsed = time.time() - start

            if result.returncode == 0:
                response = (result.stdout or "").strip()
                print(f"   ✅ Response in {elapsed:.1f}s: {response[:50]}...")

                team = None
                for abbr in [
                    "NOP",
                    "MIL",
                    "LAL",
                    "GSW",
                    "BOS",
                    "PHI",
                    "DEN",
                    "PHX",
                ]:
                    if abbr in response.upper():
                        team = abbr
                        break

                results.append(
                    {
                        "player": player,
                        "response": response[:100],
                        "team_found": team,
                        "time_seconds": round(elapsed, 1),
                        "success": True,
                    }
                )
            else:
                err = (result.stderr or "").strip()
                print(f"   ❌ Error: {err[:100]}")
                results.append(
                    {
                        "player": player,
                        "success": False,
                        "error": err[:100],
                    }
                )

        except subprocess.TimeoutExpired:
            print("   ⏰ Timeout after 30s")
            results.append({"player": player, "success": False, "error": "timeout"})

    with open("mistral_test.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    success = [r for r in results if r.get("success")]
    print(f"\n📊 Summary: {len(success)}/{len(results)} successful")
    return results


if __name__ == "__main__":
    validate_with_mistral()
