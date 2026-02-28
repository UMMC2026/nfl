#!/usr/bin/env python3
"""src/markets/binary_markets.py

FUOOM Binary Markets Engine — DraftKings Predictions + Sportsbook Odds
======================================================================

Fetches team-level binary outcome markets from Odds API:
  - Moneyline (h2h)   → home/away WIN probability
  - Spreads            → home/away COVER probability
  - Totals             → OVER/UNDER probability

Converts American odds → implied probability → vig-removed fair probability.
Calculates edges against model probability when available.

Compatible with DraftKings Predictions YES/NO format, traditional sportsbooks,
and any market expressed as a two-outcome binary.

Usage:
    from src.markets.binary_markets import BinaryMarketEngine
    engine = BinaryMarketEngine.from_env()
    markets = engine.fetch_game_markets(sport="NBA")
    for m in markets:
        print(f"{m['entity']} {m['market_type']} implied={m['implied_prob']:.1%}")
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ── Odds → Probability Conversion ──────────────────────────────────


def american_to_implied(odds: float) -> float:
    """Convert American odds to implied probability (0-1).

    +270 → 100/(270+100) = 0.2703 (27.0%)
    -150 → 150/(150+100) = 0.6000 (60.0%)
    """
    if odds > 0:
        return 100.0 / (odds + 100.0)
    elif odds < 0:
        return abs(odds) / (abs(odds) + 100.0)
    else:
        return 0.5


def decimal_to_implied(odds: float) -> float:
    """Convert decimal odds to implied probability (0-1)."""
    if odds <= 1.0:
        return 0.0
    return 1.0 / odds


def remove_vig_two_way(prob_a: float, prob_b: float) -> Tuple[float, float]:
    """Remove vig from a two-outcome market.

    The sum of implied probabilities exceeds 1.0 by the vig amount.
    We normalise both sides to sum to 1.0 (proportional vig removal).

    Returns: (fair_prob_a, fair_prob_b)
    """
    total = prob_a + prob_b
    if total <= 0:
        return 0.5, 0.5
    return prob_a / total, prob_b / total


def remove_vig_multi_way(probs: List[float]) -> List[float]:
    """Remove vig from a multi-outcome market (e.g., MVP with 10 candidates)."""
    total = sum(probs)
    if total <= 0:
        return [1.0 / len(probs)] * len(probs) if probs else []
    return [p / total for p in probs]


def edge_pct(model_prob: float, market_fair_prob: float) -> float:
    """Calculate edge as model_prob - market_fair_prob.

    Positive = model sees more value than market.
    """
    return model_prob - market_fair_prob


def expected_value(model_prob: float, american_odds: float) -> float:
    """Calculate expected value per $100 wagered.

    EV = (win_prob × profit_if_win) - (lose_prob × stake)
    """
    if american_odds > 0:
        profit = american_odds  # +270 → $270 profit on $100
    else:
        profit = 100.0 * (100.0 / abs(american_odds))  # -150 → $66.67 profit
    lose_prob = 1.0 - model_prob
    return (model_prob * profit) - (lose_prob * 100.0)


# ── Market Schema ──────────────────────────────────────────────────


@dataclass
class BinaryMarket:
    """A single binary outcome market."""

    # Identification
    market_id: str = ""                # Unique identifier
    sport: str = ""                    # NBA, NFL, NHL, etc.
    market_type: str = ""              # moneyline, spread, total, mvp, winner, prop_binary
    entity: str = ""                   # Team name, player name, or outcome description
    event_id: str = ""                 # Odds API event ID
    event_description: str = ""        # "Lakers vs Celtics"

    # Sides
    side: str = ""                     # home/away, over/under, yes/no
    opponent_side: str = ""            # The other side of this binary

    # Lines (for spreads/totals)
    line: Optional[float] = None       # Spread value or total line

    # Odds & Probabilities
    american_odds: float = 0.0         # Raw American odds from book
    implied_prob: float = 0.0          # Implied probability (with vig)
    fair_prob: float = 0.0             # Vig-removed fair probability
    vig_pct: float = 0.0              # Vig percentage for this market

    # Edge (populated when model probability is available)
    model_prob: Optional[float] = None
    edge: Optional[float] = None       # model_prob - fair_prob
    ev_per_100: Optional[float] = None # Expected value per $100

    # Metadata
    bookmaker: str = ""
    commence_time: str = ""
    home_team: str = ""
    away_team: str = ""
    fetched_at: str = ""
    source: str = "OddsAPI"

    # DK Predictions specific
    dk_predictions_format: bool = False  # True if from DK Predictions YES/NO market

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @property
    def tier(self) -> str:
        """Classify market edge into governance tiers."""
        if self.edge is None:
            return "UNKNOWN"
        edge_abs = abs(self.edge)
        if edge_abs >= 0.08:
            return "SLAM"  # 8%+ edge
        elif edge_abs >= 0.04:
            return "STRONG"  # 4-8% edge
        elif edge_abs >= 0.02:
            return "LEAN"  # 2-4% edge
        else:
            return "NO_PLAY"  # <2% edge

    @property
    def is_playable(self) -> bool:
        """Binary markets need ≥2% edge to be actionable."""
        if self.edge is None:
            return False
        return self.edge >= 0.02


# ── Odds API Market Fetcher ────────────────────────────────────────


def _try_import_odds_api():
    """Import OddsApiClient from the repo's existing module."""
    try:
        import sys
        project_root = Path(__file__).resolve().parents[2]
        src_dir = project_root / "src"
        if str(src_dir) not in sys.path:
            sys.path.insert(0, str(src_dir))
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))

        from sources.odds_api import (
            OddsApiClient,
            OddsApiError,
            oddsapi_sport_key_for_tag,
        )
        return OddsApiClient, OddsApiError, oddsapi_sport_key_for_tag
    except Exception:
        return None


# Sport → Odds API sport key mapping for team-level markets
SPORT_KEYS = {
    "NBA": "basketball_nba",
    "WNBA": "basketball_wnba",
    "CBB": "basketball_ncaab",
    "NCAAB": "basketball_ncaab",
    "NFL": "americanfootball_nfl",
    "NCAAF": "americanfootball_ncaaf",
    "NHL": "icehockey_nhl",
    "MLB": "baseball_mlb",
    "MLS": "soccer_usa_mls",
    "EPL": "soccer_epl",
    "SOCCER_EPL": "soccer_epl",
    "SOCCER_MLS": "soccer_usa_mls",
    "SOCCER_LA_LIGA": "soccer_spain_la_liga",
    "SOCCER_BUNDESLIGA": "soccer_germany_bundesliga",
    "SOCCER_SERIE_A": "soccer_italy_serie_a",
}

# Which markets to fetch for each sport
SPORT_MARKETS = {
    "NBA":     ["h2h", "spreads", "totals"],
    "WNBA":    ["h2h", "spreads", "totals"],
    "CBB":     ["h2h", "spreads", "totals"],
    "NCAAB":   ["h2h", "spreads", "totals"],
    "NFL":     ["h2h", "spreads", "totals"],
    "NCAAF":   ["h2h", "spreads", "totals"],
    "NHL":     ["h2h", "spreads", "totals"],
    "MLB":     ["h2h", "spreads", "totals"],
    "MLS":     ["h2h"],
    "EPL":     ["h2h"],
    "SOCCER_EPL": ["h2h"],
    "SOCCER_MLS": ["h2h"],
}

# Default bookmakers for team-level markets (traditional sportsbooks, not DFS)
DEFAULT_BOOKMAKERS = "fanduel,draftkings,betmgm,caesars,pointsbet,bet365"


class BinaryMarketEngine:
    """Fetch and process team-level binary markets from Odds API."""

    def __init__(self, client, *, regions: str = "us", bookmakers: str = DEFAULT_BOOKMAKERS):
        self.client = client
        self.regions = regions
        self.bookmakers = bookmakers

    @classmethod
    def from_env(cls, *, regions: str = "us", bookmakers: str = DEFAULT_BOOKMAKERS) -> Optional["BinaryMarketEngine"]:
        """Create engine from ODDS_API_KEY environment variable."""
        imports = _try_import_odds_api()
        if imports is None:
            return None
        OddsApiClient, _, _ = imports
        client = OddsApiClient.from_env()
        if client is None:
            return None
        return cls(client, regions=regions, bookmakers=bookmakers)

    def fetch_game_markets(
        self,
        *,
        sport: str = "NBA",
        market_types: Optional[List[str]] = None,
    ) -> List[BinaryMarket]:
        """Fetch team-level binary markets for a sport.

        Returns a list of BinaryMarket objects with implied and fair probabilities.
        """
        sport_upper = sport.upper()
        sport_key = SPORT_KEYS.get(sport_upper)
        if not sport_key:
            raise ValueError(f"Unsupported sport for binary markets: {sport}")

        if market_types is None:
            market_types = SPORT_MARKETS.get(sport_upper, ["h2h"])

        markets_str = ",".join(market_types)
        now_iso = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

        try:
            data, quota = self.client.get_odds(
                sport_key=sport_key,
                regions=self.regions,
                markets=markets_str,
                odds_format="american",
                bookmakers=self.bookmakers,
            )
        except Exception as e:
            print(f"  ⚠ Binary markets fetch failed: {e}")
            return []

        all_markets: List[BinaryMarket] = []

        for event in data:
            event_id = event.get("id", "")
            home_team = event.get("home_team", "")
            away_team = event.get("away_team", "")
            commence = event.get("commence_time", "")
            event_desc = f"{away_team} @ {home_team}"

            for bookmaker in event.get("bookmakers", []):
                bk_key = bookmaker.get("key", "")

                for market in bookmaker.get("markets", []):
                    mkt_key = market.get("key", "")
                    outcomes = market.get("outcomes", [])

                    parsed = self._parse_market_outcomes(
                        market_key=mkt_key,
                        outcomes=outcomes,
                        sport=sport_upper,
                        event_id=event_id,
                        event_desc=event_desc,
                        home_team=home_team,
                        away_team=away_team,
                        commence=commence,
                        bookmaker=bk_key,
                        fetched_at=now_iso,
                    )
                    all_markets.extend(parsed)

        return all_markets

    def _parse_market_outcomes(
        self,
        *,
        market_key: str,
        outcomes: List[Dict[str, Any]],
        sport: str,
        event_id: str,
        event_desc: str,
        home_team: str,
        away_team: str,
        commence: str,
        bookmaker: str,
        fetched_at: str,
    ) -> List[BinaryMarket]:
        """Parse outcomes from a single market into BinaryMarket objects."""

        results: List[BinaryMarket] = []

        if market_key == "h2h":
            # Moneyline: two outcomes (home_team, away_team)
            results.extend(
                self._parse_h2h(outcomes, sport=sport, event_id=event_id,
                                event_desc=event_desc, home_team=home_team,
                                away_team=away_team, commence=commence,
                                bookmaker=bookmaker, fetched_at=fetched_at)
            )

        elif market_key == "spreads":
            results.extend(
                self._parse_spreads(outcomes, sport=sport, event_id=event_id,
                                    event_desc=event_desc, home_team=home_team,
                                    away_team=away_team, commence=commence,
                                    bookmaker=bookmaker, fetched_at=fetched_at)
            )

        elif market_key == "totals":
            results.extend(
                self._parse_totals(outcomes, sport=sport, event_id=event_id,
                                   event_desc=event_desc, home_team=home_team,
                                   away_team=away_team, commence=commence,
                                   bookmaker=bookmaker, fetched_at=fetched_at)
            )

        return results

    def _parse_h2h(self, outcomes, **ctx) -> List[BinaryMarket]:
        """Parse moneyline (head-to-head) outcomes."""
        if len(outcomes) < 2:
            return []

        # Build implied probs for all outcomes
        side_data: List[Tuple[str, str, float, float]] = []
        for o in outcomes:
            name = o.get("name", "")
            odds = o.get("price", 0)
            imp = american_to_implied(odds)
            side = "home" if name == ctx["home_team"] else "away"
            side_data.append((name, side, odds, imp))

        # Remove vig (two-way)
        if len(side_data) == 2:
            fair_a, fair_b = remove_vig_two_way(side_data[0][3], side_data[1][3])
            fairs = [fair_a, fair_b]
        else:
            fairs = remove_vig_multi_way([sd[3] for sd in side_data])

        markets = []
        vig_total = sum(sd[3] for sd in side_data)
        vig_pct = vig_total - 1.0 if vig_total > 1.0 else 0.0

        for i, (name, side, odds, imp) in enumerate(side_data):
            opp_side = "away" if side == "home" else "home"
            mkt_id = f"{ctx['event_id']}_{ctx['bookmaker']}_h2h_{side}"

            markets.append(BinaryMarket(
                market_id=mkt_id,
                sport=ctx["sport"],
                market_type="moneyline",
                entity=name,
                event_id=ctx["event_id"],
                event_description=ctx["event_desc"],
                side=side,
                opponent_side=opp_side,
                line=None,
                american_odds=odds,
                implied_prob=round(imp, 6),
                fair_prob=round(fairs[i], 6),
                vig_pct=round(vig_pct, 4),
                bookmaker=ctx["bookmaker"],
                commence_time=ctx["commence"],
                home_team=ctx["home_team"],
                away_team=ctx["away_team"],
                fetched_at=ctx["fetched_at"],
            ))

        return markets

    def _parse_spreads(self, outcomes, **ctx) -> List[BinaryMarket]:
        """Parse spread (point spread) outcomes."""
        if len(outcomes) < 2:
            return []

        side_data = []
        for o in outcomes:
            name = o.get("name", "")
            odds = o.get("price", 0)
            point = o.get("point", 0)
            imp = american_to_implied(odds)
            side = "home" if name == ctx["home_team"] else "away"
            side_data.append((name, side, odds, imp, point))

        if len(side_data) == 2:
            fair_a, fair_b = remove_vig_two_way(side_data[0][3], side_data[1][3])
            fairs = [fair_a, fair_b]
        else:
            fairs = remove_vig_multi_way([sd[3] for sd in side_data])

        markets = []
        vig_total = sum(sd[3] for sd in side_data)
        vig_pct = vig_total - 1.0 if vig_total > 1.0 else 0.0

        for i, (name, side, odds, imp, point) in enumerate(side_data):
            opp_side = "away" if side == "home" else "home"
            mkt_id = f"{ctx['event_id']}_{ctx['bookmaker']}_spread_{side}"

            markets.append(BinaryMarket(
                market_id=mkt_id,
                sport=ctx["sport"],
                market_type="spread",
                entity=name,
                event_id=ctx["event_id"],
                event_description=ctx["event_desc"],
                side=side,
                opponent_side=opp_side,
                line=point,
                american_odds=odds,
                implied_prob=round(imp, 6),
                fair_prob=round(fairs[i], 6),
                vig_pct=round(vig_pct, 4),
                bookmaker=ctx["bookmaker"],
                commence_time=ctx["commence"],
                home_team=ctx["home_team"],
                away_team=ctx["away_team"],
                fetched_at=ctx["fetched_at"],
            ))

        return markets

    def _parse_totals(self, outcomes, **ctx) -> List[BinaryMarket]:
        """Parse game total (over/under) outcomes."""
        if len(outcomes) < 2:
            return []

        side_data = []
        for o in outcomes:
            name = str(o.get("name", "")).lower()
            odds = o.get("price", 0)
            point = o.get("point", 0)
            imp = american_to_implied(odds)
            side = "over" if name == "over" else "under"
            entity = f"{ctx['event_desc']} Total"
            side_data.append((entity, side, odds, imp, point))

        if len(side_data) == 2:
            fair_a, fair_b = remove_vig_two_way(side_data[0][3], side_data[1][3])
            fairs = [fair_a, fair_b]
        else:
            fairs = remove_vig_multi_way([sd[3] for sd in side_data])

        markets = []
        vig_total = sum(sd[3] for sd in side_data)
        vig_pct = vig_total - 1.0 if vig_total > 1.0 else 0.0

        for i, (entity, side, odds, imp, point) in enumerate(side_data):
            opp_side = "under" if side == "over" else "over"
            mkt_id = f"{ctx['event_id']}_{ctx['bookmaker']}_total_{side}"

            markets.append(BinaryMarket(
                market_id=mkt_id,
                sport=ctx["sport"],
                market_type="total",
                entity=entity,
                event_id=ctx["event_id"],
                event_description=ctx["event_desc"],
                side=side,
                opponent_side=opp_side,
                line=point,
                american_odds=odds,
                implied_prob=round(imp, 6),
                fair_prob=round(fairs[i], 6),
                vig_pct=round(vig_pct, 4),
                bookmaker=ctx["bookmaker"],
                commence_time=ctx["commence"],
                home_team=ctx["home_team"],
                away_team=ctx["away_team"],
                fetched_at=ctx["fetched_at"],
            ))

        return markets


# ── DraftKings Predictions Parser ──────────────────────────────────


def parse_dk_predictions_text(text: str, *, sport: str = "NFL") -> List[BinaryMarket]:
    """Parse DraftKings Predictions page text into BinaryMarket objects.

    DK Predictions format (from scraped page text):
        Sam Darnold
        YES +127
        NO -257

        Drake Maye
        YES +270
        NO -900

    This parser handles the vertical text extraction pattern used by FUOOM's
    existing Playwright scraper pipeline.
    """
    import re

    lines = [l.strip() for l in text.split("\n") if l.strip()]
    markets: List[BinaryMarket] = []
    now_iso = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    i = 0
    current_entity = None

    while i < len(lines):
        line = lines[i]

        # Skip UI noise
        skip_words = ["sign in", "log in", "deposit", "withdraw", "rewards",
                      "featured", "popular", "lobby", "my entries"]
        if any(sw in line.lower() for sw in skip_words):
            i += 1
            continue

        # Try to match YES/NO odds pattern: "YES +127" or "NO -257"
        yes_match = re.match(r'^YES\s+([+-]?\d+)$', line, re.IGNORECASE)
        no_match = re.match(r'^NO\s+([+-]?\d+)$', line, re.IGNORECASE)

        if yes_match and current_entity:
            yes_odds = float(yes_match.group(1))
            yes_imp = american_to_implied(yes_odds)

            # Look ahead for the NO line
            no_odds = None
            no_imp = 0.5
            if i + 1 < len(lines):
                no_m = re.match(r'^NO\s+([+-]?\d+)$', lines[i + 1], re.IGNORECASE)
                if no_m:
                    no_odds = float(no_m.group(1))
                    no_imp = american_to_implied(no_odds)
                    i += 1  # consume the NO line

            # Vig removal
            fair_yes, fair_no = remove_vig_two_way(yes_imp, no_imp)
            vig_total = yes_imp + no_imp
            vig_pct = vig_total - 1.0 if vig_total > 1.0 else 0.0

            mkt_id = f"dk_pred_{current_entity.replace(' ', '_')}_{now_iso}"

            markets.append(BinaryMarket(
                market_id=mkt_id,
                sport=sport,
                market_type="prop_binary",
                entity=current_entity,
                side="yes",
                opponent_side="no",
                american_odds=yes_odds,
                implied_prob=round(yes_imp, 6),
                fair_prob=round(fair_yes, 6),
                vig_pct=round(vig_pct, 4),
                fetched_at=now_iso,
                source="DK_Predictions",
                dk_predictions_format=True,
            ))

            # Also store the NO side
            if no_odds is not None:
                markets.append(BinaryMarket(
                    market_id=mkt_id + "_no",
                    sport=sport,
                    market_type="prop_binary",
                    entity=current_entity,
                    side="no",
                    opponent_side="yes",
                    american_odds=no_odds,
                    implied_prob=round(no_imp, 6),
                    fair_prob=round(fair_no, 6),
                    vig_pct=round(vig_pct, 4),
                    fetched_at=now_iso,
                    source="DK_Predictions",
                    dk_predictions_format=True,
                ))

            current_entity = None
            i += 1
            continue

        elif no_match:
            # Standalone NO line (YES was already consumed) — skip
            i += 1
            continue

        # Check if this looks like an entity name (not a number, not a keyword)
        if (len(line) > 2
            and not re.match(r'^[+-]?\d+\.?\d*$', line)
            and not re.match(r'^(YES|NO)\b', line, re.IGNORECASE)
            and line.lower() not in skip_words):
            current_entity = line

        i += 1

    return markets


# ── Edge Application ───────────────────────────────────────────────


def apply_model_probabilities(
    markets: List[BinaryMarket],
    model_probs: Dict[str, float],
) -> List[BinaryMarket]:
    """Apply model probabilities to markets and calculate edges.

    model_probs: dict mapping entity name or market_id → model probability.
    Example: {"Los Angeles Lakers": 0.62, "Boston Celtics": 0.38}
    """
    for m in markets:
        # Try exact entity match, then market_id match
        prob = model_probs.get(m.entity) or model_probs.get(m.market_id)

        if prob is not None:
            m.model_prob = prob
            m.edge = round(edge_pct(prob, m.fair_prob), 6)
            m.ev_per_100 = round(expected_value(prob, m.american_odds), 2)

    return markets


# ── Consensus / Best Line ──────────────────────────────────────────


def consensus_markets(markets: List[BinaryMarket]) -> List[BinaryMarket]:
    """Aggregate markets across bookmakers into consensus (average) lines.

    Groups by (event_id, market_type, side) and produces one consensus
    BinaryMarket per group with averaged fair probabilities.
    """
    from collections import defaultdict

    groups: Dict[str, List[BinaryMarket]] = defaultdict(list)
    for m in markets:
        key = f"{m.event_id}|{m.market_type}|{m.side}|{m.entity}"
        groups[key].append(m)

    consensus: List[BinaryMarket] = []
    for key, group in groups.items():
        if not group:
            continue

        # Average fair probability across bookmakers
        avg_fair = sum(m.fair_prob for m in group) / len(group)
        avg_implied = sum(m.implied_prob for m in group) / len(group)
        avg_vig = sum(m.vig_pct for m in group) / len(group)

        # Find best odds (most favorable for this side)
        best = max(group, key=lambda m: m.american_odds)

        ref = group[0]
        consensus.append(BinaryMarket(
            market_id=f"consensus_{ref.event_id}_{ref.market_type}_{ref.side}",
            sport=ref.sport,
            market_type=ref.market_type,
            entity=ref.entity,
            event_id=ref.event_id,
            event_description=ref.event_description,
            side=ref.side,
            opponent_side=ref.opponent_side,
            line=ref.line,
            american_odds=best.american_odds,
            implied_prob=round(avg_implied, 6),
            fair_prob=round(avg_fair, 6),
            vig_pct=round(avg_vig, 4),
            model_prob=ref.model_prob,
            edge=round(edge_pct(ref.model_prob, avg_fair), 6) if ref.model_prob else None,
            ev_per_100=round(expected_value(ref.model_prob, best.american_odds), 2) if ref.model_prob else None,
            bookmaker=f"consensus({len(group)})",
            commence_time=ref.commence_time,
            home_team=ref.home_team,
            away_team=ref.away_team,
            fetched_at=ref.fetched_at,
            source="Consensus",
        ))

    return consensus


# ── Output / Serialization ─────────────────────────────────────────


def markets_to_json(markets: List[BinaryMarket], path: Path) -> Path:
    """Write markets to a JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "count": len(markets),
        "markets": [m.to_dict() for m in markets],
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def format_market_table(
    markets: List[BinaryMarket],
    *,
    show_edge: bool = True,
    max_rows: int = 50,
) -> str:
    """Format markets as a text table for terminal display."""

    lines = []
    header = f"{'Entity':<30} {'Type':<10} {'Side':<6} {'Odds':>7} {'Implied':>8} {'Fair':>8}"
    if show_edge:
        header += f" {'Model':>7} {'Edge':>7} {'EV/100':>8} {'Tier':<8}"
    lines.append(header)
    lines.append("─" * len(header))

    for m in markets[:max_rows]:
        entity_short = m.entity[:29]
        row = f"{entity_short:<30} {m.market_type:<10} {m.side:<6} {m.american_odds:>+7.0f} {m.implied_prob:>7.1%} {m.fair_prob:>7.1%}"
        if show_edge:
            mp = f"{m.model_prob:.1%}" if m.model_prob is not None else "  -  "
            ep = f"{m.edge:>+6.1%}" if m.edge is not None else "  -  "
            ev = f"${m.ev_per_100:>+7.1f}" if m.ev_per_100 is not None else "   -   "
            tier = m.tier if m.edge is not None else ""
            row += f" {mp:>7} {ep:>7} {ev:>8} {tier:<8}"
        lines.append(row)

    return "\n".join(lines)


# ── CLI Entry Point ────────────────────────────────────────────────


def main():
    """CLI entry point for binary markets analysis."""
    import argparse

    parser = argparse.ArgumentParser(description="FUOOM Binary Markets Engine")
    parser.add_argument("--sport", default="NBA", help="Sport (NBA, NFL, NHL, etc.)")
    parser.add_argument("--markets", default=None, help="Market types: h2h,spreads,totals")
    parser.add_argument("--bookmakers", default=DEFAULT_BOOKMAKERS, help="Bookmakers to query")
    parser.add_argument("--output", default=None, help="Output JSON path")
    parser.add_argument("--consensus", action="store_true", help="Show consensus lines")
    args = parser.parse_args()

    # Load .env
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except Exception:
        pass

    engine = BinaryMarketEngine.from_env(bookmakers=args.bookmakers)
    if engine is None:
        print("❌ ODDS_API_KEY not found in environment")
        return 1

    sport = args.sport.upper()
    market_types = args.markets.split(",") if args.markets else None

    print(f"\n{'═' * 60}")
    print(f"  🎯 FUOOM BINARY MARKETS — {sport}")
    print(f"{'═' * 60}\n")

    markets = engine.fetch_game_markets(sport=sport, market_types=market_types)

    if not markets:
        print("  No markets found. Check sport/API key/upcoming games.")
        return 0

    if args.consensus:
        markets = consensus_markets(markets)
        print(f"  📊 Consensus lines across bookmakers:\n")
    else:
        print(f"  📊 {len(markets)} market outcomes from {sport}:\n")

    print(format_market_table(markets, show_edge=False))

    if args.output:
        out_path = Path(args.output)
        markets_to_json(markets, out_path)
        print(f"\n  ✅ Saved to {out_path}")

    print(f"\n  Vig range: {min(m.vig_pct for m in markets):.1%} – {max(m.vig_pct for m in markets):.1%}")
    print(f"  Events covered: {len(set(m.event_id for m in markets))}")
    print(f"  Bookmakers: {', '.join(sorted(set(m.bookmaker for m in markets)))}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
