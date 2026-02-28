"""
FUOOM PERFORMANCE DASHBOARD
Web-based dashboard for tracking pick performance, calibration, and analytics.

Run with:
    python dashboard/app.py
    
Then open: http://localhost:5050

Features:
    - Real-time performance metrics
    - Calibration by tier/stat/player
    - Shareable reports
    - Pick history browser
    - Matchup analysis
"""

import sys
sys.path.insert(0, '.')  # Add parent directory

# Regret metrics integration
from dashboard.regret_metrics import get_regret_metrics

from flask import Flask, render_template, jsonify, request
from pathlib import Path
from datetime import datetime, timedelta
import sqlite3
import json

from dashboard.auth import require_api_key

# ═══════════════════════════════════════════════════════════════════
# FLASK APP
# ═══════════════════════════════════════════════════════════════════

app = Flask(__name__)

# Add Jinja2 datetime function
@app.context_processor
def utility_processor():
    def now():
        return datetime.now().strftime("%Y-%m-%d %H:%M")
    return dict(now=now)

# Database paths
PICK_DB = Path("cache/pick_history.db")
STATS_DB = Path("cache/player_stats.db")
DEFENSE_DB = Path("cache/opponent_defense.db")
INJURY_DB = Path("cache/injury_tracker.db")

# ═══════════════════════════════════════════════════════════════════
# DATABASE HELPERS
# ═══════════════════════════════════════════════════════════════════

def get_db_conn(db_path):
    """Get database connection"""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def get_pick_stats(sport: str | None = None, since_days: int | None = None):
    """Get overall pick statistics.

    Optional filters:
    - sport: restrict to a given sport (e.g., 'NBA', 'TENNIS')
    - since_days: restrict to picks created in last N days
    """
    if not PICK_DB.exists():
        return {'total': 0, 'resolved': 0, 'hit_rate': 0}
    
    conn = get_db_conn(PICK_DB)

    where = []
    params = []
    if sport:
        where.append('sport = ?')
        params.append(sport)
    if since_days is not None:
        where.append('created_at >= ?')
        params.append((datetime.now() - timedelta(days=since_days)).isoformat(sep=' '))

    where_sql = (' WHERE ' + ' AND '.join(where)) if where else ''
    total = conn.execute(f'SELECT COUNT(*) FROM picks{where_sql}', params).fetchone()[0]

    where_resolved = where + ['hit IS NOT NULL']
    params_resolved = list(params)
    where_sql_resolved = ' WHERE ' + ' AND '.join(where_resolved)
    resolved = conn.execute(f'SELECT COUNT(*) FROM picks{where_sql_resolved}', params_resolved).fetchone()[0]

    where_hits = where + ['hit = 1']
    params_hits = list(params)
    where_sql_hits = ' WHERE ' + ' AND '.join(where_hits)
    hits = conn.execute(f'SELECT COUNT(*) FROM picks{where_sql_hits}', params_hits).fetchone()[0]
    
    conn.close()
    
    return {
        'total': total,
        'resolved': resolved,
        'pending': total - resolved,
        'hits': hits,
        'misses': resolved - hits,
        'hit_rate': round(hits / resolved * 100, 1) if resolved > 0 else 0
    }


def get_picks_by_tier(sport: str | None = None):
    """Get hit rate breakdown by tier."""
    if not PICK_DB.exists():
        return []
    
    conn = get_db_conn(PICK_DB)
    
    if sport:
        tiers = conn.execute('''
        SELECT 
            tier,
            COUNT(*) as total,
            SUM(CASE WHEN hit = 1 THEN 1 ELSE 0 END) as hits,
            SUM(CASE WHEN hit IS NOT NULL THEN 1 ELSE 0 END) as resolved
        FROM picks
        WHERE sport = ?
        GROUP BY tier
        ORDER BY 
            CASE tier 
                WHEN 'SLAM' THEN 1 
                WHEN 'STRONG' THEN 2 
                WHEN 'LEAN' THEN 3 
                ELSE 4 
            END
    ''', (sport,)).fetchall()
    else:
        tiers = conn.execute('''
        SELECT 
            tier,
            COUNT(*) as total,
            SUM(CASE WHEN hit = 1 THEN 1 ELSE 0 END) as hits,
            SUM(CASE WHEN hit IS NOT NULL THEN 1 ELSE 0 END) as resolved
        FROM picks
        GROUP BY tier
        ORDER BY 
            CASE tier 
                WHEN 'SLAM' THEN 1 
                WHEN 'STRONG' THEN 2 
                WHEN 'LEAN' THEN 3 
                ELSE 4 
            END
    ''').fetchall()
    
    conn.close()
    
    return [
        {
            'tier': row['tier'],
            'total': row['total'],
            'resolved': row['resolved'],
            'hits': row['hits'],
            'hit_rate': round(row['hits'] / row['resolved'] * 100, 1) if row['resolved'] > 0 else 0
        }
        for row in tiers
    ]


def get_picks_by_stat(sport: str | None = None):
    """Get hit rate breakdown by stat type."""
    if not PICK_DB.exists():
        return []
    
    conn = get_db_conn(PICK_DB)
    
    if sport:
        stats = conn.execute('''
        SELECT 
            stat,
            COUNT(*) as total,
            SUM(CASE WHEN hit = 1 THEN 1 ELSE 0 END) as hits,
            SUM(CASE WHEN hit IS NOT NULL THEN 1 ELSE 0 END) as resolved
        FROM picks
        WHERE sport = ?
        GROUP BY stat
        ORDER BY total DESC
        LIMIT 10
    ''', (sport,)).fetchall()
    else:
        stats = conn.execute('''
        SELECT 
            stat,
            COUNT(*) as total,
            SUM(CASE WHEN hit = 1 THEN 1 ELSE 0 END) as hits,
            SUM(CASE WHEN hit IS NOT NULL THEN 1 ELSE 0 END) as resolved
        FROM picks
        GROUP BY stat
        ORDER BY total DESC
        LIMIT 10
    ''').fetchall()
    
    conn.close()
    
    return [
        {
            'stat': row['stat'],
            'total': row['total'],
            'resolved': row['resolved'],
            'hits': row['hits'],
            'hit_rate': round(row['hits'] / row['resolved'] * 100, 1) if row['resolved'] > 0 else 0
        }
        for row in stats
    ]


def get_picks_by_direction(sport: str | None = None):
    """Get hit rate by direction (HIGHER/LOWER)."""
    if not PICK_DB.exists():
        return []
    
    conn = get_db_conn(PICK_DB)
    
    if sport:
        directions = conn.execute('''
        SELECT 
            direction,
            COUNT(*) as total,
            SUM(CASE WHEN hit = 1 THEN 1 ELSE 0 END) as hits,
            SUM(CASE WHEN hit IS NOT NULL THEN 1 ELSE 0 END) as resolved
        FROM picks
        WHERE sport = ?
        GROUP BY direction
    ''', (sport,)).fetchall()
    else:
        directions = conn.execute('''
        SELECT 
            direction,
            COUNT(*) as total,
            SUM(CASE WHEN hit = 1 THEN 1 ELSE 0 END) as hits,
            SUM(CASE WHEN hit IS NOT NULL THEN 1 ELSE 0 END) as resolved
        FROM picks
        GROUP BY direction
    ''').fetchall()
    
    conn.close()
    
    return [
        {
            'direction': row['direction'],
            'total': row['total'],
            'resolved': row['resolved'],
            'hits': row['hits'],
            'hit_rate': round(row['hits'] / row['resolved'] * 100, 1) if row['resolved'] > 0 else 0
        }
        for row in directions
    ]


def get_recent_picks(limit: int = 50, sport: str | None = None, since_days: int | None = None, resolved_only: bool = False):
    """Get recent picks with optional filters."""
    if not PICK_DB.exists():
        return []
    
    conn = get_db_conn(PICK_DB)
    
    where = []
    params: list = []
    if sport:
        where.append('sport = ?')
        params.append(sport)
    if since_days is not None:
        where.append('created_at >= ?')
        params.append((datetime.now() - timedelta(days=since_days)).isoformat(sep=' '))
    if resolved_only:
        where.append('hit IS NOT NULL')

    where_sql = (' WHERE ' + ' AND '.join(where)) if where else ''
    params.append(limit)

    picks = conn.execute(f'''
        SELECT * FROM picks
        {where_sql}
        ORDER BY created_at DESC
        LIMIT ?
    ''', tuple(params)).fetchall()
    
    conn.close()
    
    return [dict(row) for row in picks]


def get_player_performance(player_name=None, sport: str | None = None):
    """Get performance by player."""
    if not PICK_DB.exists():
        return []
    
    conn = get_db_conn(PICK_DB)
    
    query = '''
        SELECT 
            player_name,
            COUNT(*) as total,
            SUM(CASE WHEN hit = 1 THEN 1 ELSE 0 END) as hits,
            SUM(CASE WHEN hit IS NOT NULL THEN 1 ELSE 0 END) as resolved,
            AVG(confidence) as avg_confidence
        FROM picks
    '''

    params = []
    if sport:
        query += ' WHERE sport = ?'
        params.append(sport)

    query += '''
        GROUP BY player_name
        HAVING resolved > 0
        ORDER BY total DESC
    '''

    players = conn.execute(query, tuple(params)).fetchall()
    conn.close()
    
    return [
        {
            'player': row['player_name'],
            'total': row['total'],
            'resolved': row['resolved'],
            'hits': row['hits'],
            'hit_rate': round(row['hits'] / row['resolved'] * 100, 1) if row['resolved'] > 0 else 0,
            'avg_confidence': round(row['avg_confidence'] * 100, 1) if row['avg_confidence'] else 0
        }
        for row in players
    ]


def get_injuries():
    """Get current injuries"""
    if not INJURY_DB.exists():
        return []
    
    conn = get_db_conn(INJURY_DB)
    
    injuries = conn.execute('''
        SELECT * FROM injuries 
        ORDER BY 
            CASE status 
                WHEN 'OUT' THEN 1 
                WHEN 'DOUBTFUL' THEN 2 
                WHEN 'GTD' THEN 3
                WHEN 'QUESTIONABLE' THEN 4 
                ELSE 5 
            END
    ''').fetchall()
    
    conn.close()
    
    return [dict(row) for row in injuries]


def get_daily_performance(sport: str | None = None):
    """Get performance by day."""
    if not PICK_DB.exists():
        return []
    
    conn = get_db_conn(PICK_DB)
    
    if sport:
        days = conn.execute('''
        SELECT 
            DATE(created_at) as date,
            COUNT(*) as total,
            SUM(CASE WHEN hit = 1 THEN 1 ELSE 0 END) as hits,
            SUM(CASE WHEN hit IS NOT NULL THEN 1 ELSE 0 END) as resolved
        FROM picks
        WHERE sport = ?
        GROUP BY DATE(created_at)
        ORDER BY date DESC
        LIMIT 30
    ''', (sport,)).fetchall()
    else:
        days = conn.execute('''
        SELECT 
            DATE(created_at) as date,
            COUNT(*) as total,
            SUM(CASE WHEN hit = 1 THEN 1 ELSE 0 END) as hits,
            SUM(CASE WHEN hit IS NOT NULL THEN 1 ELSE 0 END) as resolved
        FROM picks
        GROUP BY DATE(created_at)
        ORDER BY date DESC
        LIMIT 30
    ''').fetchall()
    
    conn.close()
    
    return [
        {
            'date': row['date'],
            'total': row['total'],
            'resolved': row['resolved'],
            'hits': row['hits'],
            'hit_rate': round(row['hits'] / row['resolved'] * 100, 1) if row['resolved'] > 0 else 0
        }
        for row in days
    ]


# ═══════════════════════════════════════════════════════════════════
# ROUTES
# ═══════════════════════════════════════════════════════════════════

@app.route('/')
def index():
    """Main dashboard page"""
    stats = get_pick_stats()
    by_tier = get_picks_by_tier()
    by_stat = get_picks_by_stat()
    by_direction = get_picks_by_direction()
    injuries = get_injuries()
    daily = get_daily_performance()
    regret = get_regret_metrics()
    return render_template('dashboard.html',
                          stats=stats,
                          by_tier=by_tier,
                          by_stat=by_stat,
                          by_direction=by_direction,
                          injuries=injuries,
                          daily=daily,
                          regret=regret)


@app.route('/api/stats')
@require_api_key
def api_stats():
    """API endpoint for stats"""
    sport = request.args.get('sport', type=str)
    since_days = request.args.get('since_days', type=int)
    return jsonify(get_pick_stats(sport=sport, since_days=since_days))


@app.route('/api/picks')
@require_api_key
def api_picks():
    """API endpoint for recent picks"""
    limit = request.args.get('limit', 50, type=int)
    sport = request.args.get('sport', type=str)
    since_days = request.args.get('since_days', type=int)
    resolved_only = request.args.get('resolved_only', default=0, type=int) == 1
    return jsonify(get_recent_picks(limit, sport=sport, since_days=since_days, resolved_only=resolved_only))


@app.route('/api/tier/<tier>')
@require_api_key
def api_tier(tier):
    """API endpoint for tier breakdown"""
    sport = request.args.get('sport', type=str)
    by_tier = get_picks_by_tier(sport=sport)
    for t in by_tier:
        if t['tier'] == tier.upper():
            return jsonify(t)
    return jsonify({'error': 'Tier not found'}), 404


@app.route('/api/players')
@require_api_key
def api_players():
    """API endpoint for player performance"""
    sport = request.args.get('sport', type=str)
    return jsonify(get_player_performance(sport=sport))


@app.route('/api/injuries')
@require_api_key
def api_injuries():
    """API endpoint for injuries"""
    return jsonify(get_injuries())


@app.route('/api/daily')
@require_api_key
def api_daily():
    """API endpoint for daily performance"""
    sport = request.args.get('sport', type=str)
    return jsonify(get_daily_performance(sport=sport))


@app.route('/share')
def share():
    """Shareable summary page"""
    stats = get_pick_stats()
    by_tier = get_picks_by_tier()
    return render_template('share.html', stats=stats, by_tier=by_tier)


# ═══════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    print("=" * 60)
    print("🚀 FUOOM Performance Dashboard")
    print("=" * 60)
    print()
    print("   Starting server at http://localhost:5050")
    print()
    print("   Press Ctrl+C to stop")
    print("=" * 60)
    
    app.run(host='0.0.0.0', port=5050, debug=True)
