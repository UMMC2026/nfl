import json
from pathlib import Path
out_dir = Path("outputs")
latest = sorted([f for f in out_dir.glob("*RISK_FIRST*.json") if "_STAT_RANKINGS" not in f.name], key=lambda p: p.stat().st_mtime, reverse=True)[0]
print(f"File: {latest.name}")
data = json.load(open(latest))
results = data.get("results", [])
for pick in results[:10]:
    arch = pick.get("nba_role_archetype", "NONE")
    conf = pick.get("effective_confidence", 0)
    stat = pick.get("stat", "?")
    decision = pick.get("decision", "?")
    print(f'{pick.get("player"):20} | {stat:15} | {arch:25} | conf={conf:5.1f}% | {decision}')
