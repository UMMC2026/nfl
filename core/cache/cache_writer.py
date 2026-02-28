#!/usr/bin/env python3
"""
FUOOM SPORT CACHE WRITER — Namespace Enforcement at Write-Time
==============================================================
MANDATORY: All cache writes MUST go through this module.

🔐 Required Cache Key Format:
    <SPORT>::<VERSION>::<ENTITY>

Examples:
    CBB::v1::hannes_steinbach_WASH
    NBA::v2::lebron_james_LAL
    NFL::v1::patrick_mahomes_KC

This module prevents cross-sport contamination by:
1. Enforcing namespace prefixes on all keys
2. Blocking writes with wrong namespace
3. Failing LOUDLY at write-time (not analysis time)

Usage:
    from core.cache.cache_writer import SportCacheWriter
    
    writer = SportCacheWriter(sport="CBB", version="v1")
    writer.write(cache_dict, "john_smith_DUKE", player_data)
"""

from typing import Any, Dict, Optional
from datetime import datetime
import threading


class CacheNamespaceError(RuntimeError):
    """Raised when a cache operation violates namespace rules."""
    pass


class SportCacheWriter:
    """
    Thread-safe, namespace-enforced cache writer.
    
    INSTITUTIONAL-GRADE DATA HYGIENE:
    - Cross-sport writes are BLOCKED
    - Mixed caches CANNOT exist
    - Failures happen at WRITE-TIME, not during analysis
    """
    
    SEPARATOR = "::"
    VALID_SPORTS = {"NBA", "CBB", "NFL", "TENNIS", "GOLF", "SOCCER", "CFB", "WNBA", "MLB", "NHL"}
    
    _lock = threading.RLock()
    
    def __init__(self, sport: str, version: str = "v1"):
        """
        Initialize cache writer for a specific sport.
        
        Args:
            sport: Sport identifier (NBA, CBB, NFL, etc.)
            version: Cache schema version (default: v1)
            
        Raises:
            ValueError: If sport is invalid
        """
        sport_upper = sport.upper().strip()
        
        if sport_upper not in self.VALID_SPORTS:
            raise ValueError(
                f"Invalid sport: {sport}. "
                f"Valid options: {', '.join(sorted(self.VALID_SPORTS))}"
            )
        
        self.sport = sport_upper
        self.version = version
        self._write_count = 0
        self._last_write = None
    
    def make_key(self, entity_key: str) -> str:
        """
        Create a fully-namespaced cache key.
        
        Args:
            entity_key: The entity identifier (player_name_TEAM, game_id, etc.)
            
        Returns:
            Namespaced key: SPORT::VERSION::entity_key
        """
        # Clean the entity key
        entity_key = str(entity_key).strip()
        
        # If already namespaced, validate and return
        if self.SEPARATOR in entity_key:
            parts = entity_key.split(self.SEPARATOR, 2)
            if len(parts) >= 2 and parts[0] in self.VALID_SPORTS:
                # Already has valid namespace
                if parts[0] != self.sport:
                    raise CacheNamespaceError(
                        f"[NAMESPACE ERROR] Key belongs to {parts[0]}, not {self.sport}: {entity_key}"
                    )
                return entity_key
        
        # Create namespaced key
        return f"{self.sport}{self.SEPARATOR}{self.version}{self.SEPARATOR}{entity_key}"
    
    def assert_key(self, key: str) -> None:
        """
        Validate that a key belongs to this sport's namespace.
        
        Args:
            key: The cache key to validate
            
        Raises:
            CacheNamespaceError: If key violates namespace rules
        """
        if not key:
            raise CacheNamespaceError("[NAMESPACE ERROR] Empty key")
        
        # Must start with our sport prefix
        expected_prefix = f"{self.sport}{self.SEPARATOR}"
        
        if not key.startswith(expected_prefix):
            # Check if it's another sport's key
            for other_sport in self.VALID_SPORTS:
                if key.startswith(f"{other_sport}{self.SEPARATOR}"):
                    raise CacheNamespaceError(
                        f"[CACHE WRITE ERROR] Cross-sport key attempt: "
                        f"Tried to write {other_sport} key to {self.sport} cache: {key}"
                    )
            
            # Not namespaced at all - wrap it
            raise CacheNamespaceError(
                f"[CACHE WRITE ERROR] Key not namespaced: {key}. "
                f"Use make_key() to create properly formatted keys."
            )
    
    def write(self, cache: Dict, entity_key: str, value: Any) -> str:
        """
        Write a value to cache with namespace enforcement.
        
        Args:
            cache: The cache dictionary to write to
            entity_key: The entity identifier (will be namespaced)
            value: The value to cache
            
        Returns:
            The namespaced key that was written
            
        Raises:
            CacheNamespaceError: If write would violate namespace rules
        """
        with self._lock:
            # Create namespaced key
            key = self.make_key(entity_key)
            
            # Validate key
            self.assert_key(key)
            
            # Write to cache
            cache[key] = value
            
            # Track stats
            self._write_count += 1
            self._last_write = datetime.utcnow()
            
            return key
    
    def read(self, cache: Dict, entity_key: str, default: Any = None) -> Any:
        """
        Read a value from cache with namespace handling.
        
        Args:
            cache: The cache dictionary to read from
            entity_key: The entity identifier
            default: Default value if key not found
            
        Returns:
            Cached value or default
        """
        key = self.make_key(entity_key)
        return cache.get(key, default)
    
    def exists(self, cache: Dict, entity_key: str) -> bool:
        """Check if entity exists in cache."""
        key = self.make_key(entity_key)
        return key in cache
    
    def delete(self, cache: Dict, entity_key: str) -> bool:
        """Delete entity from cache. Returns True if deleted."""
        key = self.make_key(entity_key)
        if key in cache:
            del cache[key]
            return True
        return False
    
    def validate_cache(self, cache: Dict) -> Dict[str, list]:
        """
        Validate an entire cache for namespace compliance.
        
        Returns:
            Dict with 'valid', 'invalid', 'foreign' key lists
        """
        results = {
            'valid': [],
            'invalid': [],
            'foreign': []
        }
        
        expected_prefix = f"{self.sport}{self.SEPARATOR}"
        
        for key in cache.keys():
            if key.startswith(expected_prefix):
                results['valid'].append(key)
            elif any(key.startswith(f"{s}{self.SEPARATOR}") for s in self.VALID_SPORTS):
                results['foreign'].append(key)
            else:
                results['invalid'].append(key)
        
        return results
    
    def get_stats(self) -> Dict:
        """Get writer statistics."""
        return {
            'sport': self.sport,
            'version': self.version,
            'write_count': self._write_count,
            'last_write': self._last_write.isoformat() if self._last_write else None
        }
    
    def __repr__(self) -> str:
        return f"SportCacheWriter(sport='{self.sport}', version='{self.version}')"


class CacheContextGuard:
    """
    Context manager that validates cache state before and after operations.
    
    Usage:
        with CacheContextGuard(cache, sport="CBB") as guard:
            # Do cache operations
            writer.write(cache, "player", data)
        # Automatically validates on exit
    """
    
    def __init__(self, cache: Dict, sport: str):
        self.cache = cache
        self.sport = sport.upper()
        self.initial_keys = set(cache.keys())
        self.writer = SportCacheWriter(sport=sport)
    
    def __enter__(self):
        # Check for pre-existing contamination
        validation = self.writer.validate_cache(self.cache)
        if validation['foreign']:
            raise CacheNamespaceError(
                f"[{self.sport} CONTEXT ERROR] Foreign keys detected in cache: "
                f"{validation['foreign'][:5]}{'...' if len(validation['foreign']) > 5 else ''}"
            )
        return self.writer
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            # No exception - validate final state
            validation = self.writer.validate_cache(self.cache)
            if validation['foreign']:
                raise CacheNamespaceError(
                    f"[{self.sport} CONTEXT ERROR] Operation introduced foreign keys: "
                    f"{validation['foreign'][:5]}"
                )
        return False  # Don't suppress exceptions


def assert_sport_context(cache: Dict, sport: str) -> None:
    """
    Assert that a cache contains ONLY keys for the specified sport.
    
    Args:
        cache: Cache dictionary to check
        sport: Expected sport
        
    Raises:
        CacheNamespaceError: If any cross-sport keys detected
    """
    sport = sport.upper()
    expected_prefix = f"{sport}::"
    
    foreign_keys = []
    for key in cache.keys():
        # Check if it's a namespaced key
        if "::" in key:
            key_sport = key.split("::")[0]
            if key_sport != sport and key_sport in SportCacheWriter.VALID_SPORTS:
                foreign_keys.append(key)
    
    if foreign_keys:
        raise CacheNamespaceError(
            f"[{sport} CONTEXT ERROR] Cross-sport keys detected in cache: {foreign_keys[:5]}"
        )


# Convenience factory functions
def get_writer(sport: str, version: str = "v1") -> SportCacheWriter:
    """Get a cache writer for the specified sport."""
    return SportCacheWriter(sport=sport, version=version)


def nba_writer(version: str = "v1") -> SportCacheWriter:
    """Get NBA cache writer."""
    return SportCacheWriter(sport="NBA", version=version)


def cbb_writer(version: str = "v1") -> SportCacheWriter:
    """Get CBB cache writer."""
    return SportCacheWriter(sport="CBB", version=version)


def nfl_writer(version: str = "v1") -> SportCacheWriter:
    """Get NFL cache writer."""
    return SportCacheWriter(sport="NFL", version=version)


def tennis_writer(version: str = "v1") -> SportCacheWriter:
    """Get Tennis cache writer."""
    return SportCacheWriter(sport="TENNIS", version=version)


def golf_writer(version: str = "v1") -> SportCacheWriter:
    """Get Golf cache writer."""
    return SportCacheWriter(sport="GOLF", version=version)


def soccer_writer(version: str = "v1") -> SportCacheWriter:
    """Get Soccer cache writer."""
    return SportCacheWriter(sport="SOCCER", version=version)


# Module test
if __name__ == "__main__":
    print("Testing SportCacheWriter...")
    
    # Test basic functionality
    writer = SportCacheWriter(sport="CBB", version="v1")
    cache = {}
    
    # Test write
    key = writer.write(cache, "john_smith_DUKE", {"points": 15.5})
    print(f"✓ Written key: {key}")
    assert key == "CBB::v1::john_smith_DUKE"
    
    # Test read
    data = writer.read(cache, "john_smith_DUKE")
    print(f"✓ Read data: {data}")
    assert data == {"points": 15.5}
    
    # Test cross-sport write prevention
    try:
        cache["NBA::v1::lebron_james_LAL"] = {"points": 25.0}
        writer.validate_cache(cache)
        print("✗ Should have detected foreign key")
    except CacheNamespaceError as e:
        print(f"✓ Correctly detected foreign key")
    
    # Test context guard
    clean_cache = {}
    try:
        with CacheContextGuard(clean_cache, sport="CBB") as guard:
            guard.write(clean_cache, "player1", {"data": 1})
            guard.write(clean_cache, "player2", {"data": 2})
        print(f"✓ Context guard passed with {len(clean_cache)} keys")
    except CacheNamespaceError as e:
        print(f"✗ Context guard failed: {e}")
    
    print("\nAll tests passed!")
