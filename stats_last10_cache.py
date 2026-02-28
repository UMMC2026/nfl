"""stats_last10_cache.py

Daily cache for NBA API last-N game log derived (mu, sigma).

Design goals:
- Run once per day (first analysis run) to keep stats realistic.
- Only refresh for players actually in the slate (fast enough for daily use).
- Never hard-fail a report run: if NBA API is unavailable, fall back to existing stats.

This module intentionally avoids touching any static stats dictionaries on disk.
It provides an in-memory overlay to be applied by callers.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Dict, Iterable, Optional, Tuple

import unicodedata


# We keep this minimal: numpy is already in the project.
import numpy as np


# Stats supported directly by NBA API game logs
_SUPPORTED_BASE_STATS = {
    "points": "PTS",
    "rebounds": "REB",
    "assists": "AST",
    "3pm": "FG3M",
    "steals": "STL",
    "blocks": "BLK",
    "turnovers": "TOV",
    "fga": "FGA",
    "fgm": "FGM",
    "ftm": "FTM",
    "fta": "FTA",
    "minutes": "MIN",
}


@dataclass(frozen=True)
class RefreshResult:
    overlay: Dict[Tuple[str, str], Tuple[float, float]]
    team_map: Dict[str, str]
    # Optional per-player/per-stat recent values (most recent first). Used for empirical probabilities.
    series: Dict[Tuple[str, str], list[float]]
    # Optional per-player minutes coefficient of variation (std/mean) over the long window.
    minutes_cv: Dict[str, float]
    refreshed: bool
    source: str
    warnings: list[str]


def _cache_dir() -> Path:
    d = Path("outputs") / "stats_cache"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _cache_path(today: date, *, mode: str, last_n_games: int, short_n_games: Optional[int], blend_weight: Optional[float]) -> Path:
    """Cache file is per-day and includes the refresh mode to avoid mixing methodologies."""
    if mode == "blend" and short_n_games and blend_weight is not None:
        return _cache_dir() / (
            f"nba_mu_sigma_L{last_n_games}_L{short_n_games}_blend{blend_weight:.2f}_auto_{today.isoformat()}.json"
        )
    # For other modes, include mode in filename to avoid mixing methodologies.
    if mode and mode != "simple":
        return _cache_dir() / f"nba_mu_sigma_{mode}_L{last_n_games}_{today.isoformat()}.json"
    return _cache_dir() / f"nba_mu_sigma_L{last_n_games}_{today.isoformat()}.json"


def _load_overlay(path: Path) -> Dict[Tuple[str, str], Tuple[float, float]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    overlay: Dict[Tuple[str, str], Tuple[float, float]] = {}
    for item in raw.get("stats", []):
        player = item.get("player")
        stat = item.get("stat")
        mu = item.get("mu")
        sigma = item.get("sigma")
        if isinstance(player, str) and isinstance(stat, str) and isinstance(mu, (int, float)) and isinstance(sigma, (int, float)):
            overlay[(player, stat)] = (float(mu), float(sigma))
    return overlay


def _load_team_map(path: Path) -> Dict[str, str]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    team_map: Dict[str, str] = {}
    for item in raw.get("teams", []):
        player = item.get("player")
        team = item.get("team")
        if isinstance(player, str) and isinstance(team, str) and team.strip():
            team_map[player] = team.strip().upper()[:3]
    return team_map


def _save_overlay(
    path: Path,
    overlay: Dict[Tuple[str, str], Tuple[float, float]],
    *,
    meta: dict,
    team_map: Dict[str, str],
    series: Optional[Dict[Tuple[str, str], list[float]]] = None,
    minutes_cv: Optional[Dict[str, float]] = None,
) -> None:
    payload = {
        "date": meta.get("date"),
        "season": meta.get("season"),
        "last_n_games": meta.get("last_n_games"),
        "short_n_games": meta.get("short_n_games"),
        "mode": meta.get("mode"),
        "blend_weight": meta.get("blend_weight"),
        "auto_adjust_blend_weight": meta.get("auto_adjust_blend_weight"),
        "source": meta.get("source"),
        "teams": [
            {"player": p, "team": t}
            for p, t in sorted(team_map.items(), key=lambda x: x[0])
            if isinstance(p, str) and isinstance(t, str)
        ],
        "minutes": [
            {"player": p, "cv": float(cv)}
            for p, cv in sorted((minutes_cv or {}).items(), key=lambda x: x[0])
            if isinstance(p, str) and isinstance(cv, (int, float))
        ],
        "stats": [
            {"player": p, "stat": s, "mu": mu, "sigma": sigma}
            for (p, s), (mu, sigma) in sorted(overlay.items(), key=lambda x: (x[0][0], x[0][1]))
        ],
        "series": [
            {"player": p, "stat": s, "values": vals}
            for (p, s), vals in sorted((series or {}).items(), key=lambda x: (x[0][0], x[0][1]))
            if isinstance(p, str) and isinstance(s, str) and isinstance(vals, list)
        ],
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    
    # Auto-backup on daily refresh (best-effort, won't fail if backup module missing)
    try:
        from scripts.nba_data_backup import auto_backup_on_refresh
        auto_backup_on_refresh(reason="daily_refresh")
    except Exception:
        pass  # Backup is optional, don't fail the main operation


def _parse_minutes(v) -> Optional[float]:
    """Parse nba_api minutes formats into float minutes.

    Supports:
    - numeric minutes (int/float)
    - "MM:SS" strings
    - numeric-like strings
    """
    try:
        if v is None:
            return None
        if isinstance(v, (int, float)):
            return float(v)
        s = str(v).strip()
        if not s:
            return None
        if ":" in s:
            parts = s.split(":", 1)
            mm = float(parts[0])
            ss = float(parts[1]) if parts[1] else 0.0
            return float(mm + ss / 60.0)
        return float(s)
    except Exception:
        return None


def _strip_diacritics(name: str) -> str:
    """Return a best-effort ASCII-ish version of a player name.

    This helps nba_api name matching when the paste contains diacritics
    (e.g., 'Dončić', 'Nurkić').
    """
    try:
        s = str(name or "")
        s = unicodedata.normalize("NFKD", s)
        s = "".join(ch for ch in s if not unicodedata.combining(ch))
        return s
    except Exception:
        return str(name or "")


def _weighted_mean_std(values: np.ndarray, *, half_life_games: float) -> tuple[float, float]:
    """Exponentially weighted mean/std with most-recent-first ordering.

    half_life_games: number of games after which weight halves.
    """
    if values.size <= 0:
        return 0.0, 1.0
    if values.size == 1:
        return float(values[0]), 1.0

    hl = float(half_life_games)
    if not np.isfinite(hl) or hl <= 0.0:
        # Fallback to unweighted.
        mu = float(np.mean(values))
        return mu, _safe_std(values)

    # age=0 is most recent.
    ages = np.arange(values.size, dtype=float)
    # exp(-ln2 * age/half_life)
    weights = np.exp((-np.log(2.0) / hl) * ages)
    wsum = float(np.sum(weights))
    if wsum <= 0.0 or not np.isfinite(wsum):
        mu = float(np.mean(values))
        return mu, _safe_std(values)

    mu = float(np.sum(weights * values) / wsum)
    var = float(np.sum(weights * (values - mu) ** 2) / wsum)
    sigma = float(np.sqrt(max(var, 0.0)))
    return float(mu), float(max(sigma, 0.75))


def _blend(mu_long: float, sigma_long: float, mu_short: float, sigma_short: float, weight_short: float) -> tuple[float, float]:
    """Blend long/short windows to be both stable and responsive.

    weight_short: how much to trust the short window (0..1). Higher = more reactive.
    """
    w = float(max(0.0, min(1.0, weight_short)))
    mu = w * mu_short + (1.0 - w) * mu_long
    sigma = w * sigma_short + (1.0 - w) * sigma_long
    return float(mu), float(max(sigma, 0.75))


def _effective_short_weight(
    base_weight_short: float,
    *,
    long_games: int,
    short_games: int,
    last_n_games: int,
    short_n_games: int,
) -> float:
    """Auto-adjust the short-window weight based on available sample size.

    Rationale:
    - If a player only has ~5-7 games available, the L5 window becomes the *entire* sample.
      In that case we rely less on the short window to avoid overreacting to tiny samples.

    We scale the base weight by:
      scale_long = min(1, long_games / last_n_games)
      scale_short = min(1, short_games / short_n_games)
    """
    try:
        w0 = float(base_weight_short)
        if last_n_games <= 0 or short_n_games <= 0:
            return float(max(0.0, min(1.0, w0)))

        lg = int(max(0, long_games))
        sg = int(max(0, short_games))
        scale_long = min(1.0, lg / float(last_n_games))
        scale_short = min(1.0, sg / float(short_n_games))
        w = w0 * scale_long * scale_short
        return float(max(0.0, min(1.0, w)))
    except Exception:
        # Never fail refresh due to weight math.
        return float(max(0.0, min(1.0, float(base_weight_short))))


def _safe_std(values: np.ndarray) -> float:
    """Return a non-zero sigma to keep downstream math stable."""
    if values.size <= 1:
        return 1.0
    sigma = float(np.std(values, ddof=1))
    return max(sigma, 0.75)  # floor to avoid overconfident/zero-variance artifacts


def _infer_team_from_gamelog_df(df) -> Optional[str]:
    """Infer team abbreviation from the most recent game log row.

    nba_api PlayerGameLog data typically includes either TEAM_ABBREVIATION or MATCHUP.
    MATCHUP is formatted like "LAL vs. BOS" or "LAL @ BOS"; the first 3 chars are the team.
    """
    try:
        if df is None or df.empty:
            return None

        if "TEAM_ABBREVIATION" in df.columns:
            t = df.loc[df.index[0], "TEAM_ABBREVIATION"]
            s = str(t).strip().upper()
            return s[:3] if s else None

        if "MATCHUP" in df.columns:
            m = str(df.loc[df.index[0], "MATCHUP"]).strip().upper()
            if len(m) >= 3:
                return m[:3]
    except Exception:
        return None
    return None


# Fast timeout for NBA API calls (default 30s is too slow)
_NBA_API_TIMEOUT = 10  # seconds per request
_NBA_API_RETRIES = 2   # max retries on timeout


def _try_import_nba_api():
    try:
        from nba_api.stats.static import players as nba_players
        from nba_api.stats.endpoints import playergamelog
        return nba_players, playergamelog
    except Exception:
        return None, None


def _fetch_gamelog_with_timeout(playergamelog, player_id: int, season: str, timeout: int = _NBA_API_TIMEOUT):
    """Fetch player game log with reduced timeout and retry logic."""
    import time
    last_err = None
    for attempt in range(_NBA_API_RETRIES):
        try:
            gl = playergamelog.PlayerGameLog(
                player_id=player_id,
                season=season,
                timeout=timeout
            )
            return gl.get_data_frames()[0]
        except Exception as e:
            last_err = e
            if attempt < _NBA_API_RETRIES - 1:
                time.sleep(0.5)  # Brief pause before retry
    raise last_err if last_err else Exception("Unknown error")


def _resolve_player_id(player_name: str, nba_players) -> Optional[int]:
    # Try exact-ish matching via nba_api helpers
    matches = nba_players.find_players_by_full_name(player_name)
    if not matches:
        # Retry with diacritics removed (common for copy/paste).
        norm = _strip_diacritics(player_name)
        if norm and norm != player_name:
            matches = nba_players.find_players_by_full_name(norm)
    if not matches:
        # Fallback: try just last name token (better than nothing)
        tokens = [t for t in player_name.replace("-", " ").split(" ") if t]
        if tokens:
            matches = nba_players.find_players_by_full_name(tokens[-1])

    if not matches:
        return None

    # Prefer active players, else first match
    active = [m for m in matches if m.get("is_active")]
    pick = active[0] if active else matches[0]
    pid = pick.get("id")
    return int(pid) if pid is not None else None


def refresh_daily_last10_mu_sigma(
    players: Iterable[str],
    *,
    season: str = "2025-26",
    last_n_games: int = 10,
    short_n_games: Optional[int] = 5,
    mode: str = "blend",
    blend_weight: float = 0.65,
    half_life_games: float = 5.0,
    force: bool = False,
) -> RefreshResult:
    """Return an overlay {(player, stat): (mu, sigma)} refreshed once per day.

    This does NOT mutate any global stats dict. Callers should apply the overlay.

    If NBA API is unavailable, returns an empty overlay with a warning.
    """
    today = date.today()
    cache_path = _cache_path(
        today,
        mode=mode,
        last_n_games=last_n_games,
        short_n_games=short_n_games,
        blend_weight=blend_weight,
    )

    warnings: list[str] = []

    # De-dup / preserve order (used in both cache and refresh paths)
    seen = set()
    slate_players = [p for p in players if isinstance(p, str) and p and not (p in seen or seen.add(p))]

    if cache_path.exists() and not force:
        try:
            raw = json.loads(cache_path.read_text(encoding="utf-8"))

            # If we're in blend mode, older caches without the auto-adjust flag are considered stale.
            # This avoids silently reusing a pre-auto-adjust cache on the same day.
            if mode == "blend" and raw.get("auto_adjust_blend_weight") is not True:
                raise ValueError("stale cache: missing auto_adjust_blend_weight")

            overlay: Dict[Tuple[str, str], Tuple[float, float]] = {}
            for item in raw.get("stats", []):
                player = item.get("player")
                stat = item.get("stat")
                mu = item.get("mu")
                sigma = item.get("sigma")
                if isinstance(player, str) and isinstance(stat, str) and isinstance(mu, (int, float)) and isinstance(sigma, (int, float)):
                    overlay[(player, stat)] = (float(mu), float(sigma))

            team_map: Dict[str, str] = {}
            try:
                team_map = _load_team_map(cache_path)
            except Exception:
                team_map = {}

            series: Dict[Tuple[str, str], list[float]] = {}
            try:
                for item in raw.get("series", []) or []:
                    p = item.get("player")
                    s = item.get("stat")
                    vals = item.get("values")
                    if isinstance(p, str) and isinstance(s, str) and isinstance(vals, list):
                        series[(p, s)] = [float(x) for x in vals if isinstance(x, (int, float))]
            except Exception:
                series = {}

            minutes_cv: Dict[str, float] = {}
            try:
                for item in raw.get("minutes", []) or []:
                    p = item.get("player")
                    cv = item.get("cv")
                    if isinstance(p, str) and isinstance(cv, (int, float)):
                        minutes_cv[p] = float(cv)
            except Exception:
                minutes_cv = {}

            # If the cache exists but does NOT include all requested players, append the missing ones.
            cached_players = {p for (p, _s) in overlay.keys()}
            missing_players = [p for p in slate_players if p not in cached_players]
            if not missing_players:
                return RefreshResult(
                    overlay=overlay,
                    team_map=team_map,
                    series=series,
                    minutes_cv=minutes_cv,
                    refreshed=False,
                    source=str(cache_path),
                    warnings=[],
                )

            nba_players, playergamelog = _try_import_nba_api()
            if nba_players is None or playergamelog is None:
                warnings.append(
                    f"nba_api not available; cache missing {len(missing_players)} player(s): "
                    + ", ".join(missing_players[:5])
                    + ("..." if len(missing_players) > 5 else "")
                )
                return RefreshResult(
                    overlay=overlay,
                    team_map=team_map,
                    series=series,
                    minutes_cv=minutes_cv,
                    refreshed=False,
                    source=str(cache_path),
                    warnings=warnings,
                )

            # Fetch missing players and merge into the existing cache payload.
            for player_name in missing_players:
                pid = _resolve_player_id(player_name, nba_players)
                if pid is None:
                    warnings.append(f"NBA API: could not resolve player id for '{player_name}'")
                    continue

                try:
                    df = _fetch_gamelog_with_timeout(playergamelog, pid, season)

                    if df.empty:
                        warnings.append(f"NBA API: empty game log for '{player_name}'")
                        continue

                    inferred_team = _infer_team_from_gamelog_df(df.head(1))
                    if inferred_team:
                        team_map[player_name] = inferred_team

                    df_long = df.head(last_n_games)
                    df_short = df_long.head(short_n_games) if (mode == "blend" and short_n_games) else None
                    df_season = df

                    long_games = int(len(df_long))
                    short_games = int(len(df_short)) if df_short is not None else 0

                    # Minutes uncertainty proxy
                    try:
                        if "MIN" in df_long.columns:
                            mins = [m for m in (_parse_minutes(x) for x in df_long["MIN"].tolist()) if isinstance(m, (int, float))]
                            if len(mins) >= 2:
                                m_mu = float(np.mean(np.asarray(mins, dtype=float)))
                                m_sd = float(np.std(np.asarray(mins, dtype=float), ddof=1))
                                if m_mu > 1e-9:
                                    minutes_cv[player_name] = float(max(0.0, m_sd / m_mu))
                    except Exception:
                        pass

                    w_eff = blend_weight
                    if mode == "blend" and df_short is not None and short_n_games:
                        w_eff = _effective_short_weight(
                            blend_weight,
                            long_games=long_games,
                            short_games=short_games,
                            last_n_games=last_n_games,
                            short_n_games=short_n_games,
                        )

                    for stat_key, col in _SUPPORTED_BASE_STATS.items():
                        if col not in df_long.columns:
                            continue

                        vals_long = df_long[col].astype(float).to_numpy()
                        try:
                            vals_season = df_season[col].astype(float).to_numpy()
                        except Exception:
                            vals_season = vals_long

                        if mode == "blend" and df_short is not None and short_n_games:
                            vals_short = df_short[col].astype(float).to_numpy()
                            mu_long = float(np.mean(vals_long))
                            sigma_long = _safe_std(vals_long)
                            mu_short = float(np.mean(vals_short))
                            sigma_short = _safe_std(vals_short)
                            mu, sigma = _blend(mu_long, sigma_long, mu_short, sigma_short, w_eff)
                        else:
                            mu = float(np.mean(vals_long))
                            sigma = _safe_std(vals_long)

                        overlay[(player_name, stat_key)] = (float(mu), float(max(sigma, 0.75)))
                        series[(player_name, stat_key)] = [float(x) for x in vals_season.tolist()[:last_n_games]]

                except Exception as e:
                    warnings.append(f"NBA API: failed for '{player_name}': {e}")

            # Persist updated cache for the rest of the day.
            try:
                meta = {
                    "date": today.isoformat(),
                    "season": season,
                    "last_n_games": last_n_games,
                    "short_n_games": short_n_games,
                    "mode": mode,
                    "blend_weight": blend_weight,
                    "auto_adjust_blend_weight": True,
                    "source": "nba_api",
                }
                _save_overlay(cache_path, overlay, meta=meta, team_map=team_map, series=series, minutes_cv=minutes_cv)
            except Exception as e:
                warnings.append(f"Cache save failed after append: {e}")

            return RefreshResult(
                overlay=overlay,
                team_map=team_map,
                series=series,
                minutes_cv=minutes_cv,
                refreshed=True,
                source=str(cache_path),
                warnings=warnings,
            )
        except Exception as e:
            warnings.append(f"Cache read failed, will attempt refresh: {e}")

    nba_players, playergamelog = _try_import_nba_api()
    if nba_players is None or playergamelog is None:
        warnings.append("nba_api not available; using static stats only")
        return RefreshResult(overlay={}, team_map={}, series={}, minutes_cv={}, refreshed=False, source="static", warnings=warnings)

    overlay: Dict[Tuple[str, str], Tuple[float, float]] = {}
    team_map: Dict[str, str] = {}
    series: Dict[Tuple[str, str], list[float]] = {}
    minutes_cv: Dict[str, float] = {}

    for player_name in slate_players:
        pid = _resolve_player_id(player_name, nba_players)
        if pid is None:
            warnings.append(f"NBA API: could not resolve player id for '{player_name}'")
            continue

        try:
            df = _fetch_gamelog_with_timeout(playergamelog, pid, season)

            if df.empty:
                warnings.append(f"NBA API: empty game log for '{player_name}'")
                continue

            inferred_team = _infer_team_from_gamelog_df(df.head(1))
            if inferred_team:
                team_map[player_name] = inferred_team

            # Keep most recent games for L10/L5 blended analysis
            df_long = df.head(last_n_games)
            df_short = df_long.head(short_n_games) if (mode == "blend" and short_n_games) else None
            # Keep FULL SEASON for true season averages
            df_season = df

            long_games = int(len(df_long))
            short_games = int(len(df_short)) if df_short is not None else 0
            season_games = int(len(df_season))

            # Minutes uncertainty proxy: coefficient of variation over last_n_games
            try:
                if "MIN" in df_long.columns:
                    mins = [m for m in (_parse_minutes(x) for x in df_long["MIN"].tolist()) if isinstance(m, (int, float))]
                    if len(mins) >= 2:
                        m_mu = float(np.mean(np.asarray(mins, dtype=float)))
                        m_sd = float(np.std(np.asarray(mins, dtype=float), ddof=1))
                        if m_mu > 1e-9:
                            minutes_cv[player_name] = float(max(0.0, m_sd / m_mu))
            except Exception:
                pass

            # Per-player weight auto-adjust (e.g., if only 5-7 games exist, rely less on L5).
            w_eff = blend_weight
            if mode == "blend" and df_short is not None and short_n_games:
                w_eff = _effective_short_weight(
                    blend_weight,
                    long_games=long_games,
                    short_games=short_games,
                    last_n_games=last_n_games,
                    short_n_games=short_n_games,
                )
                if w_eff + 1e-9 < float(blend_weight):
                    warnings.append(
                        f"NBA API: '{player_name}' has only {long_games} games; "
                        f"short-window weight reduced {blend_weight:.2f}->{w_eff:.2f}"
                    )

            for stat_key, col in _SUPPORTED_BASE_STATS.items():
                if col not in df_long.columns:
                    continue

                vals_long = df_long[col].astype(float).to_numpy()
                
                # Store FULL SEASON series for true season averages (most recent first)
                try:
                    vals_season = df_season[col].astype(float).to_numpy()
                    series[(player_name, stat_key)] = [float(x) for x in vals_season.tolist()]
                except Exception:
                    series[(player_name, stat_key)] = [float(x) for x in vals_long.tolist()]

                if mode == "exp":
                    mu, sigma = _weighted_mean_std(vals_long, half_life_games=half_life_games)
                    overlay[(player_name, stat_key)] = (float(mu), float(sigma))
                    continue

                # Default: unweighted or blend
                mu_long = float(np.mean(vals_long))
                sigma_long = _safe_std(vals_long)

                if df_short is not None and col in df_short.columns:
                    vals_short = df_short[col].astype(float).to_numpy()
                    mu_short = float(np.mean(vals_short))
                    sigma_short = _safe_std(vals_short)
                    mu, sigma = _blend(mu_long, sigma_long, mu_short, sigma_short, w_eff)
                else:
                    mu, sigma = mu_long, sigma_long

                overlay[(player_name, stat_key)] = (float(mu), float(sigma))

        except Exception as e:
            warnings.append(f"NBA API: fetch failed for '{player_name}': {e}")
            continue

    # Save cache best-effort
    try:
        _save_overlay(
            cache_path,
            overlay,
            meta={
                "date": today.isoformat(),
                "season": season,
                "last_n_games": last_n_games,
                "short_n_games": short_n_games,
                "mode": mode,
                "blend_weight": blend_weight,
                "auto_adjust_blend_weight": True if mode == "blend" else False,
                "source": "nba_api.playergamelog",
            },
            team_map=team_map,
            series=series,
            minutes_cv=minutes_cv,
        )
        source = str(cache_path)
        refreshed = True
    except Exception as e:
        warnings.append(f"Cache write failed: {e}")
        source = "nba_api (uncached)"
        refreshed = True

    return RefreshResult(
        overlay=overlay,
        team_map=team_map,
        series=series,
        minutes_cv=minutes_cv,
        refreshed=refreshed,
        source=source,
        warnings=warnings,
    )


def _load_cache_full(path: Path) -> tuple[
    dict,
    Dict[Tuple[str, str], Tuple[float, float]],
    Dict[str, str],
    Dict[Tuple[str, str], list[float]],
    Dict[str, float],
]:
    """Load raw payload + parsed cache sections."""
    raw = json.loads(path.read_text(encoding="utf-8"))

    overlay: Dict[Tuple[str, str], Tuple[float, float]] = {}
    for item in raw.get("stats", []) or []:
        player = item.get("player")
        stat = item.get("stat")
        mu = item.get("mu")
        sigma = item.get("sigma")
        if isinstance(player, str) and isinstance(stat, str) and isinstance(mu, (int, float)) and isinstance(sigma, (int, float)):
            overlay[(player, stat)] = (float(mu), float(sigma))

    team_map: Dict[str, str] = {}
    try:
        team_map = _load_team_map(path)
    except Exception:
        team_map = {}

    series: Dict[Tuple[str, str], list[float]] = {}
    try:
        for item in raw.get("series", []) or []:
            p = item.get("player")
            s = item.get("stat")
            vals = item.get("values")
            if isinstance(p, str) and isinstance(s, str) and isinstance(vals, list):
                series[(p, s)] = [float(x) for x in vals if isinstance(x, (int, float))]
    except Exception:
        series = {}

    minutes_cv: Dict[str, float] = {}
    try:
        for item in raw.get("minutes", []) or []:
            p = item.get("player")
            cv = item.get("cv")
            if isinstance(p, str) and isinstance(cv, (int, float)):
                minutes_cv[p] = float(cv)
    except Exception:
        minutes_cv = {}

    return raw, overlay, team_map, series, minutes_cv


def _missing_players_for_required_stats(
    players: Iterable[str],
    *,
    overlay: Dict[Tuple[str, str], Tuple[float, float]],
    series: Dict[Tuple[str, str], list[float]],
    required_stats: Iterable[str],
) -> list[str]:
    req = [s for s in required_stats if isinstance(s, str) and s]
    missing: list[str] = []
    for p in players:
        if not isinstance(p, str) or not p.strip():
            continue
        player = p.strip()
        ok = True
        for stat in req:
            if (player, stat) not in overlay:
                ok = False
                break
            if (player, stat) not in series or not series.get((player, stat)):
                ok = False
                break
        if not ok:
            missing.append(player)
    return missing


def ensure_daily_last10_mu_sigma(
    players: Iterable[str],
    *,
    required_stats: Optional[Iterable[str]] = None,
    season: str = "2025-26",
    last_n_games: int = 10,
    short_n_games: Optional[int] = 5,
    mode: str = "blend",
    blend_weight: float = 0.65,
    half_life_games: float = 5.0,
    force_live_missing: bool = False,
) -> RefreshResult:
    """Ensure today's cache contains complete data for the requested players.

    Unlike refresh_daily_last10_mu_sigma(), this function is safe to call repeatedly:
    - If the daily cache exists and already has all required stats (overlay + series), it is returned unchanged.
    - If the cache is missing some players/stats, it fetches ONLY the missing subset from nba_api,
      merges them into the existing cache payload, and writes the merged result back.

    required_stats: stats that must exist for each player (defaults to supported base stats).
    force_live_missing: if True, will attempt to refresh missing players even when cache exists.
    """
    today = date.today()
    cache_path = _cache_path(
        today,
        mode=mode,
        last_n_games=last_n_games,
        short_n_games=short_n_games,
        blend_weight=blend_weight,
    )

    req_stats = set(required_stats or _SUPPORTED_BASE_STATS.keys())
    warnings: list[str] = []

    overlay: Dict[Tuple[str, str], Tuple[float, float]] = {}
    team_map: Dict[str, str] = {}
    series: Dict[Tuple[str, str], list[float]] = {}
    minutes_cv: Dict[str, float] = {}

    raw: dict = {}
    if cache_path.exists():
        try:
            raw, overlay, team_map, series, minutes_cv = _load_cache_full(cache_path)

            # If we're in blend mode, older caches without the auto-adjust flag are considered stale.
            if mode == "blend" and raw.get("auto_adjust_blend_weight") is not True:
                warnings.append("stale cache: missing auto_adjust_blend_weight; will rebuild")
                raw, overlay, team_map, series, minutes_cv = {}, {}, {}, {}, {}
        except Exception as e:
            warnings.append(f"Cache read failed; will attempt refresh: {e}")
            raw, overlay, team_map, series, minutes_cv = {}, {}, {}, {}, {}

    # De-dup / preserve order
    seen = set()
    slate_players = [p.strip() for p in players if isinstance(p, str) and p.strip() and not (p.strip() in seen or seen.add(p.strip()))]

    missing = _missing_players_for_required_stats(
        slate_players,
        overlay=overlay,
        series=series,
        required_stats=req_stats,
    )

    if cache_path.exists() and not missing and not force_live_missing:
        return RefreshResult(
            overlay=overlay,
            team_map=team_map,
            series=series,
            minutes_cv=minutes_cv,
            refreshed=False,
            source=str(cache_path),
            warnings=[],
        )

    if missing:
        warnings.append(f"cache missing {len(missing)}/{len(slate_players)} players; will attempt refresh")

    nba_players, playergamelog = _try_import_nba_api()
    if nba_players is None or playergamelog is None:
        warnings.append("nba_api not available; cannot hydrate missing stats")
        return RefreshResult(
            overlay=overlay,
            team_map=team_map,
            series=series,
            minutes_cv=minutes_cv,
            refreshed=False,
            source=str(cache_path) if cache_path.exists() else "static",
            warnings=warnings,
        )

    # Fetch only missing players (or all if cache didn't load)
    to_fetch = missing if missing else slate_players

    supported_stats = {k: v for k, v in _SUPPORTED_BASE_STATS.items() if k in req_stats}

    for player_name in to_fetch:
        pid = _resolve_player_id(player_name, nba_players)
        if pid is None:
            warnings.append(f"NBA API: could not resolve player id for '{player_name}'")
            continue

        try:
            gl = playergamelog.PlayerGameLog(player_id=pid, season=season)
            df = gl.get_data_frames()[0]
            if df.empty:
                warnings.append(f"NBA API: empty game log for '{player_name}'")
                continue

            inferred_team = _infer_team_from_gamelog_df(df.head(1))
            if inferred_team:
                team_map[player_name] = inferred_team

            df_long = df.head(last_n_games)
            df_short = df_long.head(short_n_games) if (mode == "blend" and short_n_games) else None
            df_season = df

            long_games = int(len(df_long))
            short_games = int(len(df_short)) if df_short is not None else 0

            # Minutes uncertainty proxy
            try:
                if "MIN" in df_long.columns:
                    mins = [m for m in (_parse_minutes(x) for x in df_long["MIN"].tolist()) if isinstance(m, (int, float))]
                    if len(mins) >= 2:
                        m_mu = float(np.mean(np.asarray(mins, dtype=float)))
                        m_sd = float(np.std(np.asarray(mins, dtype=float), ddof=1))
                        if m_mu > 1e-9:
                            minutes_cv[player_name] = float(max(0.0, m_sd / m_mu))
            except Exception:
                pass

            w_eff = blend_weight
            if mode == "blend" and df_short is not None and short_n_games:
                w_eff = _effective_short_weight(
                    blend_weight,
                    long_games=long_games,
                    short_games=short_games,
                    last_n_games=last_n_games,
                    short_n_games=short_n_games,
                )

            for stat_key, col in supported_stats.items():
                if col not in df_long.columns:
                    continue

                vals_long = df_long[col].astype(float).to_numpy()

                # Store full season series (most recent first)
                try:
                    vals_season = df_season[col].astype(float).to_numpy()
                    series[(player_name, stat_key)] = [float(x) for x in vals_season.tolist()]
                except Exception:
                    series[(player_name, stat_key)] = [float(x) for x in vals_long.tolist()]

                if mode == "exp":
                    mu, sigma = _weighted_mean_std(vals_long, half_life_games=half_life_games)
                    overlay[(player_name, stat_key)] = (float(mu), float(sigma))
                    continue

                mu_long = float(np.mean(vals_long))
                sigma_long = _safe_std(vals_long)

                if df_short is not None and col in df_short.columns:
                    vals_short = df_short[col].astype(float).to_numpy()
                    mu_short = float(np.mean(vals_short))
                    sigma_short = _safe_std(vals_short)
                    mu, sigma = _blend(mu_long, sigma_long, mu_short, sigma_short, w_eff)
                else:
                    mu, sigma = mu_long, sigma_long

                overlay[(player_name, stat_key)] = (float(mu), float(sigma))

        except Exception as e:
            warnings.append(f"NBA API: fetch failed for '{player_name}': {e}")
            continue

    # Save merged cache best-effort
    try:
        _save_overlay(
            cache_path,
            overlay,
            meta={
                "date": today.isoformat(),
                "season": season,
                "last_n_games": last_n_games,
                "short_n_games": short_n_games,
                "mode": mode,
                "blend_weight": blend_weight,
                "auto_adjust_blend_weight": True if mode == "blend" else False,
                "source": "nba_api.playergamelog",
            },
            team_map=team_map,
            series=series,
            minutes_cv=minutes_cv,
        )
        source = str(cache_path)
    except Exception as e:
        warnings.append(f"Cache write failed: {e}")
        source = "nba_api (uncached)"

    # Report completeness post-merge
    missing_after = _missing_players_for_required_stats(
        slate_players,
        overlay=overlay,
        series=series,
        required_stats=req_stats,
    )
    if missing_after:
        warnings.append(f"still missing {len(missing_after)} players after refresh")

    return RefreshResult(
        overlay=overlay,
        team_map=team_map,
        series=series,
        minutes_cv=minutes_cv,
        refreshed=True,
        source=source,
        warnings=warnings,
    )
