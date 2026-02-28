"""
CALIBRATED TENNIS PROPS PIPELINE
================================
Uses real Tennis Abstract data instead of generic priors.

Upgrades:
- Real player stats from 1700+ ATP/WTA 2024 matches
- Surface-specific adjustments
- Historical variance for confidence
- Head-to-head integration

SOP v2.1 Compliant - Data-Driven Analysis
"""

from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import sys

# Path setup
TENNIS_DIR = Path(__file__).parent
sys.path.insert(0, str(TENNIS_DIR))
sys.path.insert(0, str(TENNIS_DIR.parent))

from player_profiler import TennisPlayerProfiler, CalibratedTennisMC, TennisPlayerProfile


# ============================================================================
# CONFIDENCE CAPS (SOP v2.1)
# ============================================================================

STAT_CONFIDENCE_CAPS = {
    'aces': 70,
    'double_faults': 65,
    'games_won': 72,
    'games_played': 70,
    'total_games': 70,
    '1st_set_games': 68,
    'sets_played': 65,
    'sets_won': 68,
    'tiebreakers': 55,
    'breakpoints_won': 66,
    'fantasy_score': 65,
}

# Correlation groups (can't have multiple in same parlay)
CORRELATION_GROUPS = {
    'match_duration': ['games_played', 'total_games', 'sets_played'],
    'player_games': ['games_won', '1st_set_games_won'],
    'serve_stats': ['aces', 'double_faults'],
}


# ============================================================================
# CALIBRATED PIPELINE
# ============================================================================

class CalibratedTennisPropsEngine:
    """
    Tennis props engine using real historical data.
    
    Flow:
    1. Parse Underdog paste
    2. Look up real player stats from Tennis Abstract
    3. Run Monte Carlo with calibrated parameters
    4. Apply confidence caps and tiers
    5. Mark correlations
    """
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = TENNIS_DIR / "data" / "tennis_stats.db"
        
        self.profiler = TennisPlayerProfiler(str(db_path))
        self.mc = CalibratedTennisMC(self.profiler)
        
        # Cache for player profiles
        self._profile_cache: Dict[str, TennisPlayerProfile] = {}
    
    def close(self):
        self.profiler.close()
    
    def analyze_prop(
        self,
        player: str,
        stat_type: str,
        line: float,
        direction: str,
        opponent: str = None,
        surface: str = "Hard"
    ) -> Dict:
        """
        Analyze a single prop using real player data.
        Returns full analysis dict with NLP-driven narrative.
        """
        result = self.mc.simulate_prop(
            player_name=player,
            stat_type=stat_type,
            line=line,
            direction=direction,
            opponent=opponent,
            surface=surface
        )
        # Add correlation warning
        result['correlation_group'] = self._get_correlation_group(stat_type)

        # --- NLP-driven narrative generation ---
        def generate_narrative(player, stat, line, direction, probability, sample_n, opponent=None):
            dir_word = "exceed" if direction.upper() == "HIGHER" else "fall below"
            opp_str = f" against {opponent}" if opponent else ""
            conf = "high confidence" if probability >= 0.7 else ("moderate confidence" if probability >= 0.6 else "cautious outlook")
            return (
                f"Based on Monte Carlo simulations and recent performance, {player} is projected to {dir_word} {line} {stat}{opp_str} with {conf} (n={sample_n})."
            )
        prob = result.get('probability', result.get('confidence', 0)) or 0
        sample_n = result.get('sample_n') or result.get('n_matches') or 0
        result['narrative'] = generate_narrative(player, stat_type, line, direction, prob, sample_n, opponent)
        return result
    
    def analyze_slate(
        self,
        props: List[Dict],
        surface: str = "Hard"
    ) -> Dict:
        """
        Analyze a full slate of props.
        
        Args:
            props: List of dicts with keys: player, stat, line, direction, opponent
            surface: Court surface
        
        Returns:
            Dict with all results, sorted by confidence
        """
        print("\n" + "=" * 70)
        print("🎾 CALIBRATED TENNIS ANALYSIS")
        print(f"   Using Tennis Abstract 2024 data (1700+ matches)")
        print("=" * 70)
        
        results = []
        players_analyzed = set()
        players_not_found = set()
        
        for prop in props:
            player = prop.get('player')
            stat = prop.get('stat', prop.get('stat_type'))
            line = prop.get('line')
            direction = prop.get('direction', 'HIGHER')
            opponent = prop.get('opponent')
            
            if not all([player, stat, line]):
                continue

            # Parse "Player1 vs Player2" match names (total_games props)
            # so the profiler gets the right player and opponent
            if ' vs ' in str(player):
                parts = str(player).split(' vs ', 1)
                if len(parts) == 2:
                    if not opponent or opponent == player:
                        opponent = parts[1].strip()
                    # Keep original match name for display but profile the first player
                    # (The profiler will find them via LIKE match anyway)
            
            # Check if we have data for this player
            if player not in self._profile_cache:
                profile = self.profiler.get_profile(player, surface=surface)
                if profile:
                    self._profile_cache[player] = profile
                    players_analyzed.add(player)
                else:
                    players_not_found.add(player)
                    continue
            
            # Run analysis
            result = self.analyze_prop(
                player=player,
                stat_type=stat,
                line=line,
                direction=direction,
                opponent=opponent,
                surface=surface
            )
            
            if result.get('error'):
                continue
            
            results.append(result)
        
        # Deduplicate results - aggressive: same player + stat + line (keep highest prob direction)
        seen = {}  # key -> result with highest probability
        for r in results:
            key = (r.get('player', '').lower().strip(), 
                   r.get('stat', '').lower().strip(), 
                   float(r.get('line', 0)))
            prob = r.get('probability', r.get('confidence', 0)) or 0
            
            if key not in seen or prob > (seen[key].get('probability', seen[key].get('confidence', 0)) or 0):
                seen[key] = r
        
        results = list(seen.values())
        
        # Sort by confidence
        results.sort(key=lambda x: x.get('confidence', 0), reverse=True)
        
        # Group by tier
        tiers = {
            'SLAM': [r for r in results if r.get('tier') == 'SLAM'],
            'STRONG': [r for r in results if r.get('tier') == 'STRONG'],
            'LEAN': [r for r in results if r.get('tier') == 'LEAN'],
            'NO_PLAY': [r for r in results if r.get('tier') == 'NO_PLAY'],
        }
        
        # Summary
        print(f"\n[SUMMARY]")
        print(f"  Players with data: {len(players_analyzed)}")
        if players_not_found:
            print(f"  Players NOT FOUND: {', '.join(players_not_found)}")
        print(f"\n  Props analyzed: {len(results)}")
        print(f"    SLAM:   {len(tiers['SLAM'])}")
        print(f"    STRONG: {len(tiers['STRONG'])}")
        print(f"    LEAN:   {len(tiers['LEAN'])}")
        print(f"    NO_PLAY: {len(tiers['NO_PLAY'])}")
        
        return {
            'results': results,
            'tiers': tiers,
            'players_analyzed': list(players_analyzed),
            'players_not_found': list(players_not_found),
            'surface': surface,
            'timestamp': datetime.now().isoformat()
        }
    
    def _get_correlation_group(self, stat_type: str) -> Optional[str]:
        """Get correlation group for a stat type"""
        stat_lower = stat_type.lower().replace(' ', '_')
        
        for group, stats in CORRELATION_GROUPS.items():
            if stat_lower in stats or any(s in stat_lower for s in stats):
                return group
        
        return None
    
    def parse_underdog_paste(self, paste: str) -> List[Dict]:
        """
        Parse Underdog paste format into prop dicts.
        
        ROBUST: Handles BOTH Underdog paste formats:
        - Format A: Player name FIRST, then props
        - Format B: Props FIRST, player name at END (after "Fewer picks")
        
        Also handles:
        - "- Player" lines, "Trending" lines
        - "More" after "Less" (UI artifact)
        - Blank lines, duplicate player names
        - Time patterns like "50m 26s"
        """
        import re
        
        # Pre-clean: Remove junk lines
        raw_lines = paste.strip().split('\n')
        lines = []
        last_was_less = False
        for l in raw_lines:
            l = l.strip()
            if not l:
                continue
            l_lower = l.lower()
            # Skip junk lines
            if '- player' in l_lower:
                continue
            if l_lower.startswith('trending'):
                continue
            if re.match(r'^\d+\.?\d*k$', l_lower):  # e.g., "17.3K"
                continue
            # Skip "More" ONLY if it comes immediately after "Less" (Underdog UI artifact)
            if l_lower == 'more' and last_was_less:
                last_was_less = False
                continue
            # Track if current line is "Less" for next iteration
            last_was_less = (l_lower == 'less')
            # Skip time-remaining patterns like "50m 26s", "10m 26s"
            if re.match(r'^\d+m\s*\d*s?$', l_lower):
                continue
            # Skip "Fewer picks" / "More picks" navigation text
            if l_lower in ('fewer picks', 'more picks', 'athlete or team avatar'):
                continue
            if 'demon' in l_lower or 'goblin' in l_lower or 'taco' in l_lower:
                # Strip suffix from player name (e.g., "Alycia ParksDemon" -> "Alycia Parks")
                l = re.sub(r'(Demon|Goblin|Taco)$', '', l, flags=re.IGNORECASE).strip()
            lines.append(l)
        
        props = []
        
        # Stat type mapping
        stat_map = {
            'games played': 'games_played',
            'total games': 'games_played',
            'games won': 'games_won',
            '1st set games played': '1st_set_games',
            '1st set games won': '1st_set_games_won',
            'sets played': 'sets_played',
            'sets won': 'sets_won',
            'total sets': 'sets_played',
            'aces': 'aces',
            'double faults': 'double_faults',
            'breakpoints won': 'breakpoints_won',
            'break points won': 'breakpoints_won',
            'tiebreakers played': 'tiebreakers',
            'fantasy score': 'fantasy_score',
        }
        
        # TWO-PASS PARSING to handle player name at START or END
        # Pass 1: Identify player blocks (sections between player names or match info)
        # Pass 2: Extract props from each block
        
        # First, find all player names and match info positions
        player_positions = []  # [(index, player_name, opponent)]
        
        for i, line in enumerate(lines):
            if self._is_player_name(line):
                # Check if next line is match info
                opponent = None
                if i + 1 < len(lines):
                    next_line = lines[i + 1]
                    if ' vs ' in next_line.lower() or ' @ ' in next_line.lower():
                        opponent = self._extract_opponent(line, next_line)
                player_positions.append((i, line, opponent))
        
        # If no players found, return empty
        if not player_positions:
            return []
        
        # Parse props - collect pending props and assign to players
        current_player = None
        current_opponent = None
        pending_props = []  # Props waiting for player assignment
        
        i = 0
        while i < len(lines):
            line = lines[i]
            line_lower = line.lower()
            
            # Check if this is a player name
            if self._is_player_name(line):
                # If we have pending props without a player, assign them to this player
                if pending_props and current_player is None:
                    for pp in pending_props:
                        pp['player'] = line
                        # Try to get opponent from next line
                        if i + 1 < len(lines):
                            next_line = lines[i + 1]
                            if ' vs ' in next_line.lower() or ' @ ' in next_line.lower():
                                pp['opponent'] = self._extract_opponent(line, next_line)
                        props.append(pp)
                    pending_props = []
                
                # Set current player for subsequent props
                current_player = line
                
                # Get opponent from next line if match info
                if i + 1 < len(lines):
                    next_line = lines[i + 1]
                    if ' vs ' in next_line.lower() or ' @ ' in next_line.lower():
                        current_opponent = self._extract_opponent(line, next_line)
                        i += 1  # Skip match info line
                
                i += 1
                continue
            
            # Check if it's a line value (number)
            current_line = None
            current_stat = None
            current_higher_mult = None
            current_lower_mult = None
            
            if self._is_line_value(line):
                current_line = float(line.replace(',', ''))
                
                # Look ahead for stat type
                # CRITICAL: Sort by key length (longest first) to match "1st set games won"
                # before the shorter "games won" substring
                sorted_stats = sorted(stat_map.items(), key=lambda x: len(x[0]), reverse=True)
                for j in range(i + 1, min(i + 3, len(lines))):
                    for stat_key, stat_val in sorted_stats:
                        if stat_key in lines[j].lower():
                            current_stat = stat_val
                            break
                    if current_stat:
                        break
                
                if current_stat and current_line:
                    # Look ahead for BOTH directions + multipliers.
                    # Underdog paste commonly appears as:
                    #   Higher
                    #   1.03x
                    #   Lower
                    #   0.88x
                    # Some lines omit multipliers (no x line).
                    directions_found = set()
                    mode = None  # 'HIGHER' | 'LOWER' | None
                    for j in range(i + 1, min(i + 14, len(lines))):
                        scan_raw = lines[j].strip()
                        scan = scan_raw.lower()

                        # Stop scanning when the next prop starts
                        if self._is_line_value(scan_raw):
                            break
                        # Or a new player name begins
                        if self._is_player_name(scan_raw):
                            break

                        if scan in ('more', 'higher') or scan.startswith('more') or scan.startswith('higher'):
                            mode = 'HIGHER'
                            directions_found.add('HIGHER')
                            continue
                        if scan in ('less', 'lower') or scan.startswith('less') or scan.startswith('lower'):
                            mode = 'LOWER'
                            directions_found.add('LOWER')
                            continue

                        # Multiplier line like "1.03x" or "0.88x"
                        if 'x' in scan_raw:
                            m = re.search(r'(\d+\.?\d*)\s*x', scan_raw, flags=re.IGNORECASE)
                            if m:
                                try:
                                    val = float(m.group(1))
                                except ValueError:
                                    val = None
                                if val is not None:
                                    if mode == 'HIGHER':
                                        current_higher_mult = val
                                    elif mode == 'LOWER':
                                        current_lower_mult = val

                    # Emit one prop per direction observed. If none are found, skip.
                    for direction in ('HIGHER', 'LOWER'):
                        if direction not in directions_found:
                            continue
                        mult = 1.0
                        if direction == 'HIGHER' and current_higher_mult is not None:
                            mult = float(current_higher_mult)
                        if direction == 'LOWER' and current_lower_mult is not None:
                            mult = float(current_lower_mult)

                        prop = {
                            'player': current_player,
                            'stat': current_stat,
                            'line': current_line,
                            'direction': direction,
                            'opponent': current_opponent,
                            'multiplier': mult,
                            # Keep raw multipliers for downstream value/edge logic if needed
                            'higher_mult': current_higher_mult,
                            'lower_mult': current_lower_mult,
                        }

                        if current_player:
                            props.append(prop)
                        else:
                            pending_props.append(prop)
            
            i += 1
        
        # Handle any remaining pending props (player at end of paste)
        if pending_props:
            # Find the last player in the lines
            for line in reversed(lines):
                if self._is_player_name(line):
                    for pp in pending_props:
                        pp['player'] = line
                    props.extend(pending_props)
                    break
        
        # Deduplicate: same player + stat + line + direction
        seen = set()
        unique_props = []
        for p in props:
            if p.get('player'):
                key = (p['player'].lower(), p['stat'], p['line'], p['direction'])
                if key not in seen:
                    seen.add(key)
                    unique_props.append(p)
        
        return unique_props
    
    def _is_player_name(self, line: str) -> bool:
        """Detect if line is a player name - ROBUST VERSION"""
        import re
        
        line = line.strip()
        line_lower = line.lower()
        
        # Exclude empty
        if not line:
            return False
        
        # Exclude stat types and other keywords
        stat_keywords = [
            'games', 'sets', 'aces', 'faults', 'points', 'higher', 'lower', 
            'fantasy', 'tiebreakers', 'breakpoints', 'played', 'won',
            'avatar', 'athlete', 'fewer', 'more', 'picks', 'less',
            'total', 'break', 'score'
        ]
        if any(kw in line_lower for kw in stat_keywords):
            return False
        
        # Exclude lines containing "vs" or "@" (match info lines)
        if ' vs ' in line_lower or ' @ ' in line_lower:
            return False
        
        # Exclude multipliers (e.g., "1.03x")
        if re.match(r'^\d+\.?\d*x?$', line.strip()):
            return False
        
        # Exclude numbers (betting lines)
        try:
            float(line.replace(',', ''))
            return False
        except ValueError:
            pass
        
        # Exclude time patterns (e.g., "2:30AM", "50m 26s", "Mon 3:00am")
        if re.search(r'\d+:\d+', line):
            return False
        if re.search(r'\d+m\s*\d*s?', line_lower):
            return False
        
        # Exclude day patterns (Mon, Tue, etc.)
        if re.search(r'^(mon|tue|wed|thu|fri|sat|sun)\s', line_lower):
            return False
        
        # Player names are typically 2-4 words
        words = line.split()
        if len(words) < 2 or len(words) > 5:
            return False
        
        # Check if it looks like a name (has capital letters, mostly alpha)
        alpha_chars = sum(1 for c in line if c.isalpha())
        if alpha_chars < 5:
            return False
        
        # Most words should start with uppercase
        caps_count = sum(1 for w in words if w and w[0].isupper())
        if caps_count >= len(words) - 1:  # Allow one lowercase word (e.g., "de", "van")
            return True
        
        return False
    
    def _is_line_value(self, line: str) -> bool:
        """Detect if line is a betting line"""
        try:
            val = float(line.replace(',', ''))
            return 0 < val < 100
        except ValueError:
            return False
    
    def _extract_opponent(self, player: str, match_info: str) -> Optional[str]:
        """Extract opponent name from match info"""
        import re

        player = (player or "").strip()
        player_lower = player.lower()
        player_last = player.split()[-1].lower() if player.split() else ""
        
        match_info_clean = re.sub(r'\s*-\s*\d+:\d+.*', '', match_info)  # Remove time
        
        if ' vs ' in match_info_clean.lower():
            parts = re.split(r'\s+vs\s+', match_info_clean, flags=re.IGNORECASE)
            parts = [p.strip() for p in parts if p.strip()]
            if len(parts) == 2:
                a, b = parts
                a_lower, b_lower = a.lower(), b.lower()

                # Prefer full-name match
                if player_lower and player_lower in a_lower:
                    return b
                if player_lower and player_lower in b_lower:
                    return a

                # Fallback: last-name match (common in Underdog: "Dellien vs Olivieri")
                if player_last and player_last in a_lower:
                    return b
                if player_last and player_last in b_lower:
                    return a

                # If no match at all, return the second side by convention
                return b
        
        return None
    
    def generate_cheatsheet(self, results: Dict) -> str:
        """Generate formatted cheatsheet from results - PRINTABLE FORMAT"""
        output = []
        
        output.append("")
        output.append("=" * 75)
        output.append("  TENNIS PROPS CHEATSHEET")
        output.append(f"  Surface: {results.get('surface', 'Hard').upper()}")
        output.append(f"  Generated: {datetime.now().strftime('%A, %B %d, %Y at %I:%M %p')}")
        output.append("=" * 75)
        
        tiers = results.get('tiers', {})
        total_plays = len(tiers.get('SLAM', [])) + len(tiers.get('STRONG', [])) + len(tiers.get('LEAN', []))
        
        # Summary box
        output.append("")
        output.append("  SUMMARY")
        output.append("  " + "-" * 35)
        output.append(f"  Total Playable:    {total_plays}")
        output.append(f"  SLAM (70%+):       {len(tiers.get('SLAM', []))}")
        output.append(f"  STRONG (62-70%):   {len(tiers.get('STRONG', []))}")
        output.append(f"  LEAN (55-62%):     {len(tiers.get('LEAN', []))}")
        output.append("")
        
        for tier in ['SLAM', 'STRONG', 'LEAN']:
            tier_results = results.get('tiers', {}).get(tier, [])
            if not tier_results:
                continue
            
            tier_emoji = {'SLAM': '***', 'STRONG': '**', 'LEAN': '*'}
            output.append(f"  [{tier}] {tier_emoji.get(tier, '')} ({len(tier_results)} picks)")
            output.append("  " + "-" * 75)
            output.append(f"  {'PLAYER':<24} {'PICK':<22} {'LINE':<7} {'PROB':<7} {'n'}")
            output.append("  " + "-" * 75)
            
            for r in tier_results:
                corr_flag = " [CORR]" if r.get('correlation_group') else ""
                profile_info = r.get('profile_data', {})
                n_matches = profile_info.get('n_matches', '?')
                
                direction = r.get('direction', '').upper()
                stat = r.get('stat', '')
                pick_text = f"{direction} {stat}"[:21]  # Wider to fit games_played, sets_played
                # probability is stored as decimal (0.70), convert to percent for display
                prob = r.get('probability', r.get('confidence', 0))
                prob_pct = prob * 100 if prob and prob < 1.5 else prob  # Convert decimal to %
                
                output.append(
                    f"  {r['player']:<24} {pick_text:<22} {r['line']:<7} {prob_pct:.0f}%     {n_matches}{corr_flag}"
                )
            output.append("")
        
        # No plays section
        no_plays = results.get('tiers', {}).get('NO_PLAY', [])
        if no_plays:
            output.append(f"  [AVOID] ({len(no_plays)} props below 55%)")
            output.append("  " + "-" * 40)
            for r in no_plays[:5]:  # Show first 5
                prob = r.get('probability', r.get('confidence', 0))
                prob_pct = prob * 100 if prob and prob < 1.5 else prob  # Convert decimal to %
                output.append(f"    {r['player']}: {r.get('stat', '')} ({prob_pct:.0f}%)")
            if len(no_plays) > 5:
                output.append(f"    ... and {len(no_plays) - 5} more")
            output.append("")
        
        # Players not found
        if results.get('players_not_found'):
            output.append("  [NO DATA]")
            output.append("  " + "-" * 40)
            for p in results['players_not_found']:
                output.append(f"    {p}")
            output.append("")
        
        # Rules footer
        output.append("=" * 75)
        output.append("  RULES (SOP v2.1)")
        output.append("  - One player, one bet per match")
        output.append("  - [CORR] = Correlated stats - don't combine in parlays")
        output.append("  - Probabilities from 2,000 Monte Carlo simulations")
        output.append("=" * 75)
        
        return '\n'.join(output)


# ============================================================================
# CLI / INTERACTIVE
# ============================================================================

def interactive_analysis():
    """Interactive mode for paste analysis"""
    
    print("\n" + "=" * 70)
    print("🎾 CALIBRATED TENNIS PROPS ENGINE")
    print("   Using real Tennis Abstract 2024 data")
    print("=" * 70)
    print("\nPaste Underdog tennis props below.")
    print("Type 'END' on a new line when done.\n")
    
    lines = []
    
    while True:
        try:
            line = input()
            if line.strip().upper() == 'END':
                break
            lines.append(line)
        except (EOFError, KeyboardInterrupt):
            break
    
    if not lines:
        print("\n[!] No input received")
        return
    
    paste = '\n'.join(lines)
    
    # Run analysis
    engine = CalibratedTennisPropsEngine()
    
    try:
        # Parse props
        props = engine.parse_underdog_paste(paste)
        print(f"\n✓ Parsed {len(props)} props")
        
        if not props:
            print("✗ No valid props found")
            return
        
        # Analyze
        results = engine.analyze_slate(props, surface="Hard")
        
        # Generate cheatsheet
        cheatsheet = engine.generate_cheatsheet(results)
        print(cheatsheet)
        
        # Save to file
        output_dir = TENNIS_DIR / "outputs"
        output_dir.mkdir(exist_ok=True)
        
        filename = f"TENNIS_CALIBRATED_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        with open(output_dir / filename, 'w') as f:
            f.write(cheatsheet)
        
        print(f"\n✓ Saved to: {output_dir / filename}")
        
        # CROSS-SPORT DATABASE: Save top picks
        try:
            import sys
            sys.path.insert(0, str(TENNIS_DIR.parent))
            from engine.daily_picks_db import save_top_picks
            
            tennis_edges = []
            for r in results:
                if r.get("tier") in ("SLAM", "STRONG", "LEAN"):
                    tennis_edges.append({
                        "player": r.get("player", ""),
                        "stat": r.get("stat", ""),
                        "line": r.get("line", 0),
                        "direction": r.get("direction", ""),
                        "probability": r.get("probability", 0.5) * 100 if r.get("probability", 0.5) <= 1 else r.get("probability", 50),
                        "tier": r.get("tier", "LEAN")
                    })
            
            if tennis_edges:
                saved = save_top_picks(tennis_edges, "TENNIS", top_n=5)
                print(f"✓ Cross-Sport DB: Saved {saved} Tennis picks")
        except ImportError as e:
            print(f"⚠️ Cross-Sport DB not available: {e}")
        except Exception as e:
            print(f"⚠️ Cross-Sport DB save failed: {e}")
        
    finally:
        engine.close()


def main():
    """Demo the calibrated pipeline"""
    
    print("\n" + "=" * 70)
    print("🎾 CALIBRATED TENNIS ENGINE DEMO")
    print("=" * 70)
    
    # Demo with AO Finals matchups
    engine = CalibratedTennisPropsEngine()
    
    # First, show what real averages look like
    print("\n[PLAYER PROFILES FROM 2024 DATA]")
    for name in ['Carlos Alcaraz', 'Novak Djokovic', 'Aryna Sabalenka', 'Elena Rybakina']:
        profile = engine.profiler.get_profile(name, 'Hard')
        if profile:
            print(f"  {profile.player_name}:")
            print(f"    Aces: {profile.avg_aces:.1f} ± {profile.std_aces:.1f} (n={profile.n_matches})")
            print(f"    Games Won: {profile.avg_games_won:.1f} ± {profile.std_games_won:.1f}")
    
    # Sample props - realistic lines based on player averages
    # Alcaraz: 5.1 avg aces → Line 4.5 = HIGHER should be ~55%
    # Djokovic: 7.6 avg aces → Line 6.5 = HIGHER should be ~60%
    demo_props = [
        # Alcaraz - avg aces 5.1, line below avg = good HIGHER
        {'player': 'Carlos Alcaraz', 'stat': 'aces', 'line': 4.5, 'direction': 'HIGHER', 'opponent': 'Novak Djokovic'},
        {'player': 'Carlos Alcaraz', 'stat': 'aces', 'line': 6.5, 'direction': 'LOWER', 'opponent': 'Novak Djokovic'},
        
        # Djokovic - avg aces 7.6, test both directions
        {'player': 'Novak Djokovic', 'stat': 'aces', 'line': 6.5, 'direction': 'HIGHER', 'opponent': 'Carlos Alcaraz'},
        {'player': 'Novak Djokovic', 'stat': 'aces', 'line': 9.5, 'direction': 'LOWER', 'opponent': 'Carlos Alcaraz'},
        
        # Sabalenka - avg aces 4.0
        {'player': 'Aryna Sabalenka', 'stat': 'aces', 'line': 3.5, 'direction': 'HIGHER', 'opponent': 'Elena Rybakina'},
        {'player': 'Aryna Sabalenka', 'stat': 'aces', 'line': 5.5, 'direction': 'LOWER', 'opponent': 'Elena Rybakina'},
        
        # Rybakina - avg aces 6.9
        {'player': 'Elena Rybakina', 'stat': 'aces', 'line': 5.5, 'direction': 'HIGHER', 'opponent': 'Aryna Sabalenka'},
        {'player': 'Elena Rybakina', 'stat': 'aces', 'line': 8.5, 'direction': 'LOWER', 'opponent': 'Aryna Sabalenka'},
        
        # Games won - higher variance, test a few
        {'player': 'Carlos Alcaraz', 'stat': 'games_won', 'line': 11.5, 'direction': 'HIGHER', 'opponent': 'Novak Djokovic'},
        {'player': 'Aryna Sabalenka', 'stat': 'games_won', 'line': 8.5, 'direction': 'HIGHER', 'opponent': 'Elena Rybakina'},
    ]
    
    results = engine.analyze_slate(demo_props, surface="Hard")
    cheatsheet = engine.generate_cheatsheet(results)
    print(cheatsheet)
    
    engine.close()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == '--interactive':
        interactive_analysis()
    else:
        main()
