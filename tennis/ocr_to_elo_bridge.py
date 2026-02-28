"""
Wire OCR match results to automatic Elo updates.
Monitors parse_results_image.py output and updates player Elo ratings.

Usage:
    python tennis/ocr_to_elo_bridge.py
    
This script can be called from watch_screenshots.py or run standalone.
"""

import json
import re
import sys
from pathlib import Path
from typing import Optional, Dict

# Add tennis dir to path
TENNIS_DIR = Path(__file__).parent
sys.path.insert(0, str(TENNIS_DIR))

from elo_updater import TennisEloSystem


def parse_tennis_result(ocr_text: str) -> Optional[Dict]:
    """
    Extract tennis match result from OCR text.
    
    Expected formats:
    - "Jannik Sinner def. Carlos Alcaraz"
    - "Sinner (2) defeated Alcaraz (3)"
    - "Winner: Sinner | Loser: Alcaraz"
    """
    text = ocr_text.lower()
    
    # Pattern 1: "X def. Y" or "X defeated Y"
    match = re.search(r'([a-z\s]+?)\s+(?:def\.|defeated)\s+([a-z\s]+)', text)
    if match:
        winner = match.group(1).strip().title()
        loser = match.group(2).strip().title()
        return {"winner": winner, "loser": loser}
    
    # Pattern 2: "Winner: X | Loser: Y"
    match = re.search(r'winner:\s*([a-z\s]+?)\s*\|\s*loser:\s*([a-z\s]+)', text)
    if match:
        winner = match.group(1).strip().title()
        loser = match.group(2).strip().title()
        return {"winner": winner, "loser": loser}
    
    # Pattern 3: "X beats Y" or "X beat Y"
    match = re.search(r'([a-z\s]+?)\s+beats?\s+([a-z\s]+)', text)
    if match:
        winner = match.group(1).strip().title()
        loser = match.group(2).strip().title()
        return {"winner": winner, "loser": loser}
    
    return None


def detect_surface(ocr_text: str, tournament_name: Optional[str] = None) -> str:
    """
    Detect surface from OCR text or tournament name.
    
    Default: HARD (most common on tour)
    """
    text = ocr_text.lower()
    
    # Check text for surface mentions
    if "clay" in text or "terre battue" in text:
        return "CLAY"
    if "grass" in text or "lawn" in text:
        return "GRASS"
    if "indoor" in text or "carpet" in text:
        return "INDOOR"
    
    # Check tournament name
    if tournament_name:
        t = tournament_name.lower()
        if "roland garros" in t or "french open" in t or "monte carlo" in t or "rome" in t:
            return "CLAY"
        if "wimbledon" in t:
            return "GRASS"
        if "atp finals" in t or "paris masters" in t:
            return "INDOOR"
    
    # Default to hard court (most common)
    return "HARD"


def detect_tournament_tier(ocr_text: str, tournament_name: Optional[str] = None) -> str:
    """
    Detect tournament tier for K-factor selection.
    
    Default: ATP_500
    """
    text = ocr_text.lower()
    
    # Grand Slams
    if any(gs in text for gs in ["australian open", "french open", "wimbledon", "us open", "roland garros"]):
        return "GRAND_SLAM"
    
    # ATP 1000
    if any(m in text for m in ["indian wells", "miami", "monte carlo", "madrid", "rome", "canada", "cincinnati", "shanghai", "paris"]):
        return "ATP_1000"
    
    if tournament_name:
        t = tournament_name.lower()
        if any(gs in t for gs in ["australian open", "french open", "wimbledon", "us open"]):
            return "GRAND_SLAM"
        if "masters" in t or "1000" in t:
            return "ATP_1000"
        if "500" in t:
            return "ATP_500"
        if "250" in t:
            return "ATP_250"
    
    return "ATP_500"  # Default


def process_tennis_result(
    ocr_text: str,
    surface: Optional[str] = None,
    tournament_tier: Optional[str] = None,
    tournament_name: Optional[str] = None,
    auto_save: bool = True
) -> Optional[Dict]:
    """
    Process OCR text and update Elo if match result detected.
    
    Returns:
        Elo update summary if successful, None otherwise
    """
    # Parse winner/loser
    result = parse_tennis_result(ocr_text)
    if not result:
        return None
    
    winner = result["winner"]
    loser = result["loser"]
    
    # Detect surface and tier if not provided
    if not surface:
        surface = detect_surface(ocr_text, tournament_name)
    
    if not tournament_tier:
        tournament_tier = detect_tournament_tier(ocr_text, tournament_name)
    
    # Update Elo
    elo_sys = TennisEloSystem()
    update_summary = elo_sys.update_match_result(
        winner=winner,
        loser=loser,
        surface=surface,
        tournament_tier=tournament_tier,
        save=auto_save
    )
    
    print(f"\n[ELO] Updated from OCR result:")
    print(f"      {winner} def. {loser}")
    print(f"      Surface: {surface} | Tier: {tournament_tier}")
    print(f"      {winner}: {update_summary['winner_elo_old']} → {update_summary['winner_elo_new']} ({update_summary['winner_change']:+.2f})")
    print(f"      {loser}: {update_summary['loser_elo_old']} → {update_summary['loser_elo_new']} ({update_summary['loser_change']:+.2f})")
    
    return update_summary


if __name__ == "__main__":
    # Test with sample text
    if len(sys.argv) > 1:
        test_text = " ".join(sys.argv[1:])
        process_tennis_result(test_text)
    else:
        # Example
        sample = "Jannik Sinner def. Carlos Alcaraz in Australian Open QF"
        print("Testing with sample:")
        print(f"  '{sample}'")
        process_tennis_result(sample, tournament_name="Australian Open 2026")
