"""
FUOOM API Wrapper Layer
======================
Centralized API wrappers with circuit breakers, metrics, and tracing.

This module provides drop-in replacements for common API calls:
- ESPN API (schedule, box scores)
- NBA API (stats.nba.com)
- Telegram API
- SerpAPI (Google search)

Usage:
    # Instead of direct calls, import from here:
    from observability.api_wrappers import (
        fetch_espn_nba_schedule,
        fetch_nba_player_gamelog,
        send_telegram_message,
    )
"""

import json
import time
import urllib.request
import ssl
from typing import Dict, Any, List, Optional
from functools import wraps
from datetime import datetime

# Import observability components
from observability.metrics import get_metrics
from observability.circuit_breaker import get_circuit_breaker, CircuitOpenError
from observability.tracer import get_tracer

# Initialize singletons
_metrics = get_metrics()
_cb = get_circuit_breaker()
_tracer = get_tracer()

# Configure additional circuit breakers
_cb.configure("nba_api", fail_threshold=3, reset_timeout=120)
_cb.configure("datagolf_api", fail_threshold=2, reset_timeout=300)
_cb.configure("api_sports_tennis", fail_threshold=3, reset_timeout=180)
_cb.configure("api_football", fail_threshold=3, reset_timeout=180)
_cb.configure("deepseek_api", fail_threshold=2, reset_timeout=60)
_cb.configure("balldontlie_api", fail_threshold=3, reset_timeout=120)
_cb.configure("ollama_api", fail_threshold=5, reset_timeout=30)

# SSL context for urllib
_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE


def _api_wrapper(api_name: str, fallback_value: Any = None):
    """
    Decorator factory for API call protection.
    
    Provides:
    - Circuit breaker protection
    - Metrics recording
    - Tracing
    - Fallback values on failure
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Check circuit breaker
            if not _cb.can_execute(api_name):
                _metrics.record_api_call(api_name, success=False, latency=0)
                if fallback_value is not None:
                    return fallback_value
                raise CircuitOpenError(f"Circuit '{api_name}' is open")
            
            start_time = time.time()
            
            with _tracer.span(f"api_{api_name}", api=api_name) as span:
                try:
                    result = func(*args, **kwargs)
                    
                    latency = time.time() - start_time
                    _metrics.record_api_call(api_name, success=True, latency=latency)
                    _cb.record_success(api_name)
                    
                    span.set_attribute("latency_ms", latency * 1000)
                    span.set_attribute("success", True)
                    
                    return result
                    
                except Exception as e:
                    latency = time.time() - start_time
                    _metrics.record_api_call(api_name, success=False, latency=latency)
                    _cb.record_failure(api_name, e)
                    
                    span.set_attribute("latency_ms", latency * 1000)
                    span.set_error(e)
                    
                    if fallback_value is not None:
                        return fallback_value
                    raise
        
        return wrapper
    return decorator


# =============================================================================
# ESPN API WRAPPERS
# =============================================================================

@_api_wrapper("espn_api", fallback_value=[])
def fetch_espn_nba_schedule(date_str: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Fetch NBA schedule from ESPN.
    
    Args:
        date_str: Date in YYYYMMDD format (default: today)
    
    Returns:
        List of game dicts: [{"home": "LAL", "away": "BOS", "game_id": "..."}, ...]
    """
    if date_str is None:
        date_str = datetime.now().strftime("%Y%m%d")
    
    url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={date_str}"
    
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, context=_SSL_CTX, timeout=10) as resp:
        data = json.loads(resp.read())
    
    games = []
    for event in data.get("events", []):
        comp = event.get("competitions", [{}])[0]
        competitors = comp.get("competitors", [])
        
        home, away = "", ""
        for team in competitors:
            abbr = team.get("team", {}).get("abbreviation", "")
            if team.get("homeAway") == "home":
                home = abbr
            else:
                away = abbr
        
        if home and away:
            games.append({
                "home": home,
                "away": away,
                "game_id": event.get("id", ""),
                "status": comp.get("status", {}).get("type", {}).get("name", ""),
            })
    
    return games


@_api_wrapper("espn_api", fallback_value={})
def fetch_espn_nfl_schedule(date_str: Optional[str] = None) -> List[Dict[str, Any]]:
    """Fetch NFL schedule from ESPN."""
    if date_str is None:
        date_str = datetime.now().strftime("%Y%m%d")
    
    url = f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates={date_str}"
    
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, context=_SSL_CTX, timeout=10) as resp:
        data = json.loads(resp.read())
    
    games = []
    for event in data.get("events", []):
        comp = event.get("competitions", [{}])[0]
        competitors = comp.get("competitors", [])
        
        home, away = "", ""
        for team in competitors:
            abbr = team.get("team", {}).get("abbreviation", "")
            if team.get("homeAway") == "home":
                home = abbr
            else:
                away = abbr
        
        if home and away:
            games.append({
                "home": home,
                "away": away,
                "game_id": event.get("id", ""),
            })
    
    return games


@_api_wrapper("espn_api", fallback_value={})
def fetch_espn_box_score(game_id: str, sport: str = "nba") -> Dict[str, Any]:
    """Fetch box score from ESPN."""
    if sport == "nba":
        url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event={game_id}"
    elif sport == "nfl":
        url = f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary?event={game_id}"
    else:
        return {}
    
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, context=_SSL_CTX, timeout=15) as resp:
        return json.loads(resp.read())


# =============================================================================
# NBA API WRAPPERS (stats.nba.com)
# =============================================================================

@_api_wrapper("nba_api", fallback_value=None)
def fetch_nba_player_gamelog(player_id: int, season: str = "2025-26", num_games: int = 10):
    """
    Fetch player game log from NBA API.
    
    Returns pandas DataFrame or None on failure.
    """
    try:
        from nba_api.stats.endpoints import playergamelog
        
        gamelog = playergamelog.PlayerGameLog(
            player_id=player_id,
            season=season,
            season_type_all_star="Regular Season"
        )
        time.sleep(0.6)  # Rate limiting
        
        df = gamelog.get_data_frames()[0]
        return df.head(num_games) if not df.empty else None
        
    except ImportError:
        return None


@_api_wrapper("nba_api", fallback_value={})
def fetch_nba_league_stats(season: str = "2025-26", last_n_games: int = 0):
    """
    Fetch league-wide player stats from NBA API.
    
    Returns dict mapping player names to stat dicts.
    """
    try:
        from nba_api.stats.endpoints import leaguedashplayerstats
        
        kwargs = {
            "season": season,
            "per_mode_detailed": "PerGame",
        }
        if last_n_games > 0:
            kwargs["last_n_games"] = last_n_games
        
        stats = leaguedashplayerstats.LeagueDashPlayerStats(**kwargs)
        time.sleep(0.6)  # Rate limiting
        
        df = stats.get_data_frames()[0]
        
        data = {}
        for _, row in df.iterrows():
            data[row["PLAYER_NAME"]] = {
                "team": row["TEAM_ABBREVIATION"],
                "points": float(row["PTS"]),
                "rebounds": float(row["REB"]),
                "assists": float(row["AST"]),
                "fg3m": float(row.get("FG3M", 0)),
                "minutes": float(row.get("MIN", 0)),
                "games": int(row.get("GP", 0)),
            }
        
        return data
        
    except ImportError:
        return {}


@_api_wrapper("nba_api", fallback_value=None)
def find_nba_player_id(player_name: str) -> Optional[int]:
    """Find NBA player ID by name."""
    try:
        from nba_api.stats.static import players
        
        all_players = players.get_players()
        
        # Exact match first
        for p in all_players:
            if p['full_name'].lower() == player_name.lower():
                return p['id']
        
        # Partial match
        for p in all_players:
            if player_name.lower() in p['full_name'].lower():
                return p['id']
        
        return None
        
    except ImportError:
        return None


# =============================================================================
# TELEGRAM API WRAPPERS
# =============================================================================

@_api_wrapper("telegram_api", fallback_value=False)
def send_telegram_message(bot_token: str, chat_id: str, message: str, parse_mode: str = "HTML") -> bool:
    """
    Send a message via Telegram Bot API.
    
    Returns True on success, False on failure.
    """
    import urllib.parse
    
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": message,
        "parse_mode": parse_mode,
    }).encode()
    
    req = urllib.request.Request(url, data=data, method="POST")
    with urllib.request.urlopen(req, timeout=10) as resp:
        result = json.loads(resp.read())
        return result.get("ok", False)


# =============================================================================
# SERPAPI WRAPPERS
# =============================================================================

@_api_wrapper("serpapi", fallback_value={})
def fetch_serpapi_search(query: str, api_key: str) -> Dict[str, Any]:
    """
    Perform a Google search via SerpAPI.
    """
    import urllib.parse
    
    params = urllib.parse.urlencode({
        "q": query,
        "api_key": api_key,
        "engine": "google",
    })
    
    url = f"https://serpapi.com/search?{params}"
    
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


# =============================================================================
# SPORT-SPECIFIC API WRAPPERS
# =============================================================================

@_api_wrapper("datagolf_api", fallback_value={})
def fetch_datagolf_stats(endpoint: str, api_key: str) -> Dict[str, Any]:
    """Fetch data from DataGolf API."""
    url = f"https://feeds.datagolf.com/{endpoint}?key={api_key}"
    
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


@_api_wrapper("api_sports_tennis", fallback_value={})
def fetch_tennis_api(endpoint: str, api_key: str) -> Dict[str, Any]:
    """Fetch data from API-Sports Tennis."""
    url = f"https://v1.tennis.api-sports.io/{endpoint}"
    
    req = urllib.request.Request(url, headers={
        "x-apisports-key": api_key,
        "User-Agent": "Mozilla/5.0"
    })
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


@_api_wrapper("api_football", fallback_value={})
def fetch_football_api(endpoint: str, api_key: str) -> Dict[str, Any]:
    """Fetch data from API-Football."""
    url = f"https://v3.football.api-sports.io/{endpoint}"
    
    req = urllib.request.Request(url, headers={
        "x-apisports-key": api_key,
        "User-Agent": "Mozilla/5.0"
    })
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


@_api_wrapper("balldontlie_api", fallback_value={})
def fetch_balldontlie(endpoint: str) -> Dict[str, Any]:
    """Fetch data from BallDontLie API."""
    url = f"https://www.balldontlie.io/api/v1/{endpoint}"
    
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


# =============================================================================
# OLLAMA / LLM WRAPPERS
# =============================================================================

@_api_wrapper("ollama_api", fallback_value=None)
def fetch_ollama_completion(prompt: str, model: str = "mistral", host: str = "http://localhost:11434") -> Optional[str]:
    """
    Get completion from local Ollama instance.
    """
    url = f"{host}/api/generate"
    
    data = json.dumps({
        "model": model,
        "prompt": prompt,
        "stream": False,
    }).encode()
    
    req = urllib.request.Request(url, data=data, method="POST", headers={
        "Content-Type": "application/json"
    })
    
    with urllib.request.urlopen(req, timeout=60) as resp:
        result = json.loads(resp.read())
        return result.get("response")


@_api_wrapper("deepseek_api", fallback_value=None)
def fetch_deepseek_completion(prompt: str, api_key: str) -> Optional[str]:
    """
    Get completion from DeepSeek API.
    """
    url = "https://api.deepseek.com/v1/chat/completions"
    
    data = json.dumps({
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
    }).encode()
    
    req = urllib.request.Request(url, data=data, method="POST", headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    })
    
    with urllib.request.urlopen(req, timeout=60) as resp:
        result = json.loads(resp.read())
        return result.get("choices", [{}])[0].get("message", {}).get("content")


# =============================================================================
# HELPER: Check API Health
# =============================================================================

def get_all_api_health() -> Dict[str, Dict[str, Any]]:
    """Get health status of all configured APIs."""
    return _cb.get_status()


def print_api_health():
    """Print formatted API health status."""
    _cb.print_status()


def reset_api_circuit(api_name: str):
    """Manually reset a circuit breaker."""
    _cb.reset(api_name)


__all__ = [
    # ESPN
    "fetch_espn_nba_schedule",
    "fetch_espn_nfl_schedule", 
    "fetch_espn_box_score",
    # NBA API
    "fetch_nba_player_gamelog",
    "fetch_nba_league_stats",
    "find_nba_player_id",
    # Telegram
    "send_telegram_message",
    # SerpAPI
    "fetch_serpapi_search",
    # Sport-specific
    "fetch_datagolf_stats",
    "fetch_tennis_api",
    "fetch_football_api",
    "fetch_balldontlie",
    # LLM
    "fetch_ollama_completion",
    "fetch_deepseek_completion",
    # Health
    "get_all_api_health",
    "print_api_health",
    "reset_api_circuit",
]
