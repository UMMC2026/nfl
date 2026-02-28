"""
Advanced Analysis Configuration System

Provides a unified configuration interface for all analysis parameters:
- Gate system (hard/soft/minimal)
- Probability models (Normal CDF, Empirical, Hybrid, GMM)
- Bayesian updating
- Correlation handling
- Kelly criterion edge calculation
- Portfolio balancing
- Confidence thresholds
"""

import json
import os
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Dict, Optional, List
from enum import Enum
from datetime import datetime

# =============================================================================
# PENALTY MODE CONFIGURATION (2026-01-29)
# =============================================================================
def _load_penalty_mode() -> dict:
    """Load penalty mode configuration."""
    config_path = Path(__file__).parent / "config" / "penalty_mode.json"
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        return config.get("active_mode_settings", {})
    except Exception:
        return {"master_penalties_off": False}

_PENALTY_MODE = _load_penalty_mode()

# Config file location
CONFIG_FILE = Path(__file__).parent / ".analysis_config.json"


class GateSystem(str, Enum):
    HARD = "hard"           # Block all violations
    SOFT = "soft"           # Graduated penalties (recommended)
    MINIMAL = "minimal"     # Only critical safety blocks
    NONE = "none"           # Raw model output (experimental)


class PenaltySeverity(str, Enum):
    CONSERVATIVE = "conservative"   # Heavy penalties (0.60/0.75/0.90)
    MEDIUM = "medium"               # Balanced (0.70/0.85/0.95)
    AGGRESSIVE = "aggressive"       # Light penalties (0.85/0.92/0.98)
    CUSTOM = "custom"               # Manual adjustment


class PortfolioBalance(str, Enum):
    OFF = "off"             # No balancing
    TEAM = "team"           # Diversify across teams
    GAME = "game"           # Diversify across games
    POSITION = "position"   # Diversify by player position


class ProbabilityModel(str, Enum):
    NORMAL_CDF = "normal_cdf"       # Fast, deterministic
    NEG_BINOMIAL = "neg_binomial"   # For count stats only
    EMPIRICAL = "empirical"         # Historical hit rate
    HYBRID = "hybrid"               # Blend model + empirical (recommended)
    GMM = "gmm"                     # Gaussian mixture (advanced)


class BayesianMode(str, Enum):
    OFF = "off"             # Use raw season stats
    STANDARD = "standard"   # Recent 10 games weighted
    AGGRESSIVE = "aggressive"  # Heavy recent weighting (L5 games)
    HIERARCHICAL = "hierarchical"  # Full Bayesian (slow, accurate)


class CorrelationModel(str, Enum):
    INDEPENDENT = "independent"     # No correlation penalty (λ=0)
    LAMBDA_FIXED = "lambda_fixed"   # Fixed 5% penalty (λ=0.05)
    LAMBDA_CALIBRATED = "lambda_calibrated"  # Empirical λ per team
    COPULA = "copula"               # Full dependency structure (advanced)


class EdgeCalculation(str, Enum):
    Z_SCORE = "z_score"     # Statistical significance
    RAW_EDGE = "raw_edge"   # μ - line difference
    KELLY = "kelly"         # Optimal bet sizing (recommended)
    SHARPE = "sharpe"       # Risk-adjusted returns


class MonteCarloMode(str, Enum):
    OFF = "off"             # No portfolio optimization
    FAST = "fast"           # 1k sims - quick approximation
    STANDARD = "standard"   # 10k sims - balanced
    EXACT = "exact"         # Poisson-binomial (recommended)
    GPU = "gpu"             # 100k sims (if available)


class MemoryPenalty(str, Enum):
    OFF = "off"             # Ignore player history
    RAW = "raw"             # Apply all historical penalties
    REGULARIZED = "regularized"  # Empirical Bayes shrinkage (recommended)
    ADAPTIVE = "adaptive"   # Learn from recent outcomes


class ConfidencePreset(str, Enum):
    CONSERVATIVE = "conservative"   # PLAY: 70%, LEAN: 60%, PASS: <60%
    STANDARD = "standard"           # PLAY: 65%, LEAN: 55%, PASS: <55%
    AGGRESSIVE = "aggressive"       # PLAY: 60%, LEAN: 52%, PASS: <52%
    CUSTOM = "custom"               # Set your own thresholds


# Penalty multipliers by severity level
PENALTY_MULTIPLIERS = {
    PenaltySeverity.CONSERVATIVE: {
        "composite_stat": 0.60,
        "elite_defense": 0.75,
        "role_mismatch": 0.90,
        "bench_player": 0.65,
        "b2b_fatigue": 0.85,
    },
    PenaltySeverity.MEDIUM: {
        "composite_stat": 0.70,
        "elite_defense": 0.85,
        "role_mismatch": 0.95,
        "bench_player": 0.75,
        "b2b_fatigue": 0.90,
    },
    PenaltySeverity.AGGRESSIVE: {
        "composite_stat": 0.85,
        "elite_defense": 0.92,
        "role_mismatch": 0.98,
        "bench_player": 0.88,
        "b2b_fatigue": 0.95,
    },
}

# Confidence thresholds by preset
CONFIDENCE_THRESHOLDS = {
    ConfidencePreset.CONSERVATIVE: {"play": 0.70, "lean": 0.60, "pass": 0.60},
    ConfidencePreset.STANDARD: {"play": 0.65, "lean": 0.55, "pass": 0.55},
    ConfidencePreset.AGGRESSIVE: {"play": 0.60, "lean": 0.52, "pass": 0.52},
}

# Lambda values for correlation
LAMBDA_VALUES = {
    CorrelationModel.INDEPENDENT: 0.0,
    CorrelationModel.LAMBDA_FIXED: 0.05,
    CorrelationModel.LAMBDA_CALIBRATED: None,  # Computed per team
}

# Stat-specific confidence multipliers (based on calibration backtest)
# Backtest: points=45.9%, 3pm=43.8%, assists=77.8%, rebounds=61.5%, combos=75%
#
# ⚠️  DEPRECATED: These hardcoded values should be replaced with calibration-based
#    adjustments. See: engine/stat_adjustment_deprecation.py
#    These are kept for backwards compatibility but should not be used for new code.
#
STAT_CONFIDENCE_MULTIPLIERS = {
    # UNDERWATER stats - penalize
    "points": 0.85,           # 45.9% hit rate -> penalize 15%
    "1q_pts": 0.85,
    "1h_points": 0.85,
    "3pm": 0.80,              # 43.8% hit rate -> penalize 20%
    
    # STRONG stats - boost slightly
    "assists": 1.10,          # 77.8% hit rate -> boost 10%
    "pts+reb+ast": 1.08,      # 75.0% hit rate -> boost 8%
    "pts+reb": 1.05,          # Combo smoothing
    "pts+ast": 1.05,
    "reb+ast": 1.05,
    
    # SOLID stats - neutral
    "rebounds": 1.02,         # 61.5% hit rate -> slight boost
    "steals": 0.90,           # High variance
    "blocks": 0.90,           # High variance, small sample
    "turnovers": 0.95,
}

# Stat-specific minimum edge thresholds (Z-score)
# Higher threshold = harder to qualify
STAT_MINIMUM_EDGE = {
    # UNDERWATER stats need higher edges to play
    "points": 1.5,            # Needs +1.5σ edge (was ~0.8σ default)
    "1q_pts": 1.5,
    "1h_points": 1.5,
    "3pm": 1.8,               # High variance needs bigger edge
    
    # STRONG stats can play with smaller edges
    "assists": 0.5,           # Just need +0.5σ
    "pts+reb+ast": 0.6,       # Combos are reliable
    "pts+reb": 0.6,
    "pts+ast": 0.6,
    "reb+ast": 0.6,
    
    # SOLID stats - standard threshold
    "rebounds": 0.8,
    "steals": 1.2,            # High variance
    "blocks": 1.2,            # High variance
    "turnovers": 1.0,
}

# Default values for unknown stats
DEFAULT_STAT_MULTIPLIER = 1.0
DEFAULT_MIN_EDGE = 0.8


@dataclass
class AnalysisConfig:
    """Complete analysis configuration."""
    
    # [1] Gate System
    gate_system: str = GateSystem.SOFT.value
    
    # [2] Penalty Severity
    penalty_severity: str = PenaltySeverity.MEDIUM.value
    custom_penalties: Dict[str, float] = field(default_factory=dict)
    
    # [3] Portfolio Balancing
    portfolio_balance: str = PortfolioBalance.TEAM.value
    max_same_team: int = 2
    max_same_game: int = 3
    
    # [4] Probability Model
    probability_model: str = ProbabilityModel.HYBRID.value
    hybrid_blend: float = 0.40  # 40% L5 recent, 60% L10 stable (reduced from 0.65 to fix recency bias)
    
    # [5] Bayesian Updating
    bayesian_mode: str = BayesianMode.STANDARD.value
    bayesian_window: int = 10  # Games for recent weighting
    
    # [6] Correlation Model
    correlation_model: str = CorrelationModel.LAMBDA_FIXED.value
    lambda_value: float = 0.05
    
    # [7] Edge Calculation
    edge_calculation: str = EdgeCalculation.KELLY.value
    kelly_fraction: float = 0.25  # Fractional Kelly (25%)
    
    # [8] Monte Carlo Settings
    monte_carlo_mode: str = MonteCarloMode.EXACT.value
    mc_simulations: int = 10000
    
    # [9] Memory Penalties
    memory_penalty: str = MemoryPenalty.REGULARIZED.value
    memory_shrinkage: float = 0.7  # How much to shrink toward mean
    
    # [10] Confidence Thresholds
    confidence_preset: str = ConfidencePreset.STANDARD.value
    custom_thresholds: Dict[str, float] = field(default_factory=dict)
    
    # [11] Backtest Mode
    backtest_mode: str = "live"  # "off", "live", "historical"
    
    # [12] Stat-Specific Adjustments (calibration-driven)
    stat_adjustments_enabled: bool = True  # Apply stat-specific multipliers
    stat_multipliers: Dict[str, float] = field(default_factory=dict)  # Custom overrides
    stat_min_edges: Dict[str, float] = field(default_factory=dict)    # Custom edge thresholds
    
    # Profile metadata
    profile_name: str = "default"
    last_modified: str = ""
    
    def get_penalties(self) -> Dict[str, float]:
        """Get penalty multipliers for current severity."""
        if self.penalty_severity == PenaltySeverity.CUSTOM.value:
            return self.custom_penalties
        return PENALTY_MULTIPLIERS.get(
            PenaltySeverity(self.penalty_severity),
            PENALTY_MULTIPLIERS[PenaltySeverity.MEDIUM]
        )
    
    def get_thresholds(self) -> Dict[str, float]:
        """Get confidence thresholds for current preset."""
        if self.confidence_preset == ConfidencePreset.CUSTOM.value:
            return self.custom_thresholds
        return CONFIDENCE_THRESHOLDS.get(
            ConfidencePreset(self.confidence_preset),
            CONFIDENCE_THRESHOLDS[ConfidencePreset.STANDARD]
        )
    
    def get_lambda(self) -> float:
        """Get correlation lambda value."""
        if self.correlation_model == CorrelationModel.LAMBDA_CALIBRATED.value:
            return self.lambda_value  # Use stored calibrated value
        return LAMBDA_VALUES.get(
            CorrelationModel(self.correlation_model), 0.05
        ) or self.lambda_value
    
    def is_soft_gates(self) -> bool:
        """Check if soft gates are enabled."""
        return self.gate_system in (GateSystem.SOFT.value, GateSystem.MINIMAL.value)
    
    def is_hard_block(self) -> bool:
        """Check if hard blocking is enabled."""
        return self.gate_system == GateSystem.HARD.value
    
    def get_mc_sims(self) -> int:
        """Get Monte Carlo simulation count based on mode."""
        mode_sims = {
            "off": 0,
            "fast": 1000,
            "standard": 10000,
            "exact": 0,  # Uses exact Poisson-binomial
            "gpu": 100000,
        }
        return mode_sims.get(self.monte_carlo_mode, self.mc_simulations)
    
    def get_stat_multiplier(self, stat: str) -> float:
        """Get confidence multiplier for a stat type (calibration-driven)."""
        if not self.stat_adjustments_enabled:
            return 1.0
        
        stat_lower = stat.lower().strip()
        
        # Check custom overrides first
        if stat_lower in self.stat_multipliers:
            return self.stat_multipliers[stat_lower]
        
        # Use calibrated defaults
        return STAT_CONFIDENCE_MULTIPLIERS.get(stat_lower, DEFAULT_STAT_MULTIPLIER)
    
    def get_stat_min_edge(self, stat: str) -> float:
        """Get minimum Z-score edge required for a stat type."""
        if not self.stat_adjustments_enabled:
            return DEFAULT_MIN_EDGE
        
        stat_lower = stat.lower().strip()
        
        # Check custom overrides first
        if stat_lower in self.stat_min_edges:
            return self.stat_min_edges[stat_lower]
        
        # Use calibrated defaults
        return STAT_MINIMUM_EDGE.get(stat_lower, DEFAULT_MIN_EDGE)
    
    def apply_stat_adjustment(self, stat: str, confidence: float, z_score: float) -> tuple:
        """
        Apply stat-specific adjustments to confidence and check edge threshold.
        CONTROLLED BY: config/penalty_mode.json → stat_multipliers
        
        Returns: (adjusted_confidence, meets_min_edge, adjustment_info)
        """
        # MASTER SWITCH: If penalties off, return raw confidence
        if _PENALTY_MODE.get("master_penalties_off", False) or not _PENALTY_MODE.get("stat_multipliers", True):
            info = {
                "stat": stat,
                "raw_confidence": confidence,
                "multiplier": 1.0,
                "adjusted_confidence": confidence,
                "z_score": z_score,
                "min_edge_required": 0,
                "meets_min_edge": True,
                "penalties_off": True
            }
            return confidence, True, info
        
        multiplier = self.get_stat_multiplier(stat)
        min_edge = self.get_stat_min_edge(stat)
        
        adjusted = confidence * multiplier
        meets_edge = z_score >= min_edge
        
        info = {
            "stat": stat,
            "raw_confidence": confidence,
            "multiplier": multiplier,
            "adjusted_confidence": adjusted,
            "z_score": z_score,
            "min_edge_required": min_edge,
            "meets_min_edge": meets_edge,
        }
        
        return adjusted, meets_edge, info


def load_config() -> AnalysisConfig:
    """Load configuration from file."""
    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text())
            return AnalysisConfig(**data)
        except Exception:
            pass
    return AnalysisConfig()


def save_config(config: AnalysisConfig):
    """Save configuration to file."""
    config.last_modified = datetime.now().isoformat()
    CONFIG_FILE.write_text(json.dumps(asdict(config), indent=2))


def load_profile(name: str) -> Optional[AnalysisConfig]:
    """Load a named profile."""
    profiles_dir = Path(__file__).parent / "config_profiles"
    profile_file = profiles_dir / f"{name}.json"
    if profile_file.exists():
        try:
            data = json.loads(profile_file.read_text())
            return AnalysisConfig(**data)
        except Exception:
            pass
    return None


def save_profile(config: AnalysisConfig, name: str):
    """Save configuration as a named profile."""
    profiles_dir = Path(__file__).parent / "config_profiles"
    profiles_dir.mkdir(exist_ok=True)
    
    config.profile_name = name
    config.last_modified = datetime.now().isoformat()
    
    profile_file = profiles_dir / f"{name}.json"
    profile_file.write_text(json.dumps(asdict(config), indent=2))


def list_profiles() -> List[str]:
    """List available configuration profiles."""
    profiles_dir = Path(__file__).parent / "config_profiles"
    if not profiles_dir.exists():
        return []
    return [f.stem for f in profiles_dir.glob("*.json")]


# ============================================================================
# ASCII MENU UI
# ============================================================================

def display_config_menu(config: AnalysisConfig):
    """Display the beautiful ASCII configuration menu."""
    
    # Build display values
    gate_display = {
        "hard": "Hard Gates",
        "soft": "Soft Gates",
        "minimal": "Minimal",
        "none": "No Gates",
    }.get(config.gate_system, config.gate_system)
    
    penalty_display = config.penalty_severity.title()
    balance_display = {
        "off": "Off",
        "team": "Team",
        "game": "Game",
        "position": "Position",
    }.get(config.portfolio_balance, config.portfolio_balance)
    
    prob_display = {
        "normal_cdf": "Normal CDF",
        "neg_binomial": "Neg Binomial",
        "empirical": "Empirical",
        "hybrid": "Hybrid",
        "gmm": "GMM",
    }.get(config.probability_model, config.probability_model)
    
    bayes_display = config.bayesian_mode.title()
    corr_display = {
        "independent": "Independent",
        "lambda_fixed": "Lambda Fixed",
        "lambda_calibrated": "Lambda Cal",
        "copula": "Copula",
    }.get(config.correlation_model, config.correlation_model)
    
    edge_display = {
        "z_score": "Z-Score",
        "raw_edge": "Raw Edge",
        "kelly": "Kelly",
        "sharpe": "Sharpe",
    }.get(config.edge_calculation, config.edge_calculation)
    
    mc_display = {
        "off": "Off",
        "fast": "Fast (1k)",
        "standard": "Standard",
        "exact": "Exact",
        "gpu": "GPU (100k)",
    }.get(config.monte_carlo_mode, config.monte_carlo_mode)
    
    memory_display = config.memory_penalty.title()
    conf_display = config.confidence_preset.title()
    bt_display = config.backtest_mode.title()
    stat_display = "ON" if config.stat_adjustments_enabled else "OFF"
    
    menu = f"""
┌─ ANALYSIS CONFIGURATION ────────────────────────────────────────────┐
│                                                                      │
│  [1] GATE SYSTEM                                    [{gate_display:<12}] │
│      ├─ Hard Gates       - Block all violations                     │
│      ├─ Soft Gates       - Graduated penalties (recommended)        │
│      ├─ Minimal Gates    - Only critical safety blocks              │
│      └─ No Gates         - Raw model output (experimental)          │
│                                                                      │
│  [2] PENALTY SEVERITY                               [{penalty_display:<12}] │
│      ├─ Conservative     - Heavy penalties (0.60/0.75/0.90)         │
│      ├─ Medium           - Balanced (0.70/0.85/0.95)                │
│      └─ Aggressive       - Light penalties (0.85/0.92/0.98)         │
│                                                                      │
│  [3] PORTFOLIO BALANCING                            [{balance_display:<12}] │
│      ├─ Off              - No balancing                             │
│      ├─ Team Balanced    - Diversify across teams                   │
│      ├─ Game Balanced    - Diversify across games                   │
│      └─ Position         - Diversify by player position             │
│                                                                      │
│  [4] PROBABILITY MODEL                              [{prob_display:<12}] │
│      ├─ Normal CDF       - Fast, deterministic                      │
│      ├─ Empirical        - Historical hit rate                      │
│      ├─ Hybrid           - Blend model + empirical (recommended)    │
│      └─ GMM              - Gaussian mixture (advanced)              │
│                                                                      │
│  [5] BAYESIAN UPDATING                              [{bayes_display:<12}] │
│      ├─ Off              - Use raw season stats                     │
│      ├─ Standard         - Recent 10 games weighted                 │
│      ├─ Aggressive       - Heavy recent weighting (L5 games)        │
│      └─ Hierarchical     - Full Bayesian (slow, accurate)           │
│                                                                      │
│  [6] CORRELATION MODEL                              [{corr_display:<12}] │
│      ├─ Independent      - No correlation penalty (λ=0)             │
│      ├─ Lambda Fixed     - Fixed 5% penalty (λ=0.05)                │
│      ├─ Lambda Calibrated - Empirical λ per team                    │
│      └─ Copula           - Full dependency structure (advanced)     │
│                                                                      │
│  [7] EDGE CALCULATION                               [{edge_display:<12}] │
│      ├─ Z-Score          - Statistical significance                 │
│      ├─ Raw Edge         - μ - line difference                      │
│      ├─ Kelly            - Optimal bet sizing (recommended)         │
│      └─ Sharpe           - Risk-adjusted returns                    │
│                                                                      │
│  [8] MONTE CARLO SETTINGS                           [{mc_display:<12}] │
│      ├─ Off              - No portfolio optimization                │
│      ├─ Fast (1k sims)   - Quick approximation                      │
│      ├─ Standard (10k)   - Balanced speed/accuracy                  │
│      ├─ Exact            - Poisson-binomial (recommended)           │
│      └─ GPU Accelerated  - 100k simulations (if available)          │
│                                                                      │
│  [9] MEMORY PENALTIES                               [{memory_display:<12}] │
│      ├─ Off              - Ignore player history                    │
│      ├─ Raw              - Apply all historical penalties           │
│      ├─ Regularized      - Empirical Bayes shrinkage (recommended)  │
│      └─ Adaptive         - Learn from recent outcomes               │
│                                                                      │
│  [10] CONFIDENCE THRESHOLDS                         [{conf_display:<12}] │
│       ├─ Conservative    - PLAY: 70%, LEAN: 60%                     │
│       ├─ Standard        - PLAY: 65%, LEAN: 55%                     │
│       └─ Aggressive      - PLAY: 60%, LEAN: 52%                     │
│                                                                      │
│  [11] BACKTEST MODE                                 [{bt_display:<12}] │
│       ├─ Off             - No backtesting                           │
│       ├─ Live            - Real-time validation                     │
│       └─ Historical      - Test on past slates                      │
│                                                                      │
│  [12] STAT ADJUSTMENTS (Calibration)                [{stat_display:<12}] │
│       ├─ ON: points=-15%, 3pm=-20%, assists=+10%, combos=+8%        │
│       ├─ Min edges: points≥1.5σ, 3pm≥1.8σ, assists≥0.5σ             │
│       └─ OFF: No stat-specific adjustments                          │
│                                                                      │
│  [S] Save Profile   [L] Load Profile   [R] Reset   [Q] Back         │
│                                                                      │
│  Profile: {config.profile_name:<15}  Modified: {config.last_modified[:16] if config.last_modified else 'Never':<16}  │
└──────────────────────────────────────────────────────────────────────┘
"""
    print(menu)


def cycle_option(current: str, options: list) -> str:
    """Cycle to next option in list."""
    try:
        idx = options.index(current)
        return options[(idx + 1) % len(options)]
    except ValueError:
        return options[0]


def run_config_menu() -> AnalysisConfig:
    """Run the interactive configuration menu."""
    
    config = load_config()
    
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        display_config_menu(config)
        
        choice = input("\nSelect option [1-11, S/L/R/Q]: ").strip().upper()
        
        if choice == "1":
            options = ["hard", "soft", "minimal", "none"]
            config.gate_system = cycle_option(config.gate_system, options)
            
        elif choice == "2":
            options = ["conservative", "medium", "aggressive"]
            config.penalty_severity = cycle_option(config.penalty_severity, options)
            
        elif choice == "3":
            options = ["off", "team", "game", "position"]
            config.portfolio_balance = cycle_option(config.portfolio_balance, options)
            
        elif choice == "4":
            options = ["normal_cdf", "empirical", "hybrid", "gmm"]
            config.probability_model = cycle_option(config.probability_model, options)
            
        elif choice == "5":
            options = ["off", "standard", "aggressive", "hierarchical"]
            config.bayesian_mode = cycle_option(config.bayesian_mode, options)
            
        elif choice == "6":
            options = ["independent", "lambda_fixed", "lambda_calibrated", "copula"]
            config.correlation_model = cycle_option(config.correlation_model, options)
            
        elif choice == "7":
            options = ["z_score", "raw_edge", "kelly", "sharpe"]
            config.edge_calculation = cycle_option(config.edge_calculation, options)
            
        elif choice == "8":
            options = ["off", "fast", "standard", "exact", "gpu"]
            config.monte_carlo_mode = cycle_option(config.monte_carlo_mode, options)
            
        elif choice == "9":
            options = ["off", "raw", "regularized", "adaptive"]
            config.memory_penalty = cycle_option(config.memory_penalty, options)
            
        elif choice == "10":
            options = ["conservative", "standard", "aggressive"]
            config.confidence_preset = cycle_option(config.confidence_preset, options)
            
        elif choice == "11":
            options = ["off", "live", "historical"]
            config.backtest_mode = cycle_option(config.backtest_mode, options)
            
        elif choice == "12":
            # Toggle stat adjustments
            config.stat_adjustments_enabled = not config.stat_adjustments_enabled
            status = "ON" if config.stat_adjustments_enabled else "OFF"
            print(f"\n  Stat adjustments: {status}")
            if config.stat_adjustments_enabled:
                print("  Calibration-driven adjustments active:")
                print("    PENALIZED: points(-15%), 3pm(-20%)")
                print("    BOOSTED:   assists(+10%), combos(+8%)")
                print("    MIN EDGES: points≥1.5σ, 3pm≥1.8σ, assists≥0.5σ")
            input("Press Enter...")
            
        elif choice == "S":
            name = input("Profile name to save: ").strip()
            if name:
                save_profile(config, name)
                save_config(config)
                print(f"✓ Saved profile '{name}'")
                input("Press Enter...")
                
        elif choice == "L":
            profiles = list_profiles()
            if profiles:
                print(f"Available profiles: {', '.join(profiles)}")
                name = input("Profile name to load: ").strip()
                loaded = load_profile(name)
                if loaded:
                    config = loaded
                    save_config(config)
                    print(f"✓ Loaded profile '{name}'")
                else:
                    print(f"✗ Profile '{name}' not found")
            else:
                print("No saved profiles found")
            input("Press Enter...")
            
        elif choice == "R":
            config = AnalysisConfig()
            save_config(config)
            print("✓ Reset to defaults")
            input("Press Enter...")
            
        elif choice == "Q":
            save_config(config)
            break
    
    return config


# ============================================================================
# INTEGRATION HELPERS
# ============================================================================

def get_active_config() -> AnalysisConfig:
    """Get the currently active configuration (for use by analysis modules)."""
    return load_config()


def apply_config_to_environment(config: AnalysisConfig):
    """Set environment variables from config (for subprocess compatibility)."""
    os.environ["SOFTGATES"] = "1" if config.is_soft_gates() else "0"
    os.environ["GATE_SYSTEM"] = config.gate_system
    os.environ["PROB_MODEL"] = config.probability_model
    os.environ["BAYES_MODE"] = config.bayesian_mode
    os.environ["CORR_MODEL"] = config.correlation_model
    os.environ["EDGE_CALC"] = config.edge_calculation
    os.environ["MC_MODE"] = config.monte_carlo_mode
    os.environ["CONF_PRESET"] = config.confidence_preset
    os.environ["PENALTY_SEVERITY"] = config.penalty_severity


def get_config_summary(config: AnalysisConfig = None) -> str:
    """Get a one-line summary of current config."""
    if config is None:
        config = load_config()
    stat_status = "ON" if config.stat_adjustments_enabled else "OFF"
    return (
        f"Gates={config.gate_system} | Prob={config.probability_model} | "
        f"Bayes={config.bayesian_mode} | Edge={config.edge_calculation} | "
        f"MC={config.monte_carlo_mode} | StatAdj={stat_status}"
    )


if __name__ == "__main__":
    run_config_menu()
