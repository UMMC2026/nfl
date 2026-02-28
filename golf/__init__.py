"""
Golf/PGA Analytics Module
=========================
Strokes Gained modeling, tournament simulations, and prop generation.

Supports:
- Outright winner probabilities
- Top 5/10/20 finish props
- Make/miss cut props
- Head-to-head matchups
- Round scoring unders/overs

Data Sources:
- DataGolf API (Strokes Gained, rankings, course fit)
- Weather API (wind, temperature)
- Manual slate entry (Underdog props)
"""

from pathlib import Path

GOLF_DIR = Path(__file__).parent
INPUTS_DIR = GOLF_DIR / "inputs"
OUTPUTS_DIR = GOLF_DIR / "outputs"
DATA_DIR = GOLF_DIR / "data"
CONFIG_DIR = GOLF_DIR / "config"

# Ensure directories exist
for d in [INPUTS_DIR, OUTPUTS_DIR, DATA_DIR, CONFIG_DIR]:
    d.mkdir(exist_ok=True)
