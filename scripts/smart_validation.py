"""
SMART Ollama integration with intelligent fallback.
- Uses local SQLite cache to avoid repeated queries
- Falls back to rule-based validation when Ollama times out
- Prioritizes speed over perfection
"""
import subprocess
import json
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import hashlib
import time


class OllamaCache:
    """Local SQLite cache for Ollama responses."""
    
    def __init__(self, cache_dir: str = "cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.db_path = self.cache_dir / "ollama_responses.db"
        self._init_db()
    
    def _init_db(self):
        """Create cache table if not exists."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cache (
                    hash TEXT PRIMARY KEY,
                    prompt TEXT,
                    response TEXT,
                    timestamp INTEGER,
                    model TEXT
                )
            """)
            conn.commit()
    
    def get(self, prompt: str, model: str = "mistral") -> Optional[str]:
        """Get cached response if exists."""
        hash_key = hashlib.md5(f"{prompt}:{model}".encode()).hexdigest()
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT response FROM cache WHERE hash = ? AND model = ?",
                (hash_key, model)
            )
            result = cursor.fetchone()
            return result[0] if result else None
    
    def set(self, prompt: str, response: str, model: str = "mistral"):
        """Cache a response."""
        hash_key = hashlib.md5(f"{prompt}:{model}".encode()).hexdigest()
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO cache (hash, prompt, response, timestamp, model) "
                "VALUES (?, ?, ?, ?, ?)",
                (hash_key, prompt, response, int(time.time()), model)
            )
            conn.commit()


# Built-in player/team validation rules (no Ollama needed)
NBA_TEAMS = {
    'ATL', 'BOS', 'BRK', 'CHA', 'CHI', 'CLE', 'DAL', 'DEN', 'DET', 'GSW',
    'HOU', 'LAC', 'LAL', 'MEM', 'MIA', 'MIL', 'MIN', 'NOP', 'NYK', 'OKC',
    'ORL', 'PHI', 'PHX', 'POR', 'SAC', 'SAS', 'TOR', 'UTA', 'WAS'
}

VALID_STATS = {
    'points', 'pts', 'rebounds', 'reb', 'assists', 'ast',
    '3pm', '3pa', 'steals', 'stl', 'blocks', 'blk',
    'turnovers', 'to', 'pra', 'pts+reb+ast',
    'pr', 'pts+reb', 'pa', 'pts+ast', 'ra', 'reb+ast',
    'pass_yds', 'rush_yds', 'rec_yds', 'receptions'
}

INVALID_COMBOS = {
    # (player_first_name, stat) combinations that are impossible
    ('AJ', 'points'),  # Guard/forward specific issues
}


def rule_based_validation(player: str, team: str, stat: str) -> Tuple[bool, str]:
    """Fast rule-based validation without Ollama."""
    
    # Team validation
    if team and team.upper() not in NBA_TEAMS:
        return False, f"'{team}' is not an NBA team"
    
    # Stat validation
    stat_normalized = stat.lower().replace(' ', '')
    if stat_normalized not in {s.replace(' ', '') for s in VALID_STATS}:
        return False, f"'{stat}' is not a valid stat"
    
    # Obvious impossible combos (can add more)
    first_name = player.split()[0] if player else ''
    for invalid_first, invalid_stat in INVALID_COMBOS:
        if first_name.startswith(invalid_first) and stat.lower().startswith(invalid_stat):
            return False, f"{player} doesn't play {stat}"
    
    # Default: seems reasonable
    return True, "Reasonable pick"


def ollama_validate(player: str, stat: str, direction: str, timeout: int = 5) -> Optional[str]:
    """
    Ask Ollama for validation. Returns response or None if timeout.
    """
    prompt = f"NBA quick check: {player} {direction} {stat}. Reasonable? Yes or No."
    
    try:
        result = subprocess.run(
            ["ollama", "run", "mistral", prompt],
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding='utf-8',
            errors='ignore'
        )
        
        if result.returncode == 0:
            return result.stdout.strip()[:100]
        return None
    
    except subprocess.TimeoutExpired:
        return None
    except Exception:
        return None


def validate_pick(
    pick: Dict,
    cache: OllamaCache,
    use_ollama: bool = False,
    timeout: int = 5
) -> Dict:
    """
    Validate a pick using rule-based checks + optional Ollama.
    Returns: {valid: bool, reason: str, method: str, time: float}
    """
    start = time.time()
    player = pick.get('player', '')
    team = pick.get('team', '')
    stat = pick.get('stat', '')
    direction = 'OVER' if pick.get('mu', 0) > pick.get('line', 0) else 'UNDER'
    
    # Try cache first
    cache_key = f"{player}|{stat}|{team}"
    cached = cache.get(cache_key)
    if cached:
        return {
            'valid': True,
            'reason': f"Cached: {cached}",
            'method': 'cache',
            'time': time.time() - start
        }
    
    # Fast rule-based check
    is_valid, reason = rule_based_validation(player, team, stat)
    
    if not is_valid:
        return {
            'valid': False,
            'reason': reason,
            'method': 'rules',
            'time': time.time() - start
        }
    
    # If use_ollama enabled AND rules passed, ask Ollama
    if use_ollama:
        ollama_response = ollama_validate(player, stat, direction, timeout)
        
        if ollama_response:
            cache.set(cache_key, ollama_response)
            return {
                'valid': 'Yes' in ollama_response,
                'reason': ollama_response,
                'method': 'ollama',
                'time': time.time() - start
            }
        # Ollama timeout → use rules result
    
    return {
        'valid': True,
        'reason': 'Passed rule-based check',
        'method': 'rules_only',
        'time': time.time() - start
    }


def batch_validate_picks(picks: List[Dict], max_picks: int = 10, use_ollama: bool = False) -> List[Dict]:
    """Validate multiple picks."""
    
    cache = OllamaCache()
    results = []
    
    print(f"\n✅ SMART PICK VALIDATION ({max_picks} picks)")
    print("=" * 70)
    print(f"Method: {'Rule-based + Ollama' if use_ollama else 'Rule-based only'}")
    print("=" * 70 + "\n")
    
    start_total = time.time()
    
    for i, pick in enumerate(picks[:max_picks], 1):
        result = validate_pick(pick, cache, use_ollama=use_ollama, timeout=3)
        results.append({
            'player': pick.get('player'),
            'stat': pick.get('stat'),
            **result
        })
        
        status = "✅" if result['valid'] else "❌"
        method_icon = "🔍" if result['method'] == 'ollama' else "⚡" if result['method'] == 'rules' else "💾"
        
        print(
            f"{status} {method_icon} [{i:2}] {pick.get('player'):20} {pick.get('stat'):15} "
            f"| {result['reason'][:35]:35} | {result['time']:.2f}s"
        )
    
    elapsed = time.time() - start_total
    
    print("\n" + "=" * 70)
    print(f"✅ Validated {max_picks} picks in {elapsed:.1f}s ({elapsed/max_picks:.2f}s avg)")
    print(f"📊 Method breakdown: {sum(1 for r in results if r['method'] == 'rules')} rules, "
          f"{sum(1 for r in results if r['method'] == 'ollama')} ollama, "
          f"{sum(1 for r in results if r['method'] == 'cache')} cached")
    print("=" * 70)
    
    return results


def main():
    """Main entry point."""
    
    # Load picks
    if not Path("picks_hydrated.json").exists():
        print("❌ picks_hydrated.json not found")
        return
    
    with open("picks_hydrated.json") as f:
        picks = json.load(f)
    
    picks.sort(key=lambda p: p.get('confidence', 0), reverse=True)
    
    # Validate using smart method (rules-only for speed, no Ollama timeouts)
    results = batch_validate_picks(picks, max_picks=10, use_ollama=False)
    
    # Save results
    output = Path("outputs") / f"pick_validation_{int(time.time())}.json"
    with open(output, 'w') as f:
        json.dump({
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'method': 'rule-based validation',
            'picks_validated': len(results),
            'results': results
        }, f, indent=2)
    
    print(f"\n✅ Results saved to: {output.name}")


if __name__ == "__main__":
    main()
