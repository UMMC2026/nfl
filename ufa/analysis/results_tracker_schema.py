"""
Database Schema for UFA Results Tracker

This schema defines the database structure for storing pick results,
enabling efficient querying and analysis for the learning loop.

Recommended: PostgreSQL or SQLite for local development.
"""

# SQL Schema for results_tracker database

RESULTS_TRACKER_SCHEMA = """
-- UFA Results Tracker Database Schema
-- Stores historical pick performance for learning and analysis

-- Main picks table
CREATE TABLE IF NOT EXISTS picks (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    player_name VARCHAR(100) NOT NULL,
    team VARCHAR(10) NOT NULL,
    stat VARCHAR(50) NOT NULL,  -- 'points', 'assists', 'pts+reb+ast', etc.
    line DECIMAL(5,1) NOT NULL,
    direction VARCHAR(10) NOT NULL CHECK (direction IN ('higher', 'lower')),
    tier VARCHAR(20) NOT NULL CHECK (tier IN ('SLAM', 'STRONG', 'LEAN')),
    confidence DECIMAL(3,2) NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    result VARCHAR(10) CHECK (result IN ('HIT', 'MISS', 'PUSH', 'PENDING', 'UNKNOWN')),
    actual_value DECIMAL(6,1),  -- Actual stat achieved
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Ensure unique pick per player/stat/date
    UNIQUE(date, player_name, stat)
);

-- Index for efficient queries
CREATE INDEX IF NOT EXISTS idx_picks_date ON picks(date);
CREATE INDEX IF NOT EXISTS idx_picks_player ON picks(player_name);
CREATE INDEX IF NOT EXISTS idx_picks_stat ON picks(stat);
CREATE INDEX IF NOT EXISTS idx_picks_tier ON picks(tier);
CREATE INDEX IF NOT EXISTS idx_picks_result ON picks(result);

-- Learning analysis cache table (optional - for performance)
CREATE TABLE IF NOT EXISTS analysis_cache (
    id SERIAL PRIMARY KEY,
    analysis_type VARCHAR(50) NOT NULL,  -- 'pattern_analysis', 'anomaly_detection', etc.
    date_range_start DATE NOT NULL,
    date_range_end DATE NOT NULL,
    parameters JSONB,  -- Analysis parameters
    results JSONB,     -- Cached results
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,  -- When to refresh cache

    UNIQUE(analysis_type, date_range_start, date_range_end, parameters)
);

-- Anomalies table for tracking large misses that need investigation
CREATE TABLE IF NOT EXISTS anomalies (
    id SERIAL PRIMARY KEY,
    pick_id INTEGER REFERENCES picks(id),
    deviation DECIMAL(5,1) NOT NULL,  -- How far off the prediction was
    investigation_status VARCHAR(20) DEFAULT 'PENDING' CHECK (investigation_status IN ('PENDING', 'INVESTIGATED', 'RESOLVED')),
    investigation_notes TEXT,
    serpapi_search_query TEXT,  -- Query used for contextual search
    serpapi_results JSONB,      -- Results from SerpApi investigation
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Model refinement suggestions table
CREATE TABLE IF NOT EXISTS model_suggestions (
    id SERIAL PRIMARY KEY,
    suggestion_type VARCHAR(50) NOT NULL,  -- 'confidence_adjustment', 'stat_penalty', etc.
    target_entity VARCHAR(100) NOT NULL,   -- What to adjust (stat type, player, tier, etc.)
    current_value DECIMAL(5,2),            -- Current value
    suggested_value DECIMAL(5,2),          -- Suggested new value
    reasoning TEXT NOT NULL,
    confidence DECIMAL(3,2) NOT NULL,      -- How confident we are in this suggestion
    implemented BOOLEAN DEFAULT FALSE,
    implemented_at TIMESTAMP,
    results_observed TEXT,                 -- What happened after implementation
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Performance snapshots for tracking improvement over time
CREATE TABLE IF NOT EXISTS performance_snapshots (
    id SERIAL PRIMARY KEY,
    snapshot_date DATE NOT NULL,
    analysis_period_days INTEGER NOT NULL,
    total_picks INTEGER NOT NULL,
    win_rate DECIMAL(5,2) NOT NULL,
    roi_units DECIMAL(6,2),
    tier_performance JSONB,  -- Win rates by tier
    stat_performance JSONB,  -- Win rates by stat type
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(snapshot_date, analysis_period_days)
);
"""

# Python class for database operations
class ResultsTrackerDB:
    """
    Database-backed results tracker.

    This would replace or supplement the JSON-based ResultsTracker.
    """

    def __init__(self, connection_string: str = "sqlite:///ufa_results.db"):
        # Use SQLAlchemy or similar ORM
        pass

    def save_pick(self, pick_data: dict):
        """Save a pick to the database."""
        # Implementation would use SQLAlchemy or similar
        pass

    def update_result(self, date: str, player: str, stat: str, result: str, actual_value: float = None):
        """Update pick result after game."""
        # Implementation
        pass

    def get_learning_data(self, days_back: int = 30) -> list:
        """Get resolved picks for learning analysis."""
        # Query for picks with HIT/MISS/PUSH results
        pass

    def save_analysis_results(self, analysis_type: str, results: dict):
        """Cache analysis results for performance."""
        pass

# Migration script from JSON to database
def migrate_json_to_db(json_dir: str = "data_center/results", db_connection = None):
    """
    Migrate existing JSON results to database.

    Run this once to migrate from the current JSON-based system.
    """
    import json
    from pathlib import Path

    json_dir = Path(json_dir)
    if not json_dir.exists():
        print("No JSON results directory found")
        return

    migrated_count = 0
    for json_file in json_dir.glob("results_*.json"):
        with open(json_file, 'r') as f:
            data = json.load(f)

        date = data['date']
        for pick_dict in data['picks']:
            # Convert to database format
            pick_data = {
                'date': date,
                'player_name': pick_dict['player'],
                'team': pick_dict['team'],
                'stat': pick_dict['stat'],
                'line': pick_dict['line'],
                'direction': pick_dict['direction'],
                'tier': pick_dict['tier'],
                'confidence': pick_dict['confidence'],
                'result': pick_dict['result'],
                'actual_value': pick_dict['actual_value']
            }

            # Save to database
            # db_connection.save_pick(pick_data)
            migrated_count += 1

    print(f"Migrated {migrated_count} picks to database")

# Example queries for learning analysis
LEARNING_QUERIES = {
    "win_rate_by_stat": """
        SELECT
            stat,
            COUNT(*) as total_picks,
            SUM(CASE WHEN result = 'HIT' THEN 1 ELSE 0 END) as hits,
            ROUND(
                SUM(CASE WHEN result = 'HIT' THEN 1 ELSE 0 END)::decimal /
                NULLIF(SUM(CASE WHEN result IN ('HIT', 'MISS') THEN 1 ELSE 0 END), 0), 3
            ) as win_rate
        FROM picks
        WHERE result IN ('HIT', 'MISS')
          AND date >= CURRENT_DATE - INTERVAL '%s days'
        GROUP BY stat
        HAVING COUNT(*) >= 5
        ORDER BY win_rate DESC
    """,

    "anomalies": """
        SELECT
            player_name,
            stat,
            line,
            actual_value,
            CASE
                WHEN direction = 'higher' THEN line - actual_value
                ELSE actual_value - line
            END as deviation,
            confidence,
            date
        FROM picks
        WHERE result = 'MISS'
          AND CASE
                WHEN direction = 'higher' THEN line - actual_value
                ELSE actual_value - line
              END > 5
        ORDER BY deviation DESC
        LIMIT 10
    """,

    "tier_performance": """
        SELECT
            tier,
            COUNT(*) as total_picks,
            ROUND(AVG(confidence), 3) as avg_confidence,
            ROUND(
                SUM(CASE WHEN result = 'HIT' THEN 1 ELSE 0 END)::decimal /
                NULLIF(SUM(CASE WHEN result IN ('HIT', 'MISS') THEN 1 ELSE 0 END), 0), 3
            ) as win_rate
        FROM picks
        WHERE result IN ('HIT', 'MISS')
          AND date >= CURRENT_DATE - INTERVAL '%s days'
        GROUP BY tier
        ORDER BY win_rate DESC
    """
}

if __name__ == "__main__":
    print("UFA Results Tracker Database Schema")
    print("=" * 50)
    print("Copy the SQL above to create the database tables.")
    print("\nTo migrate existing JSON data:")
    print("  migrate_json_to_db()")
    print("\nFor learning queries, see LEARNING_QUERIES dict.")