# engine/run_daily_pipeline.py

import subprocess
import sys


def run_daily_pipeline():
    """
    Runs daily_pipeline.py as a subprocess.
    Hard-fails if pipeline fails.
    """

    print("\n🔄 Running Daily Pipeline...\n")

    result = subprocess.run(
        [sys.executable, "daily_pipeline.py"],
        capture_output=False,
        text=True
    )

    if result.returncode != 0:
        raise RuntimeError("Daily pipeline failed. No output was generated.")

    print("\n✅ Daily pipeline completed successfully.\n")
