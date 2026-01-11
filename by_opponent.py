# views/by_opponent.py

from utils.io import load_json
from engine.render_gate import render_gate


def view_by_opponent():
    picks = load_json("outputs/validated_primary_edges.json")
    picks = render_gate(picks)

    picks = [p for p in picks if p["is_primary"]]

    grouped = {}
    for p in picks:
        key = f"{p['team']} vs {p['opponent']}"
        grouped.setdefault(key, []).append(p)

    return grouped
