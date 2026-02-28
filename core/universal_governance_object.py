"""
UNIVERSAL GOVERNANCE OBJECT (UGO) v1.0
======================================

**THE KEYSTONE**: Every sport MUST output edges in this format.

This is the mathematical language that enables:
- ESS (Edge Stability Score)
- FAS (Failure Attribution Schema)
- Cross-sport portfolio optimization
- Kelly criterion
- Calibration tracking

WITHOUT THIS: Sports are isolated, governance is decorative, portfolio theory is impossible.
WITH THIS: System becomes institutionalgrade quant operation.

PHILOSOPHY:
- Schema is immutable after v1.0 lock
- Sport-specific metadata goes in `sport_context` dict
- All probability calculations MUST produce these core fields
- edge_std (z-score) is THE universal comparability metric

GOVERNANCE RULE:
If a sport cannot produce edge_std, confidence, and stability_tags,
it is NOT ready for governance integration.
"""

from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, List, Literal
from datetime import datetime
from enum import Enum
import hashlib
import json


# =============================================================================
# ENUMS (Cross-Sport Constants)
# =============================================================================

class Sport(str, Enum):
    """Supported sports."""
    NBA = "NBA"
    CBB = "CBB"
    NFL = "NFL"
    TENNIS = "TENNIS"
    SOCCER = "SOCCER"
    GOLF = "GOLF"


class Direction(str, Enum):
    """Universal direction terminology."""
    HIGHER = "HIGHER"  # Over, More, Yes
    LOWER = "LOWER"    # Under, Less, No


class Tier(str, Enum):
    """Universal tier system (from config/thresholds.py)."""
    SLAM = "SLAM"      # 80%+ (82% tennis, disabled CBB)
    STRONG = "STRONG"  # 65%+ (68% tennis, 70% CBB)
    LEAN = "LEAN"      # 55%+ (58% tennis, 60% CBB)
    AVOID = "AVOID"    # <55%


class PickState(str, Enum):
    """Governance state machine."""
    RAW = "RAW"                    # Fresh from model
    ADJUSTED = "ADJUSTED"          # After context/penalties
    VETTED = "VETTED"              # Context only, NOT optimizable
    OPTIMIZABLE = "OPTIMIZABLE"    # Enters Monte Carlo
    REJECTED = "REJECTED"          # Hidden from all outputs


class StabilityTag(str, Enum):
    """ESS-compatible stability indicators."""
    HIGH_VARIANCE = "HIGH_VARIANCE"              # σ/μ > threshold
    LOW_SAMPLE = "LOW_SAMPLE"                    # n < 5 games
    ROLE_UNCERTAINTY = "ROLE_UNCERTAINTY"        # Rotation flux
    FRAGILE = "FRAGILE"                          # ESS < threshold
    BENCH_MICROWAVE = "BENCH_MICROWAVE"          # 80%+ bench minutes
    SPECIALIST_CAP = "SPECIALIST_CAP"            # Confidence capped
    BLOWOUT_RISK = "BLOWOUT_RISK"                # High probability garbage time
    MINUTE_VOLATILITY = "MINUTE_VOLATILITY"      # CV(minutes) > threshold
    WEATHER_IMPACT = "WEATHER_IMPACT"            # Weather affecting play (NFL)
    INJURY_DOWNGRADE = "INJURY_DOWNGRADE"        # Playing but limited
    USAGE_ENTROPY = "USAGE_ENTROPY"              # Target/carry uncertainty


# =============================================================================
# CORE UGO (Universal Governance Object)
# =============================================================================

@dataclass
class UniversalGovernanceObject:
    """
    THE UNIVERSAL EDGE FORMAT
    
    Every sport pipeline MUST produce edges in this format.
    This enables cross-sport governance, ESS, FAS, and portfolio optimization.
    
    CRITICAL FIELDS (Non-Negotiable):
    - mu: Player/outcome projection (stat anchor)
    - sigma: Standard deviation (uncertainty)
    - line: Prop line from book
    - edge_std: (mu - line) / sigma  ← Z-SCORE (universal comparability)
    - confidence: 0.0-1.0 (governance-adjusted probability)
    - stability_tags: ESS/FAS classification
    
    SPORT-SPECIFIC: Use sport_context dict for non-universal data.
    """
    
    # =========================================================================
    # IDENTITY (Required)
    # =========================================================================
    edge_id: str                    # Unique identifier (hash-based)
    sport: Sport                    # Sport enum
    game_id: str                    # Game/match identifier
    date: str                       # ISO 8601 date (YYYY-MM-DD)
    
    # =========================================================================
    # ENTITY (Required)
    # =========================================================================
    entity: str                     # Player/team name
    market: str                     # Stat type (PTS, REB, total_goals, etc.)
    line: float                     # Prop line from book
    direction: Direction            # HIGHER or LOWER
    
    # =========================================================================
    # STATISTICAL CORE (Required for ESS/FAS)
    # =========================================================================
    mu: float                       # Projection (stat anchor)
    sigma: float                    # Standard deviation
    edge_std: float                 # (mu - line) / sigma ← Z-SCORE
    sample_n: int                   # Games in sample (for confidence)
    
    # =========================================================================
    # GOVERNANCE (Required)
    # =========================================================================
    probability: float              # 0.0-1.0 (governance-adjusted)
    confidence: float               # 0.0-1.0 (certainty measure)
    tier: Tier                      # SLAM/STRONG/LEAN/AVOID
    pick_state: PickState           # RAW/ADJUSTED/VETTED/OPTIMIZABLE/REJECTED
    
    # =========================================================================
    # STABILITY (Required for ESS)
    # =========================================================================
    ess_score: Optional[float] = None           # Edge Stability Score
    stability_tags: List[StabilityTag] = field(default_factory=list)
    tail_risk: Optional[float] = None           # P(X < 0.5*mu) for HIGHER
    variance_penalty: Optional[float] = None    # CV-based penalty
    
    # =========================================================================
    # FAS (Failure Attribution Schema)
    # =========================================================================
    minute_stability: Optional[float] = None    # 0.0-1.0 (minute consistency)
    role_entropy: Optional[float] = None        # 0.0-1.0 (rotation flux)
    blowout_risk: Optional[float] = None        # 0.0-1.0 (garbage time prob)
    specialist_type: Optional[str] = None       # CATCH_SHOOT_3PM, BIG_MAN_3PM, etc.
    
    # =========================================================================
    # METADATA (Optional)
    # =========================================================================
    generated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    model_version: str = "UGO_v1.0"
    data_sources: List[str] = field(default_factory=list)
    blocked: bool = False
    block_reason: Optional[str] = None
    
    # =========================================================================
    # SPORT-SPECIFIC CONTEXT (Flexible Dict)
    # =========================================================================
    sport_context: Dict = field(default_factory=dict)
    """
    Sport-specific metadata that doesn't fit universal schema.
    Examples:
    - NBA: {"opponent": "LAL", "pace_adj": 1.05, "matchup_tier": "ELITE"}
    - Tennis: {"surface": "HARD", "opponent": "Federer", "best_of": 5}
    - Soccer: {"league": "EPL", "xg_home": 1.8, "xg_away": 1.2}
    - Golf: {"tournament": "Masters", "course_difficulty": 0.85}
    - NFL: {"weather": "rain", "home_field": True, "division_game": True}
    """
    
    def __post_init__(self):
        """Validate required fields and calculate derived values."""
        # Validate mu/sigma/line populated
        if self.mu is None or self.sigma is None or self.line is None:
            raise ValueError("mu, sigma, and line are required")
        
        # Auto-calculate edge_std if not provided
        if self.edge_std is None:
            if self.sigma == 0:
                raise ValueError("sigma cannot be 0")
            self.edge_std = (self.mu - self.line) / self.sigma
        
        # Validate probability/confidence in [0,1]
        if not (0.0 <= self.probability <= 1.0):
            raise ValueError(f"probability must be in [0,1], got {self.probability}")
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(f"confidence must be in [0,1], got {self.confidence}")
        
        # Validate sample_n >= 1
        if self.sample_n < 1:
            raise ValueError(f"sample_n must be >= 1, got {self.sample_n}")
    
    def to_dict(self) -> Dict:
        """Convert to dict with enum serialization."""
        data = asdict(self)
        # Convert enums to strings
        data['sport'] = self.sport.value
        data['direction'] = self.direction.value
        data['tier'] = self.tier.value
        data['pick_state'] = self.pick_state.value
        data['stability_tags'] = [tag.value for tag in self.stability_tags]
        return data
    
    def get_governance_hash(self) -> str:
        """Generate hash for governance tracking."""
        key_fields = f"{self.edge_id}::{self.mu:.2f}::{self.sigma:.2f}::{self.line:.2f}::{self.pick_state.value}"
        return hashlib.sha256(key_fields.encode()).hexdigest()[:16]
    
    def is_optimizable(self) -> bool:
        """Check if edge can enter Monte Carlo optimization."""
        return self.pick_state == PickState.OPTIMIZABLE and not self.blocked
    
    def is_vetted_only(self) -> bool:
        """Check if edge is vetted but not optimizable (context only)."""
        return self.pick_state == PickState.VETTED and not self.blocked
    
    def is_rejected(self) -> bool:
        """Check if edge is rejected."""
        return self.pick_state == PickState.REJECTED or self.blocked


# =============================================================================
# SPORT ADAPTERS (Convert Sport-Specific → UGO)
# =============================================================================

class SportAdapter:
    """Base class for sport-specific adapters."""
    
    def __init__(self, sport: Sport):
        self.sport = sport
    
    def adapt(self, sport_edge: Dict) -> UniversalGovernanceObject:
        """
        Convert sport-specific edge format to UGO.
        
        MUST BE IMPLEMENTED BY EACH SPORT.
        """
        raise NotImplementedError("Each sport must implement adapt()")
    
    def validate_required_fields(self, sport_edge: Dict, required: List[str]):
        """Validate sport edge has required fields."""
        missing = [f for f in required if f not in sport_edge]
        if missing:
            raise ValueError(f"{self.sport.value} edge missing required fields: {missing}")


class NBAAdapter(SportAdapter):
    """NBA → UGO adapter."""
    
    def __init__(self):
        super().__init__(Sport.NBA)
    
    def adapt(self, nba_edge: Dict) -> UniversalGovernanceObject:
        """Convert NBA risk_first_analyzer output to UGO."""
        self.validate_required_fields(nba_edge, ['player', 'stat', 'line', 'direction'])
        
        # NBA uses "higher"/"lower" strings
        direction = Direction.HIGHER if nba_edge['direction'].lower() == 'higher' else Direction.LOWER
        
        # Extract tier (may be "SLAM", "STRONG", "LEAN", or custom)
        tier_str = nba_edge.get('tier', 'AVOID').upper()
        try:
            tier = Tier[tier_str]
        except KeyError:
            tier = Tier.AVOID
        
        # Pick state from NBA logic
        pick_state = PickState[nba_edge.get('pick_state', 'RAW').upper()]
        
        # Stability tags from NBA system
        stability_tags = []
        for tag_str in nba_edge.get('stability_tags', []):
            try:
                stability_tags.append(StabilityTag[tag_str])
            except KeyError:
                pass  # Ignore unknown tags
        
        # Extract mu/sigma
        mu = float(nba_edge.get('mu', nba_edge.get('mean', 0)))
        sigma = float(nba_edge.get('sigma', nba_edge.get('std', 1)))
        line = float(nba_edge['line'])
        
        # Auto-calculate edge_std if not provided
        if 'edge_std' not in nba_edge or nba_edge['edge_std'] is None:
            edge_std = (mu - line) / sigma if sigma > 0 else 0.0
        else:
            edge_std = float(nba_edge['edge_std'])
        
        return UniversalGovernanceObject(
            edge_id=nba_edge.get('edge_id', f"NBA::{nba_edge['player']}::{nba_edge['stat']}::{nba_edge['line']}"),
            sport=Sport.NBA,
            game_id=nba_edge.get('game_id', ''),
            date=nba_edge.get('date', ''),
            entity=nba_edge['player'],
            market=nba_edge['stat'],
            line=line,
            direction=direction,
            mu=mu,
            sigma=sigma,
            edge_std=edge_std,
            sample_n=int(nba_edge.get('sample_n', nba_edge.get('n', 10))),
            probability=float(nba_edge.get('probability', 0.5)),
            confidence=float(nba_edge.get('confidence', nba_edge.get('probability', 0.5))),
            tier=tier,
            pick_state=pick_state,
            ess_score=nba_edge.get('ess_score'),
            stability_tags=stability_tags,
            tail_risk=nba_edge.get('tail_risk'),
            variance_penalty=nba_edge.get('variance_penalty'),
            minute_stability=nba_edge.get('minute_stability'),
            role_entropy=nba_edge.get('role_entropy'),
            blowout_risk=nba_edge.get('blowout_risk'),
            specialist_type=nba_edge.get('specialist_type'),
            data_sources=nba_edge.get('data_sources', ['espn', 'nba_api']),
            blocked=nba_edge.get('blocked', False),
            block_reason=nba_edge.get('block_reason'),
            sport_context={
                'opponent': nba_edge.get('opponent', ''),
                'home_away': nba_edge.get('home_away', ''),
                'pace_adj': nba_edge.get('pace_adj'),
                'defensive_rating': nba_edge.get('defensive_rating'),
                'rest_days': nba_edge.get('rest_days'),
                'b2b': nba_edge.get('b2b', False),
            }
        )


class SoccerAdapter(SportAdapter):
    """Soccer → UGO adapter."""
    
    def __init__(self):
        super().__init__(Sport.SOCCER)
    
    def adapt(self, soccer_edge: Dict) -> UniversalGovernanceObject:
        """
        Convert Soccer to UGO.
        
        CRITICAL FIX: Soccer currently uses inverted CDF (line - mean).
        This adapter STANDARDIZES to (mu - line) for governance compatibility.
        """
        self.validate_required_fields(soccer_edge, ['entity', 'market', 'line', 'direction'])
        
        # Soccer uses string directions
        direction = Direction.HIGHER if soccer_edge['direction'].upper() in ['OVER', 'HIGHER'] else Direction.LOWER
        
        # Extract mu from lambda/xG projection (MARKET-AWARE)
        xg_proj = soccer_edge.get('xg_projection', {})
        market = soccer_edge.get('market', 'total_goals').lower()
        
        # Market-aware mu calculation
        if market in ['total_goals', 'goals', 'over_under', 'total']:
            # Total goals = sum of both teams
            mu = xg_proj.get('home', 1.5) + xg_proj.get('away', 1.2)
        elif market in ['home_goals', 'team_goals_home']:
            mu = xg_proj.get('home', 1.5)
        elif market in ['away_goals', 'team_goals_away']:
            mu = xg_proj.get('away', 1.2)
        elif 'home' in soccer_edge.get('entity', '').lower():
            mu = xg_proj.get('home', 1.5)
        else:
            mu = xg_proj.get('away', 1.2)
        
        # Estimate sigma from Poisson variance (σ² ≈ λ for Poisson)
        # For total goals: σ² = σ²_home + σ²_away
        if market in ['total_goals', 'goals', 'over_under', 'total']:
            var_home = xg_proj.get('home', 1.5)
            var_away = xg_proj.get('away', 1.2)
            sigma = (var_home + var_away) ** 0.5
        else:
            sigma = mu ** 0.5 if mu > 0 else 1.0
        
        # CRITICAL: Standardize edge_std calculation
        line = float(soccer_edge['line'])
        edge_std = (mu - line) / sigma if sigma > 0 else 0.0
        
        # Sample size for soccer (match-based, not game-based)
        sample_n = soccer_edge.get('sample_n', 5)  # Assume 5 recent matches
        
        return UniversalGovernanceObject(
            edge_id=soccer_edge.get('edge_id', ''),
            sport=Sport.SOCCER,
            game_id=soccer_edge.get('game_id', ''),
            date=soccer_edge.get('date', ''),
            entity=soccer_edge['entity'],
            market=soccer_edge['market'],
            line=line,
            direction=direction,
            mu=mu,
            sigma=sigma,
            edge_std=edge_std,
            sample_n=sample_n,
            probability=float(soccer_edge.get('probability', 0.5)),
            confidence=float(soccer_edge.get('probability', 0.5)) * 0.9,  # Soccer penalty
            tier=Tier[soccer_edge.get('tier', 'AVOID').upper()],
            pick_state=PickState.OPTIMIZABLE if not soccer_edge.get('blocked') else PickState.REJECTED,
            stability_tags=[],  # Soccer doesn't have ESS yet
            data_sources=soccer_edge.get('data_sources', ['manual', 'xg']),
            blocked=soccer_edge.get('blocked', False),
            block_reason=soccer_edge.get('block_reason'),
            sport_context={
                'league': soccer_edge.get('league', ''),
                'match': soccer_edge.get('match', ''),
                'kickoff': soccer_edge.get('kickoff', ''),
                'xg_projection': xg_proj,
                'lambda_home': soccer_edge.get('lambda_home'),
                'lambda_away': soccer_edge.get('lambda_away'),
            }
        )


class CBBAdapter(SportAdapter):
    """CBB (College Basketball) → UGO adapter."""
    
    def __init__(self):
        super().__init__(Sport.CBB)
    
    def adapt(self, cbb_edge: Dict) -> UniversalGovernanceObject:
        """Convert CBB edge to UGO."""
        self.validate_required_fields(cbb_edge, ['player', 'stat', 'line', 'direction'])
        
        # CBB uses "higher"/"lower" or "over"/"under"
        direction_str = cbb_edge.get('direction', 'higher').lower()
        direction = Direction.HIGHER if direction_str in ['higher', 'over'] else Direction.LOWER
        
        # CBB uses 'mean' and 'std' instead of 'mu' and 'sigma'
        mu = float(cbb_edge.get('mu', cbb_edge.get('mean', 0)))
        sigma = float(cbb_edge.get('sigma', cbb_edge.get('std', 1)))
        line = float(cbb_edge['line'])
        
        # Auto-calculate edge_std if not provided
        if 'edge_std' not in cbb_edge or cbb_edge['edge_std'] is None:
            edge_std = (mu - line) / sigma if sigma > 0 else 0.0
        else:
            edge_std = float(cbb_edge['edge_std'])
        
        # CBB tier mapping (NO SLAM tier in CBB)
        tier_str = cbb_edge.get('tier', 'AVOID').upper()
        if tier_str == 'SLAM':
            tier = Tier.STRONG  # CBB doesn't have SLAM, downgrade
        else:
            try:
                tier = Tier[tier_str]
            except KeyError:
                tier = Tier.AVOID
        
        # Pick state
        pick_state_str = cbb_edge.get('pick_state', 'RAW').upper()
        try:
            pick_state = PickState[pick_state_str]
        except KeyError:
            pick_state = PickState.RAW
        
        return UniversalGovernanceObject(
            edge_id=cbb_edge.get('edge_id', f"CBB::{cbb_edge['player']}::{cbb_edge['stat']}::{line}"),
            sport=Sport.CBB,
            game_id=cbb_edge.get('game_id', ''),
            date=cbb_edge.get('date', ''),
            entity=cbb_edge['player'],
            market=cbb_edge['stat'],
            line=line,
            direction=direction,
            mu=mu,
            sigma=sigma,
            edge_std=edge_std,
            sample_n=int(cbb_edge.get('sample_n', cbb_edge.get('n', cbb_edge.get('games', 10)))),
            probability=float(cbb_edge.get('probability', 0.5)),
            confidence=float(cbb_edge.get('confidence', cbb_edge.get('probability', 0.5))),
            tier=tier,
            pick_state=pick_state,
            ess_score=cbb_edge.get('ess_score'),
            stability_tags=[],  # CBB doesn't have stability tags yet
            data_sources=cbb_edge.get('data_sources', ['espn', 'ncaa']),
            blocked=cbb_edge.get('blocked', False),
            block_reason=cbb_edge.get('block_reason'),
            sport_context={
                'opponent': cbb_edge.get('opponent', ''),
                'home_away': cbb_edge.get('home_away', ''),
                'conference': cbb_edge.get('conference', ''),
                'tempo': cbb_edge.get('tempo'),
                'defensive_efficiency': cbb_edge.get('defensive_efficiency'),
            }
        )


class NFLAdapter(SportAdapter):
    """NFL → UGO adapter."""
    
    def __init__(self):
        super().__init__(Sport.NFL)
    
    def adapt(self, nfl_edge: Dict) -> UniversalGovernanceObject:
        """Convert NFL edge to UGO."""
        self.validate_required_fields(nfl_edge, ['entity', 'market', 'line', 'direction'])
        
        # NFL uses 'more'/'less' or 'higher'/'lower'
        direction_str = nfl_edge.get('direction', 'higher').lower()
        direction = Direction.HIGHER if direction_str in ['higher', 'over', 'more'] else Direction.LOWER
        
        # NFL already uses mu/sigma from hydration
        mu = float(nfl_edge.get('mu', nfl_edge.get('mean', 0)))
        sigma = float(nfl_edge.get('sigma', nfl_edge.get('std', 1)))
        line = float(nfl_edge['line'])
        
        # Auto-calculate edge_std
        if 'edge_std' not in nfl_edge or nfl_edge['edge_std'] is None:
            edge_std = (mu - line) / sigma if sigma > 0 else 0.0
        else:
            edge_std = float(nfl_edge['edge_std'])
        
        # NFL tier
        tier_str = nfl_edge.get('tier', 'AVOID').upper()
        try:
            tier = Tier[tier_str]
        except KeyError:
            tier = Tier.AVOID
        
        # Pick state
        pick_state = PickState.OPTIMIZABLE if not nfl_edge.get('blocked') else PickState.REJECTED
        
        return UniversalGovernanceObject(
            edge_id=nfl_edge.get('edge_id', f"NFL::{nfl_edge.get('entity')}::{nfl_edge.get('market')}::{line}"),
            sport=Sport.NFL,
            game_id=nfl_edge.get('game_id', ''),
            date=nfl_edge.get('date', ''),
            entity=nfl_edge.get('entity', nfl_edge.get('player', '')),
            market=nfl_edge['market'],
            line=line,
            direction=direction,
            mu=mu,
            sigma=sigma,
            edge_std=edge_std,
            sample_n=int(nfl_edge.get('sample_n', nfl_edge.get('n', 10))),
            probability=float(nfl_edge.get('probability', 0.5)),
            confidence=float(nfl_edge.get('confidence', nfl_edge.get('probability', 0.5))),
            tier=tier,
            pick_state=pick_state,
            ess_score=nfl_edge.get('ess_score'),
            stability_tags=[],  # NFL stability tags TBD
            data_sources=nfl_edge.get('data_sources', ['nflverse', 'espn']),
            blocked=nfl_edge.get('blocked', False),
            block_reason=nfl_edge.get('block_reason'),
            sport_context={
                'opponent': nfl_edge.get('opponent', ''),
                'home_away': nfl_edge.get('home_away', ''),
                'weather': nfl_edge.get('weather', ''),
                'week': nfl_edge.get('week'),
                'season': nfl_edge.get('season'),
                'injury_status': nfl_edge.get('injury_status', ''),
            }
        )


class TennisAdapter(SportAdapter):
    """Tennis → UGO adapter."""
    
    def __init__(self):
        super().__init__(Sport.TENNIS)
    
    def adapt(self, tennis_edge: Dict) -> UniversalGovernanceObject:
        """Convert Tennis edge to UGO."""
        self.validate_required_fields(tennis_edge, ['market', 'line', 'direction'])
        
        # Tennis uses 'OVER'/'UNDER' or 'HIGHER'/'LOWER'
        direction_str = tennis_edge.get('direction', 'OVER').upper()
        direction = Direction.HIGHER if direction_str in ['OVER', 'HIGHER'] else Direction.LOWER
        
        # Tennis entity can be player or match
        entity = tennis_edge.get('player', tennis_edge.get('entity', ''))
        if not entity and 'players' in tennis_edge:
            entity = ' vs '.join(tennis_edge['players'])
        
        # Tennis probability-based (use features for mu/sigma estimation)
        features = tennis_edge.get('features', {})
        
        # For player props (aces, games won, etc.)
        if 'E_aces' in features:
            mu = features['E_aces']
            sigma = features.get('std_dev', mu * 0.25)
        elif 'E_games_won' in features:
            mu = features['E_games_won']
            sigma = features.get('std_dev', mu * 0.20)
        elif 'prediction' in tennis_edge:
            mu = tennis_edge['prediction']
            sigma = features.get('std_dev', mu * 0.25)
        else:
            # Fallback: estimate from probability
            prob = tennis_edge.get('probability', 0.5)
            line = float(tennis_edge['line'])
            # Reverse engineer mu from normal CDF
            # Very rough approximation
            mu = line + (1.0 if prob > 0.5 else -1.0)
            sigma = 1.0
        
        line = float(tennis_edge['line'])
        edge_std = (mu - line) / sigma if sigma > 0 else 0.0
        
        # Tennis tier
        tier_str = tennis_edge.get('tier', 'AVOID').upper()
        try:
            tier = Tier[tier_str]
        except KeyError:
            tier = Tier.AVOID
        
        # Pick state
        pick_state = PickState.OPTIMIZABLE if not tennis_edge.get('blocked') else PickState.REJECTED
        
        return UniversalGovernanceObject(
            edge_id=tennis_edge.get('edge_id', f"TENNIS::{entity}::{tennis_edge['market']}::{line}"),
            sport=Sport.TENNIS,
            game_id=tennis_edge.get('game_id', ''),
            date=tennis_edge.get('date', ''),
            entity=entity,
            market=tennis_edge['market'],
            line=line,
            direction=direction,
            mu=mu,
            sigma=sigma,
            edge_std=edge_std,
            sample_n=int(features.get('sample_n', tennis_edge.get('recent_matches', 10))),
            probability=float(tennis_edge.get('probability', 0.5)),
            confidence=float(tennis_edge.get('probability', 0.5)),
            tier=tier,
            pick_state=pick_state,
            ess_score=tennis_edge.get('ess_score'),
            stability_tags=[],  # Tennis stability tags TBD
            data_sources=tennis_edge.get('sources', ['tennis_abstract', 'atp']),
            blocked=tennis_edge.get('blocked', False),
            block_reason=tennis_edge.get('block_reason'),
            sport_context={
                'opponent': tennis_edge.get('opponent', ''),
                'surface': tennis_edge.get('surface', 'HARD'),
                'best_of': tennis_edge.get('best_of', 3),
                'tournament': tennis_edge.get('tournament', ''),
                'round': tennis_edge.get('round', ''),
            }
        )


class GolfAdapter(SportAdapter):
    """
    Golf → UGO adapter.
    
    HYBRID APPROACH:
    - Primary: Multiplier-based market efficiency
    - Shadow: Performance anchor (SG:Total, xStrokes)
    
    This preserves golf's pricing edge while enabling FAS/ESS.
    """
    
    def __init__(self):
        super().__init__(Sport.GOLF)
    
    def adapt(self, golf_edge: Dict) -> UniversalGovernanceObject:
        """Convert Golf multiplier edge to UGO with shadow anchor."""
        self.validate_required_fields(golf_edge, ['player', 'market', 'line'])
        
        # Golf direction from recommended_direction
        direction_str = golf_edge.get('recommended_direction', golf_edge.get('direction', 'higher'))
        direction = Direction.HIGHER if direction_str.lower() in ['higher', 'better'] else Direction.LOWER
        
        # SHADOW ANCHOR: Use SG:Total or xStrokes as μ
        sg_total = golf_edge.get('sg_total', 0.0)  # Strokes Gained Total
        baseline_score = golf_edge.get('course_baseline', 72.0)  # Par
        market = golf_edge.get('market', '').lower()
        
        # Market-aware mu calculation
        if 'finishing' in market or 'position' in market:
            # Finishing position: LOWER number is BETTER
            # Line is position (e.g., 10.5 = top 10.5 finish)
            # Don't convert to score — use position directly
            mu = golf_edge.get('avg_finish', 15.0)  # Average finishing position
        else:
            # Score-based markets (scoring, strokes, etc.)
            mu = baseline_score - sg_total  # Lower score = better
        
        # Sigma from SG variance or historical position variance
        if 'finishing' in market or 'position' in market:
            sigma = golf_edge.get('finish_std', 5.0)  # Position variance
        else:
            sigma = abs(sg_total * 0.3) if sg_total != 0 else 2.0  # Score variance
        
        # Edge std (z-score) — MARKET-AWARE
        line = float(golf_edge.get('line', mu))
        if 'finishing' in market or 'position' in market:
            # Finishing position: Better finish = LOWER number
            # So if mu=8.5 and line=10.5, mu is BETTER (edge_std positive)
            edge_std = (line - mu) / sigma if sigma > 0 else 0.0  # INVERTED
        else:
            # Score-based: Standard formula
            edge_std = (mu - line) / sigma if sigma > 0 else 0.0
        
        # Probability from multiplier edge
        prob = float(golf_edge.get('implied_prob_higher', 0.5))
        if direction == Direction.LOWER:
            prob = float(golf_edge.get('implied_prob_lower', 0.5))
        
        # Confidence from golf confidence tags
        confidence_map = {"HIGH": 0.75, "MEDIUM": 0.60, "LOW": 0.45}
        confidence = confidence_map.get(golf_edge.get('confidence', 'MEDIUM'), 0.60)
        
        return UniversalGovernanceObject(
            edge_id=golf_edge.get('edge_id', f"GOLF::{golf_edge['player']}::{golf_edge['market']}::{line}"),
            sport=Sport.GOLF,
            game_id=golf_edge.get('tournament', ''),
            date=golf_edge.get('date', ''),
            entity=golf_edge['player'],
            market=golf_edge['market'],
            line=line,
            direction=direction,
            mu=mu,  # Shadow anchor
            sigma=sigma,
            edge_std=edge_std,
            sample_n=int(golf_edge.get('sample_n', 10)),  # Rounds
            probability=prob,
            confidence=confidence,
            tier=Tier.LEAN,  # Golf defaults to LEAN (no SLAM)
            pick_state=PickState.OPTIMIZABLE,
            stability_tags=[],  # Golf stability TBD
            data_sources=['datagolf', 'pga_tour'],
            blocked=False,
            sport_context={
                'tournament': golf_edge.get('tournament', ''),
                'round_num': golf_edge.get('round_num'),
                'tee_time': golf_edge.get('tee_time', ''),
                'higher_mult': golf_edge.get('higher_mult'),
                'lower_mult': golf_edge.get('lower_mult'),
                'better_mult': golf_edge.get('better_mult'),
                'multiplier_edge': golf_edge.get('multiplier_edge'),
                'sg_total': sg_total,
                'course_difficulty': golf_edge.get('course_difficulty'),
            }
        )


# =============================================================================
# ADAPTER REGISTRY
# =============================================================================

SPORT_ADAPTERS: Dict[Sport, SportAdapter] = {
    Sport.NBA: NBAAdapter(),
    Sport.CBB: CBBAdapter(),
    Sport.NFL: NFLAdapter(),
    Sport.TENNIS: TennisAdapter(),
    Sport.SOCCER: SoccerAdapter(),
    Sport.GOLF: GolfAdapter(),
}


def adapt_edge(sport: Sport, sport_edge: Dict) -> UniversalGovernanceObject:
    """
    Universal adapter dispatcher.
    
    Usage:
        nba_edge = {...}  # from risk_first_analyzer
        ugo = adapt_edge(Sport.NBA, nba_edge)
        
        # Now ugo is governance-ready for ESS/FAS/portfolio
    """
    adapter = SPORT_ADAPTERS.get(sport)
    if adapter is None:
        raise ValueError(f"No adapter registered for {sport.value}")
    return adapter.adapt(sport_edge)


# =============================================================================
# VALIDATION
# =============================================================================

def validate_ugo(ugo: UniversalGovernanceObject) -> tuple[bool, Optional[str]]:
    """
    Validate UGO meets governance requirements.
    
    Returns:
        (is_valid, error_message)
    """
    # Check required fields
    if ugo.mu is None:
        return False, "mu (projection) is required"
    if ugo.sigma is None or ugo.sigma <= 0:
        return False, "sigma must be > 0"
    if ugo.edge_std is None:
        return False, "edge_std (z-score) is required"
    if ugo.sample_n < 1:
        return False, "sample_n must be >= 1"
    
    # Check probability/confidence range
    if not (0.0 <= ugo.probability <= 1.0):
        return False, f"probability {ugo.probability} out of range [0,1]"
    if not (0.0 <= ugo.confidence <= 1.0):
        return False, f"confidence {ugo.confidence} out of range [0,1]"
    
    # ESS/stability tags are optional (can be calculated later)
    # Removed strict requirement for OPTIMIZABLE picks
    
    return True, None


# =============================================================================
# EXAMPLE USAGE
# =============================================================================

if __name__ == "__main__":
    # Example: NBA edge → UGO
    nba_edge_example = {
        'player': 'LeBron James',
        'stat': 'PTS',
        'line': 25.5,
        'direction': 'higher',
        'mu': 28.3,
        'sigma': 4.2,
        'sample_n': 10,
        'probability': 0.72,
        'tier': 'STRONG',
        'pick_state': 'OPTIMIZABLE',
        'edge_id': 'NBA::LeBron_James::PTS::25.5',
        'game_id': 'LAL_vs_GSW_20260201',
        'date': '2026-02-01',
        'ess_score': 0.68,
        'stability_tags': ['HIGH_VARIANCE'],
        'opponent': 'GSW',
        'home_away': 'HOME',
    }
    
    ugo = adapt_edge(Sport.NBA, nba_edge_example)
    print("✅ UGO Created:")
    print(json.dumps(ugo.to_dict(), indent=2))
    
    # Validate
    is_valid, error = validate_ugo(ugo)
    print(f"\n{'✅' if is_valid else '❌'} Validation: {error or 'PASS'}")
    
    # Governance checks
    print(f"\nOptimizable: {ugo.is_optimizable()}")
    print(f"Governance Hash: {ugo.get_governance_hash()}")
