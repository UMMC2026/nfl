"""
THRESHOLD OPTIMIZER (Bayesian Gate Tuner)
==========================================
Learn optimal gate thresholds from historical hit/miss data using
Beta-Binomial conjugate priors.

NOTE: This is NOT a full Bayesian probability model. It uses Beta
distributions to estimate GATE THRESHOLDS, not to model player stats.
The actual probability calculations use normal (Gaussian) approximations.

Mathematical Foundation:
- Prior: Beta(1,1) = Uniform
- Likelihood: Binomial (hits, misses)
- Posterior: Beta(α + hits, β + misses)

This learns:
- Optimal confidence thresholds for each tier
- Penalty/boost magnitudes for contextual factors
- Sample size minimums for statistical significance
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
import json
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class BetaPosterior:
    alpha: float = 1.0
    beta: float = 1.0
    
    @property
    def mean(self) -> float:
        return self.alpha / (self.alpha + self.beta)
    
    @property
    def variance(self) -> float:
        a, b = self.alpha, self.beta
        return (a * b) / ((a + b) ** 2 * (a + b + 1))
    
    @property
    def std(self) -> float:
        return math.sqrt(self.variance)
    
    @property
    def confidence_interval_95(self) -> Tuple[float, float]:
        from scipy import stats
        return stats.beta.ppf(0.025, self.alpha, self.beta), stats.beta.ppf(0.975, self.alpha, self.beta)
    
    def update(self, hits: int, misses: int) -> "BetaPosterior":
        return BetaPosterior(
            alpha=self.alpha + hits,
            beta=self.beta + misses
        )


@dataclass
class GateRecommendation:
    gate_name: str
    current_threshold: float
    recommended_threshold: float
    posterior_mean: float
    posterior_std: float
    sample_size: int
    confidence: str
    rationale: str


@dataclass
class TuningResult:
    recommendations: List[GateRecommendation] = field(default_factory=list)
    posteriors: Dict[str, BetaPosterior] = field(default_factory=dict)
    generated_at: str = ""
    total_samples: int = 0
    resolved_samples: int = 0  # Only resolved picks (HIT/MISS)


CURRENT_THRESHOLDS = {
    "R2_ELITE_DEF": {"confidence_cap": 65, "min_games": 3},
    "R3_STAR_GUARD": {"confidence_cap": 65, "min_avg": 15},
    "LEAN_THRESHOLD": {"min_confidence": 55},
    "PLAY_THRESHOLD": {"min_confidence": 62},
    "CONFIDENCE_ADJ_POSITIVE": {"boost": 5},
    "CONFIDENCE_ADJ_NEGATIVE": {"penalty": 8},
}


class BayesianTuner:
    def __init__(self, history_path: Optional[Path] = None):
        self.history_path = history_path or PROJECT_ROOT / "calibration_history.csv"
        self.gate_posteriors: Dict[str, BetaPosterior] = defaultdict(BetaPosterior)
        self.tier_posteriors: Dict[str, BetaPosterior] = defaultdict(BetaPosterior)
        self.stat_posteriors: Dict[str, BetaPosterior] = defaultdict(BetaPosterior)
    
    def load_history(self) -> List[dict]:
        if not self.history_path.exists():
            print(f"[BAYES] No history file: {self.history_path}")
            return []
        
        rows = []
        with open(self.history_path, "r", encoding="utf-8") as f:
            header = None
            for line in f:
                line = line.strip()
                if not line:
                    continue
                if header is None:
                    header = line.split(",")
                    continue
                vals = line.split(",")
                if len(vals) >= len(header):
                    rows.append(dict(zip(header, vals)))
        
        return rows
    
    def fit(self, history: Optional[List[dict]] = None) -> TuningResult:
        if history is None:
            history = self.load_history()
        
        result = TuningResult()
        result.generated_at = datetime.now().isoformat()
        result.total_samples = len(history)
        
        if not history:
            return result
        
        tier_stats = defaultdict(lambda: {"hits": 0, "misses": 0})
        stat_stats = defaultdict(lambda: {"hits": 0, "misses": 0})
        conf_bucket_stats = defaultdict(lambda: {"hits": 0, "misses": 0})
        
        resolved_count = 0
        for row in history:
            # Fix: Check actual_result column (values: "hit"/"miss") OR hit column (values: "true"/"1")
            actual = row.get("actual_result", row.get("outcome", row.get("hit", ""))).lower().strip()
            
            # CRITICAL FIX: Skip unresolved picks (empty, nan, pending)
            # Only process rows where outcome is explicitly HIT or MISS
            if actual not in ("hit", "miss", "true", "false", "1", "0", "win", "won", "loss", "lost"):
                continue  # Skip pending/unresolved picks
            
            hit = actual in ("hit", "true", "1", "win", "won")
            resolved_count += 1
            tier = row.get("decision", row.get("tier", "UNKNOWN"))
            stat = row.get("stat", "UNKNOWN")
            conf_raw = row.get("effective_confidence", row.get("predicted_prob", row.get("confidence", "50")))
            
            try:
                conf = float(conf_raw)
            except (ValueError, TypeError):
                conf = 50.0
            
            if tier:
                if hit:
                    tier_stats[tier]["hits"] += 1
                else:
                    tier_stats[tier]["misses"] += 1
            
            if stat:
                if hit:
                    stat_stats[stat]["hits"] += 1
                else:
                    stat_stats[stat]["misses"] += 1
            
            bucket = f"{int(conf // 5) * 5}-{int(conf // 5) * 5 + 5}"
            if hit:
                conf_bucket_stats[bucket]["hits"] += 1
            else:
                conf_bucket_stats[bucket]["misses"] += 1
        
        for tier, stats in tier_stats.items():
            prior = BetaPosterior(alpha=1, beta=1)
            self.tier_posteriors[tier] = prior.update(stats["hits"], stats["misses"])
        
        for stat, stats in stat_stats.items():
            prior = BetaPosterior(alpha=1, beta=1)
            self.stat_posteriors[stat] = prior.update(stats["hits"], stats["misses"])
        
        for bucket, stats in conf_bucket_stats.items():
            prior = BetaPosterior(alpha=1, beta=1)
            self.gate_posteriors[f"conf_{bucket}"] = prior.update(stats["hits"], stats["misses"])
        
        result.posteriors = {**self.tier_posteriors, **self.stat_posteriors, **self.gate_posteriors}
        
        # Store resolved count for report
        result.resolved_samples = resolved_count
        
        result.recommendations = self._generate_recommendations(tier_stats, stat_stats, conf_bucket_stats)
        
        return result
    
    def _generate_recommendations(self, tier_stats, stat_stats, conf_bucket_stats) -> List[GateRecommendation]:
        recs = []
        
        if "PLAY" in self.tier_posteriors:
            post = self.tier_posteriors["PLAY"]
            n = tier_stats["PLAY"]["hits"] + tier_stats["PLAY"]["misses"]
            
            if post.mean < 0.55 and n >= 20:
                recs.append(GateRecommendation(
                    gate_name="PLAY_THRESHOLD",
                    current_threshold=62,
                    recommended_threshold=65,
                    posterior_mean=post.mean,
                    posterior_std=post.std,
                    sample_size=n,
                    confidence="HIGH" if n >= 50 else "MEDIUM",
                    rationale=f"PLAY tier hitting {post.mean:.1%}, recommend raising threshold"
                ))
            elif post.mean > 0.70 and n >= 20:
                recs.append(GateRecommendation(
                    gate_name="PLAY_THRESHOLD",
                    current_threshold=62,
                    recommended_threshold=58,
                    posterior_mean=post.mean,
                    posterior_std=post.std,
                    sample_size=n,
                    confidence="HIGH" if n >= 50 else "MEDIUM",
                    rationale=f"PLAY tier hitting {post.mean:.1%}, can lower threshold"
                ))
        
        if "LEAN" in self.tier_posteriors:
            post = self.tier_posteriors["LEAN"]
            n = tier_stats["LEAN"]["hits"] + tier_stats["LEAN"]["misses"]
            
            if post.mean < 0.45 and n >= 20:
                recs.append(GateRecommendation(
                    gate_name="LEAN_THRESHOLD",
                    current_threshold=55,
                    recommended_threshold=58,
                    posterior_mean=post.mean,
                    posterior_std=post.std,
                    sample_size=n,
                    confidence="HIGH" if n >= 50 else "MEDIUM",
                    rationale=f"LEAN tier hitting {post.mean:.1%}, recommend raising threshold"
                ))
        
        for stat, post in self.stat_posteriors.items():
            n = stat_stats[stat]["hits"] + stat_stats[stat]["misses"]
            if n >= 15 and post.mean < 0.40:
                recs.append(GateRecommendation(
                    gate_name=f"STAT_PENALTY_{stat.upper()}",
                    current_threshold=0,
                    recommended_threshold=5,
                    posterior_mean=post.mean,
                    posterior_std=post.std,
                    sample_size=n,
                    confidence="MEDIUM" if n >= 30 else "LOW",
                    rationale=f"{stat} hitting only {post.mean:.1%}, recommend adding confidence penalty"
                ))
        
        return recs
    
    def generate_report(self, result: TuningResult) -> str:
        lines = ["=" * 70, "BAYESIAN GATE TUNING ANALYSIS", f"Generated: {result.generated_at}", 
                 f"Total Samples: {result.total_samples} (Resolved: {result.resolved_samples})", "=" * 70, ""]
        
        lines.append("TIER HIT RATES (Posterior Estimates):")
        lines.append("-" * 40)
        for tier in ["PLAY", "LEAN", "NO_PLAY", "SKIP"]:
            if tier in self.tier_posteriors:
                post = self.tier_posteriors[tier]
                lines.append(f"   {tier:10} | {post.mean:.1%} +/- {post.std:.1%} (n={int(post.alpha + post.beta - 2)})")
        lines.append("")
        
        lines.append("STAT HIT RATES (Top/Bottom 5):")
        lines.append("-" * 40)
        sorted_stats = sorted(self.stat_posteriors.items(), key=lambda x: x[1].mean, reverse=True)
        for stat, post in sorted_stats[:5]:
            lines.append(f"   {stat:15} | {post.mean:.1%} (n={int(post.alpha + post.beta - 2)})")
        if len(sorted_stats) > 5:
            lines.append("   ...")
            for stat, post in sorted_stats[-3:]:
                lines.append(f"   {stat:15} | {post.mean:.1%} (n={int(post.alpha + post.beta - 2)})")
        lines.append("")
        
        if result.recommendations:
            lines.append("=" * 70)
            lines.append("RECOMMENDATIONS:")
            lines.append("=" * 70)
            for rec in result.recommendations:
                lines.append(f"\n[{rec.confidence}] {rec.gate_name}")
                lines.append(f"   Current: {rec.current_threshold} -> Recommended: {rec.recommended_threshold}")
                lines.append(f"   Posterior: {rec.posterior_mean:.1%} +/- {rec.posterior_std:.1%} (n={rec.sample_size})")
                lines.append(f"   Rationale: {rec.rationale}")
        else:
            lines.append("\nNo threshold changes recommended at this time.")
        
        return "\n".join(lines)


def run_bayesian_tuning(output_path: Optional[Path] = None) -> TuningResult:
    tuner = BayesianTuner()
    result = tuner.fit()
    report = tuner.generate_report(result)
    
    if output_path is None:
        output_path = PROJECT_ROOT / "outputs" / f"bayesian_tuning_{datetime.now().strftime('%Y%m%d_%H%M')}.txt"
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report, encoding="utf-8")
    
    print(f"\n[BAYES] Bayesian tuning report: {output_path}")
    print(report)
    
    return result
