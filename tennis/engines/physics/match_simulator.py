"""tennis.engines.physics.match_simulator

Physics-style tennis simulator:
- canonical parameters are point win probabilities on serve for each player
  (pA_srv_point, pB_srv_point)
- we lift point -> hold probability -> game outcomes
- we simulate sets with correct server alternation and 6-6 tiebreaks

This intentionally avoids external deps (numpy/scipy) and is optimized for
robustness and auditability over raw speed.
"""

from __future__ import annotations

from dataclasses import dataclass
import random
from typing import Dict, List, Literal, Tuple

from .hold_math import hold_probability

PlayerKey = Literal["A", "B"]


def _other(p: PlayerKey) -> PlayerKey:
    return "B" if p == "A" else "A"


@dataclass(frozen=True)
class MatchSample:
    # Set-level outcomes
    sets_a: int
    sets_b: int

    # Game-level outcomes
    games_a: int
    games_b: int
    total_games: int
    first_set_total_games: int
    first_set_games_a: int
    first_set_games_b: int

    # Service games (used to scale aces/DF)
    service_games_a: int
    service_games_b: int

    # Tiebreak indicator
    had_tiebreak: bool


def _simulate_tiebreak(
    first_server: PlayerKey,
    pA_srv_point: float,
    pB_srv_point: float,
    rng: random.Random,
) -> Tuple[PlayerKey, PlayerKey]:
    """Simulate a 7-point tiebreak (win by 2).

    Returns:
        (winner, next_set_first_server)

    Rule implemented:
    - First point served by first_server
    - Then serve alternates in blocks of 2
    - Next set begins with the player who *received* the first point,
      i.e. the opposite of first_server.
    """

    pts_a = 0
    pts_b = 0

    def point_win_prob(server: PlayerKey) -> float:
        return pA_srv_point if server == "A" else pB_srv_point

    point_idx = 0
    server = first_server

    while True:
        p_srv = point_win_prob(server)
        if rng.random() < p_srv:
            # server wins point
            if server == "A":
                pts_a += 1
            else:
                pts_b += 1
        else:
            # returner wins point
            if server == "A":
                pts_b += 1
            else:
                pts_a += 1

        point_idx += 1

        if (pts_a >= 7 or pts_b >= 7) and abs(pts_a - pts_b) >= 2:
            winner: PlayerKey = "A" if pts_a > pts_b else "B"
            next_set_first = _other(first_server)
            return winner, next_set_first

        # Service order: 1, then 2,2,2,...
        if point_idx == 1:
            server = _other(server)
        else:
            # Switch server every 2 points after the first.
            if (point_idx - 1) % 2 == 0:
                server = _other(server)


def _simulate_set(
    first_server: PlayerKey,
    p_hold_a: float,
    p_hold_b: float,
    pA_srv_point: float,
    pB_srv_point: float,
    rng: random.Random,
    tiebreak: bool = True,
) -> Tuple[int, int, int, int, PlayerKey, bool]:
    """Simulate a single set.

    Returns:
        (games_a, games_b, service_games_a, service_games_b, next_set_first_server, had_tiebreak)
    """

    ga = 0
    gb = 0
    sga = 0
    sgb = 0

    server = first_server
    had_tb = False

    while True:
        if server == "A":
            sga += 1
            if rng.random() < p_hold_a:
                ga += 1
            else:
                gb += 1
        else:
            sgb += 1
            if rng.random() < p_hold_b:
                gb += 1
            else:
                ga += 1

        # Check normal set end
        if (ga >= 6 or gb >= 6) and abs(ga - gb) >= 2:
            next_first = _other(server)  # next game server after last game would be the other
            return ga, gb, sga, sgb, next_first, had_tb

        # Tiebreak at 6-6
        if tiebreak and ga == 6 and gb == 6:
            had_tb = True
            tb_winner, next_first = _simulate_tiebreak(server, pA_srv_point, pB_srv_point, rng)
            if tb_winner == "A":
                ga += 1
            else:
                gb += 1
            return ga, gb, sga, sgb, next_first, had_tb

        # Otherwise next game
        server = _other(server)


def simulate_match_best_of_3(
    pA_srv_point: float,
    pB_srv_point: float,
    rng: random.Random | None = None,
    *,
    tiebreak: bool = True,
) -> MatchSample:
    """Simulate a best-of-3 match.

    Args:
        pA_srv_point: P(A wins a point on A serve)
        pB_srv_point: P(B wins a point on B serve)

    Returns:
        MatchSample with set/game totals.
    """

    r = rng or random.Random()

    p_hold_a = hold_probability(pA_srv_point)
    p_hold_b = hold_probability(pB_srv_point)

    # Randomize first server (unknown pre-match for most prop contexts)
    first_server: PlayerKey = "A" if r.random() < 0.5 else "B"

    sets_a = 0
    sets_b = 0
    games_a = 0
    games_b = 0
    sga_total = 0
    sgb_total = 0
    first_set_total_games = 0
    first_set_games_a = 0
    first_set_games_b = 0
    had_tb = False

    next_set_first = first_server
    set_idx = 0

    while sets_a < 2 and sets_b < 2:
        set_idx += 1
        ga, gb, sga, sgb, next_set_first, set_had_tb = _simulate_set(
            next_set_first,
            p_hold_a,
            p_hold_b,
            pA_srv_point,
            pB_srv_point,
            r,
            tiebreak=tiebreak,
        )
        had_tb = had_tb or set_had_tb

        games_a += ga
        games_b += gb
        sga_total += sga
        sgb_total += sgb

        if set_idx == 1:
            first_set_total_games = ga + gb
            first_set_games_a = ga
            first_set_games_b = gb

        if ga > gb:
            sets_a += 1
        else:
            sets_b += 1

    return MatchSample(
        sets_a=sets_a,
        sets_b=sets_b,
        games_a=games_a,
        games_b=games_b,
        total_games=games_a + games_b,
        first_set_total_games=first_set_total_games,
        first_set_games_a=first_set_games_a,
        first_set_games_b=first_set_games_b,
        service_games_a=sga_total,
        service_games_b=sgb_total,
        had_tiebreak=had_tb,
    )


def summarize_samples(samples: List[MatchSample]) -> Dict[str, float]:
    """Compute means for common match stats."""

    if not samples:
        return {}

    n = float(len(samples))
    return {
        "mean_total_games": sum(s.total_games for s in samples) / n,
        "mean_games_a": sum(s.games_a for s in samples) / n,
        "mean_games_b": sum(s.games_b for s in samples) / n,
        "mean_sets_a": sum(s.sets_a for s in samples) / n,
        "mean_sets_b": sum(s.sets_b for s in samples) / n,
        "mean_first_set_total_games": sum(s.first_set_total_games for s in samples) / n,
        "mean_first_set_games_a": sum(s.first_set_games_a for s in samples) / n,
        "mean_first_set_games_b": sum(s.first_set_games_b for s in samples) / n,
        "p_tiebreak": sum(1.0 for s in samples if s.had_tiebreak) / n,
    }
