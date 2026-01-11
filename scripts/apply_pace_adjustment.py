"""
Add pace adjustment multiplier for opponent context
Currently uses static values - TODO: fetch real pace from ESPN/NBA API
"""
import pandas as pd

DATE = "2026-01-07"
FILE = f"data/features/props_clean_{DATE}.csv"

# League average pace (possessions per 48 min)
LEAGUE_AVG_PACE = 99.0

# Team pace estimates (TODO: fetch from NBA API)
# Current values are 2023-24 season estimates
TEAM_PACE = {
    "ATL": 100.5,
    "BOS": 98.7,
    "BKN": 99.1,
    "CHA": 100.8,
    "CHI": 97.3,
    "CLE": 96.8,
    "DAL": 98.5,
    "DEN": 97.9,
    "DET": 99.6,
    "GS": 100.2,
    "GSW": 100.2,
    "HOU": 101.3,
    "IND": 101.7,
    "LAC": 98.4,
    "LAL": 99.8,
    "MEM": 100.9,
    "MIA": 96.5,
    "MIL": 97.1,
    "MIN": 99.4,
    "NO": 101.1,
    "NOP": 101.1,
    "NY": 96.2,
    "NYK": 96.2,
    "OKC": 98.6,
    "ORL": 95.8,
    "PHI": 97.5,
    "PHX": 100.4,
    "POR": 99.7,
    "SA": 99.2,
    "SAC": 102.1,
    "TOR": 98.3,
    "UTAH": 99.5,
    "UTA": 99.5,
    "WSH": 100.6,
    "WAS": 100.6,
}

print(f"⚡ Applying pace adjustment: {FILE}")
df = pd.read_csv(FILE)

def pace_multiplier(row):
    """Calculate pace adjustment factor"""
    opp = row.get("opponent", "UNK")
    if opp == "UNK" or opp not in TEAM_PACE:
        return 1.0
    return TEAM_PACE[opp] / LEAGUE_AVG_PACE

df["pace_mult"] = df.apply(pace_multiplier, axis=1)

# Count how many got adjusted
adjusted = (df["pace_mult"] != 1.0).sum()
print(f"   Pace adjusted: {adjusted}/{len(df)} props")
print(f"   Range: {df['pace_mult'].min():.3f} - {df['pace_mult'].max():.3f}")

df.to_csv(FILE, index=False)
print(f"✅ Pace adjustment complete")
