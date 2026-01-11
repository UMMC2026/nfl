#!/usr/bin/env python3
"""
NFL RESULTS RESOLUTION
======================

NFL feeds into the unified resolved ledger with sport segmentation.

Same truth ledger as NBA, but separate calibration checks.
"""

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class ResolvedNFLPick:
    """A resolved NFL pick (graded against final stats)."""
    date: str
    game_id: str
    sport: str = "NFL"
    player_name: str = ""
    team: str = ""
    stat: str = ""
    direction: str = ""
    line: float = 0.0
    actual_value: Optional[float] = None
    outcome: str = "UNKNOWN"  # HIT, MISS, PUSH, UNKNOWN
    
    # Context
    position: str = ""
    snap_pct: float = 0.0
    
    # Learning flags
    validation_passed: bool = False
    non_learning_flag: bool = False


class NFLResultResolver:
    """Resolve NFL picks against final results."""
    
    def grade_pick(self, pick: Dict, final_stats: Dict) -> str:
        """
        Grade a single NFL pick.
        
        OVER 100 yards: actual > 100 → HIT
        UNDER 100 yards: actual < 100 → HIT
        actual == line → PUSH
        """
        direction = pick.get("direction", "").upper()
        line = float(pick.get("line", 0.0))
        actual = float(final_stats.get("actual_value", 0.0))
        
        if actual is None:
            return "UNKNOWN"
        
        if direction == "OVER":
            return "HIT" if actual > line else ("PUSH" if actual == line else "MISS")
        elif direction == "UNDER":
            return "HIT" if actual < line else ("PUSH" if actual == line else "MISS")
        else:
            return "UNKNOWN"
    
    def resolve_nfl_game(self,
                        game_id: str,
                        picks: List[Dict],
                        final_stats: Dict,
                        validation_result: Dict) -> List[ResolvedNFLPick]:
        """
        Resolve all picks for an NFL game.
        
        Args:
            game_id: NFL game ID
            picks: List of picks for this game
            final_stats: Final player stats
            validation_result: Results from validation gates
            
        Returns:
            List of ResolvedNFLPick objects
        """
        resolved = []
        
        for pick in picks:
            player_name = pick.get("player_name", "")
            stat = pick.get("stat", "")
            
            # Find final stat for this player
            player_final = final_stats.get(player_name, {})
            
            if not player_final:
                outcome = "UNKNOWN"
            else:
                stat_name_map = {
                    "passing_yards": "passing_yards",
                    "rushing_yards": "rushing_yards",
                    "receiving_yards": "receiving_yards",
                    "receptions": "receptions",
                    "targets": "targets",
                    "touchdowns": "touchdowns",
                }
                
                actual_stat = stat_name_map.get(stat)
                if actual_stat:
                    player_final["actual_value"] = player_final.get(actual_stat, 0.0)
                    outcome = self.grade_pick(pick, player_final)
                else:
                    outcome = "UNKNOWN"
            
            # Check if this is a learning edge
            non_learning = False
            if validation_result.get("gates", {}).get("4_injury_certainty", {}).get("warnings"):
                # If player has injury warnings, flag as non-learning
                if any(player_name in w for w in validation_result["gates"]["4_injury_certainty"]["warnings"]):
                    non_learning = True
            
            resolved_pick = ResolvedNFLPick(
                date=datetime.now().date().isoformat(),
                game_id=game_id,
                player_name=player_name,
                team=pick.get("team", ""),
                stat=stat,
                direction=pick.get("direction", ""),
                line=float(pick.get("line", 0.0)),
                actual_value=player_final.get(stat_name_map.get(stat, ""), None),
                outcome=outcome,
                position=pick.get("position", ""),
                snap_pct=player_final.get("snap_pct", 0.0),
                validation_passed=validation_result.get("overall_passed", False),
                non_learning_flag=non_learning,
            )
            
            resolved.append(resolved_pick)
        
        return resolved


def write_resolved_nfl_picks(resolved_picks: List[ResolvedNFLPick],
                            output_path: Path):
    """Write resolved picks to CSV (append-only)."""
    
    csv_header = (
        "date,game_id,sport,player_name,team,stat,direction,line,"
        "actual_value,outcome,position,snap_pct,validation_passed,non_learning\n"
    )
    
    # Check if file exists
    file_exists = output_path.exists()
    
    with open(output_path, "a") as f:
        if not file_exists:
            f.write(csv_header)
        
        for pick in resolved_picks:
            row = (
                f"{pick.date},{pick.game_id},{pick.sport},{pick.player_name},"
                f"{pick.team},{pick.stat},{pick.direction},{pick.line},"
                f"{pick.actual_value},{pick.outcome},{pick.position},"
                f"{pick.snap_pct},{pick.validation_passed},{pick.non_learning_flag}\n"
            )
            f.write(row)


def resolve_nfl_game(game_id: str,
                    picks: List[Dict],
                    final_stats: Dict,
                    validation_result: Dict,
                    output_path: Path) -> List[ResolvedNFLPick]:
    """
    Main NFL resolution pipeline.
    
    1. Grade all picks
    2. Flag non-learning edges
    3. Write to CSV (append)
    4. Return for ledger
    """
    resolver = NFLResultResolver()
    
    resolved = resolver.resolve_nfl_game(game_id, picks, final_stats, validation_result)
    
    write_resolved_nfl_picks(resolved, output_path)
    
    return resolved


if __name__ == "__main__":
    print("NFL Results Resolver ready for pipeline integration.")
