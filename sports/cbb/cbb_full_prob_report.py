"""
cbb_full_prob_report.py — Generate a full CBB probability report with both HIGHER and LOWER for every prop/stat line.
"""
import json
from pathlib import Path
from collections import defaultdict

# Load the latest risk-first output
outputs_dir = Path(__file__).parent / "outputs"
risk_json = sorted(outputs_dir.glob("cbb_RISK_FIRST_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[0]
with open(risk_json, "r", encoding="utf-8") as f:
    data = json.load(f)

# Group by player/stat/line
props = defaultdict(dict)
for pick in data["picks"]:
    key = (pick["player"], pick["stat"], pick["line"])
    props[key][pick["direction"]] = pick

# Write report
lines = []
lines.append("CBB FULL PROBABILITY REPORT\n============================\n")
for (player, stat, line), dirs in sorted(props.items()):
    lower = dirs.get("lower")
    higher = dirs.get("higher")
    if not lower and not higher:
        continue
    mu = lower["player_mean"] if lower else higher["player_mean"]
    mu_src = lower.get("mean_source") if lower else higher.get("mean_source")
    lines.append(f"{player} {stat} {line}")
    if higher:
        lines.append(f"  HIGHER: {higher['probability']*100:.1f}% | Tier: {higher['tier']} | Proj: {mu} ({higher.get('mean_source','?')})")
    if lower:
        lines.append(f"  LOWER:  {lower['probability']*100:.1f}% | Tier: {lower['tier']} | Proj: {mu} ({lower.get('mean_source','?')})")
    lines.append("")


output_path = outputs_dir / "cbb_full_prob_report.txt"
with open(output_path, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))

print("[OK] cbb_full_prob_report.txt generated.")
