# telegram/send.py

from utils.io import load_json
from engine.render_gate import render_gate


def send(bot):
    picks = load_json("outputs/validated_primary_edges.json")
    picks = render_gate(picks)

    for p in picks:
        if not p["is_primary"]:
            continue

        msg = (
            f"{p['player']} {p['direction']} {p['line']} {p['stat']} "
            f"{int(p['probability']*100)}% {p['confidence_tier']}"
        )
        bot.send_message(msg)
