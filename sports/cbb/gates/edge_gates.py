"""
CBB Edge Gates

Hard gates that block edges from being generated:
1. Roster Gate - Player must be on active roster
2. Minutes Gate - Player must average ≥20 MPG
3. Blowout Gate - Skip overs when spread >25 points
4. Games Played Gate - Minimum games for reliable data

Soft gates that apply penalties (in scoring phase):
- Role mismatch
- Conference mismatch
- Travel fatigue
- Public fade
"""

from typing import Dict, List, Tuple, Optional
from pathlib import Path
import yaml

# Gate thresholds (can be overridden by config)
DEFAULT_THRESHOLDS = {
    "min_mpg": 20.0,           # Legacy (unused in v2.2 — see direction-aware thresholds)
    "min_mpg_over": 18.0,      # v2.2: OVER requires 18+ MPG
    "min_mpg_under": 10.0,     # v2.2: UNDER only blocked if < 10 MPG (DNP risk)
    "min_games_played": 5,     # Minimum games for reliable stats
    "blowout_spread": 25.0,    # Skip overs when spread exceeds this
    "max_variance_ratio": 0.4, # Skip if std > mean * ratio
}


def load_gate_config() -> Dict:
    """Load gate configuration from YAML."""
    config_path = Path(__file__).parent.parent / "config" / "gate_thresholds.yaml"
    
    if config_path.exists():
        try:
            with open(config_path) as f:
                return yaml.safe_load(f) or {}
        except:
            pass
    
    return DEFAULT_THRESHOLDS


class CBBEdgeGates:
    """
    CBB-specific edge gates.
    
    All hard gates return: (passed: bool, reason: str)
    """
    
    def __init__(self):
        self.config = load_gate_config()
        self._data_provider = None
        self._offline = self._check_offline()
    
    @staticmethod
    def _check_offline() -> bool:
        import os
        return (os.environ.get("CBB_OFFLINE") or "").strip().lower() in ("1", "true", "yes")
    
    @property
    def data_provider(self):
        """Lazy load data provider."""
        if self._data_provider is None:
            from sports.cbb.ingest.cbb_data_provider import CBBDataProvider
            self._data_provider = CBBDataProvider()
        return self._data_provider
    
    def check_all_gates(self, prop: Dict, game_context: Optional[Dict] = None) -> Tuple[bool, List[str], List[str]]:
        """
        Run all hard gates on a prop.
        
        Returns: (all_passed, passed_gates, failed_gates)
        """
        passed_gates: List[str] = []
        failed_gates: List[str] = []
        gate_status: List[Dict[str, str]] = []
        
        player = prop.get("player", "")
        team = prop.get("team", "")
        stat = prop.get("stat", "")
        direction = prop.get("direction", "")
        line = prop.get("line", 0)
        
        # 1. Roster Gate
        passed, reason = self.roster_gate(player, team)
        if passed:
            passed_gates.append(f"roster: {reason}")
            gate_status.append({"gate": "roster", "status": "PASS", "reason": str(reason)})
        else:
            failed_gates.append(f"roster: {reason}")
            gate_status.append({"gate": "roster", "status": "FAIL", "reason": str(reason)})
        
        # 2. Minutes Gate (v2.2: direction-aware)
        passed, reason = self.minutes_gate(player, team, direction=direction)
        if passed:
            passed_gates.append(f"minutes: {reason}")
            status = "NO_DATA" if str(reason) == "NO_DATA" else "PASS"
            gate_status.append({"gate": "minutes", "status": status, "reason": str(reason)})
        else:
            failed_gates.append(f"minutes: {reason}")
            gate_status.append({"gate": "minutes", "status": "FAIL", "reason": str(reason)})
        
        # 3. Games Played Gate
        passed, reason = self.games_played_gate(player, team)
        if passed:
            passed_gates.append(f"games: {reason}")
            status = "NO_DATA" if str(reason) == "NO_DATA" else "PASS"
            gate_status.append({"gate": "games", "status": status, "reason": str(reason)})
        else:
            failed_gates.append(f"games: {reason}")
            gate_status.append({"gate": "games", "status": "FAIL", "reason": str(reason)})
        
        # 4. Blowout Gate (v3.0: direction-aware — applies to OVER and UNDER)
        if not game_context or game_context.get("spread") is None:
            # v2.0: spread missing is risk, not neutral
            passed_gates.append("blowout: NO_DATA")
            gate_status.append({"gate": "blowout", "status": "NO_DATA", "reason": "SPREAD_MISSING"})
        else:
            passed, reason = self.blowout_gate(game_context, direction=direction)
            if passed:
                passed_gates.append(f"blowout: {reason}")
                gate_status.append({"gate": "blowout", "status": "PASS", "reason": str(reason)})
            else:
                failed_gates.append(f"blowout: {reason}")
                gate_status.append({"gate": "blowout", "status": "FAIL", "reason": str(reason)})
        
        all_passed = len(failed_gates) == 0

        # Attach structured gate status for downstream reporting/scoring
        prop["gate_status"] = gate_status
        prop["has_no_data"] = any(gs.get("status") == "NO_DATA" for gs in gate_status)
        return all_passed, passed_gates, failed_gates
    
    def roster_gate(self, player_name: str, team_abbr: str) -> Tuple[bool, str]:
        """Check if player is on active roster."""
        from sports.cbb.gates.roster_gate import check_roster_gate
        return check_roster_gate(player_name, team_abbr)
    
    def minutes_gate(self, player_name: str, team_abbr: str, direction: str = "") -> Tuple[bool, str]:
        """Check if player averages enough minutes.
        
        v2.2: Direction-aware MPG gate.
        - HIGHER/OVER: requires MIN_MPG_FOR_OVER (18 MPG)
        - LOWER/UNDER: exempt unless MPG < 10 (DNP risk)
        
        Logic: Low-minute players are bad OVER bets but VALID UNDER bets.
        A bench player averaging 16 MPG with a points line at 17.5 is exactly
        the edge — low minutes = low stats = UNDER value.
        """
        min_mpg_over = self.config.get("min_mpg_over", 18.0)
        min_mpg_under = self.config.get("min_mpg_under", 10.0)
        
        # v3.0: Also check mpg_gate section from YAML
        mpg_cfg = self.config.get("mpg_gate", {})
        if mpg_cfg:
            min_mpg_over = mpg_cfg.get("min_mpg_for_over", min_mpg_over)
            min_mpg_under = mpg_cfg.get("min_mpg_for_under", min_mpg_under)
        
        if self._offline:
            return True, "OFFLINE_SKIP"
        
        try:
            mpg = self.data_provider.get_minutes_avg(player_name, team_abbr)
        except Exception:
            return True, "API_ERROR"
        
        if mpg is None:
            return True, "NO_DATA"
        
        dir_upper = (direction or "").upper()
        
        # LOWER/UNDER: exempt from MPG floor (only block DNP risk < 10 MPG)
        if dir_upper in ("LOWER", "UNDER"):
            if mpg < min_mpg_under:
                return False, f"MPG={mpg:.1f} < {min_mpg_under} (DNP risk even for UNDER)"
            return True, f"MPG={mpg:.1f} (UNDER exempt from MPG floor)"
        
        # HIGHER/OVER: requires minimum minutes
        if mpg < min_mpg_over:
            return False, f"MPG={mpg:.1f} < {min_mpg_over}"
        
        return True, f"MPG={mpg:.1f}"
    
    def games_played_gate(self, player_name: str, team_abbr: str) -> Tuple[bool, str]:
        """Check if player has enough games for reliable stats."""
        min_games = self.config.get("min_games_played", DEFAULT_THRESHOLDS["min_games_played"])
        
        if self._offline:
            return True, "OFFLINE_SKIP"
        
        try:
            player = self.data_provider.get_player_stats_by_name(player_name, team_abbr)
        except Exception:
            # ESPN API timeout/failure — allow gate to pass gracefully
            return True, "API_ERROR"
        
        if player is None:
            return True, "NO_DATA"
        
        if player.games_played < min_games:
            return False, f"GP={player.games_played} < {min_games}"
        
        return True, f"GP={player.games_played}"
    
    def blowout_gate(self, game_context: Dict, direction: str = "higher") -> Tuple[bool, str]:
        """Direction-aware blowout gate (v3.0).
        
        UNDER on underdog: Block if team is +6 or worse (star plays more).
        OVER on favorite:  Block if team is -15 or worse (star rests in blowout).
        
        Falls back to legacy flat threshold if blowout_gate section missing from config.
        """
        blowout_cfg = self.config.get("blowout_gate", {})
        spread = game_context.get("spread", 0)
        abs_spread = abs(spread)
        is_favorite = game_context.get("is_favorite", False)
        dir_upper = (direction or "").upper()

        # ---- v3.0 direction-aware logic ----
        if blowout_cfg:
            # UNDER on underdog
            if dir_upper in ("LOWER", "UNDER") and not is_favorite:
                rules = blowout_cfg.get("under_on_underdog", {})
                block_at = rules.get("block_if_spread_gte", 6)
                warn_at = rules.get("warn_if_spread_gte", 3)
                if abs_spread >= block_at:
                    return False, f"BLOWOUT_BLOCK: UNDER on +{abs_spread:.1f} underdog (≥{block_at})"
                if abs_spread >= warn_at:
                    game_context["blowout_warning"] = True

            # OVER on heavy favorite
            if dir_upper in ("HIGHER", "OVER") and is_favorite:
                rules = blowout_cfg.get("over_on_favorite", {})
                block_at = rules.get("block_if_spread_gte", 15)
                warn_at = rules.get("warn_if_spread_gte", 10)
                if abs_spread >= block_at:
                    return False, f"BLOWOUT_BLOCK: OVER on -{abs_spread:.1f} favorite (≥{block_at}, star rests)"
                if abs_spread >= warn_at:
                    game_context["blowout_warning"] = True

            return True, f"SPREAD={abs_spread:.1f}"

        # ---- Legacy flat threshold fallback ----
        threshold = self.config.get("blowout_spread", DEFAULT_THRESHOLDS["blowout_spread"])
        if abs_spread > threshold:
            return False, f"SPREAD={abs_spread:.1f} > {threshold}"
        
        return True, f"SPREAD={abs_spread:.1f}"
    
    def variance_gate(self, player_name: str, team_abbr: str, stat: str) -> Tuple[bool, str]:
        """Skip if stat variance is too high relative to mean."""
        max_ratio = self.config.get("max_variance_ratio", DEFAULT_THRESHOLDS["max_variance_ratio"])
        
        # Would need historical game logs to compute variance
        # For now, pass all
        return True, "VARIANCE_OK"


# Singleton instance
_gates = None

def get_gates() -> CBBEdgeGates:
    """Get singleton gates instance."""
    global _gates
    if _gates is None:
        _gates = CBBEdgeGates()
    return _gates


def apply_all_gates(props: List[Dict], game_contexts: Optional[Dict[str, Dict]] = None) -> List[Dict]:
    """
    Apply all gates to a list of props.
    
    Returns props with gates_passed and gates_failed populated.
    """
    gates = get_gates()
    game_contexts = game_contexts or {}
    
    results = []
    
    for prop in props:
        # Get game context if available
        game_key = f"{prop.get('team', '')}_{prop.get('opponent', '')}"
        game_context = game_contexts.get(game_key, {})
        
        # Run gates
        all_passed, passed, failed = gates.check_all_gates(prop, game_context)
        
        # Update prop
        prop_copy = prop.copy()
        prop_copy["gates_passed"] = passed
        prop_copy["gates_failed"] = failed
        prop_copy["gates_all_passed"] = all_passed
        
        results.append(prop_copy)
    
    return results
