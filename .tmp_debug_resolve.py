from engine.normalize_picks import normalize_picks
from engine.schedule_gate import get_today_games_from_espn, gate_today_games
from engine.roster_gate import build_active_roster_map, gate_active_roster
from engine.collapse_edges import dedupe_player_props, collapse_edges
from engine.score_edges import score_edges
from engine.resolve_player_primaries import resolve_player_primaries
from utils.io import load_json

picks = load_json('picks_hydrated.json')
print('loaded', len(picks), 'picks')
normalized = normalize_picks(picks)
print('normalized', len(normalized))

today_games = get_today_games_from_espn('NBA')
print('today games fetched', len(today_games))
scheduled = gate_today_games(normalized, today_games)
print('scheduled', len(scheduled))

roster_map = build_active_roster_map('NBA')
if roster_map:
    print('roster_map size', len(roster_map))
    roster_fixed = gate_active_roster(scheduled, roster_map)
else:
    print('no roster map, skipping')
    roster_fixed = scheduled

print('deduping')
deduped = dedupe_player_props(roster_fixed)
print('deduped', len(deduped))

collapsed = collapse_edges(deduped)
print('collapsed', len(collapsed))

scored = score_edges(collapsed)
print('scored', len(scored))

resolved = resolve_player_primaries(scored)
print('resolved', len(resolved))

# find Mark Williams
for p in resolved:
    if p.get('player','').lower().startswith('mark will'):
        import pprint
        pprint.pprint(p)
        break
else:
    print('Mark Williams not found in resolved')
