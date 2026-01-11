"""
Phase C-1: Ticket-Level Exposure Governor

Enforces risk limits **inside each individual parlay/entry**:
- Max 2 alt-stats per ticket
- Max 1 early-sequence stat per ticket  
- Max 1 event-binary stat per ticket
- Blocks same-player multiple stats
- Applies soft penalties for same-team correlation

No state persistence (per-ticket evaluation).
Safe to run on any slate without side effects.

Architecture: Input ticket → evaluate → output (verdict, adjustments, warnings)
"""

from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
from enum import Enum


class VerdictType(Enum):
    """Ticket verdict."""
    APPROVED = "approved"
    APPROVED_WITH_PENALTY = "approved_with_penalty"
    DOWNGRADED = "downgraded"
    BLOCKED = "blocked"


@dataclass
class TicketAdjustment:
    """Single adjustment to a ticket."""
    verdict: VerdictType
    message: str
    penalty_mult: float = 1.0  # EV multiplier
    warnings: List[str] = None
    notes: List[str] = None
    
    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []
        if self.notes is None:
            self.notes = []


class TicketGovernor:
    """
    Evaluates individual parlay tickets for exposure violations.
    
    Hard limits (blocking):
    - 3+ alt-stats in same ticket → blocked
    - 2+ early-sequence stats in same ticket → blocked
    - 2+ event-binary stats in same ticket → blocked
    - 3+ same-team stats in same ticket → downgrade tier
    - 2+ same-player stats → downgrade tier
    
    Soft penalties (EV multiplier):
    - 2 alt-stats: 0.95x (5% penalty)
    - 1 early + 1 event: 0.90x (10% penalty)
    - 2 same-team: 0.85x (15% penalty)
    """
    
    def __init__(self):
        self.hard_blocks = {
            "alt_stat_max": 2,           # Max alt-stats per ticket
            "sequence_early_max": 1,     # Max early-sequence per ticket
            "event_binary_max": 1,       # Max event-binary per ticket
            "same_team_max": 2,          # Max same team (soft: downgrade at 3)
            "same_player_max": 1,        # Max same player (block at 2+)
        }
        
        self.soft_penalties = {
            "two_alt_stats": 0.95,       # 2 alt-stats: 5% penalty
            "early_plus_event": 0.90,    # 1 early + 1 event: 10% penalty
            "two_same_team": 0.85,       # 2 same team: 15% penalty
            "three_same_team": 0.70,     # 3 same team: 30% penalty (hard downgrade)
        }
    
    def evaluate_ticket(self, picks: List[Dict]) -> TicketAdjustment:
        """
        Evaluate a single ticket (list of picks in the parlay).
        
        Args:
            picks: List of pick dicts with keys:
                   - player: str
                   - team: str
                   - stat: str
                   - stat_class: str (core, volume_micro, sequence_early, event_binary)
                   - display_prob: float
                   - tier: str (SLAM, STRONG, LEAN)
        
        Returns:
            TicketAdjustment with verdict, message, penalty, warnings
        """
        if not picks or len(picks) < 2:
            return TicketAdjustment(
                verdict=VerdictType.APPROVED,
                message="Single or empty ticket (no exposure check needed)",
                penalty_mult=1.0
            )
        
        # Extract stat classes
        stat_classes = [p.get("stat_class", "core") for p in picks]
        players = [p.get("player", "UNK") for p in picks]
        teams = [p.get("team", "UNK") for p in picks]
        
        # Count alt-stats
        alt_stats_count = sum(1 for sc in stat_classes if sc != "core")
        early_sequence_count = stat_classes.count("sequence_early")
        event_binary_count = stat_classes.count("event_binary")
        
        # Hard blocks (3+ alt-stats)
        if alt_stats_count > self.hard_blocks["alt_stat_max"]:
            return TicketAdjustment(
                verdict=VerdictType.BLOCKED,
                message=f"❌ BLOCKED: {alt_stats_count} alt-stats in same ticket (max: {self.hard_blocks['alt_stat_max']})",
                warnings=[f"Alt-stats: {stat_classes}"],
                penalty_mult=0.0  # Blocked = 0 EV
            )
        
        # Hard blocks (2+ early-sequence)
        if early_sequence_count > self.hard_blocks["sequence_early_max"]:
            return TicketAdjustment(
                verdict=VerdictType.BLOCKED,
                message=f"❌ BLOCKED: {early_sequence_count} early-sequence stats in same ticket",
                warnings=["Cannot stack early-sequence stats (high correlation)"],
                penalty_mult=0.0
            )
        
        # Hard blocks (2+ event-binary)
        if event_binary_count > self.hard_blocks["event_binary_max"]:
            return TicketAdjustment(
                verdict=VerdictType.BLOCKED,
                message=f"❌ BLOCKED: {event_binary_count} event-binary stats in same ticket",
                warnings=["Cannot stack event/binary stats"],
                penalty_mult=0.0
            )
        
        # Hard block: 2+ same player
        player_counts = {}
        for p in players:
            player_counts[p] = player_counts.get(p, 0) + 1
        
        multi_player = [p for p, c in player_counts.items() if c > 1]
        if multi_player:
            return TicketAdjustment(
                verdict=VerdictType.BLOCKED,
                message=f"❌ BLOCKED: Same player multiple stats ({multi_player})",
                warnings=["Cannot stack same player in single ticket"],
                penalty_mult=0.0
            )
        
        # Soft: Same-team correlation (3+ = downgrade, 2 = penalty)
        team_counts = {}
        for t in teams:
            team_counts[t] = team_counts.get(t, 0) + 1
        
        max_team_count = max(team_counts.values()) if team_counts else 1
        
        # Build verdict and penalties
        verdict = VerdictType.APPROVED
        penalty_mult = 1.0
        warnings = []
        notes = []
        
        # Penalty: 2 alt-stats
        if alt_stats_count == 2:
            penalty_mult *= self.soft_penalties["two_alt_stats"]
            notes.append(f"2 alt-stats: {self.soft_penalties['two_alt_stats']:.0%} EV")
            warnings.append("Alt-stat stacking reduces confidence")
        
        # Penalty: early + event mixed
        if early_sequence_count >= 1 and event_binary_count >= 1:
            penalty_mult *= self.soft_penalties["early_plus_event"]
            notes.append(f"Early + Event mix: {self.soft_penalties['early_plus_event']:.0%} EV")
            warnings.append("Early-sequence + event stats are independent; avoid mixing")
        
        # Same-team penalties
        if max_team_count == 3:
            verdict = VerdictType.DOWNGRADED
            penalty_mult *= self.soft_penalties["three_same_team"]
            notes.append(f"3 same team: {self.soft_penalties['three_same_team']:.0%} EV (DOWNGRADED)")
            warnings.append(f"Heavy same-team correlation (3 picks)")
        elif max_team_count == 2:
            penalty_mult *= self.soft_penalties["two_same_team"]
            notes.append(f"2 same team: {self.soft_penalties['two_same_team']:.0%} EV")
            warnings.append(f"Same-team correlation reduces edge")
        
        # Final message
        if verdict == VerdictType.DOWNGRADED:
            message = f"⬇️  DOWNGRADED: {', '.join(notes)}"
        elif warnings:
            verdict = VerdictType.APPROVED_WITH_PENALTY
            message = f"✅ APPROVED (with penalty): {'; '.join(notes)}"
        else:
            message = "✅ APPROVED: Clean ticket (no exposure violations)"
        
        return TicketAdjustment(
            verdict=verdict,
            message=message,
            penalty_mult=penalty_mult,
            warnings=warnings,
            notes=notes
        )
    
    def batch_evaluate(self, ticket_list: List[List[Dict]]) -> List[TicketAdjustment]:
        """
        Evaluate multiple tickets (no cross-ticket state).
        
        Args:
            ticket_list: List of tickets, each ticket is a list of picks
        
        Returns:
            List of TicketAdjustment verdicts
        """
        return [self.evaluate_ticket(ticket) for ticket in ticket_list]
    
    def format_summary(self, adjustments: List[TicketAdjustment]) -> str:
        """
        Format governance summary for cheatsheet or logging.
        
        Args:
            adjustments: List of ticket verdicts
        
        Returns:
            Human-readable summary
        """
        if not adjustments:
            return "No tickets evaluated"
        
        approved = sum(1 for a in adjustments if a.verdict == VerdictType.APPROVED)
        approved_with_penalty = sum(1 for a in adjustments if a.verdict == VerdictType.APPROVED_WITH_PENALTY)
        downgraded = sum(1 for a in adjustments if a.verdict == VerdictType.DOWNGRADED)
        blocked = sum(1 for a in adjustments if a.verdict == VerdictType.BLOCKED)
        
        lines = ["🎟️  TICKET GOVERNANCE SUMMARY"]
        lines.append("=" * 70)
        lines.append(f"  Evaluated: {len(adjustments)} tickets")
        lines.append(f"  ✅ Approved: {approved}")
        lines.append(f"  ⚠️  Approved (with penalty): {approved_with_penalty}")
        lines.append(f"  ⬇️  Downgraded: {downgraded}")
        lines.append(f"  ❌ Blocked: {blocked}")
        lines.append("")
        
        if blocked > 0:
            lines.append(f"  ⚠️  {blocked} ticket(s) blocked due to exposure violations")
        
        if downgraded > 0:
            lines.append(f"  ⬇️  {downgraded} ticket(s) downgraded (same-team concentration)")
        
        if approved_with_penalty > 0:
            lines.append(f"  ✅ {approved_with_penalty} ticket(s) approved but penalized (alt-stat stacking)")
        
        return "\n".join(lines)


# ============================================================================
# TEST / EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":
    gov = TicketGovernor()
    
    # Example 1: Clean ticket (all core, different teams)
    ticket1 = [
        {"player": "OG Anunoby", "team": "NYK", "stat": "points", "stat_class": "core", "tier": "SLAM"},
        {"player": "Jamal Shead", "team": "TOR", "stat": "points", "stat_class": "core", "tier": "SLAM"},
        {"player": "Giannis", "team": "MIL", "stat": "points", "stat_class": "core", "tier": "SLAM"},
    ]
    
    result1 = gov.evaluate_ticket(ticket1)
    print("Ticket 1 (Clean):")
    print(f"  Verdict: {result1.verdict.value}")
    print(f"  Message: {result1.message}")
    print(f"  Penalty: {result1.penalty_mult:.0%}")
    print()
    
    # Example 2: 2 alt-stats + 1 core (approved with penalty)
    ticket2 = [
        {"player": "Lamar Jackson", "team": "BAL", "stat": "pass_attempts", "stat_class": "volume_micro", "tier": "STRONG"},
        {"player": "Derrick Henry", "team": "BAL", "stat": "rush_attempts", "stat_class": "volume_micro", "tier": "STRONG"},
        {"player": "Giannis", "team": "MIL", "stat": "points", "stat_class": "core", "tier": "SLAM"},
    ]
    
    result2 = gov.evaluate_ticket(ticket2)
    print("Ticket 2 (2 alt-stats):")
    print(f"  Verdict: {result2.verdict.value}")
    print(f"  Message: {result2.message}")
    print(f"  Penalty: {result2.penalty_mult:.0%}")
    if result2.warnings:
        print(f"  Warnings: {result2.warnings}")
    print()
    
    # Example 3: 2+ early-sequence (BLOCKED)
    ticket3 = [
        {"player": "OG Anunoby", "team": "NYK", "stat": "points_first_3_minutes", "stat_class": "sequence_early", "tier": "LEAN"},
        {"player": "Giannis", "team": "MIL", "stat": "points_first_3_minutes", "stat_class": "sequence_early", "tier": "LEAN"},
        {"player": "Jamal Shead", "team": "TOR", "stat": "points", "stat_class": "core", "tier": "SLAM"},
    ]
    
    result3 = gov.evaluate_ticket(ticket3)
    print("Ticket 3 (2 early-sequence — BLOCKED):")
    print(f"  Verdict: {result3.verdict.value}")
    print(f"  Message: {result3.message}")
    print(f"  Penalty: {result3.penalty_mult:.0%}")
    print()
    
    # Batch summary
    print("=" * 70)
    all_results = [result1, result2, result3]
    print(gov.format_summary(all_results))
