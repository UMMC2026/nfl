"""
LIQUIDITY GATE — Priority 1 Implementation
==========================================

Verifies that recommended picks actually exist on sportsbooks.

Features:
- Check if line exists on PrizePicks/Underdog/DraftKings
- Track line movement (>2% movement = stale)
- Block picks with no liquidity
- Cache API responses to avoid rate limits

Phase: 5A (Priority 1)
Created: 2026-02-05
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import hashlib

logger = logging.getLogger(__name__)

# Project root
PROJECT_ROOT = Path(__file__).parent.parent


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class LineInfo:
    """Information about a betting line from a book."""
    book: str
    player: str
    stat: str
    line: float
    direction: str  # higher/lower or over/under
    timestamp: datetime
    available: bool = True
    price: Optional[float] = None  # Implied probability or odds
    
    def is_stale(self, max_age_minutes: int = 30) -> bool:
        """Check if line info is too old."""
        age = datetime.now() - self.timestamp
        return age > timedelta(minutes=max_age_minutes)


@dataclass
class LiquidityCheckResult:
    """Result of liquidity verification."""
    pick_id: str
    player: str
    stat: str
    line: float
    direction: str
    
    # Verification results
    is_available: bool = False
    book_checked: str = ""
    actual_line: Optional[float] = None
    line_movement: float = 0.0  # Percentage movement from expected
    
    # Blocking flags
    blocked: bool = False
    block_reason: str = ""
    
    # Metadata
    checked_at: datetime = field(default_factory=datetime.now)
    cache_hit: bool = False
    
    def to_dict(self) -> Dict:
        return {
            "pick_id": self.pick_id,
            "player": self.player,
            "stat": self.stat,
            "line": self.line,
            "direction": self.direction,
            "is_available": self.is_available,
            "book_checked": self.book_checked,
            "actual_line": self.actual_line,
            "line_movement": self.line_movement,
            "blocked": self.blocked,
            "block_reason": self.block_reason,
            "checked_at": self.checked_at.isoformat(),
            "cache_hit": self.cache_hit,
        }


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class LiquidityGateConfig:
    """Configuration for liquidity checks."""
    
    # Maximum line movement before blocking (percentage)
    max_line_movement_pct: float = 5.0
    
    # Maximum age of cached line data (minutes)
    cache_max_age_minutes: int = 30
    
    # Minimum edge after line movement to keep pick
    min_edge_after_movement: float = 2.0
    
    # Books to check (in priority order)
    books_to_check: List[str] = field(default_factory=lambda: [
        "underdog",
        "prizepicks",
        "draftkings",
    ])
    
    # Whether to block or just warn on liquidity issues
    block_on_unavailable: bool = True
    warn_on_movement: bool = True
    
    # Rate limiting
    requests_per_minute: int = 30
    
    # Cache file location
    cache_file: Path = field(default_factory=lambda: 
        PROJECT_ROOT / "cache" / "liquidity_cache.json")


# Default configuration
DEFAULT_CONFIG = LiquidityGateConfig()


# =============================================================================
# LIQUIDITY CACHE
# =============================================================================

class LiquidityCache:
    """Cache for line availability data."""
    
    def __init__(self, cache_file: Path = None):
        self.cache_file = cache_file or DEFAULT_CONFIG.cache_file
        self.cache: Dict[str, Dict] = {}
        self._load_cache()
    
    def _load_cache(self):
        """Load cache from disk."""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, "r") as f:
                    raw = json.load(f)
                    # Convert timestamps
                    for key, value in raw.items():
                        if "timestamp" in value:
                            value["timestamp"] = datetime.fromisoformat(value["timestamp"])
                    self.cache = raw
            except Exception as e:
                logger.warning(f"Failed to load liquidity cache: {e}")
                self.cache = {}
        else:
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
    
    def _save_cache(self):
        """Save cache to disk."""
        try:
            # Convert timestamps for JSON
            serializable = {}
            for key, value in self.cache.items():
                entry = dict(value)
                if isinstance(entry.get("timestamp"), datetime):
                    entry["timestamp"] = entry["timestamp"].isoformat()
                serializable[key] = entry
            
            with open(self.cache_file, "w") as f:
                json.dump(serializable, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save liquidity cache: {e}")
    
    def _make_key(self, player: str, stat: str, line: float, book: str) -> str:
        """Create cache key."""
        raw = f"{player.lower()}|{stat.lower()}|{line}|{book.lower()}"
        return hashlib.md5(raw.encode()).hexdigest()[:16]
    
    def get(self, player: str, stat: str, line: float, book: str, 
            max_age_minutes: int = 30) -> Optional[LineInfo]:
        """Get cached line info if fresh."""
        key = self._make_key(player, stat, line, book)
        
        if key not in self.cache:
            return None
        
        entry = self.cache[key]
        timestamp = entry.get("timestamp")
        
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)
        
        if not timestamp:
            return None
        
        # Check freshness
        age = datetime.now() - timestamp
        if age > timedelta(minutes=max_age_minutes):
            return None
        
        return LineInfo(
            book=entry.get("book", book),
            player=entry.get("player", player),
            stat=entry.get("stat", stat),
            line=entry.get("line", line),
            direction=entry.get("direction", ""),
            timestamp=timestamp,
            available=entry.get("available", False),
            price=entry.get("price"),
        )
    
    def set(self, line_info: LineInfo):
        """Cache line info."""
        key = self._make_key(
            line_info.player, 
            line_info.stat, 
            line_info.line, 
            line_info.book
        )
        
        self.cache[key] = {
            "book": line_info.book,
            "player": line_info.player,
            "stat": line_info.stat,
            "line": line_info.line,
            "direction": line_info.direction,
            "timestamp": line_info.timestamp,
            "available": line_info.available,
            "price": line_info.price,
        }
        
        self._save_cache()
    
    def clear_stale(self, max_age_minutes: int = 60):
        """Remove stale entries."""
        now = datetime.now()
        stale_keys = []
        
        for key, entry in self.cache.items():
            timestamp = entry.get("timestamp")
            if isinstance(timestamp, str):
                timestamp = datetime.fromisoformat(timestamp)
            
            if not timestamp:
                stale_keys.append(key)
                continue
            
            age = now - timestamp
            if age > timedelta(minutes=max_age_minutes):
                stale_keys.append(key)
        
        for key in stale_keys:
            del self.cache[key]
        
        if stale_keys:
            self._save_cache()
            logger.info(f"Cleared {len(stale_keys)} stale cache entries")


# =============================================================================
# BOOK API CLIENTS (Stubs for real API integration)
# =============================================================================

class UnderdogClient:
    """Client for Underdog Fantasy API."""
    
    def __init__(self):
        self.base_url = "https://api.underdogfantasy.com"
        # In real implementation, would use API key from env
        self.api_key = os.getenv("UNDERDOG_API_KEY", "")
    
    def get_line(self, player: str, stat: str, line: float) -> Optional[LineInfo]:
        """
        Get line info from Underdog.
        
        NOTE: This is a stub. Real implementation would:
        1. Query Underdog API for player props
        2. Find matching line
        3. Return availability and current price
        
        For now, returns simulated data based on common patterns.
        """
        # Simulate API response (in production, replace with real API call)
        # Assume lines are available with small random movement
        import random
        
        # Simulate 90% availability rate
        available = random.random() < 0.90
        
        # Simulate small line movements (-0.5 to +0.5)
        if available:
            movement = random.uniform(-0.5, 0.5)
            actual_line = line + movement
        else:
            actual_line = None
        
        return LineInfo(
            book="underdog",
            player=player,
            stat=stat,
            line=actual_line if actual_line else line,
            direction="",
            timestamp=datetime.now(),
            available=available,
            price=0.50 if available else None,  # Even odds for demo
        )


class PrizePicksClient:
    """Client for PrizePicks API."""
    
    def __init__(self):
        self.base_url = "https://api.prizepicks.com"
        self.api_key = os.getenv("PRIZEPICKS_API_KEY", "")
    
    def get_line(self, player: str, stat: str, line: float) -> Optional[LineInfo]:
        """
        Get line info from PrizePicks.
        
        NOTE: Stub implementation. See UnderdogClient for details.
        """
        import random
        
        available = random.random() < 0.85
        
        if available:
            movement = random.uniform(-0.5, 0.5)
            actual_line = line + movement
        else:
            actual_line = None
        
        return LineInfo(
            book="prizepicks",
            player=player,
            stat=stat,
            line=actual_line if actual_line else line,
            direction="",
            timestamp=datetime.now(),
            available=available,
            price=0.50 if available else None,
        )


class DraftKingsClient:
    """Client for DraftKings API."""
    
    def __init__(self):
        self.base_url = "https://sportsbook.draftkings.com"
        self.api_key = os.getenv("DRAFTKINGS_API_KEY", "")
    
    def get_line(self, player: str, stat: str, line: float) -> Optional[LineInfo]:
        """
        Get line info from DraftKings.
        
        NOTE: Stub implementation. See UnderdogClient for details.
        """
        import random
        
        available = random.random() < 0.80
        
        if available:
            movement = random.uniform(-1.0, 1.0)
            actual_line = line + movement
        else:
            actual_line = None
        
        return LineInfo(
            book="draftkings",
            player=player,
            stat=stat,
            line=actual_line if actual_line else line,
            direction="",
            timestamp=datetime.now(),
            available=available,
            price=0.50 if available else None,
        )


# =============================================================================
# LIQUIDITY GATE
# =============================================================================

class LiquidityGate:
    """
    Gate that verifies picks have actual liquidity.
    
    Features:
    - Check multiple books in priority order
    - Cache results to avoid rate limits
    - Block picks with no liquidity
    - Warn on significant line movement
    """
    
    def __init__(self, config: LiquidityGateConfig = None):
        self.config = config or DEFAULT_CONFIG
        self.cache = LiquidityCache(self.config.cache_file)
        
        # Initialize book clients
        self.clients = {
            "underdog": UnderdogClient(),
            "prizepicks": PrizePicksClient(),
            "draftkings": DraftKingsClient(),
        }
    
    def check_liquidity(
        self,
        player: str,
        stat: str,
        line: float,
        direction: str,
        pick_id: str = "",
        expected_prob: float = 0.0,
    ) -> LiquidityCheckResult:
        """
        Check if a pick has liquidity.
        
        Args:
            player: Player name
            stat: Stat type (points, rebounds, etc.)
            line: Expected betting line
            direction: higher/lower or over/under
            pick_id: Unique identifier for the pick
            expected_prob: Expected probability (for edge calculation)
        
        Returns:
            LiquidityCheckResult with availability and blocking info
        """
        result = LiquidityCheckResult(
            pick_id=pick_id or f"{player}_{stat}_{line}",
            player=player,
            stat=stat,
            line=line,
            direction=direction,
        )
        
        # Try each book in priority order
        for book in self.config.books_to_check:
            # Check cache first
            cached = self.cache.get(
                player, stat, line, book,
                max_age_minutes=self.config.cache_max_age_minutes
            )
            
            if cached:
                result.cache_hit = True
                line_info = cached
            else:
                # Query the book
                client = self.clients.get(book)
                if not client:
                    continue
                
                line_info = client.get_line(player, stat, line)
                
                if line_info:
                    self.cache.set(line_info)
            
            if line_info and line_info.available:
                result.is_available = True
                result.book_checked = book
                result.actual_line = line_info.line
                
                # Calculate line movement
                if line_info.line != line:
                    movement_pct = abs(line_info.line - line) / line * 100
                    result.line_movement = movement_pct
                    
                    # Check if movement is too large
                    if movement_pct > self.config.max_line_movement_pct:
                        result.blocked = True
                        result.block_reason = (
                            f"Line moved {movement_pct:.1f}% "
                            f"(from {line} to {line_info.line})"
                        )
                
                break  # Found available line, stop checking
        
        # If no book has it, block the pick
        if not result.is_available:
            if self.config.block_on_unavailable:
                result.blocked = True
                result.block_reason = "Line not available on any checked book"
        
        return result
    
    def check_batch(
        self,
        picks: List[Dict],
        player_key: str = "player",
        stat_key: str = "stat",
        line_key: str = "line",
        direction_key: str = "direction",
    ) -> List[LiquidityCheckResult]:
        """
        Check liquidity for a batch of picks.
        
        Args:
            picks: List of pick dictionaries
            player_key: Key for player name in dict
            stat_key: Key for stat type in dict
            line_key: Key for line value in dict
            direction_key: Key for direction in dict
        
        Returns:
            List of LiquidityCheckResult objects
        """
        results = []
        
        for i, pick in enumerate(picks):
            player = pick.get(player_key, "")
            stat = pick.get(stat_key, "")
            line = pick.get(line_key, 0.0)
            direction = pick.get(direction_key, "")
            pick_id = pick.get("pick_id", pick.get("edge_id", f"pick_{i}"))
            
            result = self.check_liquidity(
                player=player,
                stat=stat,
                line=line,
                direction=direction,
                pick_id=pick_id,
            )
            
            results.append(result)
        
        return results
    
    def filter_playable(
        self,
        picks: List[Dict],
        results: List[LiquidityCheckResult] = None,
    ) -> Tuple[List[Dict], List[Dict]]:
        """
        Filter picks into playable and blocked lists.
        
        Args:
            picks: Original pick list
            results: Optional pre-computed results
        
        Returns:
            Tuple of (playable_picks, blocked_picks)
        """
        if results is None:
            results = self.check_batch(picks)
        
        playable = []
        blocked = []
        
        for pick, result in zip(picks, results):
            # Add liquidity info to pick
            pick["liquidity_check"] = result.to_dict()
            
            if result.blocked:
                blocked.append(pick)
            else:
                playable.append(pick)
        
        return playable, blocked
    
    def get_summary(self, results: List[LiquidityCheckResult]) -> Dict:
        """Get summary statistics for batch check."""
        total = len(results)
        available = sum(1 for r in results if r.is_available)
        blocked = sum(1 for r in results if r.blocked)
        cache_hits = sum(1 for r in results if r.cache_hit)
        
        avg_movement = 0.0
        if available > 0:
            movements = [r.line_movement for r in results if r.is_available]
            avg_movement = sum(movements) / len(movements) if movements else 0.0
        
        return {
            "total_checked": total,
            "available": available,
            "blocked": blocked,
            "cache_hits": cache_hits,
            "availability_rate": available / total * 100 if total > 0 else 0,
            "avg_line_movement_pct": avg_movement,
        }


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

# Global gate instance
_gate: Optional[LiquidityGate] = None


def get_gate() -> LiquidityGate:
    """Get or create global gate instance."""
    global _gate
    if _gate is None:
        _gate = LiquidityGate()
    return _gate


def check_pick_liquidity(
    player: str,
    stat: str,
    line: float,
    direction: str = "",
    pick_id: str = "",
) -> LiquidityCheckResult:
    """Check liquidity for a single pick."""
    return get_gate().check_liquidity(
        player=player,
        stat=stat,
        line=line,
        direction=direction,
        pick_id=pick_id,
    )


def filter_playable_picks(picks: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
    """Filter picks by liquidity."""
    return get_gate().filter_playable(picks)


def run_liquidity_gate(picks: List[Dict]) -> Dict:
    """
    Run liquidity gate on picks and return summary.
    
    This is the main entry point for pipeline integration.
    """
    gate = get_gate()
    results = gate.check_batch(picks)
    playable, blocked = gate.filter_playable(picks, results)
    summary = gate.get_summary(results)
    
    return {
        "playable": playable,
        "blocked": blocked,
        "summary": summary,
    }


# =============================================================================
# CLI INTERFACE
# =============================================================================

def main():
    """CLI for testing liquidity gate."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Liquidity Gate Tester")
    parser.add_argument("--player", default="LeBron James", help="Player name")
    parser.add_argument("--stat", default="points", help="Stat type")
    parser.add_argument("--line", type=float, default=25.5, help="Betting line")
    parser.add_argument("--direction", default="higher", help="Direction")
    parser.add_argument("--batch-test", action="store_true", help="Run batch test")
    
    args = parser.parse_args()
    
    if args.batch_test:
        # Test with sample picks
        test_picks = [
            {"player": "LeBron James", "stat": "points", "line": 25.5, "direction": "higher"},
            {"player": "Stephen Curry", "stat": "3pm", "line": 4.5, "direction": "higher"},
            {"player": "Nikola Jokic", "stat": "assists", "line": 8.5, "direction": "lower"},
            {"player": "Luka Doncic", "stat": "rebounds", "line": 9.5, "direction": "higher"},
            {"player": "Unknown Player", "stat": "points", "line": 15.5, "direction": "higher"},
        ]
        
        print("\n" + "=" * 60)
        print("LIQUIDITY GATE — BATCH TEST")
        print("=" * 60)
        
        result = run_liquidity_gate(test_picks)
        
        print(f"\n📊 Summary:")
        for key, value in result["summary"].items():
            print(f"   {key}: {value}")
        
        print(f"\n✅ Playable ({len(result['playable'])}):")
        for pick in result["playable"]:
            liq = pick.get("liquidity_check", {})
            print(f"   {pick['player']} {pick['stat']} {pick['line']} "
                  f"— {liq.get('book_checked', 'N/A')} "
                  f"(movement: {liq.get('line_movement', 0):.1f}%)")
        
        print(f"\n❌ Blocked ({len(result['blocked'])}):")
        for pick in result["blocked"]:
            liq = pick.get("liquidity_check", {})
            print(f"   {pick['player']} {pick['stat']} {pick['line']} "
                  f"— {liq.get('block_reason', 'Unknown')}")
    
    else:
        # Single pick test
        print("\n" + "=" * 60)
        print("LIQUIDITY GATE — SINGLE CHECK")
        print("=" * 60)
        
        result = check_pick_liquidity(
            player=args.player,
            stat=args.stat,
            line=args.line,
            direction=args.direction,
        )
        
        print(f"\nPlayer: {result.player}")
        print(f"Stat: {result.stat}")
        print(f"Line: {result.line}")
        print(f"Direction: {result.direction}")
        print(f"\nAvailable: {'✅ Yes' if result.is_available else '❌ No'}")
        print(f"Book: {result.book_checked or 'N/A'}")
        print(f"Actual Line: {result.actual_line or 'N/A'}")
        print(f"Movement: {result.line_movement:.2f}%")
        print(f"Blocked: {'❌ Yes' if result.blocked else '✅ No'}")
        if result.block_reason:
            print(f"Block Reason: {result.block_reason}")
        print(f"Cache Hit: {'Yes' if result.cache_hit else 'No'}")


if __name__ == "__main__":
    main()
