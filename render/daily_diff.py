"""
Daily Diff View ("What Changed Since Yesterday")
================================================
ENFORCEMENT LAYER C — Trust + Auditability.

NO MATH CHANGES — This is visibility/audit only.

Sections:
- 🟢 New edges
- 🔵 Probability moved
- 🟠 Tier downgraded
- 🔴 Removed by gate

Example Diff Item:
  Tyrese Maxey – Steals Over 1.5
  Prob: 58% → 52% (INJURY_ADJUSTMENT)
  Tier: STRONG → NO PLAY
"""

from __future__ import annotations

import sys
import json
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum

sys.path.insert(0, str(Path(__file__).parent.parent))


# =============================================================================
# DIFF TYPES
# =============================================================================

class DiffType(Enum):
    """Type of edge change."""
    NEW = "new"                    # 🟢 Edge didn't exist yesterday
    REMOVED = "removed"           # 🔴 Edge removed by gate
    PROB_UP = "probability_up"    # 🔵 Probability increased
    PROB_DOWN = "probability_down"# 🔵 Probability decreased
    TIER_UPGRADE = "tier_upgrade" # 🟢 Tier improved
    TIER_DOWNGRADE = "tier_downgrade"  # 🟠 Tier worsened
    LINE_MOVED = "line_moved"     # 📊 Line changed
    UNCHANGED = "unchanged"       # No significant change


DIFF_SYMBOLS = {
    DiffType.NEW: "🟢",
    DiffType.REMOVED: "🔴",
    DiffType.PROB_UP: "🔵↑",
    DiffType.PROB_DOWN: "🔵↓",
    DiffType.TIER_UPGRADE: "🟢⬆",
    DiffType.TIER_DOWNGRADE: "🟠⬇",
    DiffType.LINE_MOVED: "📊",
    DiffType.UNCHANGED: "⚪",
}


# =============================================================================
# TIER ORDERING
# =============================================================================

TIER_ORDER = {
    "SLAM": 1,
    "STRONG": 2,
    "LEAN": 3,
    "WATCH": 4,
    "NO_PLAY": 5,
    "NO PLAY": 5,
    "AVOID": 6,
    "REJECTED": 7,
}


def tier_rank(tier: str) -> int:
    """Get tier rank (lower = better)."""
    return TIER_ORDER.get(tier.upper(), 99)


# =============================================================================
# DIFF ITEM
# =============================================================================

@dataclass
class DiffItem:
    """Single change between yesterday and today."""
    edge_id: str
    player: str
    stat: str
    line: float
    direction: str
    
    diff_type: DiffType
    
    # Change details (for moved edges)
    old_probability: Optional[float] = None
    new_probability: Optional[float] = None
    probability_delta: Optional[float] = None
    
    old_tier: Optional[str] = None
    new_tier: Optional[str] = None
    
    old_line: Optional[float] = None
    new_line: Optional[float] = None
    
    change_reason: Optional[str] = None  # e.g., "INJURY_ADJUSTMENT"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "edge_id": self.edge_id,
            "player": self.player,
            "stat": self.stat,
            "line": self.line,
            "direction": self.direction,
            "diff_type": self.diff_type.value,
            "old_probability": self.old_probability,
            "new_probability": self.new_probability,
            "probability_delta": self.probability_delta,
            "old_tier": self.old_tier,
            "new_tier": self.new_tier,
            "old_line": self.old_line,
            "new_line": self.new_line,
            "change_reason": self.change_reason,
        }
    
    def format_text(self) -> str:
        """Human-readable diff."""
        symbol = DIFF_SYMBOLS.get(self.diff_type, "❓")
        lines = [f"{symbol} {self.player} – {self.stat} {self.direction} {self.line}"]
        
        if self.diff_type == DiffType.NEW:
            lines.append(f"   New edge @ {self._fmt_prob(self.new_probability)} | {self.new_tier}")
        
        elif self.diff_type == DiffType.REMOVED:
            lines.append(f"   Removed (was {self._fmt_prob(self.old_probability)} | {self.old_tier})")
            if self.change_reason:
                lines.append(f"   Reason: {self.change_reason}")
        
        elif self.diff_type in {DiffType.PROB_UP, DiffType.PROB_DOWN}:
            delta_sign = "+" if self.probability_delta > 0 else ""
            lines.append(
                f"   Prob: {self._fmt_prob(self.old_probability)} → "
                f"{self._fmt_prob(self.new_probability)} ({delta_sign}{self.probability_delta:.1f}%)"
            )
            if self.change_reason:
                lines.append(f"   ({self.change_reason})")
        
        elif self.diff_type in {DiffType.TIER_UPGRADE, DiffType.TIER_DOWNGRADE}:
            lines.append(f"   Tier: {self.old_tier} → {self.new_tier}")
            if self.change_reason:
                lines.append(f"   ({self.change_reason})")
        
        elif self.diff_type == DiffType.LINE_MOVED:
            lines.append(f"   Line: {self.old_line} → {self.new_line}")
        
        return "\n".join(lines)
    
    def _fmt_prob(self, prob: Optional[float]) -> str:
        """Format probability."""
        if prob is None:
            return "?"
        if prob <= 1.0:
            return f"{prob * 100:.0f}%"
        return f"{prob:.0f}%"


# =============================================================================
# DIFF RESULT
# =============================================================================

@dataclass
class DailyDiff:
    """Complete diff between two days."""
    yesterday_date: str
    today_date: str
    
    new_edges: List[DiffItem] = field(default_factory=list)
    removed_edges: List[DiffItem] = field(default_factory=list)
    probability_changed: List[DiffItem] = field(default_factory=list)
    tier_changed: List[DiffItem] = field(default_factory=list)
    line_changed: List[DiffItem] = field(default_factory=list)
    
    unchanged_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "yesterday_date": self.yesterday_date,
            "today_date": self.today_date,
            "summary": {
                "new": len(self.new_edges),
                "removed": len(self.removed_edges),
                "probability_changed": len(self.probability_changed),
                "tier_changed": len(self.tier_changed),
                "line_changed": len(self.line_changed),
                "unchanged": self.unchanged_count,
            },
            "new_edges": [d.to_dict() for d in self.new_edges],
            "removed_edges": [d.to_dict() for d in self.removed_edges],
            "probability_changed": [d.to_dict() for d in self.probability_changed],
            "tier_changed": [d.to_dict() for d in self.tier_changed],
            "line_changed": [d.to_dict() for d in self.line_changed],
        }
    
    @property
    def has_changes(self) -> bool:
        return (
            len(self.new_edges) > 0 or
            len(self.removed_edges) > 0 or
            len(self.probability_changed) > 0 or
            len(self.tier_changed) > 0 or
            len(self.line_changed) > 0
        )


# =============================================================================
# DIFF ENGINE
# =============================================================================

def make_edge_key(edge: Dict) -> str:
    """Create unique key for edge matching."""
    player = edge.get("player", edge.get("entity", "")).lower().strip()
    stat = edge.get("stat", edge.get("market", "")).lower().strip()
    direction = edge.get("direction", "").lower().strip()
    return f"{player}|{stat}|{direction}"


def normalize_probability(prob: Any) -> float:
    """Normalize probability to 0-100 scale."""
    if prob is None:
        return 0.0
    prob = float(prob)
    if prob <= 1.0:
        return prob * 100
    return prob


def diff_edges(today: List[Dict], yesterday: List[Dict], prob_threshold: float = 3.0) -> DailyDiff:
    """
    Compare today's edges against yesterday's.
    
    Args:
        today: List of today's edge dicts
        yesterday: List of yesterday's edge dicts
        prob_threshold: Minimum probability change (%) to flag
        
    Returns:
        DailyDiff with categorized changes
    """
    today_date = datetime.now().strftime("%Y-%m-%d")
    yesterday_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    
    diff = DailyDiff(
        yesterday_date=yesterday_date,
        today_date=today_date,
    )
    
    # Index yesterday's edges
    yesterday_map = {}
    for edge in yesterday:
        key = make_edge_key(edge)
        yesterday_map[key] = edge
    
    # Track which yesterday edges we've matched
    matched_keys = set()
    
    # Compare today's edges
    for edge in today:
        key = make_edge_key(edge)
        
        if key not in yesterday_map:
            # New edge
            diff.new_edges.append(DiffItem(
                edge_id=edge.get("edge_id", edge.get("id", key)),
                player=edge.get("player", edge.get("entity", "")),
                stat=edge.get("stat", edge.get("market", "")),
                line=float(edge.get("line", 0)),
                direction=edge.get("direction", ""),
                diff_type=DiffType.NEW,
                new_probability=normalize_probability(edge.get("probability")),
                new_tier=edge.get("tier", edge.get("confidence_tier", "")),
            ))
        else:
            matched_keys.add(key)
            old_edge = yesterday_map[key]
            
            # Compare probability
            old_prob = normalize_probability(old_edge.get("probability"))
            new_prob = normalize_probability(edge.get("probability"))
            prob_delta = new_prob - old_prob
            
            # Compare tier
            old_tier = old_edge.get("tier", old_edge.get("confidence_tier", ""))
            new_tier = edge.get("tier", edge.get("confidence_tier", ""))
            
            # Compare line
            old_line = float(old_edge.get("line", 0))
            new_line = float(edge.get("line", 0))
            
            # Determine what changed
            has_change = False
            
            # Check probability change
            if abs(prob_delta) >= prob_threshold:
                diff_type = DiffType.PROB_UP if prob_delta > 0 else DiffType.PROB_DOWN
                diff.probability_changed.append(DiffItem(
                    edge_id=edge.get("edge_id", edge.get("id", key)),
                    player=edge.get("player", edge.get("entity", "")),
                    stat=edge.get("stat", edge.get("market", "")),
                    line=new_line,
                    direction=edge.get("direction", ""),
                    diff_type=diff_type,
                    old_probability=old_prob,
                    new_probability=new_prob,
                    probability_delta=prob_delta,
                    old_tier=old_tier,
                    new_tier=new_tier,
                    change_reason=edge.get("adjustment_reason"),
                ))
                has_change = True
            
            # Check tier change
            if old_tier.upper() != new_tier.upper():
                old_rank = tier_rank(old_tier)
                new_rank = tier_rank(new_tier)
                diff_type = DiffType.TIER_UPGRADE if new_rank < old_rank else DiffType.TIER_DOWNGRADE
                diff.tier_changed.append(DiffItem(
                    edge_id=edge.get("edge_id", edge.get("id", key)),
                    player=edge.get("player", edge.get("entity", "")),
                    stat=edge.get("stat", edge.get("market", "")),
                    line=new_line,
                    direction=edge.get("direction", ""),
                    diff_type=diff_type,
                    old_probability=old_prob,
                    new_probability=new_prob,
                    old_tier=old_tier,
                    new_tier=new_tier,
                    change_reason=edge.get("adjustment_reason"),
                ))
                has_change = True
            
            # Check line change
            if abs(old_line - new_line) >= 0.5:
                diff.line_changed.append(DiffItem(
                    edge_id=edge.get("edge_id", edge.get("id", key)),
                    player=edge.get("player", edge.get("entity", "")),
                    stat=edge.get("stat", edge.get("market", "")),
                    line=new_line,
                    direction=edge.get("direction", ""),
                    diff_type=DiffType.LINE_MOVED,
                    old_line=old_line,
                    new_line=new_line,
                ))
                has_change = True
            
            if not has_change:
                diff.unchanged_count += 1
    
    # Find removed edges
    for key, old_edge in yesterday_map.items():
        if key not in matched_keys:
            diff.removed_edges.append(DiffItem(
                edge_id=old_edge.get("edge_id", old_edge.get("id", key)),
                player=old_edge.get("player", old_edge.get("entity", "")),
                stat=old_edge.get("stat", old_edge.get("market", "")),
                line=float(old_edge.get("line", 0)),
                direction=old_edge.get("direction", ""),
                diff_type=DiffType.REMOVED,
                old_probability=normalize_probability(old_edge.get("probability")),
                old_tier=old_edge.get("tier", old_edge.get("confidence_tier", "")),
                change_reason="Not in today's slate",
            ))
    
    return diff


# =============================================================================
# DIFF RENDERER
# =============================================================================

def render_diff_text(diff: DailyDiff) -> str:
    """Render diff as readable text."""
    lines = [
        "=" * 60,
        f"📊 DAILY DIFF: {diff.yesterday_date} → {diff.today_date}",
        "=" * 60,
    ]
    
    if not diff.has_changes:
        lines.append("\nNo significant changes detected.")
        return "\n".join(lines)
    
    # Summary
    lines.append("\n📈 SUMMARY")
    lines.append("-" * 40)
    lines.append(f"  🟢 New edges: {len(diff.new_edges)}")
    lines.append(f"  🔴 Removed: {len(diff.removed_edges)}")
    lines.append(f"  🔵 Probability changed: {len(diff.probability_changed)}")
    lines.append(f"  🟠 Tier changed: {len(diff.tier_changed)}")
    lines.append(f"  📊 Line moved: {len(diff.line_changed)}")
    lines.append(f"  ⚪ Unchanged: {diff.unchanged_count}")
    
    # New edges
    if diff.new_edges:
        lines.append("\n🟢 NEW EDGES")
        lines.append("-" * 40)
        for item in diff.new_edges:
            lines.append(item.format_text())
    
    # Tier downgrades (important!)
    tier_downgrades = [t for t in diff.tier_changed if t.diff_type == DiffType.TIER_DOWNGRADE]
    if tier_downgrades:
        lines.append("\n🟠 TIER DOWNGRADES")
        lines.append("-" * 40)
        for item in tier_downgrades:
            lines.append(item.format_text())
    
    # Probability changes
    if diff.probability_changed:
        lines.append("\n🔵 PROBABILITY MOVED")
        lines.append("-" * 40)
        for item in sorted(diff.probability_changed, key=lambda x: abs(x.probability_delta or 0), reverse=True):
            lines.append(item.format_text())
    
    # Removed
    if diff.removed_edges:
        lines.append("\n🔴 REMOVED BY GATE")
        lines.append("-" * 40)
        for item in diff.removed_edges:
            lines.append(item.format_text())
    
    return "\n".join(lines)


# =============================================================================
# FILE-BASED DIFF LOADING
# =============================================================================

def load_edges_from_file(filepath: Path) -> List[Dict]:
    """Load edges from JSON file."""
    if not filepath.exists():
        return []
    
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Handle various formats
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        # signals_latest.json format
        return data.get("signals", data.get("edges", data.get("results", [])))
    
    return []


def find_yesterday_file(output_dir: Path, today_date: str = None) -> Optional[Path]:
    """Find yesterday's signals file."""
    if today_date is None:
        today_date = datetime.now().strftime("%Y%m%d")
    
    yesterday = (datetime.strptime(today_date, "%Y%m%d") - timedelta(days=1)).strftime("%Y%m%d")
    
    # Try various naming patterns
    patterns = [
        f"signals_{yesterday}.json",
        f"signals_latest_{yesterday}.json",
        f"*_{yesterday}*.json",
    ]
    
    for pattern in patterns:
        matches = list(output_dir.glob(pattern))
        if matches:
            return matches[0]
    
    return None


def diff_from_files(
    today_file: Path,
    yesterday_file: Optional[Path] = None,
    output_dir: Optional[Path] = None
) -> DailyDiff:
    """
    Generate diff from files.
    
    If yesterday_file is not provided, attempts to find it automatically.
    """
    today_edges = load_edges_from_file(today_file)
    
    if yesterday_file is None and output_dir is not None:
        yesterday_file = find_yesterday_file(output_dir)
    
    if yesterday_file and yesterday_file.exists():
        yesterday_edges = load_edges_from_file(yesterday_file)
    else:
        yesterday_edges = []
    
    return diff_edges(today_edges, yesterday_edges)


# =============================================================================
# CLI
# =============================================================================

if __name__ == "__main__":
    # Test with sample data
    yesterday = [
        {"player": "Tyrese Maxey", "stat": "steals", "direction": "over", "line": 1.5, "probability": 0.58, "tier": "STRONG"},
        {"player": "Joel Embiid", "stat": "points", "direction": "over", "line": 32.5, "probability": 0.65, "tier": "SLAM"},
        {"player": "James Harden", "stat": "assists", "direction": "over", "line": 8.5, "probability": 0.55, "tier": "LEAN"},
    ]
    
    today = [
        {"player": "Tyrese Maxey", "stat": "steals", "direction": "over", "line": 1.5, "probability": 0.52, "tier": "NO_PLAY"},
        {"player": "Joel Embiid", "stat": "points", "direction": "over", "line": 30.5, "probability": 0.68, "tier": "SLAM"},  # Line moved
        # James Harden removed
        {"player": "Nikola Jokic", "stat": "rebounds", "direction": "over", "line": 12.5, "probability": 0.72, "tier": "SLAM"},  # New
    ]
    
    diff = diff_edges(today, yesterday)
    
    print(render_diff_text(diff))
    
    print("\n" + "=" * 60)
    print("JSON EXPORT:")
    print("=" * 60)
    print(json.dumps(diff.to_dict(), indent=2))
