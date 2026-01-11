"""Quick test of rank functionality"""
import json
from ufa.models.schemas import PropPick
from ufa.analysis.prob import prob_hit

# Load picks
data = json.load(open('picks.json'))
print(f"Loaded {len(data)} picks")

# Test first pick
p = PropPick(**data[0])
print(f"First pick: {p.player} {p.stat} {p.line} {p.direction}")

# Since no recent_values, we need to provide them or use default
# Let's test with dummy recent values
test_pick = PropPick(
    league="NBA",
    player="Victor Wembanyama",
    team="SAS", 
    stat="points",
    line=25.5,
    direction="higher",
    recent_values=[22, 28, 25, 31, 19, 26, 30, 24, 27, 23]
)

prob = prob_hit(test_pick.line, test_pick.direction, recent_values=test_pick.recent_values)
print(f"P(hit) for {test_pick.player} {test_pick.stat} {test_pick.line} {test_pick.direction}: {prob:.4f}")
