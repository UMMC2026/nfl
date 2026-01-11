import subprocess
import time
import json


def diagnose_ollama():
    """Diagnose why Ollama might be timing out or failing."""

    tests = [
        ("Basic echo", "echo hello"),
        ("Ollama list", "ollama list"),
        ("Ollama pull tinyllama", "ollama pull tinyllama:1.1b-chat-q4_0"),
        ("Simple query (5s)", "ollama run tinyllama:1.1b-chat-q4_0 'NBA teams? Answer: LAL'"),
        (
            "Player query (10s)",
            "ollama run tinyllama:1.1b-chat-q4_0 'Jonas Valanciunas team? Answer: NOP'",
        ),
    ]

    results = []

    for test_name, command in tests:
        print(f"\n🔧 Testing: {test_name}")
        print(f"   Command: {command}")

        try:
            start = time.time()

            if command.startswith("ollama"):
                parts = command.split()
                result = subprocess.run(
                    parts,
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
            else:
                result = subprocess.run(
                    command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=5,
                )

            elapsed = time.time() - start

            if result.returncode == 0:
                out = (result.stdout or "").strip()
                print(f"   ✅ SUCCESS ({elapsed:.1f}s)")
                print(f"   Output: {out[:100]}...")
                results.append(
                    {
                        "test": test_name,
                        "status": "success",
                        "time": elapsed,
                        "output": out[:200],
                    }
                )
            else:
                err = (result.stderr or "").strip()
                print(f"   ❌ FAILED ({elapsed:.1f}s)")
                print(f"   Error: {err[:100]}")
                results.append(
                    {
                        "test": test_name,
                        "status": "failed",
                        "error": err[:200],
                    }
                )

        except subprocess.TimeoutExpired:
            print("   ⏰ TIMEOUT")
            results.append({"test": test_name, "status": "timeout"})
        except Exception as e:  # noqa: BLE001
            print(f"   💥 EXCEPTION: {e}")
            results.append(
                {"test": test_name, "status": "exception", "error": str(e)}
            )

    with open("ollama_diagnosis.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print("\n📋 Diagnosis complete. Results saved to ollama_diagnosis.json")

    success = [r for r in results if r["status"] == "success"]
    print(f"\n📊 Summary: {len(success)}/{len(tests)} tests passed")

    return results


if __name__ == "__main__":
    diagnose_ollama()
