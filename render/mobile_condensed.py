"""
Mobile-First Condensed View (Decision Surface)
===============================================
ENFORCEMENT LAYER B — Scan → Decide → Exit format for mobile users.

NO MATH CHANGES — This is rendering/visibility only.

Condensed Row Schema:
  <Player | Stat | Line | Dir | Prob | Tier | ⚠️>

Example:
  Sengun | TD | 0.5 | U | 9% | NO | ⚠️
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))


# =============================================================================
# TIER & DIRECTION SYMBOLS
# =============================================================================

TIER_SYMBOLS = {
    "SLAM": "🔒",
    "STRONG": "💪",
    "LEAN": "📊",
    "WATCH": "👀",
    "NO_PLAY": "🚫",
    "NO PLAY": "🚫",
    "AVOID": "❌",
    "REJECTED": "⛔",
}

DIRECTION_ABBREV = {
    "higher": "O",  # Over
    "lower": "U",   # Under
    "over": "O",
    "under": "U",
    "h": "O",
    "l": "U",
}

WARNING_SYMBOL = "⚠️"


# =============================================================================
# CONDENSED ROW FORMAT
# =============================================================================

@dataclass
class CondensedRow:
    """Single condensed row for mobile display."""
    player: str
    stat: str
    line: float
    direction: str  # O or U
    probability: int  # 0-100
    tier: str
    has_warning: bool = False
    warning_reasons: List[str] = None
    edge_id: str = ""
    
    def __post_init__(self):
        if self.warning_reasons is None:
            self.warning_reasons = []
    
    def to_compact_string(self, include_emoji: bool = False) -> str:
        """
        Format: Player | Stat | Line | Dir | Prob | Tier | ⚠️
        """
        tier_sym = TIER_SYMBOLS.get(self.tier.upper(), "")
        warning = WARNING_SYMBOL if self.has_warning else ""
        
        if include_emoji:
            return f"{self.player[:12]:<12} | {self.stat[:6]:<6} | {self.line:>5.1f} | {self.direction} | {self.probability:>2}% | {tier_sym}{self.tier[:3]} {warning}"
        else:
            return f"{self.player[:12]:<12} | {self.stat[:6]:<6} | {self.line:>5.1f} | {self.direction} | {self.probability:>2}% | {self.tier[:3]} {warning}"
    
    def to_dict(self) -> Dict[str, Any]:
        """Export for JSON/API."""
        return {
            "player": self.player,
            "stat": self.stat,
            "line": self.line,
            "direction": self.direction,
            "probability": self.probability,
            "tier": self.tier,
            "has_warning": self.has_warning,
            "warning_reasons": self.warning_reasons,
            "edge_id": self.edge_id,
        }


# =============================================================================
# EDGE TO CONDENSED ROW
# =============================================================================

def edge_to_condensed(edge: Dict) -> CondensedRow:
    """Convert full edge dict to condensed row."""
    
    # Extract core fields
    player = edge.get("player", edge.get("entity", "Unknown"))
    stat = edge.get("stat", edge.get("market", ""))
    line = float(edge.get("line", 0))
    
    # Normalize direction
    direction_raw = edge.get("direction", "").lower()
    direction = DIRECTION_ABBREV.get(direction_raw, direction_raw[0].upper() if direction_raw else "?")
    
    # Probability (handle 0-1 or 0-100 scale)
    prob = edge.get("probability", edge.get("p_hit", 0))
    if isinstance(prob, float) and prob <= 1.0:
        prob = int(prob * 100)
    else:
        prob = int(prob)
    
    # Tier
    tier = edge.get("tier", edge.get("confidence_tier", ""))
    
    # Check for warnings
    warning_reasons = []
    has_warning = False
    
    # From risk tags
    risk_tags = edge.get("risk_tags", [])
    if not risk_tags:
        risk = edge.get("risk", {})
        risk_tags = risk.get("risk_tags", [])
    
    if risk_tags:
        warning_reasons.extend(risk_tags)
        has_warning = True
    
    # From parlay eligibility
    parlay = edge.get("parlay", {})
    if parlay and not parlay.get("allowed", True):
        warning_reasons.append(parlay.get("reason", "BLOCKED"))
        has_warning = True
    
    # From correlation
    if parlay.get("conflicting_edge_ids"):
        warning_reasons.append("CORRELATED")
        has_warning = True
    
    # NO_PLAY tier is always a warning
    if tier.upper() in {"NO_PLAY", "NO PLAY", "AVOID", "REJECTED"}:
        has_warning = True
    
    # Edge ID
    edge_id = edge.get("edge_id", edge.get("id", ""))
    
    return CondensedRow(
        player=player,
        stat=stat,
        line=line,
        direction=direction,
        probability=prob,
        tier=tier,
        has_warning=has_warning,
        warning_reasons=warning_reasons,
        edge_id=edge_id,
    )


# =============================================================================
# EXPANDED DRAWER (TAP TO EXPAND)
# =============================================================================

@dataclass
class ExpandedDrawer:
    """Full details shown when user taps a condensed row."""
    edge: Dict
    row: CondensedRow
    
    def to_dict(self) -> Dict[str, Any]:
        """Export for API/frontend."""
        edge = self.edge
        
        return {
            "summary": self.row.to_dict(),
            "details": {
                "full_player_name": edge.get("player", edge.get("entity", "")),
                "full_stat": edge.get("stat", edge.get("market", "")),
                "line": edge.get("line"),
                "direction": edge.get("direction"),
                "probability": edge.get("probability"),
                "tier": edge.get("tier", edge.get("confidence_tier", "")),
                
                # Risk analysis
                "risk_tags": edge.get("risk_tags", []) or edge.get("risk", {}).get("risk_tags", []),
                "correlation_group": edge.get("risk", {}).get("correlated_group"),
                "correlation_type": edge.get("risk", {}).get("correlation_type"),
                
                # Parlay info
                "parlay_allowed": edge.get("parlay", {}).get("allowed", True),
                "parlay_block_reason": edge.get("parlay", {}).get("reason"),
                "conflicting_edges": edge.get("parlay", {}).get("conflicting_edge_ids", []),
                
                # Market context
                "market_odds": edge.get("market_odds"),
                "implied_prob": edge.get("implied_probability"),
                "edge_vs_market": edge.get("edge", edge.get("edge_pct")),
                
                # Why NO PLAY (if applicable)
                "no_play_reason": self._get_no_play_reason(edge),
            }
        }
    
    def _get_no_play_reason(self, edge: Dict) -> Optional[str]:
        """Generate human-readable NO PLAY explanation."""
        tier = edge.get("tier", edge.get("confidence_tier", "")).upper()
        if tier not in {"NO_PLAY", "NO PLAY", "AVOID", "REJECTED"}:
            return None
        
        reasons = []
        
        # Low probability
        prob = edge.get("probability", 0)
        if isinstance(prob, float) and prob <= 1.0:
            prob *= 100
        if prob < 50:
            reasons.append(f"Probability too low ({prob:.0f}%)")
        
        # Risk tags
        risk_tags = edge.get("risk_tags", []) or edge.get("risk", {}).get("risk_tags", [])
        if "rare_event" in risk_tags:
            reasons.append("Rare event — high variance")
        if "low_sample" in risk_tags:
            reasons.append("Insufficient sample size")
        
        # Pick state
        pick_state = edge.get("pick_state", "")
        if pick_state == "REJECTED":
            reasons.append("Failed governance gate")
        
        return " | ".join(reasons) if reasons else "Does not meet confidence threshold"
    
    def format_text(self) -> str:
        """Text format for terminal/SMS."""
        data = self.to_dict()
        details = data["details"]
        
        lines = [
            f"┌─ {details['full_player_name']} ─┐",
            f"│ {details['full_stat']} {details['line']} {details['direction'].upper()}",
            f"│ Probability: {details['probability']*100 if isinstance(details['probability'], float) and details['probability'] <= 1 else details['probability']:.0f}%",
            f"│ Tier: {details['tier']}",
        ]
        
        if details.get("risk_tags"):
            lines.append(f"│ ⚠️ Risks: {', '.join(details['risk_tags'])}")
        
        if details.get("correlation_group"):
            lines.append(f"│ 🔗 Correlated: {details['correlation_group']}")
        
        if not details.get("parlay_allowed", True):
            lines.append(f"│ ❌ Parlay blocked: {details.get('parlay_block_reason', 'N/A')}")
        
        if details.get("no_play_reason"):
            lines.append(f"│ 🚫 NO PLAY: {details['no_play_reason']}")
        
        lines.append("└" + "─" * 40 + "┘")
        
        return "\n".join(lines)


# =============================================================================
# MOBILE VIEW RENDERER
# =============================================================================

class MobileViewRenderer:
    """Render edges in mobile-first condensed format."""
    
    def __init__(self, edges: List[Dict]):
        self.edges = edges
        self.rows = [edge_to_condensed(e) for e in edges]
    
    def render_compact_list(self, include_emoji: bool = False, max_rows: int = 20) -> str:
        """Render condensed list for mobile."""
        header = "Player       | Stat   | Line  | D | Prob | Tier"
        separator = "-" * len(header)
        
        lines = [header, separator]
        
        for row in self.rows[:max_rows]:
            lines.append(row.to_compact_string(include_emoji=include_emoji))
        
        if len(self.rows) > max_rows:
            lines.append(f"... and {len(self.rows) - max_rows} more")
        
        return "\n".join(lines)
    
    def render_by_tier(self, include_emoji: bool = True) -> str:
        """Render grouped by tier for quick scanning."""
        tier_order = ["SLAM", "STRONG", "LEAN", "WATCH", "NO_PLAY", "NO PLAY", "AVOID"]
        
        by_tier = {}
        for row in self.rows:
            tier = row.tier.upper()
            if tier not in by_tier:
                by_tier[tier] = []
            by_tier[tier].append(row)
        
        lines = []
        for tier in tier_order:
            if tier in by_tier:
                sym = TIER_SYMBOLS.get(tier, "")
                lines.append(f"\n{sym} {tier} ({len(by_tier[tier])})")
                lines.append("-" * 50)
                for row in by_tier[tier]:
                    lines.append(row.to_compact_string(include_emoji=include_emoji))
        
        return "\n".join(lines)
    
    def get_expanded_drawer(self, edge_id: str) -> Optional[ExpandedDrawer]:
        """Get expanded drawer for specific edge."""
        for edge, row in zip(self.edges, self.rows):
            if row.edge_id == edge_id:
                return ExpandedDrawer(edge=edge, row=row)
        return None
    
    def export_for_api(self) -> Dict[str, Any]:
        """Export mobile-ready data for API/frontend."""
        return {
            "generated_at": datetime.now().isoformat(),
            "total_edges": len(self.edges),
            "rows": [row.to_dict() for row in self.rows],
            "by_tier": self._group_by_tier(),
        }
    
    def _group_by_tier(self) -> Dict[str, List[Dict]]:
        """Group rows by tier."""
        by_tier = {}
        for row in self.rows:
            tier = row.tier.upper()
            if tier not in by_tier:
                by_tier[tier] = []
            by_tier[tier].append(row.to_dict())
        return by_tier


# =============================================================================
# CLI TEST
# =============================================================================

if __name__ == "__main__":
    # Test with sample edges
    test_edges = [
        {
            "edge_id": "maxey_pts_1",
            "player": "Tyrese Maxey",
            "stat": "points",
            "line": 25.5,
            "direction": "higher",
            "probability": 0.68,
            "tier": "STRONG",
        },
        {
            "edge_id": "sengun_td_1",
            "player": "Alperen Sengun",
            "stat": "triple_double",
            "line": 0.5,
            "direction": "under",
            "probability": 0.09,
            "tier": "NO_PLAY",
            "risk_tags": ["rare_event", "triple_double"],
        },
        {
            "edge_id": "jokic_reb_1",
            "player": "Nikola Jokic",
            "stat": "rebounds",
            "line": 12.5,
            "direction": "higher",
            "probability": 0.72,
            "tier": "SLAM",
        },
        {
            "edge_id": "curry_3pm_1",
            "player": "Stephen Curry",
            "stat": "3pm",
            "line": 4.5,
            "direction": "higher",
            "probability": 0.58,
            "tier": "LEAN",
            "risk_tags": ["shooting_variance"],
        },
    ]
    
    print("=" * 60)
    print("MOBILE-FIRST CONDENSED VIEW TEST")
    print("=" * 60)
    
    renderer = MobileViewRenderer(test_edges)
    
    print("\n📱 COMPACT LIST:")
    print(renderer.render_compact_list(include_emoji=True))
    
    print("\n📱 BY TIER:")
    print(renderer.render_by_tier())
    
    print("\n📱 EXPANDED DRAWER (sengun_td_1):")
    drawer = renderer.get_expanded_drawer("sengun_td_1")
    if drawer:
        print(drawer.format_text())
