"""Parse Underdog paste, resolve teams, merge with OddsAPI, run pipeline."""
import sys, json
sys.path.insert(0, ".")

from sports.cbb.ingest.parse_cbb_paste import parse_text, save_slate
from sports.cbb.ingest.cbb_data_provider import CBBStatsCache, CBBDataProvider
from pathlib import Path

PASTE = """
athlete or team avatar
Darryn Peterson
KU vs ARIZ - 8:00PM CST


20.5
Points

Higher

Lower

26.5
Pts + Rebs + Asts

Higher

Lower

3.5
Rebounds

Higher

Lower

1.5
Assists

Higher

Lower

athlete or team avatar
Flory Bidunga
KU vs ARIZ - 8:00PM CST


13.5
Points

Higher

Lower

21.5
Pts + Rebs + Asts

Higher

Lower

7.5
Rebounds

Higher

Lower

1.5
Assists

Higher

Lower

athlete or team avatar
Lamar Wilkerson
IND vs ORE - 7:30PM CST


21.5
Points

Higher

Lower

27.5
Pts + Rebs + Asts

Higher

Lower

3.5
Rebounds

Higher

Lower

2.5
Assists

Higher

Lower

athlete or team avatar
Dillon Mitchell
SJU vs XAV - 5:30PM CST


11.5
Points

Higher

Lower

23.5
Pts + Rebs + Asts

Higher

Lower

8.5
Rebounds

Higher

Lower

3.5
Assists

Higher

Lower

athlete or team avatar
Quadir Copeland
NCST @ LOU - 6:00PM CST


13.5
Points

Higher

Lower

24.5
Pts + Rebs + Asts

Higher

Lower

3.5
Rebounds

Higher

Lower

7.5
Assists

Higher

Lower

athlete or team avatar
Brayden Burries
ARIZ @ KU - 8:00PM CST


15.5
Points

Higher

Lower

22.5
Pts + Rebs + Asts

Higher

Lower

5.5
Rebounds

Higher

Lower

2.5
Assists

Higher

Lower

athlete or team avatar
Melvin Council
KU vs ARIZ - 8:00PM CST


13.5
Points

Higher

Lower

22.5
Pts + Rebs + Asts

Higher

Lower

5.5
Rebounds

Higher

Lower

4.5
Assists

Higher

Lower

athlete or team avatar
Zuby Ejiofor
SJU vs XAV - 5:30PM CST


16.5
Points

Higher

Lower

29.5
Pts + Rebs + Asts

Higher

Lower

8.5
Rebounds

Higher

Lower

3.5
Assists

Higher

Lower

athlete or team avatar
Koa Peat
ARIZ @ KU - 8:00PM CST


13.5
Points

Higher

Lower

20.5
Pts + Rebs + Asts

Higher

Lower

5.5
Rebounds

Higher

Lower

2.5
Assists

Higher

Lower

athlete or team avatar
Tucker DeVries
IND vs ORE - 7:30PM CST


13.5
Points

Higher

Lower

22.5
Pts + Rebs + Asts

Higher

Lower

7.5
Rebounds

Higher

Lower

2.5
Assists

Higher

Lower
"""

# Step 1: Parse
print("=" * 70)
print("STEP 1: PARSE UNDERDOG PASTE")
print("=" * 70)
props = parse_text(PASTE)
print(f"Parsed: {len(props)} props")

# Show player/team assignments (before resolution)
from collections import Counter
players_before = {}
for p in props:
    key = p["player"]
    if key not in players_before:
        players_before[key] = p.get("team", "UNK")
print("\nPre-resolution team assignments:")
for player, team in sorted(players_before.items()):
    print(f"  {player:22s} → {team}")

# Step 2: Roster-based team resolution
print("\n" + "=" * 70)
print("STEP 2: RESOLVE TEAMS VIA ESPN ROSTERS")
print("=" * 70)

cache = CBBStatsCache()
provider = CBBDataProvider()

# Collect unique matchups
matchups = set()
for p in props:
    team = p.get("team", "UNK")
    opp = p.get("opponent", "UNK")
    if team != "UNK" and opp != "UNK":
        matchups.add((team, opp))
    elif team != "UNK":
        matchups.add((team, "UNK"))

# Fetch rosters for all teams
all_teams = set()
for t1, t2 in matchups:
    all_teams.add(t1)
    if t2 != "UNK":
        all_teams.add(t2)

rosters = {}  # abbr → set of player names (upper)
for abbr in sorted(all_teams):
    norm = cache._normalize_team(abbr)
    try:
        team_id = provider.espn.search_team(norm)
        if team_id:
            roster = provider.espn.get_team_roster(team_id)
            names = set()
            for rp in roster:
                name = getattr(rp, "name", None) or str(rp)
                if name:
                    names.add(name.strip().upper())
            rosters[norm] = names
            print(f"  {abbr:5s} → {norm:5s} ({team_id}): {len(names)} players")
        else:
            print(f"  {abbr:5s} → {norm:5s}: NOT FOUND")
    except Exception as e:
        print(f"  {abbr:5s} → ERROR: {e}")

# Resolve each prop's team
resolved = 0
for p in props:
    player_upper = p["player"].strip().upper()
    assigned_team = p.get("team", "UNK")
    opp_team = p.get("opponent", "UNK")
    
    # Check assigned team's roster first
    norm_assigned = cache._normalize_team(assigned_team) if assigned_team != "UNK" else ""
    norm_opp = cache._normalize_team(opp_team) if opp_team != "UNK" else ""
    
    found_on_assigned = player_upper in rosters.get(norm_assigned, set())
    found_on_opp = player_upper in rosters.get(norm_opp, set())
    
    if found_on_assigned:
        p["team"] = norm_assigned
        resolved += 1
    elif found_on_opp:
        p["team"] = norm_opp
        p["opponent"] = norm_assigned  # Swap
        resolved += 1
    else:
        # Try last-name match
        last = player_upper.split()[-1] if player_upper.split() else ""
        for abbr, roster in rosters.items():
            if any(last and r.split()[-1] == last for r in roster if r.split()):
                p["team"] = abbr
                resolved += 1
                break
        else:
            p["team"] = norm_assigned or assigned_team

print(f"\nResolved: {resolved}/{len(props)} players")

# Show post-resolution
players_after = {}
for p in props:
    key = p["player"]
    if key not in players_after:
        players_after[key] = p.get("team", "UNK")
print("\nPost-resolution team assignments:")
for player, team in sorted(players_after.items()):
    print(f"  {player:22s} → {team}")

# Step 3: Load existing OddsAPI data (NCST @ LOU)
print("\n" + "=" * 70)
print("STEP 3: MERGE WITH ODDSAPI DATA")
print("=" * 70)

existing = []
latest_path = Path("sports/cbb/inputs/cbb_slate_latest.json")
if latest_path.exists():
    d = json.load(open(latest_path))
    existing = d.get("props", d) if isinstance(d, dict) else d
    print(f"Existing slate: {len(existing)} props")
    
    # Count existing players
    existing_players = set(p.get("player", "") for p in existing)
    print(f"Existing players: {', '.join(sorted(existing_players))}")

# Dedupe: remove Quadir Copeland from paste (already in OddsAPI with better lines)
paste_players = set(p["player"] for p in props)
overlap = paste_players & existing_players if existing else set()
if overlap:
    print(f"\nOverlapping players: {overlap}")
    # Keep OddsAPI version (more complete), remove from paste
    props = [p for p in props if p["player"] not in overlap]
    print(f"After removing overlap: {len(props)} paste props")

# Merge
combined = existing + props
print(f"\nCombined slate: {len(combined)} props")

# Stats summary
games = set()
for p in combined:
    t = p.get("team", "UNK")
    o = p.get("opponent", "UNK")
    if t != "UNK":
        games.add(tuple(sorted([t, o])))
stat_counts = Counter(p.get("stat", "?") for p in combined)
print(f"Games: {len(games)}")
print("Stats:")
for s, c in stat_counts.most_common():
    print(f"  {s}: {c}")

# Step 4: Save combined slate
print("\n" + "=" * 70)
print("STEP 4: SAVE & RUN PIPELINE")
print("=" * 70)
INPUTS_DIR = Path("sports/cbb/inputs")
output_path = save_slate(combined, INPUTS_DIR, filename_prefix="cbb_slate_combined")
print(f"Saved: {output_path.name}")

# Step 5: Run pipeline
from sports.cbb.cbb_main import run_full_pipeline
result = run_full_pipeline(skip_ingest=True)

# Step 6: Show results
import glob, os
f = max(glob.glob("sports/cbb/outputs/cbb_RISK_FIRST_*.json"), key=os.path.getmtime)
d = json.load(open(f))
picks = d.get("picks", [])
actionable = [p for p in picks if p.get("tier") in ("STRONG", "LEAN")]
print(f"\n{'='*90}")
print(f"FINAL: {len(actionable)} actionable / {len(picks)} total")
print(f"{'='*90}")
for p in sorted(actionable, key=lambda x: (-{"STRONG":2,"LEAN":1}.get(x.get("tier",""),0), -x.get("probability",0))):
    t = p.get("tier","?")
    pl = p.get("player","?")
    tm = p.get("team","?")
    st = p.get("stat","?")
    d_ = p.get("direction","?")
    ln = p.get("line",0)
    pr = p.get("probability",0)
    mu = p.get("player_mean",0)
    sr = p.get("mean_source","?")
    delta = ((mu - ln) / ln * 100) if ln > 0 else 0
    print(f"  {t:6s} | {pl:22s} ({tm:5s}) {st:22s} {d_:6s} line={ln:5.1f} prob={pr:.1f}% mu={mu:.1f} d={delta:+.0f}% [{sr}]")
