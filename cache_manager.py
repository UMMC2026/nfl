#!/usr/bin/env python3
"""
FUOOM CACHE MANAGER — Cross-Sport Namespace Isolation
======================================================
Prevents cache contamination between sports modules.

Features:
- Sport-namespaced cache keys (CBB|, NBA|, NFL|, TENNIS|, etc.)
- Automatic cache migration from legacy format
- Cache diagnostics and cleanup utilities
- Thread-safe operations
- Automatic expiration handling

Usage:
    from cache_manager import CacheManager
    
    cache = CacheManager(sport="CBB")
    cache.set("john_smith_DUKE", player_data)
    data = cache.get("john_smith_DUKE")
    
CLI Usage:
    python cache_manager.py --diagnose
    python cache_manager.py --clean --sport CBB
    python cache_manager.py --migrate --sport ALL
    python cache_manager.py --purge --sport TENNIS
"""

import os
import sys
import json
import pickle
import hashlib
import argparse
import threading
from pathlib import Path
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import shutil


class Sport(Enum):
    """Supported sports with cache prefixes"""
    NBA = "NBA"
    NFL = "NFL"
    CBB = "CBB"      # College Basketball
    CFB = "CFB"      # College Football
    WNBA = "WNBA"
    TENNIS = "TENNIS"
    GOLF = "GOLF"
    SOCCER = "SOCCER"
    BOXING = "BOXING"
    MMA = "MMA"
    MLB = "MLB"
    NHL = "NHL"
    
    # System caches (not sport-specific)
    SYSTEM = "SYSTEM"
    CALIBRATION = "CALIBRATION"
    MARKET = "MARKET"
    
    @classmethod
    def all_sports(cls) -> List[str]:
        return [s.value for s in cls if s not in [cls.SYSTEM, cls.CALIBRATION, cls.MARKET]]
    
    @classmethod
    def from_string(cls, s: str) -> 'Sport':
        """Parse sport from string, case-insensitive"""
        s_upper = s.upper().strip()
        for sport in cls:
            if sport.value == s_upper:
                return sport
        raise ValueError(f"Unknown sport: {s}")


@dataclass
class CacheEntry:
    """Individual cache entry with metadata"""
    key: str
    value: Any
    sport: str
    created_at: datetime
    expires_at: Optional[datetime] = None
    access_count: int = 0
    last_accessed: Optional[datetime] = None
    checksum: Optional[str] = None
    
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at
    
    def to_dict(self) -> Dict:
        return {
            "key": self.key,
            "sport": self.sport,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "access_count": self.access_count,
            "last_accessed": self.last_accessed.isoformat() if self.last_accessed else None,
            "checksum": self.checksum,
            "value_type": type(self.value).__name__,
            "value_size_bytes": len(pickle.dumps(self.value))
        }


@dataclass
class CacheDiagnostics:
    """Cache diagnostic report"""
    total_entries: int = 0
    entries_by_sport: Dict[str, int] = field(default_factory=dict)
    orphaned_entries: List[str] = field(default_factory=list)
    cross_contamination: List[Dict] = field(default_factory=list)
    expired_entries: List[str] = field(default_factory=list)
    total_size_bytes: int = 0
    size_by_sport: Dict[str, int] = field(default_factory=dict)
    legacy_keys: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "total_entries": self.total_entries,
            "entries_by_sport": self.entries_by_sport,
            "orphaned_entries": self.orphaned_entries,
            "cross_contamination": self.cross_contamination,
            "expired_entries": self.expired_entries,
            "total_size_bytes": self.total_size_bytes,
            "size_by_sport": self.size_by_sport,
            "legacy_keys": self.legacy_keys,
            "health_status": self._health_status()
        }
    
    def _health_status(self) -> str:
        if self.cross_contamination:
            return "CRITICAL - Cross-sport contamination detected"
        if self.orphaned_entries:
            return "WARNING - Orphaned entries found"
        if len(self.legacy_keys) > 10:
            return "WARNING - Many legacy keys need migration"
        if self.expired_entries:
            return "INFO - Expired entries can be cleaned"
        return "HEALTHY"


class CacheManager:
    """
    Thread-safe, sport-namespaced cache manager for FUOOM.
    
    Key Format: {SPORT}|{original_key}
    Example: CBB|john_smith_DUKE, NBA|lebron_james_LAL
    """
    
    # Default cache settings
    DEFAULT_CACHE_DIR = "cache"
    DEFAULT_TTL_HOURS = 24
    SEPARATOR = "|"
    
    # Known team codes by sport (for legacy key detection)
    TEAM_PATTERNS = {
        "CBB": {"DUKE", "UNC", "KANSAS", "UCLA", "KENTUCKY", "GONZAGA", "BAYLOR", "PURDUE", "HOUSTON", "UCONN",
                "WASH", "ARIZ", "MSU", "MICH", "IND", "OSU", "STAN", "CAL", "ORE", "COLO"},
        "NBA": {"LAL", "BOS", "GSW", "MIA", "PHX", "DEN", "MIL", "PHI", "BKN", "DAL", "LAC", "MEM", "SAC", "CLE", "NYK",
                "ATL", "CHI", "HOU", "OKC", "POR", "TOR", "UTA", "WAS", "CHA", "DET", "IND", "MIN", "NOP", "ORL", "SAS"},
        "NFL": {"KC", "SF", "DAL", "PHI", "BUF", "MIA", "BAL", "CIN", "DET", "GB", "MIN", "SEA", "LAR", "TB", "NO",
                "ATL", "CAR", "CHI", "CLE", "DEN", "HOU", "IND", "JAX", "LV", "LAC", "NE", "NYG", "NYJ", "PIT", "TEN", "WAS", "ARI"},
        "TENNIS": {"ATP", "WTA", "SLAM", "MASTERS"},
    }
    
    _instances: Dict[str, 'CacheManager'] = {}
    _lock = threading.RLock()
    
    def __new__(cls, sport: Union[str, Sport], cache_dir: Optional[str] = None):
        """Singleton per sport to prevent multiple cache handles"""
        sport_str = sport.value if isinstance(sport, Sport) else sport.upper()
        
        with cls._lock:
            if sport_str not in cls._instances:
                instance = super().__new__(cls)
                cls._instances[sport_str] = instance
            return cls._instances[sport_str]
    
    def __init__(self, sport: Union[str, Sport], cache_dir: Optional[str] = None):
        """Initialize cache manager for a specific sport"""
        # Prevent re-initialization
        if hasattr(self, '_initialized') and self._initialized:
            return
            
        self.sport = sport.value if isinstance(sport, Sport) else sport.upper()
        self.cache_dir = Path(cache_dir or self.DEFAULT_CACHE_DIR)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Sport-specific cache file
        self.cache_file = self.cache_dir / f"{self.sport.lower()}_cache.pkl"
        self.metadata_file = self.cache_dir / f"{self.sport.lower()}_metadata.json"
        
        # In-memory cache with lazy loading
        self._cache: Dict[str, CacheEntry] = {}
        self._dirty = False
        self._loaded = False
        
        # Thread lock for this instance
        self._instance_lock = threading.RLock()
        
        self._initialized = True
    
    def _make_key(self, key: str) -> str:
        """Create namespaced cache key"""
        # If already namespaced, return as-is
        if self.SEPARATOR in key and key.split(self.SEPARATOR)[0] in [s.value for s in Sport]:
            return key
        return f"{self.sport}{self.SEPARATOR}{key}"
    
    def _parse_key(self, namespaced_key: str) -> Tuple[str, str]:
        """Parse namespaced key into (sport, original_key)"""
        if self.SEPARATOR in namespaced_key:
            parts = namespaced_key.split(self.SEPARATOR, 1)
            return parts[0], parts[1]
        return "", namespaced_key
    
    def _compute_checksum(self, value: Any) -> str:
        """Compute SHA256 checksum for value"""
        return hashlib.sha256(pickle.dumps(value)).hexdigest()[:16]
    
    def _load_cache(self) -> None:
        """Lazy load cache from disk"""
        if self._loaded:
            return
            
        with self._instance_lock:
            if self._loaded:  # Double-check after acquiring lock
                return
                
            if self.cache_file.exists():
                try:
                    with open(self.cache_file, 'rb') as f:
                        data = pickle.load(f)
                        
                    # Handle both old format (dict) and new format (CacheEntry)
                    for key, value in data.items():
                        if isinstance(value, CacheEntry):
                            self._cache[key] = value
                        else:
                            # Migrate old format
                            self._cache[key] = CacheEntry(
                                key=key,
                                value=value,
                                sport=self.sport,
                                created_at=datetime.utcnow(),
                                checksum=self._compute_checksum(value)
                            )
                except Exception as e:
                    print(f"[CACHE] Warning: Could not load cache file: {e}")
                    self._cache = {}
            
            self._loaded = True
    
    def _save_cache(self) -> None:
        """Persist cache to disk"""
        if not self._dirty:
            return
            
        with self._instance_lock:
            try:
                # Atomic write with temp file
                temp_file = self.cache_file.with_suffix('.tmp')
                with open(temp_file, 'wb') as f:
                    pickle.dump(self._cache, f)
                temp_file.replace(self.cache_file)
                
                # Save metadata
                metadata = {
                    "sport": self.sport,
                    "last_updated": datetime.utcnow().isoformat(),
                    "entry_count": len(self._cache),
                    "keys": list(self._cache.keys())[:100]  # First 100 keys for inspection
                }
                with open(self.metadata_file, 'w') as f:
                    json.dump(metadata, f, indent=2)
                
                self._dirty = False
            except Exception as e:
                print(f"[CACHE] Error saving cache: {e}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get value from cache"""
        self._load_cache()
        
        namespaced_key = self._make_key(key)
        
        with self._instance_lock:
            entry = self._cache.get(namespaced_key)
            
            if entry is None:
                return default
            
            if entry.is_expired():
                del self._cache[namespaced_key]
                self._dirty = True
                return default
            
            # Update access stats
            entry.access_count += 1
            entry.last_accessed = datetime.utcnow()
            
            return entry.value
    
    def set(self, key: str, value: Any, ttl_hours: Optional[int] = None) -> None:
        """Set value in cache with optional TTL"""
        self._load_cache()
        
        namespaced_key = self._make_key(key)
        ttl = ttl_hours or self.DEFAULT_TTL_HOURS
        
        expires_at = datetime.utcnow() + timedelta(hours=ttl) if ttl > 0 else None
        
        entry = CacheEntry(
            key=namespaced_key,
            value=value,
            sport=self.sport,
            created_at=datetime.utcnow(),
            expires_at=expires_at,
            checksum=self._compute_checksum(value)
        )
        
        with self._instance_lock:
            self._cache[namespaced_key] = entry
            self._dirty = True
    
    def delete(self, key: str) -> bool:
        """Delete key from cache"""
        self._load_cache()
        
        namespaced_key = self._make_key(key)
        
        with self._instance_lock:
            if namespaced_key in self._cache:
                del self._cache[namespaced_key]
                self._dirty = True
                return True
            return False
    
    def exists(self, key: str) -> bool:
        """Check if key exists and is not expired"""
        self._load_cache()
        
        namespaced_key = self._make_key(key)
        
        with self._instance_lock:
            entry = self._cache.get(namespaced_key)
            if entry is None:
                return False
            if entry.is_expired():
                del self._cache[namespaced_key]
                self._dirty = True
                return False
            return True
    
    def keys(self, strip_namespace: bool = False) -> List[str]:
        """Get all keys in this sport's cache"""
        self._load_cache()
        
        with self._instance_lock:
            if strip_namespace:
                return [self._parse_key(k)[1] for k in self._cache.keys()]
            return list(self._cache.keys())
    
    def clear(self) -> int:
        """Clear all entries for this sport"""
        self._load_cache()
        
        with self._instance_lock:
            count = len(self._cache)
            self._cache.clear()
            self._dirty = True
            self._save_cache()
            return count
    
    def flush(self) -> None:
        """Force save cache to disk"""
        self._dirty = True
        self._save_cache()
    
    def size(self) -> int:
        """Get number of entries"""
        self._load_cache()
        return len(self._cache)
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self._save_cache()
    
    def __del__(self):
        try:
            self._save_cache()
        except:
            pass


class CacheDiagnosticTool:
    """
    Diagnostic and maintenance tool for FUOOM cache system.
    Detects cross-sport contamination and provides cleanup utilities.
    """
    
    def __init__(self, cache_dir: str = "cache"):
        self.cache_dir = Path(cache_dir)
    
    def diagnose_all(self) -> CacheDiagnostics:
        """Run full cache diagnostics"""
        diag = CacheDiagnostics()
        
        if not self.cache_dir.exists():
            return diag
        
        # Scan all cache files
        for cache_file in self.cache_dir.glob("*.pkl"):
            try:
                with open(cache_file, 'rb') as f:
                    data = pickle.load(f)
                
                sport_from_filename = cache_file.stem.replace("_cache", "").upper()
                
                for key, value in data.items():
                    diag.total_entries += 1
                    
                    # Parse key
                    if CacheManager.SEPARATOR in key:
                        sport, original_key = key.split(CacheManager.SEPARATOR, 1)
                    else:
                        sport = self._detect_sport_from_key(key)
                        original_key = key
                        diag.legacy_keys.append(key)
                    
                    # Count by sport
                    diag.entries_by_sport[sport] = diag.entries_by_sport.get(sport, 0) + 1
                    
                    # Calculate size
                    entry_size = len(pickle.dumps(value))
                    diag.total_size_bytes += entry_size
                    diag.size_by_sport[sport] = diag.size_by_sport.get(sport, 0) + entry_size
                    
                    # Check for cross-contamination
                    if sport and sport != sport_from_filename and sport_from_filename != "CACHE":
                        diag.cross_contamination.append({
                            "key": key,
                            "detected_sport": sport,
                            "file_sport": sport_from_filename,
                            "file": str(cache_file)
                        })
                    
                    # Check for orphaned (no sport detected)
                    if not sport:
                        diag.orphaned_entries.append(key)
                    
                    # Check for expired
                    if isinstance(value, CacheEntry) and value.is_expired():
                        diag.expired_entries.append(key)
                        
            except Exception as e:
                print(f"[DIAG] Error reading {cache_file}: {e}")
        
        return diag
    
    def _detect_sport_from_key(self, key: str) -> str:
        """Attempt to detect sport from legacy key patterns"""
        key_upper = key.upper()
        
        for sport, patterns in CacheManager.TEAM_PATTERNS.items():
            for pattern in patterns:
                if pattern in key_upper:
                    return sport
        
        # Check for common player name patterns
        if any(tennis_indicator in key_upper for tennis_indicator in ["ATP", "WTA", "SLAM"]):
            return "TENNIS"
        
        return ""
    
    def migrate_legacy_keys(self, sport: str, dry_run: bool = True) -> Dict:
        """Migrate legacy keys to namespaced format"""
        results = {
            "sport": sport,
            "dry_run": dry_run,
            "migrated": [],
            "skipped": [],
            "errors": []
        }
        
        cache_file = self.cache_dir / f"{sport.lower()}_cache.pkl"
        
        if not cache_file.exists():
            results["errors"].append(f"Cache file not found: {cache_file}")
            return results
        
        try:
            with open(cache_file, 'rb') as f:
                data = pickle.load(f)
            
            new_data = {}
            
            for key, value in data.items():
                if CacheManager.SEPARATOR in key:
                    # Already namespaced
                    new_data[key] = value
                    results["skipped"].append(key)
                else:
                    # Needs migration
                    new_key = f"{sport}{CacheManager.SEPARATOR}{key}"
                    
                    if isinstance(value, CacheEntry):
                        value.key = new_key
                        value.sport = sport
                        new_data[new_key] = value
                    else:
                        new_data[new_key] = CacheEntry(
                            key=new_key,
                            value=value,
                            sport=sport,
                            created_at=datetime.utcnow()
                        )
                    
                    results["migrated"].append({"old": key, "new": new_key})
            
            if not dry_run and results["migrated"]:
                # Backup original
                backup_file = cache_file.with_suffix('.pkl.bak')
                shutil.copy(cache_file, backup_file)
                
                # Write migrated data
                with open(cache_file, 'wb') as f:
                    pickle.dump(new_data, f)
                
                print(f"[MIGRATE] Backed up to {backup_file}")
                print(f"[MIGRATE] Migrated {len(results['migrated'])} keys in {cache_file}")
            
        except Exception as e:
            results["errors"].append(str(e))
        
        return results
    
    def clean_sport(self, sport: str, remove_expired: bool = True, 
                    remove_cross_contamination: bool = True) -> Dict:
        """Clean cache for a specific sport"""
        results = {
            "sport": sport,
            "removed_expired": [],
            "removed_contamination": [],
            "errors": []
        }
        
        cache_file = self.cache_dir / f"{sport.lower()}_cache.pkl"
        
        if not cache_file.exists():
            return results
        
        try:
            with open(cache_file, 'rb') as f:
                data = pickle.load(f)
            
            keys_to_remove = set()
            
            for key, value in data.items():
                # Check expiration
                if remove_expired and isinstance(value, CacheEntry) and value.is_expired():
                    keys_to_remove.add(key)
                    results["removed_expired"].append(key)
                
                # Check cross-contamination
                if remove_cross_contamination and CacheManager.SEPARATOR in key:
                    key_sport = key.split(CacheManager.SEPARATOR)[0]
                    if key_sport != sport:
                        keys_to_remove.add(key)
                        results["removed_contamination"].append(key)
            
            if keys_to_remove:
                for key in keys_to_remove:
                    del data[key]
                
                with open(cache_file, 'wb') as f:
                    pickle.dump(data, f)
                
                print(f"[CLEAN] Removed {len(keys_to_remove)} entries from {sport} cache")
            
        except Exception as e:
            results["errors"].append(str(e))
        
        return results
    
    def purge_sport(self, sport: str) -> Dict:
        """Completely purge a sport's cache"""
        results = {
            "sport": sport,
            "files_removed": [],
            "errors": []
        }
        
        patterns = [
            f"{sport.lower()}_cache.pkl",
            f"{sport.lower()}_metadata.json",
            f"{sport.lower()}_cache.pkl.bak"
        ]
        
        for pattern in patterns:
            cache_file = self.cache_dir / pattern
            if cache_file.exists():
                try:
                    cache_file.unlink()
                    results["files_removed"].append(str(cache_file))
                except Exception as e:
                    results["errors"].append(f"Failed to remove {cache_file}: {e}")
        
        return results
    
    def fix_cross_contamination(self, dry_run: bool = True) -> Dict:
        """
        Fix cross-sport contamination by moving entries to correct sport caches.
        This is the fix for the hannes_steinbach_WASH error.
        """
        results = {
            "dry_run": dry_run,
            "moved": [],
            "deleted": [],
            "errors": []
        }
        
        # First, diagnose
        diag = self.diagnose_all()
        
        if not diag.cross_contamination:
            print("[FIX] No cross-contamination detected")
            return results
        
        print(f"[FIX] Found {len(diag.cross_contamination)} contaminated entries")
        
        # Group by source file
        by_file: Dict[str, List[Dict]] = defaultdict(list)
        for item in diag.cross_contamination:
            by_file[item["file"]].append(item)
        
        # Process each contaminated file
        for cache_file_str, items in by_file.items():
            cache_file = Path(cache_file_str)
            
            try:
                with open(cache_file, 'rb') as f:
                    data = pickle.load(f)
                
                entries_to_move: Dict[str, List[Tuple[str, Any]]] = defaultdict(list)
                keys_to_remove = []
                
                for item in items:
                    key = item["key"]
                    correct_sport = item["detected_sport"]
                    
                    if key in data:
                        value = data[key]
                        
                        if correct_sport:
                            # Move to correct sport
                            entries_to_move[correct_sport].append((key, value))
                            results["moved"].append({
                                "key": key,
                                "from": item["file_sport"],
                                "to": correct_sport
                            })
                        else:
                            # Unknown sport, delete
                            results["deleted"].append(key)
                        
                        keys_to_remove.append(key)
                
                if not dry_run:
                    # Remove from source
                    for key in keys_to_remove:
                        if key in data:
                            del data[key]
                    
                    with open(cache_file, 'wb') as f:
                        pickle.dump(data, f)
                    
                    # Add to correct caches
                    for sport, entries in entries_to_move.items():
                        target_file = self.cache_dir / f"{sport.lower()}_cache.pkl"
                        
                        target_data = {}
                        if target_file.exists():
                            with open(target_file, 'rb') as f:
                                target_data = pickle.load(f)
                        
                        for key, value in entries:
                            target_data[key] = value
                        
                        with open(target_file, 'wb') as f:
                            pickle.dump(target_data, f)
                        
                        print(f"[FIX] Moved {len(entries)} entries to {sport} cache")
                
            except Exception as e:
                results["errors"].append(f"Error processing {cache_file}: {e}")
        
        return results


def print_diagnostics(diag: CacheDiagnostics):
    """Pretty print cache diagnostics"""
    print("\n" + "=" * 60)
    print("  FUOOM CACHE DIAGNOSTICS")
    print("=" * 60)
    print(f"  Status: {diag._health_status()}")
    print(f"  Total Entries: {diag.total_entries:,}")
    print(f"  Total Size: {diag.total_size_bytes / 1024:.1f} KB")
    print("-" * 60)
    
    print("\n  Entries by Sport:")
    for sport, count in sorted(diag.entries_by_sport.items()):
        size_kb = diag.size_by_sport.get(sport, 0) / 1024
        print(f"    {sport}: {count:,} entries ({size_kb:.1f} KB)")
    
    if diag.cross_contamination:
        print(f"\n  ⚠️  CROSS-CONTAMINATION DETECTED: {len(diag.cross_contamination)}")
        for item in diag.cross_contamination[:5]:
            print(f"    → {item['key']}")
            print(f"      Detected: {item['detected_sport']}, File: {item['file_sport']}")
        if len(diag.cross_contamination) > 5:
            print(f"    ... and {len(diag.cross_contamination) - 5} more")
    
    if diag.legacy_keys:
        print(f"\n  ⚠️  LEGACY KEYS (need migration): {len(diag.legacy_keys)}")
        for key in diag.legacy_keys[:5]:
            print(f"    → {key}")
        if len(diag.legacy_keys) > 5:
            print(f"    ... and {len(diag.legacy_keys) - 5} more")
    
    if diag.orphaned_entries:
        print(f"\n  ⚠️  ORPHANED ENTRIES: {len(diag.orphaned_entries)}")
        for key in diag.orphaned_entries[:5]:
            print(f"    → {key}")
    
    if diag.expired_entries:
        print(f"\n  ℹ️  EXPIRED ENTRIES: {len(diag.expired_entries)}")
    
    print("=" * 60 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="FUOOM Cache Manager — Cross-Sport Namespace Isolation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python cache_manager.py --diagnose
  python cache_manager.py --clean --sport CBB
  python cache_manager.py --migrate --sport NBA
  python cache_manager.py --migrate --sport ALL --execute
  python cache_manager.py --fix-contamination --execute
  python cache_manager.py --purge --sport TENNIS
        """
    )
    
    parser.add_argument('--cache-dir', default='cache', help='Cache directory path')
    parser.add_argument('--diagnose', action='store_true', help='Run full cache diagnostics')
    parser.add_argument('--clean', action='store_true', help='Clean expired and contaminated entries')
    parser.add_argument('--migrate', action='store_true', help='Migrate legacy keys to namespaced format')
    parser.add_argument('--fix-contamination', action='store_true', help='Fix cross-sport contamination')
    parser.add_argument('--purge', action='store_true', help='Completely purge a sport cache')
    parser.add_argument('--sport', default='ALL', help='Sport to operate on (or ALL)')
    parser.add_argument('--execute', action='store_true', help='Actually execute changes (default is dry-run)')
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    
    args = parser.parse_args()
    
    tool = CacheDiagnosticTool(args.cache_dir)
    
    if args.diagnose:
        diag = tool.diagnose_all()
        if args.json:
            print(json.dumps(diag.to_dict(), indent=2))
        else:
            print_diagnostics(diag)
    
    elif args.clean:
        sports = Sport.all_sports() if args.sport.upper() == 'ALL' else [args.sport.upper()]
        for sport in sports:
            results = tool.clean_sport(sport)
            if args.json:
                print(json.dumps(results, indent=2))
            else:
                print(f"[CLEAN] {sport}: Removed {len(results['removed_expired'])} expired, "
                      f"{len(results['removed_contamination'])} contaminated")
    
    elif args.migrate:
        dry_run = not args.execute
        sports = Sport.all_sports() if args.sport.upper() == 'ALL' else [args.sport.upper()]
        
        for sport in sports:
            results = tool.migrate_legacy_keys(sport, dry_run=dry_run)
            if args.json:
                print(json.dumps(results, indent=2))
            else:
                mode = "DRY-RUN" if dry_run else "EXECUTED"
                print(f"[MIGRATE] {sport} ({mode}): {len(results['migrated'])} to migrate, "
                      f"{len(results['skipped'])} already namespaced")
    
    elif args.fix_contamination:
        dry_run = not args.execute
        results = tool.fix_cross_contamination(dry_run=dry_run)
        if args.json:
            print(json.dumps(results, indent=2))
        else:
            mode = "DRY-RUN" if dry_run else "EXECUTED"
            print(f"[FIX] ({mode}): Moved {len(results['moved'])}, Deleted {len(results['deleted'])}")
            if results['errors']:
                print(f"[FIX] Errors: {results['errors']}")
    
    elif args.purge:
        if args.sport.upper() == 'ALL':
            print("[ERROR] Cannot purge ALL - specify a sport")
            sys.exit(1)
        
        if not args.execute:
            print(f"[PURGE] DRY-RUN: Would purge {args.sport} cache. Use --execute to confirm.")
        else:
            confirm = input(f"Are you sure you want to purge {args.sport} cache? (yes/no): ")
            if confirm.lower() == 'yes':
                results = tool.purge_sport(args.sport.upper())
                print(f"[PURGE] Removed: {results['files_removed']}")
            else:
                print("[PURGE] Cancelled")
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
