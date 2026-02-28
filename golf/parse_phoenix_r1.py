"""
WM Phoenix Open R1 Slate Parser — February 2026
================================================
Parses the Underdog paste format for Round Strokes, Birdies, Fairways props

Usage:
    python golf/parse_phoenix_r1.py
"""

import sys
import re
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional, Dict

sys.path.insert(0, str(Path(__file__).parent.parent))

# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class GolfProp:
    player: str
    event: str
    tee_time: str
    line: float
    stat: str
    higher_mult: Optional[float]
    lower_mult: Optional[float]
    
    def best_direction(self) -> tuple:
        """Return (direction, multiplier) for best play"""
        if self.higher_mult and self.lower_mult:
            if self.higher_mult > self.lower_mult:
                return ("higher", self.higher_mult)
            else:
                return ("lower", self.lower_mult)
        elif self.higher_mult:
            return ("higher", self.higher_mult)
        elif self.lower_mult:
            return ("lower", self.lower_mult)
        return ("unknown", 1.0)
    
    def implied_prob(self) -> float:
        """Convert multiplier to implied probability (lower mult = higher prob)"""
        _, mult = self.best_direction()
        # Underdog multipliers: 1.0x = 50%, 0.85x = ~59%, 1.08x = ~46%
        # Formula: implied_prob = 1 / (mult + 1)  (rough estimate)
        if mult <= 0:
            return 0.50
        # Simpler: mult < 1.0 means book thinks it's more likely
        return 0.50 + (1.0 - mult) * 0.5


# =============================================================================
# PHOENIX OPEN R1 — ROUND STROKES
# =============================================================================

ROUND_STROKES = [
    # (player, line, higher_mult, lower_mult)
    ("Rasmus Hojgaard", 69.5, None, None),
    ("Nicolai Hojgaard", 69.5, 0.94, 1.03),
    ("Max Greyserman", 69.5, 0.86, 1.07),
    ("Daniel Berger", 69.5, None, None),
    ("Sahith Theegala", 69.5, 1.03, 0.94),
    ("Jake Knapp", 69.5, 1.03, 0.94),
    ("Wyndham Clark", 69.5, 0.94, 1.03),
    ("Sepp Straka", 69.5, None, None),
    ("Ryan Fox", 70.5, None, None),
    ("Jordan Spieth", 69.5, 1.03, 0.88),
    ("Chris Gotterup", 69.5, 1.07, 0.86),
    ("Kurt Kitayama", 69.5, None, None),
    ("Jacob Bridgeman", 69.5, 0.83, 1.08),
    ("Corey Conners", 69.5, None, None),
    ("Rasmus Neergaard-Petersen", 69.5, 0.94, 1.03),
    ("Keith Mitchell", 69.5, None, None),
    ("Hideki Matsuyama", 68.5, 0.86, 1.07),
    ("Viktor Hovland", 69.5, 1.04, 0.87),
    ("Xander Schauffele", 68.5, 0.88, 1.03),
    ("Brooks Koepka", 69.5, 0.94, 1.03),
    ("Harry Hall", 69.5, 1.03, 0.94),
    ("Si Woo Kim", 68.5, 0.88, 1.03),
    ("Min Woo Lee", 69.5, None, None),
    ("Maverick McNealy", 69.5, 1.08, 0.83),
    ("Matt McCarty", 69.5, None, None),
    ("Nico Echavarria", 70.5, 1.06, 0.86),
    ("John Keefer", 69.5, 0.83, 1.08),
    ("Max McGreevy", 69.5, 0.85, 1.06),
    ("Pierceson Coody", 69.5, None, None),
    ("Michael Thorbjornsen", 69.5, None, None),
    ("Bud Cauley", 69.5, 0.82, 1.03),
    ("Sam Burns", 69.5, 1.06, 0.85),
    ("Ben Griffin", 68.5, 0.82, 1.03),
    ("Matt Fitzpatrick", 69.5, 1.03, 0.88),
    ("Nick Taylor", 69.5, None, None),
    ("Scottie Scheffler", 67.5, 1.06, 0.85),
    ("Harris English", 69.5, 1.06, 0.86),
    ("Brian Harman", 70.5, 1.08, 0.83),
    ("Michael Brennan", 70.5, 1.06, 0.86),
    ("Marco Penge", 70.5, 1.08, 0.83),
    ("Rico Hoey", 69.5, 0.88, 1.03),
    ("Kristoffer Reitan", 69.5, 0.83, 1.08),
    ("Sam Stevens", 69.5, None, None),
    ("Collin Morikawa", 69.5, 1.04, 0.94),
    ("J.T. Poston", 69.5, None, None),
    ("Cameron Young", 68.5, 0.83, 1.08),
    ("Akshay Bhatia", 69.5, 0.83, 1.08),
    ("Andrew Novak", 69.5, 0.88, 1.03),
    ("Rickie Fowler", 69.5, 1.06, 0.85),
    ("Brian Campbell", 71.5, 1.06, 0.85),
    ("Garrick Higgo", 69.5, 0.94, 1.03),
    ("Billy Horschel", 70.5, 1.05, 0.85),
    ("Sami Valimaki", 70.5, 1.09, 0.83),
    ("HaoTong Li", 69.5, 0.94, 1.03),
]

BIRDIES_OR_BETTER = [
    # (player, line, higher_mult, lower_mult)
    ("Rasmus Hojgaard", 4.5, 1.07, 0.86),
    ("Pierceson Coody", 4.5, 1.06, 0.86),
    ("Michael Thorbjornsen", 4.5, 1.06, 0.80),
    ("Daniel Berger", 4.5, 1.06, 0.80),
    ("Sahith Theegala", 4.5, 1.05, 0.85),
    ("Jake Knapp", 4.5, 1.04, 0.87),
    ("Matt Fitzpatrick", 4.5, 1.08, 0.83),
    ("Sepp Straka", 4.5, 1.04, 0.78),
    ("Ryan Fox", 3.5, 0.80, 1.06),
    ("Jordan Spieth", 4.5, 1.05, 0.81),
    ("Harris English", 4.5, 1.08, 0.83),
    ("Kurt Kitayama", 4.5, 1.08, 0.83),
    ("Jacob Bridgeman", 3.5, 0.78, 1.10),
    ("Corey Conners", 4.5, 1.06, 0.80),
    ("Rasmus Neergaard-Petersen", 3.5, 0.76, 1.08),
    ("Keith Mitchell", 4.5, 1.05, 0.85),
    ("Hideki Matsuyama", 4.5, 1.03, 0.88),
    ("Collin Morikawa", 4.5, 1.09, 0.79),
    ("Xander Schauffele", 4.5, None, None),
    ("Akshay Bhatia", 4.5, 1.09, 0.79),
    ("Harry Hall", 4.5, 1.07, 0.84),
    ("Rickie Fowler", 4.5, 1.07, 0.86),
    ("Brian Campbell", 3.5, 1.05, 0.86),
    ("Garrick Higgo", 4.5, 1.05, 0.81),
    ("Billy Horschel", 3.5, 0.84, 1.07),
    ("Nico Echavarria", 3.5, 0.84, 1.06),
    ("HaoTong Li", 4.5, 1.04, 0.81),
    ("Max McGreevy", 3.5, 0.80, 1.07),
    ("Nicolai Hojgaard", 4.5, 1.04, 0.88),
    ("Max Greyserman", 4.5, 1.06, 0.80),
    ("Bud Cauley", 3.5, 0.81, 1.05),
    ("Sam Burns", 4.5, 1.03, 0.82),
    ("Ben Griffin", 4.5, 1.08, 0.83),
    ("Wyndham Clark", 4.5, 1.03, 0.82),
    ("Nick Taylor", 3.5, 0.78, 1.05),
    ("Scottie Scheffler", 5.5, 1.06, 0.85),
    ("Chris Gotterup", 4.5, 1.03, 0.94),
    ("Brian Harman", 3.5, 0.86, 1.06),
    ("Michael Brennan", 3.5, 0.78, 1.03),
    ("Marco Penge", 4.5, 1.05, 0.81),
    ("Rico Hoey", 3.5, 0.76, 1.08),
    ("Kristoffer Reitan", 3.5, 0.76, 1.08),
    ("Sam Stevens", 4.5, 1.05, 0.77),
    ("Viktor Hovland", 4.5, 1.03, 0.88),
    ("J.T. Poston", 3.5, 0.78, 1.03),
    ("Cameron Young", 4.5, None, None),
    ("Andrew Novak", 4.5, 1.08, 0.79),
    ("Si Woo Kim", 4.5, 1.08, 0.83),
    ("Min Woo Lee", 4.5, 1.05, 0.81),
    ("Maverick McNealy", 4.5, 1.06, 0.86),
    ("Matt McCarty", 4.5, 1.09, 0.79),
    ("Sami Valimaki", 3.5, 0.84, 1.06),
    ("John Keefer", 4.5, 1.03, 0.78),
]

FAIRWAYS_HIT = [
    # (player, line, higher_mult, lower_mult)
    ("Max Greyserman", 7.5, 1.05, 0.81),
    ("Jake Knapp", 7.5, 1.05, 0.86),
    ("Matt Fitzpatrick", 8.5, 1.03, 0.82),
    ("Scottie Scheffler", 8.5, 0.82, 1.03),
    ("Chris Gotterup", 7.5, 1.08, 0.84),
    ("Marco Penge", 7.5, 1.07, 0.84),
    ("Kristoffer Reitan", 8.5, 1.05, 0.81),
    ("Collin Morikawa", 9.5, None, None),
    ("Viktor Hovland", 8.5, None, None),
    ("Cameron Young", 7.5, None, None),
    ("Si Woo Kim", 9.5, 1.08, 0.79),
    ("Matt McCarty", 8.5, 1.05, 0.85),
    ("Sam Burns", 8.5, 1.04, 0.81),
    ("Sepp Straka", 8.5, 0.84, 1.08),
    ("Ben Griffin", 7.5, 0.82, 1.03),
    ("Harris English", 8.5, None, None),
    ("Michael Brennan", 8.5, 1.03, 0.88),
    ("Corey Conners", 8.5, 0.81, 1.05),
    ("Sam Stevens", 7.5, 0.81, 1.04),
    ("Hideki Matsuyama", 8.5, 1.09, 0.79),
    ("Xander Schauffele", 7.5, 1.05, 0.85),
    ("Andrew Novak", 7.5, 0.94, 1.03),
    ("Rickie Fowler", 8.5, None, None),
    ("Maverick McNealy", 7.5, 0.81, 1.04),
]


# =============================================================================
# ANALYSIS FUNCTIONS
# =============================================================================

def mult_to_implied_prob(mult: float) -> float:
    """
    Convert Underdog multiplier to implied probability.
    
    mult < 1.0 = book thinks more likely (e.g., 0.85 = ~59%)
    mult > 1.0 = book thinks less likely (e.g., 1.08 = ~46%)
    """
    if mult is None or mult <= 0:
        return 0.50
    # Approximate: implied_prob ≈ 1 / (1 + mult)
    # But Underdog uses different math, so:
    # 0.85 → ~58%, 1.03 → ~49%, 1.08 → ~46%
    return 1.0 / (1.0 + mult)


def analyze_round_strokes():
    """Analyze Round Strokes props for edges"""
    print("\n" + "=" * 70)
    print("⛳ WM PHOENIX OPEN R1 — ROUND STROKES ANALYSIS")
    print("=" * 70)
    print("   Line = expected score | Lower mult < 1.0 = LOWER favored")
    print("-" * 70)
    
    # Find best LOWER plays (mult > 1.03)
    lower_plays = []
    higher_plays = []
    
    for player, line, h_mult, l_mult in ROUND_STROKES:
        if l_mult and l_mult >= 1.03:
            edge = (l_mult - 1.0) / 1.0 * 100  # Rough edge %
            lower_plays.append((player, line, l_mult, edge, "LOWER"))
        if h_mult and h_mult >= 1.03:
            edge = (h_mult - 1.0) / 1.0 * 100
            higher_plays.append((player, line, h_mult, edge, "HIGHER"))
    
    print("\n🔽 LOWER PLAYS (Score Under Line) — Sorted by Mult")
    print("-" * 70)
    for player, line, mult, edge, direction in sorted(lower_plays, key=lambda x: x[2], reverse=True):
        tier = "STRONG" if mult >= 1.07 else "LEAN"
        print(f"  {tier:6} | {player:25} | Line {line} | {direction} {mult:.2f}x | Edge ~{edge:.1f}%")
    
    print(f"\n  Total LOWER plays: {len(lower_plays)}")
    
    print("\n🔼 HIGHER PLAYS (Score Over Line) — Sorted by Mult")
    print("-" * 70)
    for player, line, mult, edge, direction in sorted(higher_plays, key=lambda x: x[2], reverse=True):
        tier = "STRONG" if mult >= 1.07 else "LEAN"
        print(f"  {tier:6} | {player:25} | Line {line} | {direction} {mult:.2f}x | Edge ~{edge:.1f}%")
    
    print(f"\n  Total HIGHER plays: {len(higher_plays)}")
    
    return lower_plays, higher_plays


def analyze_birdies():
    """Analyze Birdies or Better props"""
    print("\n" + "=" * 70)
    print("🐦 WM PHOENIX OPEN R1 — BIRDIES OR BETTER ANALYSIS")
    print("=" * 70)
    
    lower_plays = []
    higher_plays = []
    
    for player, line, h_mult, l_mult in BIRDIES_OR_BETTER:
        if l_mult and l_mult >= 1.03:
            edge = (l_mult - 1.0) / 1.0 * 100
            lower_plays.append((player, line, l_mult, edge, "LOWER"))
        if h_mult and h_mult >= 1.03:
            edge = (h_mult - 1.0) / 1.0 * 100
            higher_plays.append((player, line, h_mult, edge, "HIGHER"))
    
    print("\n🔽 LOWER PLAYS (Fewer Birdies)")
    print("-" * 70)
    for player, line, mult, edge, direction in sorted(lower_plays, key=lambda x: x[2], reverse=True)[:10]:
        print(f"  {player:25} | Line {line} | {direction} {mult:.2f}x | Edge ~{edge:.1f}%")
    
    print("\n🔼 HIGHER PLAYS (More Birdies)")
    print("-" * 70)
    for player, line, mult, edge, direction in sorted(higher_plays, key=lambda x: x[2], reverse=True)[:10]:
        print(f"  {player:25} | Line {line} | {direction} {mult:.2f}x | Edge ~{edge:.1f}%")
    
    return lower_plays, higher_plays


def analyze_fairways():
    """Analyze Fairways Hit props"""
    print("\n" + "=" * 70)
    print("🎯 WM PHOENIX OPEN R1 — FAIRWAYS HIT ANALYSIS")
    print("=" * 70)
    
    lower_plays = []
    higher_plays = []
    
    for player, line, h_mult, l_mult in FAIRWAYS_HIT:
        if l_mult and l_mult >= 1.03:
            edge = (l_mult - 1.0) / 1.0 * 100
            lower_plays.append((player, line, l_mult, edge, "LOWER"))
        if h_mult and h_mult >= 1.03:
            edge = (h_mult - 1.0) / 1.0 * 100
            higher_plays.append((player, line, h_mult, edge, "HIGHER"))
    
    print("\n🔽 LOWER PLAYS (Fewer Fairways)")
    print("-" * 70)
    for player, line, mult, edge, direction in sorted(lower_plays, key=lambda x: x[2], reverse=True):
        print(f"  {player:25} | Line {line} | {direction} {mult:.2f}x | Edge ~{edge:.1f}%")
    
    print("\n🔼 HIGHER PLAYS (More Fairways)")
    print("-" * 70)
    for player, line, mult, edge, direction in sorted(higher_plays, key=lambda x: x[2], reverse=True):
        print(f"  {player:25} | Line {line} | {direction} {mult:.2f}x | Edge ~{edge:.1f}%")
    
    return lower_plays, higher_plays


def build_top_picks():
    """Build consolidated top picks list"""
    print("\n" + "=" * 70)
    print("🏆 TOP PICKS — PHOENIX OPEN R1")
    print("=" * 70)
    
    all_plays = []
    
    # Collect all plays
    for player, line, h_mult, l_mult in ROUND_STROKES:
        if l_mult and l_mult >= 1.05:
            all_plays.append((player, line, l_mult, "Round Strokes LOWER", "STRONG"))
        if h_mult and h_mult >= 1.05:
            all_plays.append((player, line, h_mult, "Round Strokes HIGHER", "LEAN"))  # Higher is riskier
    
    for player, line, h_mult, l_mult in BIRDIES_OR_BETTER:
        if l_mult and l_mult >= 1.06:
            all_plays.append((player, line, l_mult, f"Birdies {line} LOWER", "STRONG"))
        if h_mult and h_mult >= 1.06:
            all_plays.append((player, line, h_mult, f"Birdies {line} HIGHER", "LEAN"))
    
    for player, line, h_mult, l_mult in FAIRWAYS_HIT:
        if l_mult and l_mult >= 1.04:
            all_plays.append((player, line, l_mult, f"Fairways {line} LOWER", "LEAN"))
        if h_mult and h_mult >= 1.06:
            all_plays.append((player, line, h_mult, f"Fairways {line} HIGHER", "LEAN"))
    
    # Sort by multiplier
    all_plays.sort(key=lambda x: x[2], reverse=True)
    
    print("\n📊 STRONGEST EDGES (mult >= 1.06)")
    print("-" * 70)
    for player, line, mult, prop, tier in all_plays[:15]:
        edge = (mult - 1.0) * 100
        print(f"  {tier:6} | {player:22} | {prop:25} | {mult:.2f}x (+{edge:.0f}%)")
    
    # Correlation check
    print("\n⚠️ CORRELATION CHECK")
    print("-" * 70)
    player_counts = {}
    for player, line, mult, prop, tier in all_plays[:15]:
        player_counts[player] = player_counts.get(player, 0) + 1
    
    correlated = [(p, c) for p, c in player_counts.items() if c > 1]
    if correlated:
        for player, count in correlated:
            print(f"  ⚠️ {player}: {count} props — CORRELATED, pick only 1")
    else:
        print("  ✅ No correlated picks in top 15")
    
    return all_plays


def main():
    """Run full analysis"""
    print("\n" + "🏌️" * 35)
    print("  WM PHOENIX OPEN R1 — FULL SLATE ANALYSIS")
    print("  February 6, 2026 | TPC Scottsdale")
    print("🏌️" * 35)
    
    # Run analyses
    rs_lower, rs_higher = analyze_round_strokes()
    b_lower, b_higher = analyze_birdies()
    f_lower, f_higher = analyze_fairways()
    
    # Build top picks
    top_picks = build_top_picks()
    
    # Summary
    print("\n" + "=" * 70)
    print("📋 SUMMARY")
    print("=" * 70)
    print(f"  Round Strokes: {len(rs_lower)} LOWER plays, {len(rs_higher)} HIGHER plays")
    print(f"  Birdies:       {len(b_lower)} LOWER plays, {len(b_higher)} HIGHER plays")
    print(f"  Fairways:      {len(f_lower)} LOWER plays, {len(f_higher)} HIGHER plays")
    print(f"\n  Total plays with edge: {len(top_picks)}")
    
    # Best parlay suggestion
    print("\n" + "=" * 70)
    print("🎯 SUGGESTED 3-LEG PARLAY (No Correlation)")
    print("=" * 70)
    
    # Pick best from each category, different players
    used_players = set()
    parlay = []
    
    for player, line, mult, prop, tier in top_picks:
        if player not in used_players and len(parlay) < 3:
            parlay.append((player, prop, mult))
            used_players.add(player)
    
    for i, (player, prop, mult) in enumerate(parlay, 1):
        print(f"  Leg {i}: {player} — {prop} ({mult:.2f}x)")
    
    combined_mult = 1.0
    for _, _, mult in parlay:
        combined_mult *= mult
    print(f"\n  Combined multiplier: {combined_mult:.2f}x")
    
    print("\n" + "=" * 70)
    print("✅ ANALYSIS COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
