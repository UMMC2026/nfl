from typing import List, Optional
from sports.cbb.ingest.cbb_data_provider import CBBGame

class MatchupEngine:
    """Generates text analysis for a CBB matchup."""
    
    @staticmethod
    def analyze_matchup(game: Optional[CBBGame]) -> List[str]:
        if not game:
            return ["Game context unavailable - Check schedule or spelling"]
            
        notes = []
        
        # 1. Pace / Total Analysis
        if game.total > 0:
            if game.total >= 150:
                notes.append(f"PACE: FAST (Projected Total: {game.total}) - Expect higher possession count")
            elif game.total <= 130:
                notes.append(f"PACE: SLOW (Projected Total: {game.total}) - Defensive grind expected")
            else:
                notes.append(f"PACE: MODERATE (Projected Total: {game.total})")
        
        # 2. Spread / Competitive Context
        if game.spread != 0:
            fav = game.home_abbr if game.spread < 0 else game.away_abbr
            spread_val = abs(game.spread)
            
            if spread_val >= 16:
                notes.append(f"SPREAD: {fav} -{spread_val} (BLOWOUT RISK) - Late game variance possible")
            elif spread_val <= 4:
                notes.append(f"SPREAD: {fav} -{spread_val} (TIGHT) - High leverage minutes expected")
            else:
                notes.append(f"SPREAD: {fav} -{spread_val}")

        # 3. Ranking Context
        if game.home_rank > 0 or game.away_rank > 0:
            h_rank = f"#{game.home_rank}" if game.home_rank else "UR"
            a_rank = f"#{game.away_rank}" if game.away_rank else "UR"
            notes.append(f"RANKING: {game.away_abbr} ({a_rank}) @ {game.home_abbr} ({h_rank})")
            
        return notes
