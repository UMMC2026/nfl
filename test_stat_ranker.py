"""Quick test for stat_rank_explainer module."""
import sys
sys.path.insert(0, ".")

from analysis.nba.stat_rank_explainer import rank_picks_by_stat, format_top5_for_display
import json
from pathlib import Path

print('='*70)
print('  STAT RANK EXPLAINER TEST')
print('='*70)

# Load latest
out_dir = Path('outputs')
risk_files = sorted(out_dir.glob('*RISK_FIRST*.json'), key=lambda p: p.stat().st_mtime, reverse=True)
latest = risk_files[0]
print(f'Loading: {latest.name}')

with open(latest, 'r', encoding='utf-8') as f:
    data = json.load(f)

picks = data.get('results', [])
print(f'Found {len(picks)} picks')

# Run ranking
result = rank_picks_by_stat(picks)

# Display
print(format_top5_for_display(result))

print(f'\nTotal analyzed: {result.total_picks_analyzed}')
print(f'Stats with data: {result.stats_with_data}')
print(f'Coverage flags: {result.coverage_flags}')
