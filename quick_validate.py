if __name__ == "__main__":
    raise RuntimeError("Direct execution forbidden. Use run_daily.py")

import json
import subprocess
import time


def quick_validate_top_n(n: int = 3, model: str = "tinyllama:1.1b-chat-q4_0"):
    """Validate only top N picks with ultra-fast settings using Ollama.

    This is intentionally simple and standalone so we can test Ollama
    responsiveness without touching the main pipeline.
    """

    # Load picks
    with open("picks_hydrated.json", "r", encoding="utf-8") as f:
        all_picks = json.load(f)

    top_picks = all_picks[:n]

    results = []

    for pick in top_picks:
        player = pick.get("player", "Unknown")
        stat = pick.get("stat", "")
        value = pick.get("mu", 0)
        team = pick.get("team", "UNK")

        print(f"\n🔍 Validating {player}...")

        # Ultra-minimal prompt for speed
        prompt = f"NBA check: {player} avg {value} {stat} for {team} reasonable? Yes/No"

        try:
            start = time.time()

            result = subprocess.run(
                ["ollama", "run", model, prompt],
                capture_output=True,
                text=True,
                timeout=10,  # 10 seconds max
            )

            elapsed = time.time() - start

            if result.returncode == 0:
                response = (result.stdout or "").strip()
                print(f"   ✅ Response ({elapsed:.1f}s): {response}")

                lower = response.lower()
                if "no" in lower or "invalid" in lower:
                    status = "INVALID"
                elif "yes" in lower or "valid" in lower:
                    status = "VALID"
                else:
                    status = "UNCLEAR"

                results.append(
                    {
                        "player": player,
                        "status": status,
                        "response": response[:100],
                        "time_seconds": round(elapsed, 1),
                    }
                )
            else:
                err = (result.stderr or "").strip()
                print(f"   ❌ Ollama error: {err[:100]}")
                results.append(
                    {
                        "player": player,
                        "status": "ERROR",
                        "error": err[:200],
                    }
                )

        except subprocess.TimeoutExpired:
            print("   ⏰ TIMEOUT after 10s")
            results.append({"player": player, "status": "TIMEOUT"})
        except Exception as e:  # noqa: BLE001
            print(f"   ❌ Exception: {e}")
            results.append({"player": player, "status": "ERROR", "error": str(e)})

    with open("quick_validation.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print("\n📊 Summary:")
    for r in results:
        print(f"   {r['player']}: {r['status']}")

    return results


if __name__ == "__main__":
    quick_validate_top_n(3, "tinyllama:1.1b-chat-q4_0")
