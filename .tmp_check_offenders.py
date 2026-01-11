from engine.normalize_picks import normalize_picks
from engine.schedule_gate import get_today_games_from_espn, gate_today_games
from engine.roster_gate import build_active_roster_map, gate_active_roster
from engine.collapse_edges import dedupe_player_props, collapse_edges
from engine.score_edges import score_edges
from engine.resolve_player_primaries import resolve_player_primaries
from engine.render_gate import TIER_THRESHOLDS
from utils.io import load_json

picks = load_json('picks_hydrated.json')
normalized = normalize_picks(picks)
today_games = get_today_games_from_espn('NBA')
scheduled = gate_today_games(normalized, today_games)
roster_map = build_active_roster_map('NBA')
roster_fixed = gate_active_roster(scheduled, roster_map) if roster_map else scheduled

deduped = dedupe_player_props(roster_fixed)
collapsed = collapse_edges(deduped)
scored = score_edges(collapsed)
resolved = resolve_player_primaries(scored)

offenders = []
for p in resolved:
    tier = p.get('confidence_tier')
    prob = p.get('probability')
    thresh = TIER_THRESHOLDS.get(tier)
    if tier and thresh is not None and prob < thresh:
        offenders.append((p['player'], p['probability'], tier, thresh, p['edge_id']))

print('offenders count', len(offenders))
for o in offenders:
    print(o)
