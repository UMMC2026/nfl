"""
Example: Using SmartParlayBuilder in menu or standalone script
- Shows how to use gates + correlation checks for safe parlay construction
"""
from integrations.parlay_constructor import SmartParlayBuilder
from types import SimpleNamespace

# Example candidate legs (normally loaded from your slate/prop ingestion)
candidate_legs = [
    SimpleNamespace(player='Jokić', stat='REB', line=12.5, direction='OVER', player_role='STARTER', minutes_prob=0.98, stat_variance=1.0, game_script_risk='LOW', edge=0.72, game_id='DEN_LAL'),
    SimpleNamespace(player='Curry', stat='PTS', line=26.5, direction='OVER', player_role='STARTER', minutes_prob=0.97, stat_variance=1.1, game_script_risk='LOW', edge=0.70, game_id='GSW_UTA'),
    SimpleNamespace(player='Tatum', stat='REB', line=8.5, direction='OVER', player_role='STARTER', minutes_prob=0.96, stat_variance=1.0, game_script_risk='LOW', edge=0.66, game_id='BOS_MIA'),
    SimpleNamespace(player='Kornet', stat='REB', line=5.5, direction='OVER', player_role='BENCH', minutes_prob=0.55, stat_variance=1.7, game_script_risk='LOW', edge=0.52, game_id='BOS_MIA'),
    SimpleNamespace(player='Markkanen', stat='PTS', line=25.5, direction='OVER', player_role='STARTER', minutes_prob=0.93, stat_variance=1.2, game_script_risk='HIGH', edge=0.68, game_id='UTA_LAC'),
    SimpleNamespace(player='Filipowski', stat='PTS', line=15.5, direction='UNDER', player_role='BENCH', minutes_prob=0.60, stat_variance=1.5, game_script_risk='HIGH', edge=0.54, game_id='UTA_LAC'),
]

builder = SmartParlayBuilder(min_edge=0.65, max_size=3)
parlay, status, reason = builder.build_parlay(candidate_legs)

print("\n=== SMART PARLAY CONSTRUCTOR DEMO ===\n")
if status == 'SUCCESS':
    print("SAFE PARLAY FOUND:")
    for leg in parlay:
        print(f"  - {leg.player} {leg.stat} {leg.direction} {leg.line} (Edge: {leg.edge:.2f})")
else:
    print(f"NO SAFE PARLAY: {reason}")

# --- Integration in NBA_MENU.py ---
# In your menu handler for Option 7:
'''
def run_ai_parlay_optimizer(self):
    from integrations.parlay_constructor import SmartParlayBuilder
    from types import SimpleNamespace
    # Load your slate/props as list of dicts
    candidate_legs = [SimpleNamespace(**d) for d in self.load_current_slate()]
    builder = SmartParlayBuilder(min_edge=0.65, max_size=3)
    parlay, status, reason = builder.build_parlay(candidate_legs)
    if status == 'SUCCESS':
        print("\nAI-APPROVED PARLAY:")
        for leg in parlay:
            print(f"  - {leg.player} {leg.stat} {leg.direction} {leg.line} (Edge: {leg.edge:.2f})")
    else:
        print(f"\nNo safe parlay: {reason}")
    input("\nPress Enter to continue...")
'''
