"""tennis/player_context_memory.py

Persistent player context memory for tennis analysis.

Purpose:
  - Enriches edge output with opponent, H2H, ranking, serve/return stats
  - Maintains a persistent memory file so future runs recall prior context
  - Provides AI-ready context bundles for narrative generation

Architecture:
  Layer 1 (Truth Engine) — data lives here, immutable
  Layer 2 (LLM Adapters) — can read this, never overrides probabilities
  Layer 3 (Render) — uses this for reports/Telegram narratives

Usage:
  from tennis.player_context_memory import MatchContextBuilder
  builder = MatchContextBuilder(profiler)
  ctx = builder.build_match_context("Swiatek", "Tjen", surface="Hard")
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


# ──────────────────────────────────────────────────────────────────────
# DATA CLASSES
# ──────────────────────────────────────────────────────────────────────

@dataclass
class PlayerSnapshot:
    """Compact player context for a single analysis run."""
    name: str
    ranking: Optional[int] = None
    elo_overall: Optional[float] = None
    elo_surface: Optional[float] = None
    win_rate: Optional[float] = None
    surface_win_rate: Optional[float] = None
    serve_hold_rate: Optional[float] = None
    bp_save_rate: Optional[float] = None
    avg_aces: Optional[float] = None
    avg_double_faults: Optional[float] = None
    avg_games_won: Optional[float] = None
    n_matches: int = 0
    player_style: Optional[str] = None          # big_server / baseliner / all_court
    surface_specialist: Optional[str] = None     # DOMINANT / STRONG / AVERAGE / WEAK
    recent_form_l10: Optional[float] = None      # L10 win rate
    ace_pct_l10: Optional[float] = None
    hold_pct_l10: Optional[float] = None


@dataclass
class HeadToHead:
    """Head-to-head record between two players."""
    player1: str
    player2: str
    total_matches: int = 0
    p1_wins: int = 0
    p2_wins: int = 0
    last_match_date: Optional[str] = None
    last_match_surface: Optional[str] = None
    last_match_score: Optional[str] = None
    history: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class MatchContext:
    """Full context for a single match — saved with every edge."""
    player: PlayerSnapshot
    opponent: Optional[PlayerSnapshot] = None
    head_to_head: Optional[HeadToHead] = None
    surface: str = "Hard"
    tournament: Optional[str] = None
    tournament_tier: Optional[str] = None       # GRAND_SLAM / MASTERS / 500 / 250
    round_name: Optional[str] = None
    commence_time: Optional[str] = None
    matchup_edge: Optional[str] = None          # who has style edge
    narrative_seed: Optional[str] = None        # one-liner for AI to expand

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for JSON output."""
        d: Dict[str, Any] = {}
        d["player"] = asdict(self.player) if self.player else None
        d["opponent"] = asdict(self.opponent) if self.opponent else None
        d["head_to_head"] = asdict(self.head_to_head) if self.head_to_head else None
        d["surface"] = self.surface
        d["tournament"] = self.tournament
        d["tournament_tier"] = self.tournament_tier
        d["round_name"] = self.round_name
        d["commence_time"] = self.commence_time
        d["matchup_edge"] = self.matchup_edge
        d["narrative_seed"] = self.narrative_seed
        return d


# ──────────────────────────────────────────────────────────────────────
# MEMORY FILE — persistent across runs
# ──────────────────────────────────────────────────────────────────────

_MEMORY_DIR = Path(__file__).resolve().parent / "data"
_MEMORY_FILE = _MEMORY_DIR / "player_context_memory.json"


def _load_memory() -> Dict[str, Any]:
    """Load persistent player context memory."""
    if _MEMORY_FILE.exists():
        try:
            return json.loads(_MEMORY_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_memory(mem: Dict[str, Any]) -> None:
    """Save persistent player context memory."""
    _MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    _MEMORY_FILE.write_text(
        json.dumps(mem, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )


def recall_player(player_name: str) -> Optional[Dict[str, Any]]:
    """Recall prior context for a player from memory."""
    mem = _load_memory()
    key = player_name.strip().lower()
    return mem.get("players", {}).get(key)


def store_player_context(player_name: str, ctx: Dict[str, Any]) -> None:
    """Store/update player context in memory."""
    mem = _load_memory()
    if "players" not in mem:
        mem["players"] = {}
    key = player_name.strip().lower()
    existing = mem["players"].get(key, {})
    existing.update(ctx)
    existing["last_updated"] = datetime.now().isoformat()
    mem["players"][key] = existing
    _save_memory(mem)


# ──────────────────────────────────────────────────────────────────────
# CONTEXT BUILDER — attaches to simulation output
# ──────────────────────────────────────────────────────────────────────

class MatchContextBuilder:
    """Builds rich match context from existing data sources."""

    def __init__(self, profiler=None, player_stats: Optional[Dict] = None):
        self.profiler = profiler
        self._player_stats = player_stats or self._load_player_stats_json()

    def _load_player_stats_json(self) -> Dict:
        ps_path = Path(__file__).resolve().parent / "data" / "player_stats.json"
        if ps_path.exists():
            try:
                return json.loads(ps_path.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    def _find_player_stats(self, name: str) -> Optional[Dict]:
        """Look up player in player_stats.json (case-insensitive)."""
        if not self._player_stats:
            return None
        ps = self._player_stats.get(name)
        if ps:
            return ps
        key = name.strip().lower()
        for k, v in self._player_stats.items():
            if isinstance(k, str) and k.strip().lower() == key:
                return v
        return None

    def build_player_snapshot(
        self, name: str, surface: str = "Hard", profile=None
    ) -> PlayerSnapshot:
        """Build a snapshot from all available sources."""
        snap = PlayerSnapshot(name=name)

        # Source 1: TennisPlayerProfile (from DB)
        if profile is not None:
            snap.win_rate = getattr(profile, "win_rate", None)
            snap.serve_hold_rate = getattr(profile, "serve_hold_rate", None)
            snap.bp_save_rate = getattr(profile, "bp_save_rate", None)
            snap.avg_aces = getattr(profile, "avg_aces", None)
            snap.avg_double_faults = getattr(profile, "avg_double_faults", None)
            snap.avg_games_won = getattr(profile, "avg_games_won", None)
            snap.n_matches = getattr(profile, "n_matches", 0)

            # Surface-specific win rate
            surf_lower = (surface or "hard").lower()
            snap.surface_win_rate = getattr(
                profile, f"{surf_lower}_win_rate", snap.win_rate
            )

        # Source 2: player_stats.json (ranking, Elo, L10 form)
        ps = self._find_player_stats(name)
        if ps and isinstance(ps, dict):
            snap.ranking = ps.get("ranking")
            snap.elo_overall = ps.get("elo_overall") or ps.get("elo")
            surf_key = (surface or "hard").lower()
            snap.elo_surface = ps.get(f"elo_{surf_key}", snap.elo_overall)
            snap.recent_form_l10 = ps.get("win_pct_L10")
            snap.ace_pct_l10 = ps.get("ace_pct_L10")
            snap.hold_pct_l10 = ps.get("hold_pct_L10")

            # Player style inference
            style = ps.get("player_style")
            if not style:
                ace_pct = ps.get("ace_pct", 0) or 0
                if ace_pct > 0.12:
                    style = "big_server"
                elif (ps.get("return_rating", 0) or 0) > 0.55:
                    style = "aggressive_returner"
                else:
                    style = "all_court"
            snap.player_style = style

        # Source 3: Previous memory (fill gaps)
        prior = recall_player(name)
        if prior and isinstance(prior, dict):
            if snap.ranking is None:
                snap.ranking = prior.get("ranking")
            if snap.player_style is None:
                snap.player_style = prior.get("player_style")

        return snap

    def build_head_to_head(self, player1: str, player2: str) -> HeadToHead:
        """Build H2H from profiler database."""
        h2h = HeadToHead(player1=player1, player2=player2)

        if self.profiler is None:
            return h2h

        try:
            raw_h2h = self.profiler.get_head_to_head(player1, player2)
            if raw_h2h and raw_h2h.get("matches", 0) > 0:
                h2h.total_matches = raw_h2h["matches"]
                h2h.p1_wins = raw_h2h.get("p1_wins", 0)
                h2h.p2_wins = raw_h2h.get("p2_wins", 0)
                history = raw_h2h.get("history", [])
                if history:
                    last = history[0]  # Most recent first (ORDER BY DESC)
                    h2h.last_match_date = last.get("match_date")
                    h2h.last_match_surface = last.get("surface")
                    h2h.last_match_score = last.get("score")
                    # Keep last 5 matches for context
                    h2h.history = [
                        {
                            "date": m.get("match_date"),
                            "tournament": m.get("tournament_name"),
                            "surface": m.get("surface"),
                            "score": m.get("score"),
                        }
                        for m in history[:5]
                    ]
        except Exception:
            pass

        return h2h

    def build_match_context(
        self,
        player_name: str,
        opponent_name: Optional[str] = None,
        surface: str = "Hard",
        player_profile=None,
        opponent_profile=None,
        commence_time: Optional[str] = None,
    ) -> MatchContext:
        """Build full match context for edge enrichment."""

        player_snap = self.build_player_snapshot(
            player_name, surface=surface, profile=player_profile
        )
        opponent_snap = None
        h2h = None
        matchup_edge = None
        narrative = None

        if opponent_name:
            opponent_snap = self.build_player_snapshot(
                opponent_name, surface=surface, profile=opponent_profile
            )
            h2h = self.build_head_to_head(player_name, opponent_name)

            # Determine matchup edge
            edges = []
            if player_snap.serve_hold_rate and opponent_snap.serve_hold_rate:
                if player_snap.serve_hold_rate > opponent_snap.serve_hold_rate:
                    edges.append(f"{player_name} serve edge")
                else:
                    edges.append(f"{opponent_name} serve edge")
            if player_snap.bp_save_rate and opponent_snap.bp_save_rate:
                if player_snap.bp_save_rate > opponent_snap.bp_save_rate:
                    edges.append(f"{player_name} clutch edge")
            if player_snap.elo_surface and opponent_snap.elo_surface:
                if player_snap.elo_surface > opponent_snap.elo_surface:
                    edges.append(f"{player_name} Elo edge on {surface}")
                else:
                    edges.append(f"{opponent_name} Elo edge on {surface}")
            matchup_edge = "; ".join(edges) if edges else None

            # Generate narrative seed
            narrative = self._generate_narrative_seed(
                player_snap, opponent_snap, h2h, surface
            )

        ctx = MatchContext(
            player=player_snap,
            opponent=opponent_snap,
            head_to_head=h2h,
            surface=surface,
            commence_time=commence_time,
            matchup_edge=matchup_edge,
            narrative_seed=narrative,
        )

        # Persist to memory for future recall
        store_player_context(player_name, {
            "ranking": player_snap.ranking,
            "elo_surface": player_snap.elo_surface,
            "win_rate": player_snap.win_rate,
            "player_style": player_snap.player_style,
            "surface_win_rate": player_snap.surface_win_rate,
            "last_surface_analyzed": surface,
            "last_opponent": opponent_name,
        })

        return ctx

    def _generate_narrative_seed(
        self,
        player: PlayerSnapshot,
        opponent: PlayerSnapshot,
        h2h: Optional[HeadToHead],
        surface: str,
    ) -> str:
        """Generate a one-liner narrative seed for AI expansion."""
        parts = []

        # Ranking context
        if player.ranking and opponent.ranking:
            if player.ranking < opponent.ranking:
                parts.append(f"#{player.ranking} {player.name} favored over #{opponent.ranking} {opponent.name}")
            else:
                parts.append(f"#{opponent.ranking} {opponent.name} ranked higher than #{player.ranking} {player.name}")

        # H2H context
        if h2h and h2h.total_matches > 0:
            parts.append(f"H2H: {h2h.p1_wins}-{h2h.p2_wins}")
            if h2h.last_match_date:
                parts.append(f"last met {h2h.last_match_date}")

        # Style matchup
        if player.player_style and opponent.player_style:
            if player.player_style != opponent.player_style:
                parts.append(f"{player.player_style} vs {opponent.player_style}")

        # Surface form
        if player.recent_form_l10 is not None:
            if player.recent_form_l10 >= 0.7:
                parts.append(f"{player.name} hot (L10: {player.recent_form_l10:.0%})")
            elif player.recent_form_l10 <= 0.3:
                parts.append(f"{player.name} cold (L10: {player.recent_form_l10:.0%})")

        return "; ".join(parts) if parts else f"{player.name} vs {opponent.name} on {surface}"
