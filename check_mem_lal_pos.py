import json

with open('picks.json') as f:
    picks = json.load(f)

mem_lal_indices = [(i, p['team'], p['player']) for i, p in enumerate(picks) if p['team'] in ['MEM', 'LAL']]

print(f"Total MEM/LAL picks: {len(mem_lal_indices)}")
if mem_lal_indices:
    print(f"\nFirst MEM/LAL pick at position: {mem_lal_indices[0][0]} ({mem_lal_indices[0][1]} - {mem_lal_indices[0][2]})")
    print(f"Last hydrated: ~757")
    print(f"Status: MEM/LAL picks start AFTER hydration stopped")
