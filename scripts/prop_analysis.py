"""Analyze props for JAX@IND and PIT@CLE games using ESPN stats.

Fixes applied:
- Explicit season/seasontype on ESPN gamelog endpoint
- Robust parsing of duplicate labels (YDS/TD in rushing vs receiving)
- Debug logging and hard guards for insufficient data
"""
import argparse
import json
import ssl
import sys
import urllib.request
import os

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

# Minimum games required to make a pick
MIN_GAMES_REQUIRED = 5

# Key players to analyze
players = {
    # JAX @ IND
    'Jonathan Taylor': 4242335,
    'Travis Etienne Jr.': 4241457,
    'Trevor Lawrence': 4360310,
    'Michael Pittman Jr.': 4241478,
    'Tyler Warren': 4567441,
    'Brian Thomas': 4697815,
    'Jakobi Meyers': 3116406,
    'Josh Downs': 4429013,
    'Brenton Strange': 4429160,
    'Alec Pierce': 4362628,
    # PIT @ CLE  
    'Aaron Rodgers': 8439,
    'Shedeur Sanders': 4432685,
    'Kenneth Gainwell': 4361579,
    'Jaylen Warren': 4372485,
    'Dylan Sampson': 4698966,
    'Jerry Jeudy': 4262921,
    'Harold Fannin': 4917389,
    'Pat Freiermuth': 4361411,
    'Myles Garrett': 3122132,
    'Adam Thielen': 16460,
    'Darnell Washington': 4430807,
}

# Ensure project root on sys.path for optional sports_quant imports
try:
    ROOT = os.path.dirname(os.path.dirname(__file__))
    if ROOT not in sys.path:
        sys.path.append(ROOT)
except Exception:
    pass

# --- Unified quant helpers (pregame/in-game scaffolding) ---
import math

def normal_cdf(x, mu, sigma):
    if sigma <= 0:
        sigma = 1e-6
    z = (x - mu) / (sigma * math.sqrt(2.0))
    return 0.5 * (1.0 + math.erf(-z))  # return right-tail by using -z

def prob_over(mean, std, line):
    # P(X > line) for Normal(mean,std)
    if std <= 0:
        std = 1e-6
    z = (line - mean) / (std * math.sqrt(2.0))
    return 0.5 * (1.0 - math.erf(z))

def prob_under(mean, std, line):
    return 1.0 - prob_over(mean, std, line)

def detect_regime(game_status=None, quarter=None, time_remaining=None):
    if isinstance(game_status, str):
        s = game_status.lower()
        if s in ("final", "post"):
            return "CLOSED"
        if s in ("in", "live"):
            return "INGAME"
    if quarter is not None:
        return "INGAME"
    return "PREGAME"

def regime_weights(regime):
    if regime == "PREGAME":
        return {"prior": 0.70, "state": 0.30}
    elif regime == "INGAME":
        return {"prior": 0.25, "state": 0.75}
    return {"prior": 0.0, "state": 0.0}

def compute_qa_flags(stats):
    flags = []
    g = stats.get('games') or 0
    if g < MIN_GAMES_REQUIRED:
        flags.append('low_sample')
    # Receiving anomalies
    recs = stats.get('receiving_REC', 0)
    rec_yds = stats.get('receiving_YDS', 0)
    if recs > 0 and rec_yds == 0:
        flags.append('rec_zero_yards_with_receptions')
    # Rushing anomalies
    rush_att = stats.get('rushing_CAR', 0)
    rush_yds = stats.get('rushing_YDS', 0)
    if rush_att > 0 and rush_yds == 0:
        flags.append('rush_zero_yards_with_attempts')
    # Passing plausibility check
    pass_yds = stats.get('passing_YDS', 0)
    pass_att = stats.get('passing_ATT', 0)
    if g > 0:
        avg_pyds = pass_yds / g
        avg_att = pass_att / g if pass_att else 0
        if avg_pyds > 0 and avg_pyds < 50 and avg_att > 15:
            flags.append('implausible_passing_stats')
    return flags

def _to_float(x):
    try:
        return float(str(x).replace(',', ''))
    except Exception:
        return None


def _parse_gamelog_totals(labels, totals):
    """Map ESPN gamelog labels/totals to unified keys.

    Handles duplicate labels by segmenting around 'REC' for non-QBs and by detecting
    passing fields for QBs (presence of 'CMP').
    """
    stats = {}
    # Normalize
    labels = list(labels or [])
    totals = list(totals or [])

    label_to_idx = {lab: i for i, lab in enumerate(labels) if lab not in (None, '')}

    if 'CMP' in label_to_idx:
        # QB totals
        for key, label in (
            ('passing_CMP', 'CMP'),
            ('passing_ATT', 'ATT'),
            ('passing_YDS', 'YDS'),
            ('passing_TD', 'TD'),
            ('passing_INT', 'INT'),
        ):
            idx = label_to_idx.get(label)
            if idx is not None and idx < len(totals):
                val = _to_float(totals[idx])
                if val is not None:
                    stats[key] = val
        # Some QB gamelog includes a 'CAR' (rushing attempts)
        idx = label_to_idx.get('CAR')
        if idx is not None and idx < len(totals):
            val = _to_float(totals[idx])
            if val is not None:
                stats['rushing_CAR'] = val
        return stats

    # Non-QB (RB/WR/TE): segment by REC block
    if 'REC' in label_to_idx:
        rec_idx = label_to_idx['REC']

        # Map rushing portion (everything from start up to REC index that matches known fields)
        rush_labels = {'CAR', 'YDS', 'AVG', 'TD', 'LNG'}
        # We assume last 5 rushing fields are right before REC, but be resilient:
        for i in range(max(0, rec_idx - 6), rec_idx):
            lab = labels[i]
            if lab in rush_labels and i < len(totals):
                val = _to_float(totals[i])
                if val is not None:
                    stats[f'rushing_{lab}'] = val

        # Receiving block starts at REC and continues until FUM (or end)
        receiving_labels = {'REC', 'TGTS', 'YDS', 'AVG', 'TD', 'LNG'}
        end_idx = len(labels)
        if 'FUM' in label_to_idx:
            end_idx = label_to_idx['FUM']
        for i in range(rec_idx, end_idx):
            lab = labels[i]
            if lab in receiving_labels and i < len(totals):
                val = _to_float(totals[i])
                if val is not None:
                    stats[f'receiving_{lab}'] = val

        # Fumbles (if present): FUM, LST, and any following like FF, KB
        tail_labels = ['FUM', 'LST', 'FF', 'KB']
        for lab in tail_labels:
            idx = label_to_idx.get(lab)
            if idx is not None and idx < len(totals):
                val = _to_float(totals[idx])
                if val is not None:
                    stats[lab] = val

        return stats

    # Fallback: map by names directly (best-effort)
    for i, lab in enumerate(labels):
        if i < len(totals):
            val = _to_float(totals[i])
            if val is not None and lab:
                stats[lab] = val
    return stats


def _parse_event_stats(labels, stats_row):
    """Parse per-game event stats aligned with global labels into unified keys."""
    return _parse_gamelog_totals(labels, stats_row)


def get_stats(player_id, name, *, season=2025, season_type=2, debug=False):
    """Fetch consolidated season totals and games played for a player.

    Primary: gamelog with explicit season & season_type (2=REG)
    Fallback: overview endpoint statistics (Regular Season split)
    """
    # 1) Gamelog
    gl_url = (
        f'https://site.api.espn.com/apis/common/v3/sports/football/nfl/athletes/{player_id}/gamelog'
        f'?season={season}&seasontype={season_type}'
    )
    try:
        req = urllib.request.Request(gl_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
            data = json.loads(resp.read().decode())
        if debug:
            # Print a compact summary of categories and a sample event
            st = (data.get('seasonTypes') or [])
            cats_dbg = []
            if st:
                for c in st[0].get('categories', []):
                    cats_dbg.append({
                        'displayName': c.get('displayName'),
                        'type': c.get('type'),
                        'splitType': c.get('splitType'),
                        'events_count': len(c.get('events', []) or []),
                        'totals_len': len(c.get('totals', []) or []),
                    })
            print(f"\n[DEBUG] GAMelog summary for {name}: labels={len(data.get('labels', []))}, categories={cats_dbg}")
            # Sample one event entry if available
            try:
                sample_events = st[0].get('categories', [])[0].get('events', [])
                if sample_events:
                    sample = sample_events[0]
                    print("[DEBUG] Sample event keys:", list(sample.keys()))
            except Exception:
                pass

        result = {'name': name, 'games': 0}
        labels = data.get('labels', [])

        # Events are top-level in this endpoint; count them robustly
        events = data.get('events', {})
        if isinstance(events, dict):
            result['games'] = len(events)
        elif isinstance(events, list):
            result['games'] = len(events)
        else:
            result['games'] = 0

        # Parse totals from the first seasonType's first category totals
        st = (data.get('seasonTypes') or [])
        if st:
            cats = st[0].get('categories', [])
            if cats:
                totals = cats[0].get('totals', [])
                parsed = _parse_gamelog_totals(labels, totals)
                result.update(parsed)

                # Per-game events
                events = cats[0].get('events', []) or []
                per_games = []
                for ev in events:
                    row = ev.get('stats', []) or []
                    if row:
                        per_games.append(_parse_event_stats(labels, row))
                if per_games:
                    result['per_game'] = per_games

        return result
    except Exception as e:
        if debug:
            print(f"[DEBUG] Gamelog fetch failed for {name}: {e}")

    # 2) Fallback to overview (cleaner season totals, no games count)
    ov_url = f'https://site.api.espn.com/apis/common/v3/sports/football/nfl/athletes/{player_id}/overview'
    try:
        req = urllib.request.Request(ov_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
            data = json.loads(resp.read().decode())
        if debug:
            print(f"\n[DEBUG] Overview response for {name} (trunc):\n" + json.dumps(data, indent=2)[:1200])

        stats_node = data.get('statistics', {})
        names = stats_node.get('names', [])
        for split in stats_node.get('splits', []):
            if split.get('displayName') == 'Regular Season':
                vals = split.get('stats', [])
                mapped = {}
                for i, n in enumerate(names):
                    if i < len(vals):
                        v = _to_float(vals[i])
                        if v is not None:
                            mapped[n] = v

                # Map to unified keys when possible
                result = {'name': name, 'games': 0}  # games unknown in overview
                # rushing
                if 'rushingYards' in mapped:
                    result['rushing_YDS'] = mapped.get('rushingYards', 0)
                    result['rushing_CAR'] = mapped.get('rushingAttempts', 0)
                    result['rushing_TD'] = mapped.get('rushingTouchdowns', 0)
                # receiving
                if 'receivingYards' in mapped:
                    result['receiving_YDS'] = mapped.get('receivingYards', 0)
                    result['receiving_REC'] = mapped.get('receptions', 0)
                    result['receiving_TD'] = mapped.get('receivingTouchdowns', 0)
                # passing
                if 'passingYards' in mapped:
                    result['passing_YDS'] = mapped.get('passingYards', 0)
                    result['passing_TD'] = mapped.get('passingTouchdowns', 0)
                    result['passing_CMP'] = mapped.get('completions', 0)
                    result['passing_ATT'] = mapped.get('attempts', 0)
                return result
        return {'name': name, 'games': 0, 'error': 'No overview regular-season stats'}
    except Exception as e:
        return {'name': name, 'games': 0, 'error': f'Overview fetch failed: {e}'}

def analyze_rb(name, stats, props):
    """Analyze RB props."""
    games = stats.get('games', 16)
    if games == 0:
        return []
    
    picks = []
    
    # Rush yards
    rush_yds = stats.get('rushing_YDS', 0)
    avg_rush = rush_yds / games if games else 0
    
    # Rec yards
    rec_yds = stats.get('receiving_YDS', 0) 
    avg_rec = rec_yds / games if games else 0
    
    # Receptions
    recs = stats.get('receiving_REC', 0)
    avg_recs = recs / games if games else 0
    
    # Rush attempts
    rush_att = stats.get('rushing_CAR', 0)
    avg_att = rush_att / games if games else 0
    
    # TDs
    rush_td = stats.get('rushing_TD', 0)
    rec_td = stats.get('receiving_TD', 0)
    total_td = rush_td + rec_td
    avg_td = total_td / games if games else 0
    
    per_games = stats.get('per_game') or []
    last_n = min(10, len(per_games))
    qa_flags = compute_qa_flags(stats)
    for prop, line, higher_odds, lower_odds in props:
        edge = None
        pick = None
        confidence = 0
        p_over = None
        p_under = None
        expected_value = None
        
        if prop == 'Rush Yards':
            diff = avg_rush - line
            pct_diff = (diff / line) * 100 if line else 0
            if abs(pct_diff) > 10 and last_n >= 5:
                pick = 'HIGHER' if diff > 0 else 'LOWER'
                # Hit rate last N
                vals = [pg.get('rushing_YDS', 0) for pg in per_games[-last_n:]]
                hits = sum(1 for v in vals if (v > line if pick == 'HIGHER' else v < line))
                hit_rate = hits / last_n if last_n else 0
                # Variance dampener
                mean = sum(vals) / last_n if last_n else 0
                std = (sum((v - mean) ** 2 for v in vals) / last_n) ** 0.5 if last_n else 0
                var_damp = max(0.6, 1.0 - (std / 30.0))  # 30 yds scale
                base = min(abs(pct_diff), 30)
                confidence = base * (0.5 + 0.5 * hit_rate) * var_damp
                edge = f"Avg {avg_rush:.1f} vs line {line} | L{last_n} hit {hit_rate:.0%}"
                p_over = prob_over(mean, max(std, 1e-6), line)
                p_under = 1.0 - p_over
                expected_value = mean - line
                
        elif prop == 'Receiving Yards':
            diff = avg_rec - line
            pct_diff = (diff / line) * 100 if line else 0
            if abs(pct_diff) > 15 and last_n >= 5:
                pick = 'HIGHER' if diff > 0 else 'LOWER'
                vals = [pg.get('receiving_YDS', 0) for pg in per_games[-last_n:]]
                hits = sum(1 for v in vals if (v > line if pick == 'HIGHER' else v < line))
                hit_rate = hits / last_n if last_n else 0
                mean = sum(vals) / last_n if last_n else 0
                std = (sum((v - mean) ** 2 for v in vals) / last_n) ** 0.5 if last_n else 0
                var_damp = max(0.6, 1.0 - (std / 25.0))
                base = min(abs(pct_diff), 30)
                confidence = base * (0.5 + 0.5 * hit_rate) * var_damp
                edge = f"Avg {avg_rec:.1f} vs line {line} | L{last_n} hit {hit_rate:.0%}"
                p_over = prob_over(mean, max(std, 1e-6), line)
                p_under = 1.0 - p_over
                expected_value = mean - line
                
        elif prop == 'Receptions':
            diff = avg_recs - line
            if abs(diff) > 0.5 and last_n >= 5:
                pick = 'HIGHER' if diff > 0 else 'LOWER'
                vals = [pg.get('receiving_REC', 0) for pg in per_games[-last_n:]]
                hits = sum(1 for v in vals if (v > line if pick == 'HIGHER' else v < line))
                hit_rate = hits / last_n if last_n else 0
                mean = sum(vals) / last_n if last_n else 0
                std = (sum((v - mean) ** 2 for v in vals) / last_n) ** 0.5 if last_n else 0
                var_damp = max(0.6, 1.0 - (std / 2.0))  # rec count variance scale
                base = min(abs(diff) * 20, 30)
                confidence = base * (0.5 + 0.5 * hit_rate) * var_damp
                edge = f"Avg {avg_recs:.1f} vs line {line} | L{last_n} hit {hit_rate:.0%}"
                p_over = prob_over(mean, max(std, 1e-6), line)
                p_under = 1.0 - p_over
                expected_value = mean - line
                
        elif prop == 'Rush Attempts':
            diff = avg_att - line
            if abs(diff) > 1 and last_n >= 5:
                pick = 'HIGHER' if diff > 0 else 'LOWER'
                vals = [pg.get('rushing_CAR', 0) for pg in per_games[-last_n:]]
                hits = sum(1 for v in vals if (v > line if pick == 'HIGHER' else v < line))
                hit_rate = hits / last_n if last_n else 0
                mean = sum(vals) / last_n if last_n else 0
                std = (sum((v - mean) ** 2 for v in vals) / last_n) ** 0.5 if last_n else 0
                var_damp = max(0.6, 1.0 - (std / 5.0))
                base = min(abs(diff) * 10, 30)
                confidence = base * (0.5 + 0.5 * hit_rate) * var_damp
                edge = f"Avg {avg_att:.1f} vs line {line} | L{last_n} hit {hit_rate:.0%}"
                p_over = prob_over(mean, max(std, 1e-6), line)
                p_under = 1.0 - p_over
                expected_value = mean - line
                
        elif prop == 'Rush + Rec Yards':
            avg_total = avg_rush + avg_rec
            diff = avg_total - line
            pct_diff = (diff / line) * 100 if line else 0
            if abs(pct_diff) > 8 and last_n >= 5:
                pick = 'HIGHER' if diff > 0 else 'LOWER'
                vals = [pg.get('rushing_YDS', 0) + pg.get('receiving_YDS', 0) for pg in per_games[-last_n:]]
                hits = sum(1 for v in vals if (v > line if pick == 'HIGHER' else v < line))
                hit_rate = hits / last_n if last_n else 0
                mean = sum(vals) / last_n if last_n else 0
                std = (sum((v - mean) ** 2 for v in vals) / last_n) ** 0.5 if last_n else 0
                var_damp = max(0.6, 1.0 - (std / 35.0))
                base = min(abs(pct_diff), 30)
                confidence = base * (0.5 + 0.5 * hit_rate) * var_damp
                edge = f"Avg {avg_total:.1f} vs line {line} | L{last_n} hit {hit_rate:.0%}"
                p_over = prob_over(mean, max(std, 1e-6), line)
                p_under = 1.0 - p_over
                expected_value = mean - line
                
        elif prop == 'Rush + Rec TDs':
            # TDs are volatile - only pick if strong edge
            if avg_td > 0.7 and line == 0.5 and last_n >= 5:
                pick = 'HIGHER'
                vals = [(pg.get('rushing_TD', 0) + pg.get('receiving_TD', 0)) for pg in per_games[-last_n:]]
                hits = sum(1 for v in vals if v >= 1)
                hit_rate = hits / last_n if last_n else 0
                base = min((avg_td - 0.5) * 40, 25)
                confidence = base * (0.5 + 0.5 * hit_rate)
                edge = f"Avg {avg_td:.2f} TDs/g | L{last_n} 1+ TD {hit_rate:.0%}"
                mean = sum(vals) / last_n if last_n else 0
                std = (sum((v - mean) ** 2 for v in vals) / last_n) ** 0.5 if last_n else 1.0
                p_over = prob_over(mean, max(std, 1e-6), 0.5)
                p_under = 1.0 - p_over
                expected_value = mean - 0.5
                
        if pick and confidence > 15:
            picks.append({
                'player': name,
                'prop': prop,
                'line': line,
                'pick': pick,
                'confidence': confidence,
                'edge': edge,
                'higher_odds': higher_odds,
                'lower_odds': lower_odds,
                'p_over': p_over,
                'p_under': p_under,
                'expected_value': expected_value,
                'qa_flags': qa_flags,
                'samples': last_n
            })
    
    return picks

def analyze_wr_te(name, stats, props):
    """Analyze WR/TE props."""
    games = stats.get('games', 16)
    if games == 0:
        return []
    
    picks = []
    
    rec_yds = stats.get('receiving_YDS', 0)
    avg_rec_yds = rec_yds / games if games else 0
    
    recs = stats.get('receiving_REC', 0)
    avg_recs = recs / games if games else 0
    
    targets = stats.get('receiving_TGTS', 0)
    avg_tgts = targets / games if games else 0
    
    rec_td = stats.get('receiving_TD', 0)
    avg_td = rec_td / games if games else 0
    
    per_games = stats.get('per_game') or []
    last_n = min(10, len(per_games))
    qa_flags = compute_qa_flags(stats)
    for prop, line, higher_odds, lower_odds in props:
        edge = None
        pick = None
        confidence = 0
        p_over = None
        p_under = None
        expected_value = None
        
        if prop == 'Receiving Yards':
            diff = avg_rec_yds - line
            pct_diff = (diff / line) * 100 if line else 0
            if abs(pct_diff) > 10 and last_n >= 5:
                pick = 'HIGHER' if diff > 0 else 'LOWER'
                vals = [pg.get('receiving_YDS', 0) for pg in per_games[-last_n:]]
                hits = sum(1 for v in vals if (v > line if pick == 'HIGHER' else v < line))
                hit_rate = hits / last_n if last_n else 0
                mean = sum(vals) / last_n if last_n else 0
                std = (sum((v - mean) ** 2 for v in vals) / last_n) ** 0.5 if last_n else 0
                var_damp = max(0.6, 1.0 - (std / 25.0))
                base = min(abs(pct_diff), 35)
                confidence = base * (0.5 + 0.5 * hit_rate) * var_damp
                edge = f"Avg {avg_rec_yds:.1f} vs line {line} | L{last_n} hit {hit_rate:.0%}"
                p_over = prob_over(mean, max(std, 1e-6), line)
                p_under = 1.0 - p_over
                expected_value = mean - line
                
        elif prop == 'Receptions':
            diff = avg_recs - line
            if abs(diff) > 0.4 and last_n >= 5:
                pick = 'HIGHER' if diff > 0 else 'LOWER'
                vals = [pg.get('receiving_REC', 0) for pg in per_games[-last_n:]]
                hits = sum(1 for v in vals if (v > line if pick == 'HIGHER' else v < line))
                hit_rate = hits / last_n if last_n else 0
                mean = sum(vals) / last_n if last_n else 0
                std = (sum((v - mean) ** 2 for v in vals) / last_n) ** 0.5 if last_n else 0
                var_damp = max(0.6, 1.0 - (std / 2.0))
                base = min(abs(diff) * 25, 35)
                confidence = base * (0.5 + 0.5 * hit_rate) * var_damp
                edge = f"Avg {avg_recs:.1f} vs line {line} | L{last_n} hit {hit_rate:.0%}"
                p_over = prob_over(mean, max(std, 1e-6), line)
                p_under = 1.0 - p_over
                expected_value = mean - line
                
        elif prop == 'Targets':
            diff = avg_tgts - line
            if abs(diff) > 0.5 and last_n >= 5:
                pick = 'HIGHER' if diff > 0 else 'LOWER'
                vals = [pg.get('receiving_TGTS', 0) for pg in per_games[-last_n:]]
                hits = sum(1 for v in vals if (v > line if pick == 'HIGHER' else v < line))
                hit_rate = hits / last_n if last_n else 0
                mean = sum(vals) / last_n if last_n else 0
                std = (sum((v - mean) ** 2 for v in vals) / last_n) ** 0.5 if last_n else 0
                var_damp = max(0.6, 1.0 - (std / 3.0))
                base = min(abs(diff) * 20, 30)
                confidence = base * (0.5 + 0.5 * hit_rate) * var_damp
                edge = f"Avg {avg_tgts:.1f} vs line {line} | L{last_n} hit {hit_rate:.0%}"
                p_over = prob_over(mean, max(std, 1e-6), line)
                p_under = 1.0 - p_over
                expected_value = mean - line
                
        elif prop == 'Rush + Rec TDs':
            if avg_td > 0.5 and line == 0.5 and last_n >= 5:
                pick = 'HIGHER'
                vals = [pg.get('receiving_TD', 0) for pg in per_games[-last_n:]]
                hits = sum(1 for v in vals if v >= 1)
                hit_rate = hits / last_n if last_n else 0
                base = min(avg_td * 30, 25)
                confidence = base * (0.5 + 0.5 * hit_rate)
                edge = f"Avg {avg_td:.2f} TDs/g | L{last_n} 1+ TD {hit_rate:.0%}"
                mean = sum(vals) / last_n if last_n else 0
                std = (sum((v - mean) ** 2 for v in vals) / last_n) ** 0.5 if last_n else 1.0
                p_over = prob_over(mean, max(std, 1e-6), 0.5)
                p_under = 1.0 - p_over
                expected_value = mean - 0.5
                
        if pick and confidence > 12:
            picks.append({
                'player': name,
                'prop': prop,
                'line': line,
                'pick': pick,
                'confidence': confidence,
                'edge': edge,
                'higher_odds': higher_odds,
                'lower_odds': lower_odds,
                'p_over': p_over,
                'p_under': p_under,
                'expected_value': expected_value,
                'qa_flags': qa_flags,
                'samples': last_n
            })
    
    return picks

def analyze_qb(name, stats, props):
    """Analyze QB props."""
    games = stats.get('games', 16)
    if games == 0:
        return []
    
    picks = []
    
    pass_yds = stats.get('passing_YDS', 0)
    avg_pass = pass_yds / games if games else 0
    
    pass_td = stats.get('passing_TD', 0)
    avg_pass_td = pass_td / games if games else 0
    
    completions = stats.get('passing_CMP', 0)
    avg_cmp = completions / games if games else 0
    
    attempts = stats.get('passing_ATT', 0)
    avg_att = attempts / games if games else 0
    
    rush_yds = stats.get('rushing_YDS', 0)
    avg_rush = rush_yds / games if games else 0
    
    ints = stats.get('passing_INT', 0)
    avg_int = ints / games if games else 0
    
    per_games = stats.get('per_game') or []
    last_n = min(10, len(per_games))
    qa_flags = compute_qa_flags(stats)
    for prop, line, higher_odds, lower_odds in props:
        edge = None
        pick = None
        confidence = 0
        p_over = None
        p_under = None
        expected_value = None
        
        if prop == 'Pass Yards':
            diff = avg_pass - line
            pct_diff = (diff / line) * 100 if line else 0
            if abs(pct_diff) > 8 and last_n >= 5:
                pick = 'HIGHER' if diff > 0 else 'LOWER'
                vals = [pg.get('passing_YDS', 0) for pg in per_games[-last_n:]]
                hits = sum(1 for v in vals if (v > line if pick == 'HIGHER' else v < line))
                hit_rate = hits / last_n if last_n else 0
                mean = sum(vals) / last_n if last_n else 0
                std = (sum((v - mean) ** 2 for v in vals) / last_n) ** 0.5 if last_n else 0
                var_damp = max(0.6, 1.0 - (std / 60.0))
                base = min(abs(pct_diff), 35)
                confidence = base * (0.5 + 0.5 * hit_rate) * var_damp
                edge = f"Avg {avg_pass:.1f} vs line {line} | L{last_n} hit {hit_rate:.0%}"
                p_over = prob_over(mean, max(std, 1e-6), line)
                p_under = 1.0 - p_over
                expected_value = mean - line
                
        elif prop == 'Pass TDs':
            diff = avg_pass_td - line
            if abs(diff) > 0.3 and last_n >= 5:
                pick = 'HIGHER' if diff > 0 else 'LOWER'
                vals = [pg.get('passing_TD', 0) for pg in per_games[-last_n:]]
                hits = sum(1 for v in vals if (v > line if pick == 'HIGHER' else v < line))
                hit_rate = hits / last_n if last_n else 0
                base = min(abs(diff) * 30, 30)
                confidence = base * (0.5 + 0.5 * hit_rate)
                edge = f"Avg {avg_pass_td:.2f} vs line {line} | L{last_n} hit {hit_rate:.0%}"
                mean = sum(vals) / last_n if last_n else 0
                std = (sum((v - mean) ** 2 for v in vals) / last_n) ** 0.5 if last_n else 1.0
                p_over = prob_over(mean, max(std, 1e-6), line)
                p_under = 1.0 - p_over
                expected_value = mean - line
                
        elif prop == 'Completions':
            diff = avg_cmp - line
            if abs(diff) > 1.5 and last_n >= 5:
                pick = 'HIGHER' if diff > 0 else 'LOWER'
                vals = [pg.get('passing_CMP', 0) for pg in per_games[-last_n:]]
                hits = sum(1 for v in vals if (v > line if pick == 'HIGHER' else v < line))
                hit_rate = hits / last_n if last_n else 0
                mean = sum(vals) / last_n if last_n else 0
                std = (sum((v - mean) ** 2 for v in vals) / last_n) ** 0.5 if last_n else 0
                var_damp = max(0.6, 1.0 - (std / 5.0))
                base = min(abs(diff) * 10, 30)
                confidence = base * (0.5 + 0.5 * hit_rate) * var_damp
                edge = f"Avg {avg_cmp:.1f} vs line {line} | L{last_n} hit {hit_rate:.0%}"
                p_over = prob_over(mean, max(std, 1e-6), line)
                p_under = 1.0 - p_over
                expected_value = mean - line
                
        elif prop == 'Pass Attempts':
            diff = avg_att - line
            if abs(diff) > 2 and last_n >= 5:
                pick = 'HIGHER' if diff > 0 else 'LOWER'
                vals = [pg.get('passing_ATT', 0) for pg in per_games[-last_n:]]
                hits = sum(1 for v in vals if (v > line if pick == 'HIGHER' else v < line))
                hit_rate = hits / last_n if last_n else 0
                mean = sum(vals) / last_n if last_n else 0
                std = (sum((v - mean) ** 2 for v in vals) / last_n) ** 0.5 if last_n else 0
                var_damp = max(0.6, 1.0 - (std / 6.0))
                base = min(abs(diff) * 8, 30)
                confidence = base * (0.5 + 0.5 * hit_rate) * var_damp
                edge = f"Avg {avg_att:.1f} vs line {line} | L{last_n} hit {hit_rate:.0%}"
                p_over = prob_over(mean, max(std, 1e-6), line)
                p_under = 1.0 - p_over
                expected_value = mean - line
                
        elif prop == 'Rush Yards':
            diff = avg_rush - line
            pct_diff = (diff / line) * 100 if line else 0
            if abs(pct_diff) > 15 and last_n >= 5:
                pick = 'HIGHER' if diff > 0 else 'LOWER'
                vals = [pg.get('rushing_YDS', 0) for pg in per_games[-last_n:]]
                hits = sum(1 for v in vals if (v > line if pick == 'HIGHER' else v < line))
                hit_rate = hits / last_n if last_n else 0
                mean = sum(vals) / last_n if last_n else 0
                std = (sum((v - mean) ** 2 for v in vals) / last_n) ** 0.5 if last_n else 0
                var_damp = max(0.6, 1.0 - (std / 25.0))
                base = min(abs(pct_diff), 30)
                confidence = base * (0.5 + 0.5 * hit_rate) * var_damp
                edge = f"Avg {avg_rush:.1f} vs line {line} | L{last_n} hit {hit_rate:.0%}"
                p_over = prob_over(mean, max(std, 1e-6), line)
                p_under = 1.0 - p_over
                expected_value = mean - line
                
        elif prop == 'INTs Thrown':
            diff = avg_int - line
            if line == 0.5 and avg_int < 0.6 and last_n >= 5:
                pick = 'LOWER'
                vals = [pg.get('passing_INT', 0) for pg in per_games[-last_n:]]
                hits = sum(1 for v in vals if v == 0)
                hit_rate = hits / last_n if last_n else 0
                confidence = 20 * (0.5 + 0.5 * hit_rate)
                edge = f"Avg {avg_int:.2f} INTs/g | L{last_n} 0 INT {hit_rate:.0%}"
                mean = sum(vals) / last_n if last_n else 0
                std = (sum((v - mean) ** 2 for v in vals) / last_n) ** 0.5 if last_n else 1.0
                p_over = prob_over(mean, max(std, 1e-6), line)
                p_under = 1.0 - p_over
                expected_value = mean - line
                
        if pick and confidence > 12:
            picks.append({
                'player': name,
                'prop': prop,
                'line': line,
                'pick': pick,
                'confidence': confidence,
                'edge': edge,
                'higher_odds': higher_odds,
                'lower_odds': lower_odds,
                'p_over': p_over,
                'p_under': p_under,
                'expected_value': expected_value,
                'qa_flags': qa_flags,
                'samples': last_n
            })
    
    return picks

# Props from user data
props_data = {
    'Jonathan Taylor': [
        ('Rush + Rec TDs', 0.5, 0.73, 1.15),
        ('Rush Yards', 73.5, 1.0, 1.0),
        ('Receiving Yards', 18.5, 1.0, 1.0),
        ('Receptions', 3.5, 1.05, 0.78),
        ('Rush Attempts', 18.5, 1.0, 1.0),
        ('Rush + Rec Yards', 97.5, 1.0, 1.0),
        ('Targets', 3.5, 1.09, 0.76),
    ],
    'Travis Etienne Jr.': [
        ('Rush + Rec TDs', 0.5, 0.74, 1.13),
        ('Rush Yards', 66.5, 1.0, 1.0),
        ('Receiving Yards', 17.5, 1.0, 1.0),
        ('Receptions', 2.5, 0.82, 1.03),
        ('Rush Attempts', 17.5, 1.03, 0.79),
        ('Rush + Rec Yards', 88.5, 1.0, 1.0),
    ],
    'Tyler Warren': [
        ('Rush + Rec TDs', 0.5, 1.32, 0.66),
        ('Receiving Yards', 48.5, 1.0, 1.0),
        ('Receptions', 5.5, 1.08, 0.79),
        ('Targets', 6.5, 0.85, 1.05),
    ],
    'Michael Pittman Jr.': [
        ('Rush + Rec TDs', 0.5, 1.52, 0.64),
        ('Receiving Yards', 44.5, 1.0, 1.0),
        ('Receptions', 4.5, 1.0, 1.0),
        ('Targets', 7.5, 1.07, 0.8),
    ],
    'Trevor Lawrence': [
        ('Rush + Rec TDs', 0.5, 1.39, 0.66),
        ('Pass Yards', 246.5, 1.0, 1.0),
        ('Pass TDs', 1.5, 0.81, 1.04),
        ('Rush Yards', 18.5, 1.0, 1.0),
        ('Rush Attempts', 4.5, 0.82, 1.04),
        ('Pass Attempts', 32.5, 0.84, 1.06),
        ('Completions', 20.5, 0.81, 1.06),
        ('INTs Thrown', 0.5, 1.0, 1.0),
    ],
    'Brian Thomas': [
        ('Rush + Rec TDs', 0.5, 1.3, 0.69),
        ('Receiving Yards', 48.5, 1.0, 1.0),
        ('Receptions', 3.5, 1.09, 0.8),
    ],
    'Jakobi Meyers': [
        ('Rush + Rec TDs', 0.5, 1.08, 0.76),
        ('Receiving Yards', 59.5, 1.0, 1.0),
        ('Receptions', 5.5, 1.03, 0.82),
        ('Targets', 7.5, 1.07, 0.84),
    ],
    'Josh Downs': [
        ('Rush + Rec TDs', 0.5, 1.79, 0.61),
        ('Receiving Yards', 35.5, 1.0, 1.0),
        ('Receptions', 3.5, 0.81, 1.06),
    ],
    'Alec Pierce': [
        ('Rush + Rec TDs', 0.5, 1.76, 0.61),
        ('Receiving Yards', 31.5, 1.0, 1.0),
        ('Receptions', 2.5, 1.03, 0.82),
        ('Targets', 4.5, 1.0, 1.0),
    ],
    'Aaron Rodgers': [
        ('Pass Yards', 187.5, 1.0, 1.0),
        ('Pass TDs', 1.5, 1.17, 0.73),
        ('Rush Yards', 0.5, 1.05, 0.81),
        ('Rush Attempts', 1.5, 1.05, 0.94),
        ('Completions', 18.5, 1.0, 1.0),
        ('Pass Attempts', 28.5, 0.87, 1.05),
        ('INTs Thrown', 0.5, 1.03, 0.82),
    ],
    'Shedeur Sanders': [
        ('Rush + Rec TDs', 0.5, 2.41, 1.0),
        ('Pass Yards', 178.5, 1.0, 1.0),
        ('Pass TDs', 0.5, 0.8, 1.06),
        ('Rush Yards', 13.5, 1.0, 1.0),
    ],
    'Kenneth Gainwell': [
        ('Rush + Rec TDs', 0.5, 1.09, 0.76),
        ('Rush Yards', 37.5, 1.0, 1.0),
        ('Receiving Yards', 30.5, 1.0, 1.0),
        ('Receptions', 4.5, 1.03, 0.88),
        ('Rush Attempts', 8.5, 0.83, 1.08),
        ('Rush + Rec Yards', 71.5, 1.0, 1.0),
    ],
    'Jaylen Warren': [
        ('Rush + Rec TDs', 0.5, 1.19, 0.73),
        ('Rush Yards', 54.5, 1.0, 1.0),
        ('Receiving Yards', 12.5, 1.0, 1.0),
        ('Receptions', 2.5, 1.09, 0.79),
        ('Rush Attempts', 13.5, 0.94, 1.05),
        ('Rush + Rec Yards', 71.5, 1.0, 1.0),
    ],
    'Dylan Sampson': [
        ('Rush + Rec TDs', 0.5, 1.28, 0.68),
        ('Rush Yards', 42.5, 1.0, 1.0),
        ('Receiving Yards', 17.5, 1.0, 1.0),
        ('Receptions', 2.5, 0.81, 1.06),
        ('Rush Attempts', 12.5, 0.86, 1.05),
        ('Rush + Rec Yards', 64.5, 1.0, 1.0),
        ('Targets', 3.5, 0.86, 1.06),
    ],
    'Jerry Jeudy': [
        ('Rush + Rec TDs', 0.5, 2.7, 1.0),
        ('Receiving Yards', 29.5, 1.0, 1.0),
        ('Receptions', 2.5, 1.04, 1.0),
        ('Targets', 4.5, 1.09, 0.83),
    ],
    'Harold Fannin': [
        ('Rush + Rec TDs', 0.5, 1.78, 0.61),
        ('Receiving Yards', 49.5, 1.0, 1.0),
        ('Receptions', 5.5, 1.09, 0.83),
    ],
    'Pat Freiermuth': [
        ('Rush + Rec TDs', 0.5, 2.72, 1.0),
        ('Receiving Yards', 22.5, 1.0, 1.0),
        ('Receptions', 2.5, 1.05, 0.84),
    ],
    'Adam Thielen': [
        ('Rush + Rec TDs', 0.5, 2.3, 1.0),
        ('Receiving Yards', 19.5, 1.0, 1.0),
        ('Receptions', 2.5, 1.07, 0.76),
    ],
    'Darnell Washington': [
        ('Rush + Rec TDs', 0.5, 2.58, 1.0),
        ('Receiving Yards', 25.5, 1.0, 1.0),
        ('Receptions', 2.5, 0.88, 1.02),
    ],
}

print("=" * 80)
print("FETCHING LIVE ESPN STATS...")
print("=" * 80)

def main():
    parser = argparse.ArgumentParser(description="Prop analysis using ESPN stats")
    parser.add_argument("--season", type=int, default=2025, help="Season year to fetch (e.g., 2025)")
    parser.add_argument("--seasontype", type=int, default=2, help="Season type: 2=Regular")
    parser.add_argument("--debug", action="store_true", help="Enable verbose ESPN response logging")
    parser.add_argument("--fail-on-missing-data", action="store_true", help="Abort if any player has insufficient data")
    args = parser.parse_args()

    missing = []
    all_stats = {}
    for name, pid in players.items():
        stats = get_stats(pid, name, season=args.season, season_type=args.seasontype, debug=args.debug)
        # Guard: count games properly; if overview fallback, games=0
        games = stats.get('games') or 0
        if games < MIN_GAMES_REQUIRED:
            missing.append((name, games))
        all_stats[name] = stats
        
        # Print key stats
        print(f"\n{name} ({games} games):")
        
        # Rushing stats
        rush_yds = stats.get('rushing_YDS', 0)
        rush_td = stats.get('rushing_TD', 0)
        rush_att = stats.get('rushing_CAR', 0)
        if rush_yds > 0:
            per_g = (rush_yds / games) if games else 0
            print(f"  Rush: {rush_yds} yds, {rush_td} TD, {rush_att} att ({per_g:.1f}/g)")
        
        # Receiving stats
        rec_yds = stats.get('receiving_YDS', 0)
        rec_td = stats.get('receiving_TD', 0)
        recs = stats.get('receiving_REC', 0)
        if rec_yds > 0 or recs > 0:
            per_g_yd = (rec_yds / games) if games else 0
            per_g_rec = (recs / games) if games else 0
            print(f"  Rec: {rec_yds} yds, {rec_td} TD, {recs} rec ({per_g_yd:.1f}/g, {per_g_rec:.1f} rec/g)")
        
        # Passing stats
        pass_yds = stats.get('passing_YDS', 0)
        pass_td = stats.get('passing_TD', 0)
        if pass_yds > 0:
            per_g = (pass_yds / games) if games else 0
            print(f"  Pass: {pass_yds} yds, {pass_td} TD ({per_g:.1f}/g)")

    if missing:
        print("\n[WARN] Insufficient data for players (games < MIN_GAMES_REQUIRED):")
        for name, g in missing:
            print(f"  - {name}: {g} games")
        if args.fail_on_missing_data:
            print("\nABORTING due to --fail-on-missing-data")
            sys.exit(1)

    # Analyze all props
    all_picks = []
    
    def has_enough(name):
        g = (all_stats.get(name, {}).get('games') or 0)
        return g >= MIN_GAMES_REQUIRED
    
    # RBs
    for name in ['Jonathan Taylor', 'Travis Etienne Jr.', 'Kenneth Gainwell', 'Jaylen Warren', 'Dylan Sampson']:
        if has_enough(name) and name in all_stats and name in props_data:
            picks = analyze_rb(name, all_stats[name], props_data[name])
            all_picks.extend(picks)
    
    # WR/TEs
    for name in ['Tyler Warren', 'Michael Pittman Jr.', 'Brian Thomas', 'Jakobi Meyers', 'Josh Downs', 
                 'Alec Pierce', 'Jerry Jeudy', 'Harold Fannin', 'Pat Freiermuth', 'Adam Thielen', 'Darnell Washington']:
        if has_enough(name) and name in all_stats and name in props_data:
            picks = analyze_wr_te(name, all_stats[name], props_data[name])
            all_picks.extend(picks)
    
    # QBs
    for name in ['Trevor Lawrence', 'Aaron Rodgers', 'Shedeur Sanders']:
        if has_enough(name) and name in all_stats and name in props_data:
            picks = analyze_qb(name, all_stats[name], props_data[name])
            all_picks.extend(picks)
    
    # Sort by confidence
    all_picks.sort(key=lambda x: x['confidence'], reverse=True)
    
    print("\n" + "=" * 80)
    print("🎯 TOP PROP PICKS (Sorted by Confidence)")
    print("=" * 80)
    
    for i, pick in enumerate(all_picks[:15], 1):
        odds = pick['higher_odds'] if pick['pick'] == 'HIGHER' else pick['lower_odds']
        odds_str = f"({odds}x)" if odds != 1.0 else ""
        print(f"\n{i}. {pick['player']} - {pick['prop']}")
        print(f"   📊 Line: {pick['line']} → {pick['pick']} {odds_str}")
        print(f"   📈 Edge: {pick['edge']}")
        print(f"   ⭐ Confidence: {pick['confidence']:.0f}%")
    
    print("\n" + "=" * 80)
    print("🏈 GAME-BY-GAME BREAKDOWN")
    print("=" * 80)
    
    # JAX @ IND picks
    print("\n📍 JAX @ IND (12:00 PM CST)")
    print("-" * 40)
    jax_ind = [p for p in all_picks if p['player'] in ['Jonathan Taylor', 'Travis Etienne Jr.', 'Tyler Warren', 
               'Michael Pittman Jr.', 'Trevor Lawrence', 'Brian Thomas', 'Jakobi Meyers', 'Josh Downs', 'Alec Pierce']]
    for pick in jax_ind[:8]:
        odds = pick['higher_odds'] if pick['pick'] == 'HIGHER' else pick['lower_odds']
        print(f"  • {pick['player']}: {pick['prop']} {pick['pick']} {pick['line']} - {pick['edge']}")
    
    # PIT @ CLE picks
    print("\n📍 PIT @ CLE (12:00 PM CST)")  
    print("-" * 40)
    pit_cle = [p for p in all_picks if p['player'] in ['Aaron Rodgers', 'Shedeur Sanders', 'Kenneth Gainwell',
               'Jaylen Warren', 'Dylan Sampson', 'Jerry Jeudy', 'Harold Fannin', 'Pat Freiermuth', 'Adam Thielen', 'Darnell Washington']]
    for pick in pit_cle[:8]:
        odds = pick['higher_odds'] if pick['pick'] == 'HIGHER' else pick['lower_odds']
        print(f"  • {pick['player']}: {pick['prop']} {pick['pick']} {pick['line']} - {pick['edge']}")
    
    print("\n" + "=" * 80)
    print("💰 BEST VALUE PLAYS (Favorable Odds + Strong Edge)")
    print("=" * 80)
    
    # Find plays where odds favor the pick AND we have edge
    value_plays = []
    for pick in all_picks:
        odds = pick['higher_odds'] if pick['pick'] == 'HIGHER' else pick['lower_odds']
        if odds >= 1.05 and pick['confidence'] >= 18:
            value_plays.append((pick, odds))
        elif odds <= 0.85 and pick['confidence'] >= 25:  # Juiced but strong edge
            value_plays.append((pick, odds))
    
    value_plays.sort(key=lambda x: x[0]['confidence'], reverse=True)
    
    for pick, odds in value_plays[:10]:
        print(f"\n  🔥 {pick['player']} - {pick['prop']} {pick['pick']} {pick['line']}")
        print(f"     Odds: {odds}x | Edge: {pick['edge']} | Conf: {pick['confidence']:.0f}%")

    # Optional: export picks to JSON/CSV for audit
    try:
        from sports_quant.reporting.export import to_json, to_csv
        out_rows = []
        for p in all_picks:
            out_rows.append({
                "player": p.get('player'),
                "prop": p.get('prop'),
                "line": p.get('line'),
                "direction": p.get('pick'),
                "confidence": round(p.get('confidence', 0.0), 2),
                "edge_text": p.get('edge'),
                "p_over": round(p.get('p_over', 0.0) if p.get('p_over') is not None else 0.0, 4),
                "p_under": round(p.get('p_under', 0.0) if p.get('p_under') is not None else 0.0, 4),
                "expected_value": round(p.get('expected_value', 0.0) if p.get('expected_value') is not None else 0.0, 3),
                "samples": p.get('samples', 0),
                "qa_flags": ",".join(p.get('qa_flags', [])) if isinstance(p.get('qa_flags'), list) else p.get('qa_flags'),
            })
        to_json("outputs/picks.json", out_rows)
        to_csv("outputs/picks.csv", out_rows)
        print("\n[INFO] Exported picks to outputs/picks.json and outputs/picks.csv")
    except Exception:
        # Fallback: write JSON and CSV directly
        out_rows = []
        for p in all_picks:
            out_rows.append({
                "player": p.get('player'),
                "prop": p.get('prop'),
                "line": p.get('line'),
                "direction": p.get('pick'),
                "confidence": round(p.get('confidence', 0.0), 2),
                "edge_text": p.get('edge'),
                "p_over": round(p.get('p_over', 0.0) if p.get('p_over') is not None else 0.0, 4),
                "p_under": round(p.get('p_under', 0.0) if p.get('p_under') is not None else 0.0, 4),
                "expected_value": round(p.get('expected_value', 0.0) if p.get('expected_value') is not None else 0.0, 3),
                "samples": p.get('samples', 0),
                "qa_flags": ",".join(p.get('qa_flags', [])) if isinstance(p.get('qa_flags'), list) else p.get('qa_flags'),
            })
        try:
            with open("outputs/picks.json", "w", encoding="utf-8") as f:
                json.dump(out_rows, f, indent=2)
            # Simple CSV
            keys = sorted({k for r in out_rows for k in r.keys()})
            with open("outputs/picks.csv", "w", encoding="utf-8") as f:
                f.write(",".join(keys) + "\n")
                for r in out_rows:
                    f.write(",".join(str(r.get(k, "")) for k in keys) + "\n")
            print("\n[INFO] Exported picks (fallback) to outputs/picks.json and outputs/picks.csv")
        except Exception as e2:
            print(f"\n[WARN] Export failed (fallback): {e2}")


if __name__ == "__main__":
    main()

