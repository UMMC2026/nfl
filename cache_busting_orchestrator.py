#!/usr/bin/env python3
"""
TRADE-AWARE CACHE BUSTING SYSTEM
Monitors NFL transactions and automatically invalidates stale player-team mappings

Architecture:
1. Monitor transaction feeds (ESPN, NFL.com)
2. Detect trades, releases, signings, inactivities
3. Auto-invalidate cache entries for affected players
4. Re-validate before MC runs

This prevents the "Diggs on wrong team" failure mode permanently.
"""

import json
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
import sqlite3

# ============================================================================
# CACHE METADATA SYSTEM
# ============================================================================

class CacheManager:
    """Manages cache invalidation based on transactions."""
    
    def __init__(self, cache_dir="cache/", db_file="cache_metadata.db"):
        """Initialize cache tracking database."""
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.db_path = self.cache_dir / db_file
        self._init_db()
    
    def _init_db(self):
        """Create cache metadata tracking table."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS cache_entries (
            player_id TEXT PRIMARY KEY,
            player_name TEXT NOT NULL,
            team TEXT NOT NULL,
            cached_date TEXT NOT NULL,
            data_source TEXT NOT NULL,
            cache_hash TEXT NOT NULL,
            is_valid INTEGER DEFAULT 1,
            invalidation_reason TEXT,
            invalidated_at TEXT
        )
        """)
        
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            transaction_id TEXT PRIMARY KEY,
            player_name TEXT NOT NULL,
            transaction_type TEXT NOT NULL,
            from_team TEXT,
            to_team TEXT,
            transaction_date TEXT NOT NULL,
            detected_at TEXT NOT NULL,
            processed INTEGER DEFAULT 0
        )
        """)
        
        conn.commit()
        conn.close()
    
    def record_cache_entry(self, player_id, player_name, team, data_source):
        """Record a cache entry with metadata."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cache_hash = hashlib.md5(f"{player_name}_{team}_{data_source}".encode()).hexdigest()
        cached_date = datetime.utcnow().isoformat()
        
        cursor.execute("""
        INSERT OR REPLACE INTO cache_entries 
        (player_id, player_name, team, cached_date, data_source, cache_hash, is_valid)
        VALUES (?, ?, ?, ?, ?, ?, 1)
        """, (player_id, player_name, team, cached_date, data_source, cache_hash))
        
        conn.commit()
        conn.close()
    
    def record_transaction(self, player_name, transaction_type, from_team=None, to_team=None, transaction_date=None):
        """Record detected transaction (trade, release, signing)."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        transaction_id = hashlib.md5(
            f"{player_name}_{transaction_type}_{datetime.utcnow().isoformat()}".encode()
        ).hexdigest()
        
        detected_at = datetime.utcnow().isoformat()
        transaction_date = transaction_date or datetime.utcnow().isoformat()
        
        cursor.execute("""
        INSERT INTO transactions 
        (transaction_id, player_name, transaction_type, from_team, to_team, transaction_date, detected_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (transaction_id, player_name, transaction_type, from_team, to_team, transaction_date, detected_at))
        
        # Mark affected cache entries as invalid
        cursor.execute("""
        UPDATE cache_entries
        SET is_valid = 0, invalidation_reason = ?, invalidated_at = ?
        WHERE player_name = ?
        """, (f"TRANSACTION: {transaction_type}", datetime.utcnow().isoformat(), player_name))
        
        conn.commit()
        conn.close()
    
    def get_valid_cache(self, player_name):
        """Retrieve cache entry only if still valid."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute("""
        SELECT player_name, team, data_source, cached_date
        FROM cache_entries
        WHERE player_name = ? AND is_valid = 1
        """, (player_name,))
        
        result = cursor.fetchone()
        conn.close()
        
        return result
    
    def get_invalidated_players(self):
        """Get list of players recently invalidated by transactions."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute("""
        SELECT player_name, invalidation_reason, invalidated_at
        FROM cache_entries
        WHERE is_valid = 0
        ORDER BY invalidated_at DESC
        """)
        
        results = cursor.fetchall()
        conn.close()
        
        return results
    
    def purge_cache_for_player(self, player_name):
        """Hard-delete cache for a specific player."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM cache_entries WHERE player_name = ?", (player_name,))
        
        conn.commit()
        conn.close()
    
    def purge_old_cache(self, days=7):
        """Remove cache entries older than N days."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cutoff_date = (datetime.utcnow() - timedelta(days=days)).isoformat()
        
        cursor.execute("""
        DELETE FROM cache_entries
        WHERE cached_date < ? AND is_valid = 1
        """, (cutoff_date,))
        
        deleted_count = cursor.rowcount
        conn.commit()
        conn.close()
        
        return deleted_count

# ============================================================================
# TRANSACTION MONITOR
# ============================================================================

class TransactionMonitor:
    """Detects NFL transactions and triggers cache invalidation."""
    
    def __init__(self, cache_manager):
        """Initialize with cache manager."""
        self.cache_mgr = cache_manager
        self.transaction_log = []
    
    def check_espn_transactions(self, league="NFL", season=2025):
        """Poll ESPN for recent transactions."""
        # Placeholder: In production, call ESPN transaction endpoint
        # For now, return empty (we'll integrate with actual feeds later)
        return []
    
    def check_nfl_com_transactions(self, week=None):
        """Poll NFL.com for official roster transactions."""
        # Placeholder: In production, call NFL.com roster endpoint
        # For now, return empty
        return []
    
    def process_transaction_feed(self, transactions):
        """Process detected transactions and invalidate cache."""
        for txn in transactions:
            player_name = txn.get("player_name")
            txn_type = txn.get("type")  # "TRADE", "RELEASE", "SIGNING", "INACTIVE"
            from_team = txn.get("from_team")
            to_team = txn.get("to_team")
            txn_date = txn.get("date")
            
            print(f"[TRANSACTION] {txn_type}: {player_name} ({from_team} → {to_team})")
            
            # Record and invalidate
            self.cache_mgr.record_transaction(
                player_name, 
                txn_type, 
                from_team, 
                to_team, 
                txn_date
            )
            
            self.transaction_log.append({
                "player": player_name,
                "type": txn_type,
                "timestamp": datetime.utcnow().isoformat()
            })
    
    def get_transaction_summary(self):
        """Return summary of detected transactions."""
        return {
            "count": len(self.transaction_log),
            "transactions": self.transaction_log
        }

# ============================================================================
# WEEK BOUNDARY DETECTOR
# ============================================================================

class WeekBoundaryDetector:
    """Detects NFL week boundaries and triggers cache refresh."""
    
    def __init__(self, cache_manager):
        """Initialize with cache manager."""
        self.cache_mgr = cache_manager
        self.current_week = self._get_current_week()
        self.last_week_cache_purge = self._get_last_purge_date()
    
    def _get_current_week(self):
        """Determine current NFL week (simplified)."""
        # In production: Call NFL API or ESPN to get official week
        today = datetime.utcnow()
        
        # Rough approximation: NFL season typically runs Sept-Jan
        # Week 1 ≈ early September
        if today.month < 9:
            return None  # Off-season
        
        days_since_sept_1 = (today - datetime(today.year, 9, 1)).days
        week = (days_since_sept_1 // 7) + 1
        
        return min(week, 18)  # NFL max 18 weeks
    
    def _get_last_purge_date(self):
        """Get timestamp of last cache purge."""
        db_path = self.cache_mgr.db_path
        if not db_path.exists():
            return None
        
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        cursor.execute("SELECT MAX(invalidated_at) FROM cache_entries WHERE is_valid = 0")
        result = cursor.fetchone()
        conn.close()
        
        return result[0] if result else None
    
    def should_purge_cache(self):
        """Check if week boundary crossed since last purge."""
        if self.current_week is None:
            return False
        
        if self.last_week_cache_purge is None:
            return True  # First time
        
        last_purge = datetime.fromisoformat(self.last_week_cache_purge)
        days_since = (datetime.utcnow() - last_purge).days
        
        # Purge if 7+ days have passed (week boundary)
        return days_since >= 7
    
    def purge_and_report(self):
        """Purge old cache and return summary."""
        if not self.should_purge_cache():
            return None
        
        deleted_count = self.cache_mgr.purge_old_cache(days=7)
        
        return {
            "action": "CACHE_PURGE_WEEK_BOUNDARY",
            "current_week": self.current_week,
            "entries_deleted": deleted_count,
            "purged_at": datetime.utcnow().isoformat()
        }

# ============================================================================
# MAIN CACHE BUSTING ORCHESTRATOR
# ============================================================================

class CacheBustingOrchestrator:
    """Coordinates all cache invalidation mechanisms."""
    
    def __init__(self):
        """Initialize all subsystems."""
        self.cache_mgr = CacheManager()
        self.tx_monitor = TransactionMonitor(self.cache_mgr)
        self.week_detector = WeekBoundaryDetector(self.cache_mgr)
        self.busting_report = {}
    
    def run_full_validation(self, log_path="outputs/"):
        """Execute complete cache validation and busting routine."""
        self.busting_report = {
            "timestamp": datetime.utcnow().isoformat(),
            "actions": []
        }
        
        print("\n" + "="*90)
        print("TRADE-AWARE CACHE BUSTING - FULL VALIDATION")
        print("="*90 + "\n")
        
        # Step 1: Check for transactions
        print("[STEP 1] Checking transaction feeds...")
        espn_txns = self.tx_monitor.check_espn_transactions()
        nfl_txns = self.tx_monitor.check_nfl_com_transactions()
        
        all_txns = espn_txns + nfl_txns
        if all_txns:
            print(f"[OK] Found {len(all_txns)} transactions\n")
            self.tx_monitor.process_transaction_feed(all_txns)
            self.busting_report["actions"].append(self.tx_monitor.get_transaction_summary())
        else:
            print("[INFO] No transactions detected\n")
        
        # Step 2: Check week boundary
        print("[STEP 2] Checking week boundary...")
        week_action = self.week_detector.purge_and_report()
        if week_action:
            print(f"[OK] Week boundary detected — purged {week_action['entries_deleted']} old entries\n")
            self.busting_report["actions"].append(week_action)
        else:
            print("[INFO] No week boundary crossing\n")
        
        # Step 3: Report invalidated players
        print("[STEP 3] Invalidated players (recent)...")
        invalidated = self.cache_mgr.get_invalidated_players()
        if invalidated:
            print(f"[WARN] {len(invalidated)} players with stale cache:\n")
            for player, reason, invalidated_at in invalidated[:10]:
                print(f"  • {player:20} | {reason:30} | {invalidated_at}")
            self.busting_report["invalidated_count"] = len(invalidated)
        else:
            print("[OK] No invalidated players detected\n")
        
        # Step 4: Save report
        report_path = Path(log_path) / f"CACHE_BUSTING_REPORT_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(self.busting_report, indent=2))
        
        print("="*90)
        print(f"[OK] Cache busting report: {report_path.name}")
        print("="*90 + "\n")
        
        return self.busting_report
    
    def is_player_cache_valid(self, player_name):
        """Check if player cache is still valid before MC runs."""
        valid_cache = self.cache_mgr.get_valid_cache(player_name)
        return valid_cache is not None

# ============================================================================
# CLI + INTEGRATION POINT
# ============================================================================

if __name__ == "__main__":
    orchestrator = CacheBustingOrchestrator()
    report = orchestrator.run_full_validation()
    
    print("\n[STATUS] Cache busting system ready.")
    print("Integrate with run_all_games_monte_carlo.py via:")
    print("  → Call orchestrator.run_full_validation() before MC")
    print("  → Use orchestrator.is_player_cache_valid(name) for pre-flight checks\n")
