# Run this once after installing requirements-extras.txt
# It prints columns so you can confirm name/stat fields for nflreadpy in your environment.
try:
    import nflreadpy as nfl
except Exception as e:
    raise SystemExit("nflreadpy not installed. Run: pip install -r requirements-extras.txt") from e

df = nfl.load_player_stats([2024])
print("columns:", df.columns)
print(df.head(5))
