"""validate_cfb_output.py

Wrapper around validate_output.py for CFB with adjusted tolerances.
"""
import argparse
import json
import os
import sys
from datetime import datetime

# Import the validation function directly
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from scripts import validate_output

DEFAULT_CFB_CONFIG = {
    "cooldown_minutes": 60,
    "caps": {
        "core_max": 0.60,
        "alt_max": 0.55,
        "td_max": 0.45
    },
    "primary_tiers": ["SLAM", "STRONG"]
}


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--edges", required=True)
    p.add_argument("--allow-time-skip", action="store_true")
    args = p.parse_args(argv)

    with open(args.edges, 'r') as fh:
        edges = json.load(fh)

    ok, errors = validate_output.validate_edges(edges, config=DEFAULT_CFB_CONFIG, allow_time_skip=args.allow_time_skip)
    if not ok:
        print({"STATUS": "ABORTED", "REASON": errors})
        return 1
    print({"STATUS": "OK", "MSG": "CFB validation passed"})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())