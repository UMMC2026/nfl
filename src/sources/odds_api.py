#!/usr/bin/env python3
# pyright: reportMissingImports=false
"""src/sources/odds_api.py

The Odds API (v4) client + adapter.

Goal: provide a *no-scrape* ingestion path for prop lines that can flow through
existing FUOOM truth-enforced artifacts/validation.

Notes:
- Player props are "additional markets" in Odds API v4 and typically must be
  queried *per event* via /v4/sports/{sport}/events/{eventId}/odds.
- Usage quota cost depends on the number of unique markets returned *per event*
  times the number of regions.

This module intentionally avoids any browser automation. It does not attempt to
bypass anti-bot or Cloudflare checks.
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple
from .odds_api_participant_validation import validate_participants

# Quota logger import
from .odds_api_quota_logger import OddsApiQuotaLogger

try:
    import requests  # type: ignore
except Exception as e:  # pragma: no cover
    requests = None  # type: ignore
    _requests_import_err = e

DEFAULT_HOST = "https://api.the-odds-api.com"


class OddsApiError(RuntimeError):
    pass


@dataclass(frozen=True)
class OddsApiQuota:
    remaining: Optional[int] = None
    used: Optional[int] = None
    last_cost: Optional[int] = None


def _to_int(v: Any) -> Optional[int]:
    try:
        if v is None:
            return None
        return int(v)
    except Exception:
        return None


def quota_from_headers(headers: Mapping[str, str]) -> OddsApiQuota:
    # Header names are case-insensitive; requests uses a CaseInsensitiveDict.
    return OddsApiQuota(
        remaining=_to_int(headers.get("x-requests-remaining")),
        used=_to_int(headers.get("x-requests-used")),
        last_cost=_to_int(headers.get("x-requests-last")),
    )


def _norm_side(value: str) -> Optional[str]:
    v = (value or "").strip().lower()
    if v in {"over", "higher", "more", "yes"}:
        return "higher"
    if v in {"under", "lower", "less", "no"}:
        return "lower"
    return None


def _market_key_to_stat(market_key: str) -> Optional[str]:
    # Keep these aligned with the repo's canonical stat naming.
    m = (market_key or "").strip().lower()

    mapping = {
        # NBA / NCAAB / WNBA (core set we support end-to-end)
        "player_points": "points",
        "player_rebounds": "rebounds",
        "player_assists": "assists",
        "player_threes": "3pm",
        "player_blocks": "blocks",
        "player_steals": "steals",
        "player_blocks_steals": "blocks+steals",
        "player_turnovers": "turnovers",
        "player_points_rebounds_assists": "pra",
        "player_points_assists": "points+assists",
        "player_points_rebounds": "points+rebounds",
        "player_rebounds_assists": "rebounds+assists",

        # NHL (subset aligned with repo NHL pipeline)
        "player_shots_on_goal": "sog",
        "player_total_saves": "saves",
        "player_goals": "goals",
        "player_points": "points",
        "player_power_play_points": "pp_points",
        "player_blocked_shots": "blocked_shots",

        # Soccer (US bookmakers only; common player prop markets)
        # Markets per The Odds API "Soccer Player Props".
        "player_shots": "shots",
        "player_shots_on_target": "shots_on_target",
        "player_assists": "assists",

        # Tennis (availability varies heavily by book/region/event)
        # These keys are best-effort based on Odds API naming conventions.
        # If a market key changes upstream, ingestion will safely skip unknown keys.
        "player_aces": "aces",
        "player_double_faults": "double_faults",
        "player_games_won": "games_won",
        "player_sets_won": "sets_won",
    }

    if m in mapping:
        return mapping[m]

    # Alternate lines (e.g., player_points_alternate) keep the same stat.
    if m.endswith("_alternate"):
        base = m[: -len("_alternate")]
        return mapping.get(base)

    return None


def _parse_outcome_player_and_direction(outcome: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    """Attempt to interpret an outcomes record into (player, direction).

    Odds API outcomes shapes vary by market/bookmaker. For player props, we
    commonly see either:
      - name = Player, description = Over/Under
      - name = Over/Under, description = Player

    We handle both.
    """

    name = str(outcome.get("name") or "").strip()
    desc = str(outcome.get("description") or "").strip()

    name_side = _norm_side(name)
    desc_side = _norm_side(desc)

    if desc_side and not name_side:
        return name or None, desc_side
    if name_side and not desc_side:
        return desc or None, name_side

    # Fallbacks: best-effort attempt.
    side = _norm_side(str(outcome.get("side") or "").strip())
    if side:
        player = outcome.get("player") or outcome.get("participant") or outcome.get("name")
        return (str(player).strip() if player else None), side

    return None, None


class OddsApiClient:
    def __init__(
        self,
        api_key: str,
        *,
        host: str = DEFAULT_HOST,
        timeout_s: int = 30,
        session: Optional[Any] = None,
        quota_log_path: Optional[str] = None,
    ) -> None:
        if requests is None:  # pragma: no cover
            raise OddsApiError(
                f"The 'requests' package is required for Odds API ingestion but could not be imported: {_requests_import_err}"
            )
        if not api_key:
            raise OddsApiError("Missing ODDS_API_KEY / api_key")

        self.api_key = api_key
        self.host = host.rstrip("/")
        self.timeout_s = timeout_s
        self.session = session or requests.Session()

        # Quota logger
        self.quota_logger = OddsApiQuotaLogger(log_path=quota_log_path)

    @classmethod
    def from_env(cls) -> Optional["OddsApiClient"]:
        key = os.getenv("ODDS_API_KEY") or os.getenv("ODDSAPI_KEY")
        if not key:
            return None
        host = os.getenv("ODDS_API_HOST") or DEFAULT_HOST
        timeout_s = int(os.getenv("ODDS_API_TIMEOUT_S") or "30")
        return cls(key, host=host, timeout_s=timeout_s)

    def _auth_params(self) -> Dict[str, str]:
        # Some official samples use api_key; docs frequently show apiKey.
        # Sending both is harmless and increases compatibility.
        return {"api_key": self.api_key, "apiKey": self.api_key}

    def _get(self, path: str, *, params: Dict[str, Any], max_retries: int = 3, log_context: str = "") -> Tuple[Any, OddsApiQuota]:
        url = f"{self.host}{path}"
        merged = dict(params)
        merged.update(self._auth_params())

        last_err: Optional[Exception] = None
        for attempt in range(max_retries):
            try:
                resp = self.session.get(url, params=merged, timeout=self.timeout_s)
                quota = quota_from_headers(resp.headers)

                # Log quota after each call
                self.quota_logger.log_quota(quota, context=f"{log_context or path} (attempt {attempt+1})")

                if resp.status_code == 429:
                    # Frequency limit: respect backoff.
                    delay = 2 * (2**attempt)
                    time.sleep(delay)
                    self.quota_logger.log_warning(f"HTTP 429 Rate limit hit for {path} (attempt {attempt+1})")
                    # Enhanced: return structured error for downstream handling
                    if attempt == max_retries - 1:
                        err_msg = f"Odds API rate limit hit (HTTP 429) after {max_retries} attempts: {path}"
                        self.quota_logger.log_error(err_msg)
                        raise OddsApiError(err_msg)
                    continue

                if resp.status_code >= 500:
                    delay = 1.5 * (2**attempt)
                    time.sleep(delay)
                    self.quota_logger.log_warning(f"HTTP {resp.status_code} server error for {path} (attempt {attempt+1})")
                    if attempt == max_retries - 1:
                        err_msg = f"Odds API server error (HTTP {resp.status_code}) after {max_retries} attempts: {path}"
                        self.quota_logger.log_error(err_msg)
                        raise OddsApiError(err_msg)
                    continue

                if resp.status_code != 200:
                    err_msg = f"Odds API request failed: {resp.status_code} {resp.text[:5000]}"
                    self.quota_logger.log_error(err_msg)
                    # Enhanced: include response body for debugging
                    raise OddsApiError({
                        "error": err_msg,
                        "status_code": resp.status_code,
                        "body": resp.text,
                        "quota": quota,
                        "url": url,
                        "params": merged,
                    })
                    raise OddsApiError(err_msg)

                return resp.json(), quota

            except Exception as e:
                last_err = e
                if attempt < max_retries - 1:
                    time.sleep(1.5 * (2**attempt))
                    continue
                self.quota_logger.log_error(f"Odds API request exception after retries: {e}")
                # Enhanced: raise structured error
                raise OddsApiError({
                    "error": str(e),
                    "last_attempt": attempt+1,
                    "url": url,
                    "params": merged,
                    "quota": quota if 'quota' in locals() else None,
                })
                raise

        raise OddsApiError({
            "error": f"Odds API request failed after retries: {last_err}",
            "url": url,
            "params": merged,
            "quota": quota if 'quota' in locals() else None,
        })

    def list_sports(self) -> Tuple[List[Dict[str, Any]], OddsApiQuota]:
        data, quota = self._get("/v4/sports", params={})
        return list(data or []), quota

    def get_events(
        self,
        *,
        sport_key: str,
        commence_time_from: Optional[str] = None,
        commence_time_to: Optional[str] = None,
    ) -> Tuple[List[Dict[str, Any]], OddsApiQuota]:
        """Fetch events, optionally filtered by commence time.

        Args:
            commence_time_from: ISO-8601 timestamp.  Only events starting *at or after*
                                this time are returned.  Saves quota.
            commence_time_to:   ISO-8601 timestamp.  Only events starting *before*
                                this time are returned.
        """
        params: Dict[str, Any] = {}
        if commence_time_from:
            params["commenceTimeFrom"] = commence_time_from
        if commence_time_to:
            params["commenceTimeTo"] = commence_time_to
        data, quota = self._get(f"/v4/sports/{sport_key}/events", params=params)
        return list(data or []), quota

    def get_odds(
        self,
        *,
        sport_key: str,
        regions: str,
        markets: str = "outrights",
        odds_format: str = "american",
        date_format: str = "iso",
        bookmakers: Optional[str] = None,
        commence_time_from: Optional[str] = None,
        commence_time_to: Optional[str] = None,
    ) -> Tuple[List[Dict[str, Any]], OddsApiQuota]:
        """Fetch odds via the featured-markets /odds endpoint.

        This is the correct endpoint for outrights, h2h, spreads, totals.
        Golf winner markets use ``markets=outrights``.

        Args:
            commence_time_from: ISO-8601.  Filter events starting at or after.
            commence_time_to:   ISO-8601.  Filter events starting before.
        """

        params: Dict[str, Any] = {
            "regions": regions,
            "markets": markets,
            "oddsFormat": odds_format,
            "dateFormat": date_format,
        }
        if bookmakers:
            params["bookmakers"] = bookmakers
        if commence_time_from:
            params["commenceTimeFrom"] = commence_time_from
        if commence_time_to:
            params["commenceTimeTo"] = commence_time_to

        data, quota = self._get(f"/v4/sports/{sport_key}/odds", params=params)
        if not isinstance(data, list):
            return [], quota
        return data, quota

    def get_event_odds(
        self,
        *,
        sport_key: str,
        event_id: str,
        regions: str,
        markets: str,
        odds_format: str = "american",
        date_format: str = "iso",
        bookmakers: Optional[str] = None,
        include_multipliers: bool = False,
    ) -> Tuple[Dict[str, Any], OddsApiQuota]:
        params: Dict[str, Any] = {
            "regions": regions,
            "markets": markets,
            "oddsFormat": odds_format,
            "dateFormat": date_format,
        }
        if bookmakers:
            params["bookmakers"] = bookmakers
        if include_multipliers:
            # DFS sites may expose multipliers; Odds API supports this on event odds endpoints.
            params["includeMultipliers"] = "true"

        data, quota = self._get(f"/v4/sports/{sport_key}/events/{event_id}/odds", params=params)
        if not isinstance(data, dict):
            raise OddsApiError("Unexpected response shape (expected object)")
        return data, quota

    def get_event_markets(
        self,
        *,
        sport_key: str,
        event_id: str,
        regions: str,
        date_format: str = "iso",
        bookmakers: Optional[str] = None,
    ) -> Tuple[Dict[str, Any], OddsApiQuota]:
        """Return available market keys for a single event.

        This is useful for dynamically discovering which market keys are valid for
        the (sport_key, regions, bookmakers) combination *today*, avoiding 422 INVALID_MARKET.
        """

        params: Dict[str, Any] = {
            "regions": regions,
            "dateFormat": date_format,
        }
        if bookmakers:
            params["bookmakers"] = bookmakers

        data, quota = self._get(f"/v4/sports/{sport_key}/events/{event_id}/markets", params=params)
        if not isinstance(data, dict):
            raise OddsApiError("Unexpected response shape (expected object)")
        return data, quota

    # ───────────────────────────────────────────────────────────────
    #  Scores — GET /v4/sports/{sport}/scores
    #  Cost: 1 request per call. Essential for auto-resolve.
    # ───────────────────────────────────────────────────────────────

    def get_scores(
        self,
        *,
        sport_key: str,
        days_from: Optional[int] = None,
        event_ids: Optional[List[str]] = None,
        date_format: str = "iso",
    ) -> Tuple[List[Dict[str, Any]], OddsApiQuota]:
        """Fetch live & recently completed scores.

        Args:
            sport_key: e.g. ``basketball_nba``
            days_from: 1-3, returns scores for events that started within the
                       last *days_from* days.  If ``None``, returns only
                       upcoming/live events.
            event_ids: Optional list of specific event IDs to filter.
            date_format: ``iso`` (default) or ``unix``.

        Returns:
            ``(list_of_score_objects, OddsApiQuota)``
        """
        params: Dict[str, Any] = {"dateFormat": date_format}
        if days_from is not None:
            params["daysFrom"] = str(days_from)
        if event_ids:
            params["eventIds"] = ",".join(event_ids)

        data, quota = self._get(f"/v4/sports/{sport_key}/scores", params=params)
        return list(data or []), quota

    # ───────────────────────────────────────────────────────────────
    #  Participants — GET /v4/sports/{sport}/participants
    #  Cost: FREE (does not count against quota).
    # ───────────────────────────────────────────────────────────────

    def get_participants(
        self,
        *,
        sport_key: str,
    ) -> Tuple[List[Dict[str, Any]], OddsApiQuota]:
        """Fetch participant rosters / teams for a sport.

        This endpoint is **free** and doesn't consume quota.
        Useful for roster validation gates.
        """
        data, quota = self._get(f"/v4/sports/{sport_key}/participants", params={})
        return list(data or []), quota

    # ───────────────────────────────────────────────────────────────
    #  Historical Odds — GET /v4/historical/sports/{sport}/odds
    #  Cost: 1 per market×region combo per snapshot.
    # ───────────────────────────────────────────────────────────────

    def get_historical_odds(
        self,
        *,
        sport_key: str,
        regions: str,
        date: str,
        markets: str = "h2h",
        odds_format: str = "american",
        date_format: str = "iso",
        bookmakers: Optional[str] = None,
    ) -> Tuple[Dict[str, Any], OddsApiQuota]:
        """Fetch a historical odds snapshot.

        Args:
            sport_key: e.g. ``basketball_nba``
            regions: e.g. ``us``, ``us_dfs``
            date: ISO-8601 timestamp (e.g. ``2026-02-19T12:00:00Z``)
            markets: Comma-separated market keys.
            odds_format: ``american`` or ``decimal``.
            bookmakers: Optional bookmaker filter.

        Returns:
            ``(response_dict, OddsApiQuota)``
            Response contains ``timestamp``, ``previous_timestamp``,
            ``next_timestamp``, ``data`` (list of odds snapshots).
        """
        params: Dict[str, Any] = {
            "regions": regions,
            "date": date,
            "markets": markets,
            "oddsFormat": odds_format,
            "dateFormat": date_format,
        }
        if bookmakers:
            params["bookmakers"] = bookmakers

        data, quota = self._get(f"/v4/historical/sports/{sport_key}/odds", params=params)
        if not isinstance(data, dict):
            return {"data": [], "timestamp": None}, quota
        return data, quota

    # ───────────────────────────────────────────────────────────────
    #  Historical Events — GET /v4/historical/sports/{sport}/events
    #  Cost: 1 request per call.
    # ───────────────────────────────────────────────────────────────

    def get_historical_events(
        self,
        *,
        sport_key: str,
        date: str,
        date_format: str = "iso",
    ) -> Tuple[Dict[str, Any], OddsApiQuota]:
        """Fetch events that existed on a past date.

        Args:
            sport_key: e.g. ``basketball_nba``
            date: ISO-8601 timestamp

        Returns:
            ``(response_dict, OddsApiQuota)``
            Response contains ``timestamp``, ``data`` (list of event dicts).
        """
        params: Dict[str, Any] = {
            "date": date,
            "dateFormat": date_format,
        }
        data, quota = self._get(f"/v4/historical/sports/{sport_key}/events", params=params)
        if not isinstance(data, dict):
            return {"data": []}, quota
        return data, quota

    # ───────────────────────────────────────────────────────────────
    #  Historical Event Odds — expensive (10× multiplier)
    #  GET /v4/historical/sports/{sport}/events/{eventId}/odds
    # ───────────────────────────────────────────────────────────────

    def get_historical_event_odds(
        self,
        *,
        sport_key: str,
        event_id: str,
        date: str,
        regions: str,
        markets: str = "h2h",
        odds_format: str = "american",
        date_format: str = "iso",
        bookmakers: Optional[str] = None,
    ) -> Tuple[Dict[str, Any], OddsApiQuota]:
        """Fetch historical odds for a single event — **EXPENSIVE**.

        This costs 10× per market×region combo.  Use sparingly.

        Args:
            sport_key: e.g. ``basketball_nba``
            event_id: Odds API event ID.
            date: ISO-8601 timestamp for the snapshot.
            regions: e.g. ``us``
            markets: Comma-separated market keys.

        Returns:
            ``(response_dict, OddsApiQuota)``
        """
        params: Dict[str, Any] = {
            "regions": regions,
            "date": date,
            "markets": markets,
            "oddsFormat": odds_format,
            "dateFormat": date_format,
        }
        if bookmakers:
            params["bookmakers"] = bookmakers

        data, quota = self._get(
            f"/v4/historical/sports/{sport_key}/events/{event_id}/odds",
            params=params,
        )
        if not isinstance(data, dict):
            return {"data": {}}, quota
        return data, quota


def _extract_invalid_markets(err_text: str) -> List[str]:
    """Extract invalid market keys from Odds API 422 responses.

    The Odds API typically returns JSON like:
      {"error_code":"INVALID_MARKET","message":"Invalid markets: a,b,c"}
    We parse conservatively to avoid false positives.
    """

    text = (err_text or "").strip()
    if not text:
        return []

    # Fast path: search for the human-readable message.
    m = re.search(r"Invalid\s+markets\s*:\s*([A-Za-z0-9_\-\s,]+)", text, flags=re.IGNORECASE)
    if m:
        return [t.strip() for t in (m.group(1) or "").split(",") if t.strip()]

    # Attempt to parse JSON bodies embedded in the exception string.
    # We look for a JSON object substring and parse it.
    try:
        j_start = text.find("{")
        j_end = text.rfind("}")
        if 0 <= j_start < j_end:
            payload = json.loads(text[j_start : j_end + 1])
        else:
            payload = json.loads(text)
    except Exception:
        return []

    if not isinstance(payload, dict):
        return []

    if str(payload.get("error_code") or "").upper() != "INVALID_MARKET":
        return []

    msg = payload.get("message")
    if isinstance(msg, str):
        m2 = re.search(r"Invalid\s+markets\s*:\s*([A-Za-z0-9_\-\s,]+)", msg, flags=re.IGNORECASE)
        if m2:
            return [t.strip() for t in (m2.group(1) or "").split(",") if t.strip()]

    invalid = payload.get("invalid_markets")
    if isinstance(invalid, list):
        out = []
        for v in invalid:
            s = str(v or "").strip()
            if s:
                out.append(s)
        return out

    return []


def _extract_available_market_keys(event_markets_json: Dict[str, Any]) -> List[str]:
    keys: List[str] = []
    for bookmaker in event_markets_json.get("bookmakers", []) or []:
        for market in bookmaker.get("markets", []) or []:
            k = str(market.get("key") or "").strip()
            if k:
                keys.append(k)
    # De-dupe while preserving order
    seen = set()
    out: List[str] = []
    for k in keys:
        if k in seen:
            continue
        seen.add(k)
        out.append(k)
    return out


def oddsapi_extract_props_from_event_odds(
    odds_json: Dict[str, Any],
    *,
    platform: str = "oddsapi",
    sport: str = "NBA",
) -> List[Dict[str, Any]]:
    """Convert a single /event/{id}/odds response into repo-style prop dicts."""

    event_id = str(odds_json.get("id") or "")
    commence_time = odds_json.get("commence_time")
    home_team = odds_json.get("home_team")
    away_team = odds_json.get("away_team")

    props: List[Dict[str, Any]] = []

    for bookmaker in odds_json.get("bookmakers", []) or []:
        b_key = bookmaker.get("key")
        b_title = bookmaker.get("title") or b_key
        markets = bookmaker.get("markets", []) or []

        for market in markets:
            market_key = str(market.get("key") or "")
            stat = _market_key_to_stat(market_key)
            if not stat:
                continue

            for outcome in market.get("outcomes", []) or []:
                line = outcome.get("point")
                if line is None:
                    continue

                player, direction = _parse_outcome_player_and_direction(outcome)
                if not player or not direction:
                    continue

                props.append(
                    {
                        "platform": platform,
                        "sport": sport,
                        "player": player,
                        "stat": stat,
                        "line": line,
                        "direction": direction,
                        "raw": {
                            "event_id": event_id,
                            "commence_time": commence_time,
                            "home_team": home_team,
                            "away_team": away_team,
                            "bookmaker_key": b_key,
                            "bookmaker_title": b_title,
                            "market_key": market_key,
                            "price": outcome.get("price"),
                            "outcome_name": outcome.get("name"),
                            "outcome_description": outcome.get("description"),
                        },
                    }
                )

    return props


def oddsapi_fetch_player_props(
    *,
    sport: str = "NBA",
    sport_key: str = "basketball_nba",
    regions: str = "us_dfs",
    markets: Iterable[str] = ("player_points",),
    bookmakers: Optional[Iterable[str]] = ("betr_us_dfs", "pick6", "prizepicks", "underdog"),
    max_events: Optional[int] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Fetch player props across (some) upcoming events.

    Returns: (props, metadata)
    """

    client = OddsApiClient.from_env()
    if client is None:
        raise OddsApiError("ODDS_API_KEY is not set")

    requested_markets: List[str] = [m for m in markets if m]
    markets_s = ",".join(requested_markets)
    bookmakers_s = None
    if bookmakers:
        bookmakers_s = ",".join([b for b in bookmakers if b]) or None

    include_multipliers = bool(
        ("us_dfs" in (regions or "").lower())
        or (bookmakers_s and any(b in bookmakers_s.lower() for b in ["prizepicks", "underdog", "pick6", "betr_us_dfs"]))
    )

    events, q_events = client.get_events(sport_key=sport_key)
    if max_events is not None:
        events = events[: max(0, int(max_events))]

    all_props: List[Dict[str, Any]] = []
    raw_event_odds: List[Dict[str, Any]] = []
    invalid_markets_global: List[str] = []
    discovered_markets_used: bool = False

    quota_last: Optional[OddsApiQuota] = None

    # Fetch participants for validation (free endpoint)
    participants, _ = client.get_participants(sport_key=sport_key)

    for ev in events:
        event_id = ev.get("id")
        if not event_id:
            continue

        # If we've already learned some markets are invalid, drop them pre-emptively.
        effective_markets = [m for m in requested_markets if m and m not in set(invalid_markets_global)]
        if not effective_markets:
            # Nothing left to query.
            break

        effective_markets_s = ",".join(effective_markets)

        def _fetch_event_odds_with_markets(mkts_s: str) -> Tuple[Dict[str, Any], OddsApiQuota]:
            return client.get_event_odds(
                sport_key=sport_key,
                event_id=str(event_id),
                regions=regions,
                markets=mkts_s,
                bookmakers=bookmakers_s,
                include_multipliers=include_multipliers,
            )

        try:
            odds_json, q = _fetch_event_odds_with_markets(effective_markets_s)
            quota_last = q
        except OddsApiError as e:
            invalid = _extract_invalid_markets(str(e))
            if not invalid:
                raise

            # Iteratively drop invalid markets and retry a couple times.
            odds_json = None  # type: ignore[assignment]
            q = None  # type: ignore[assignment]

            attempt_markets = list(effective_markets)
            for _ in range(3):
                for m in invalid:
                    if m not in invalid_markets_global:
                        invalid_markets_global.append(m)

                attempt_markets = [m for m in requested_markets if m and m not in set(invalid_markets_global)]
                if not attempt_markets:
                    break

                try:
                    odds_json, q = _fetch_event_odds_with_markets(",".join(attempt_markets))
                    break
                except OddsApiError as e2:
                    invalid2 = _extract_invalid_markets(str(e2))
                    if not invalid2:
                        raise
                    invalid = invalid2
                    continue

            if odds_json is None:
                # Optional: discover available markets for this event and retry with intersection.
                try:
                    mk_json, _q_mk = client.get_event_markets(
                        sport_key=sport_key,
                        event_id=str(event_id),
                        regions=regions,
                        bookmakers=bookmakers_s,
                    )
                    avail = _extract_available_market_keys(mk_json)
                    intersect = [m for m in requested_markets if m in set(avail)]
                    if intersect:
                        discovered_markets_used = True
                        odds_json, q = _fetch_event_odds_with_markets(",".join(intersect))
                    else:
                        continue
                except Exception:
                    continue

            quota_last = q

        raw_event_odds.append(odds_json)
        all_props.extend(oddsapi_extract_props_from_event_odds(odds_json, platform="oddsapi", sport=sport))

        # Gentle pacing to reduce freq-limit issues.
        time.sleep(float(os.getenv("ODDS_API_PACE_S") or "0.15"))

    # Validate participants
    valid_props = validate_participants(all_props, participants)

    meta: Dict[str, Any] = {
        "sport": sport,
        "sport_key": sport_key,
        "regions": regions,
        "markets": markets_s,
        "bookmakers": bookmakers_s,
        "event_count": len(events),
        "invalid_markets_dropped": invalid_markets_global or None,
        "used_market_discovery": discovered_markets_used,
        "include_multipliers": include_multipliers,
        "quota": {
            "events_list": {
                "remaining": q_events.remaining,
                "used": q_events.used,
                "last_cost": q_events.last_cost,
            },
            "last_event_odds": {
                "remaining": getattr(quota_last, "remaining", None),
                "used": getattr(quota_last, "used", None),
                "last_cost": getattr(quota_last, "last_cost", None),
            },
        },
        "raw_event_odds": raw_event_odds,
        "participant_validation": {
            "total_props": len(all_props),
            "valid_props": len(valid_props),
            "invalid_props": len(all_props) - len(valid_props),
        },
    }

    return valid_props, meta


def oddsapi_sport_key_for_tag(tag: str) -> Optional[str]:
    raw = (tag or "").strip()
    if not raw:
        return None

    # Allow callers to pass a concrete Odds API sport_key directly.
    # Example: "tennis_atp_french_open".
    raw_l = raw.lower()
    if raw_l.startswith(
        (
            "basketball_",
            "americanfootball_",
            "icehockey_",
            "baseball_",
            "soccer_",
            "golf_",
        )
    ):
        return raw_l

    # Tennis keys are commonly tournament-specific (e.g., tennis_wta_qatar_open).
    # Do NOT passthrough generic tags like TENNIS_WTA / TENNIS_ATP.
    if raw_l.startswith("tennis_") and raw_l not in {"tennis", "tennis_atp", "tennis_wta"}:
        return raw_l

    t = raw.upper()
    if t == "NBA":
        return "basketball_nba"
    if t == "WNBA":
        return "basketball_wnba"
    if t == "NFL":
        return "americanfootball_nfl"
    if t == "NHL":
        return "icehockey_nhl"
    if t == "MLB":
        return "baseball_mlb"

    # Tennis (Odds API sport keys are often tournament-specific; require explicit configuration)
    if t in {"TENNIS_ATP", "ATP"}:
        key = (os.getenv("ODDS_API_TENNIS_ATP_SPORT_KEY") or os.getenv("ODDS_API_TENNIS_SPORT_KEY") or "").strip()
        return key or None
    if t in {"TENNIS_WTA", "WTA"}:
        key = (os.getenv("ODDS_API_TENNIS_WTA_SPORT_KEY") or os.getenv("ODDS_API_TENNIS_SPORT_KEY") or "").strip()
        return key or None
    if t == "TENNIS":
        key = (os.getenv("ODDS_API_TENNIS_SPORT_KEY") or "").strip()
        return key or None

    # Soccer leagues (use explicit tags to avoid ambiguity)
    soccer_map = {
        "SOCCER_EPL": "soccer_epl",
        "SOCCER_MLS": "soccer_usa_mls",
        "SOCCER_LA_LIGA": "soccer_spain_la_liga",
        "SOCCER_BUNDESLIGA": "soccer_germany_bundesliga",
        "SOCCER_SERIE_A": "soccer_italy_serie_a",
        "SOCCER_LIGUE_1": "soccer_france_ligue_one",
        # Common short alias
        "MLS": "soccer_usa_mls",
        "EPL": "soccer_epl",
    }
    if t in soccer_map:
        return soccer_map[t]

    # Allow a generic SOCCER tag with configurable league key.
    if t == "SOCCER":
        return (os.getenv("ODDS_API_SOCCER_SPORT_KEY") or "soccer_epl").strip() or "soccer_epl"

    # Golf (Odds API only has major championship outright-winner keys)
    golf_map = {
        "GOLF_MASTERS": "golf_masters_tournament_winner",
        "GOLF_PGA": "golf_pga_championship_winner",
        "GOLF_US_OPEN": "golf_us_open_winner",
        "GOLF_OPEN": "golf_the_open_championship_winner",
        "GOLF_THE_OPEN": "golf_the_open_championship_winner",
    }
    if t in golf_map:
        return golf_map[t]

    # Generic GOLF → let user pick via env var, default to Masters
    if t == "GOLF":
        return (os.getenv("ODDS_API_GOLF_SPORT_KEY") or "").strip() or None

    return None


def dump_json(path: str, payload: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
