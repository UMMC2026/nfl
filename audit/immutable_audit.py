#!/usr/bin/env python3
"""
IMMUTABLE_AUDIT.PY — SOP v2.1 GOVERNANCE FRAMEWORK
===================================================
Cryptographically signed audit trail for pick tracking.

Every pick decision is logged with:
1. SHA-256 hash of the pick data
2. Chain hash linking to previous entry (blockchain-style)
3. Timestamp in ISO format
4. Full pick state for reconstruction

This creates an IMMUTABLE record that:
- Cannot be modified without detection
- Provides full traceability
- Enables calibration audits

Version: 2.1.0
Created: 2026-02-04
"""

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict


def utc_now() -> datetime:
    """Get current UTC time (timezone-aware)."""
    return datetime.now(timezone.utc)


# ============================================================================
# CONFIGURATION
# ============================================================================

AUDIT_DIR = Path("audit")
IMMUTABLE_LOG = AUDIT_DIR / "immutable_picks.jsonl"
CHAIN_STATE = AUDIT_DIR / "chain_state.json"


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class AuditEntry:
    """Immutable audit entry for a pick decision"""
    entry_id: str           # Unique ID: {timestamp}_{hash[:8]}
    timestamp: str          # ISO format
    run_id: str             # Pipeline run identifier
    sport: str              # NBA, Tennis, etc.
    
    # Pick data
    player: str
    stat: str
    line: float
    direction: str
    probability: float
    tier: str
    pick_state: str         # OPTIMIZABLE, VETTED, REJECTED
    
    # Context
    mu: Optional[float]
    sigma: Optional[float]
    sample_n: Optional[int]
    distribution_type: str  # normal, nbinom, poisson
    
    # Governance
    penalties_applied: Dict[str, float]  # e.g., {"cv_penalty": -0.10}
    risk_flags: List[str]
    
    # Cryptographic chain
    data_hash: str          # SHA-256 of pick data
    prev_hash: str          # Hash of previous entry (chain)
    chain_hash: str         # Hash of this entry including prev_hash


# ============================================================================
# HASHING FUNCTIONS
# ============================================================================

def compute_data_hash(pick_data: Dict) -> str:
    """Compute SHA-256 hash of pick data (deterministic)."""
    # Sort keys for deterministic hashing
    serialized = json.dumps(pick_data, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode()).hexdigest()


def compute_chain_hash(entry_data: Dict, prev_hash: str) -> str:
    """Compute chain hash including previous hash."""
    combined = json.dumps(entry_data, sort_keys=True, default=str) + prev_hash
    return hashlib.sha256(combined.encode()).hexdigest()


# ============================================================================
# CHAIN STATE MANAGEMENT
# ============================================================================

def get_chain_state() -> Dict:
    """Get current chain state (last hash, entry count)."""
    if CHAIN_STATE.exists():
        with open(CHAIN_STATE, 'r') as f:
            return json.load(f)
    return {
        "last_hash": "0" * 64,  # Genesis hash
        "entry_count": 0,
        "initialized": utc_now().isoformat()
    }


def update_chain_state(new_hash: str, entry_count: int):
    """Update chain state after new entry."""
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    state = {
        "last_hash": new_hash,
        "entry_count": entry_count,
        "last_updated": utc_now().isoformat()
    }
    with open(CHAIN_STATE, 'w') as f:
        json.dump(state, f, indent=2)


# ============================================================================
# AUDIT ENTRY CREATION
# ============================================================================

def create_audit_entry(
    run_id: str,
    sport: str,
    player: str,
    stat: str,
    line: float,
    direction: str,
    probability: float,
    tier: str,
    pick_state: str,
    mu: Optional[float] = None,
    sigma: Optional[float] = None,
    sample_n: Optional[int] = None,
    distribution_type: str = "normal",
    penalties_applied: Optional[Dict[str, float]] = None,
    risk_flags: Optional[List[str]] = None
) -> AuditEntry:
    """Create a new immutable audit entry."""
    
    timestamp = utc_now().isoformat()
    
    # Get chain state
    chain_state = get_chain_state()
    prev_hash = chain_state["last_hash"]
    entry_count = chain_state["entry_count"]
    
    # Build pick data for hashing
    pick_data = {
        "player": player,
        "stat": stat,
        "line": line,
        "direction": direction,
        "probability": probability,
        "tier": tier,
        "pick_state": pick_state,
        "mu": mu,
        "sigma": sigma,
        "sample_n": sample_n
    }
    
    # Compute hashes
    data_hash = compute_data_hash(pick_data)
    
    # Create entry ID
    entry_id = f"{timestamp.replace(':', '').replace('-', '').replace('.', '')}_{data_hash[:8]}"
    
    # Build entry data for chain hash
    entry_data = {
        "entry_id": entry_id,
        "timestamp": timestamp,
        "run_id": run_id,
        "sport": sport,
        **pick_data,
        "distribution_type": distribution_type,
        "penalties_applied": penalties_applied or {},
        "risk_flags": risk_flags or [],
        "data_hash": data_hash
    }
    
    chain_hash = compute_chain_hash(entry_data, prev_hash)
    
    return AuditEntry(
        entry_id=entry_id,
        timestamp=timestamp,
        run_id=run_id,
        sport=sport,
        player=player,
        stat=stat,
        line=line,
        direction=direction,
        probability=probability,
        tier=tier,
        pick_state=pick_state,
        mu=mu,
        sigma=sigma,
        sample_n=sample_n,
        distribution_type=distribution_type,
        penalties_applied=penalties_applied or {},
        risk_flags=risk_flags or [],
        data_hash=data_hash,
        prev_hash=prev_hash,
        chain_hash=chain_hash
    )


# ============================================================================
# LOGGING
# ============================================================================

def log_audit_entry(entry: AuditEntry) -> bool:
    """Log audit entry to immutable log file."""
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    
    try:
        # Append to JSONL file
        with open(IMMUTABLE_LOG, 'a') as f:
            f.write(json.dumps(asdict(entry), default=str) + "\n")
        
        # Update chain state
        chain_state = get_chain_state()
        update_chain_state(entry.chain_hash, chain_state["entry_count"] + 1)
        
        return True
    except Exception as e:
        print(f"[AUDIT ERROR] Failed to log entry: {e}")
        return False


def log_pick(
    run_id: str,
    sport: str,
    pick: Dict[str, Any],
    penalties: Optional[Dict[str, float]] = None,
    risk_flags: Optional[List[str]] = None
) -> bool:
    """Convenience function to log a pick from a dict."""
    
    entry = create_audit_entry(
        run_id=run_id,
        sport=sport,
        player=pick.get("player", pick.get("entity", "UNKNOWN")),
        stat=pick.get("stat", pick.get("market", "UNKNOWN")),
        line=pick.get("line", 0),
        direction=pick.get("direction", "higher"),
        probability=pick.get("probability", 0.5),
        tier=pick.get("tier", "NO_TIER"),
        pick_state=pick.get("pick_state", "UNKNOWN"),
        mu=pick.get("mu"),
        sigma=pick.get("sigma"),
        sample_n=pick.get("sample_n", pick.get("n")),
        distribution_type=pick.get("distribution_type", "normal"),
        penalties_applied=penalties,
        risk_flags=risk_flags
    )
    
    return log_audit_entry(entry)


# ============================================================================
# CHAIN VERIFICATION
# ============================================================================

def verify_chain_integrity() -> Dict:
    """Verify the integrity of the audit chain."""
    
    if not IMMUTABLE_LOG.exists():
        return {"valid": True, "entries": 0, "message": "No entries yet"}
    
    entries = []
    with open(IMMUTABLE_LOG, 'r') as f:
        for line in f:
            if line.strip():
                entries.append(json.loads(line))
    
    if not entries:
        return {"valid": True, "entries": 0, "message": "Empty log"}
    
    # Verify chain
    expected_prev_hash = "0" * 64  # Genesis
    invalid_entries = []
    
    for i, entry in enumerate(entries):
        # Check prev_hash chain
        if entry["prev_hash"] != expected_prev_hash:
            invalid_entries.append({
                "index": i,
                "entry_id": entry["entry_id"],
                "error": "prev_hash mismatch"
            })
        
        # Recompute chain hash
        entry_data = {k: v for k, v in entry.items() if k not in ["prev_hash", "chain_hash"]}
        computed_chain_hash = compute_chain_hash(entry_data, entry["prev_hash"])
        
        if computed_chain_hash != entry["chain_hash"]:
            invalid_entries.append({
                "index": i,
                "entry_id": entry["entry_id"],
                "error": "chain_hash mismatch (data tampered)"
            })
        
        expected_prev_hash = entry["chain_hash"]
    
    if invalid_entries:
        return {
            "valid": False,
            "entries": len(entries),
            "invalid": invalid_entries,
            "message": f"Chain integrity violated at {len(invalid_entries)} entries"
        }
    
    return {
        "valid": True,
        "entries": len(entries),
        "first_entry": entries[0]["timestamp"] if entries else None,
        "last_entry": entries[-1]["timestamp"] if entries else None,
        "message": "Chain integrity verified ✅"
    }


def get_audit_stats() -> Dict:
    """Get audit log statistics."""
    
    if not IMMUTABLE_LOG.exists():
        return {"total_entries": 0}
    
    entries = []
    with open(IMMUTABLE_LOG, 'r') as f:
        for line in f:
            if line.strip():
                entries.append(json.loads(line))
    
    if not entries:
        return {"total_entries": 0}
    
    # Compute stats
    by_sport = {}
    by_tier = {}
    by_state = {}
    
    for entry in entries:
        sport = entry.get("sport", "UNKNOWN")
        tier = entry.get("tier", "UNKNOWN")
        state = entry.get("pick_state", "UNKNOWN")
        
        by_sport[sport] = by_sport.get(sport, 0) + 1
        by_tier[tier] = by_tier.get(tier, 0) + 1
        by_state[state] = by_state.get(state, 0) + 1
    
    return {
        "total_entries": len(entries),
        "by_sport": by_sport,
        "by_tier": by_tier,
        "by_state": by_state,
        "first_entry": entries[0]["timestamp"],
        "last_entry": entries[-1]["timestamp"]
    }


# ============================================================================
# CLI INTERFACE
# ============================================================================

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        
        if cmd == "verify":
            result = verify_chain_integrity()
            print(json.dumps(result, indent=2))
            sys.exit(0 if result["valid"] else 1)
        
        elif cmd == "stats":
            stats = get_audit_stats()
            print(json.dumps(stats, indent=2))
        
        elif cmd == "test":
            # Test logging
            print("Testing immutable audit log...")
            
            test_pick = {
                "player": "Test Player",
                "stat": "PTS",
                "line": 25.5,
                "direction": "higher",
                "probability": 0.65,
                "tier": "STRONG",
                "pick_state": "OPTIMIZABLE",
                "mu": 27.5,
                "sigma": 5.0,
                "sample_n": 10
            }
            
            success = log_pick(
                run_id="TEST_RUN_001",
                sport="NBA",
                pick=test_pick,
                penalties={"cv_penalty": -0.05},
                risk_flags=["test_flag"]
            )
            
            print(f"Log success: {success}")
            
            # Verify
            result = verify_chain_integrity()
            print(f"Chain integrity: {result['message']}")
        
        else:
            print(f"Unknown command: {cmd}")
            print("Usage: python immutable_audit.py [verify|stats|test]")
    else:
        print("IMMUTABLE AUDIT TRAIL")
        print("=" * 40)
        stats = get_audit_stats()
        print(f"Total entries: {stats['total_entries']}")
        if stats['total_entries'] > 0:
            print(f"By sport: {stats['by_sport']}")
            print(f"By tier: {stats['by_tier']}")
        
        result = verify_chain_integrity()
        print(f"\nChain integrity: {result['message']}")
