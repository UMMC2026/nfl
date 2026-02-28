"""
BACKTEST ENGINE
===============
Measures historical calibration of probability predictions.
"""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import math
import re

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class CalibrationBucket:
    predicted_low: float
    predicted_high: float
    total: int = 0
    hits: int = 0
    sum_predicted: float = 0.0
    sum_squared_error: float = 0.0
    
    @property
    def hit_rate(self) -> float:
        return self.hits / self.total if self.total > 0 else 0.0
    
    @property
    def avg_predicted(self) -> float:
        return self.sum_predicted / self.total if self.total > 0 else 0.0
    
    @property
    def brier_score(self) -> float:
        return self.sum_squared_error / self.total if self.total > 0 else 0.0
    
    @property
    def calibration_error(self) -> float:
        return self.avg_predicted - self.hit_rate


@dataclass
class BacktestResult:
    total_picks: int = 0
    total_resolved: int = 0
    total_scored: int = 0
    calibration_buckets: List[CalibrationBucket] = field(default_factory=list)
    overall_brier: float = 0.0
    overall_hit_rate: float = 0.0
    tier_stats: Dict[str, Dict] = field(default_factory=dict)
    stat_stats: Dict[str, Dict] = field(default_factory=dict)
    role_stats: Dict[str, Dict] = field(default_factory=dict)
    gate_warning_stats: Dict[str, Dict] = field(default_factory=dict)
    generated_at: str = ""


class BacktestEngine:
    def __init__(self, history_path: Optional[Path] = None):
        self.history_path = history_path or PROJECT_ROOT / "calibration_history.csv"
        self.history: List[dict] = []
        self.outputs_dir = PROJECT_ROOT / "outputs"
        self._analysis_index_by_date: Dict[str, Dict[str, dict]] = {}
        self._load_history()

    @staticmethod
    def _norm_actual(v: str) -> str:
        s = (v or "").strip().upper()
        if s in {"HIT", "MISS"}:
            return s
        # tolerate legacy lowercase/variants
        if s in {"H", "WIN", "W"}:
            return "HIT"
        if s in {"L", "LOSS"}:
            return "MISS"
        return s

    @staticmethod
    def _norm_tier(v: str) -> str:
        s = (v or "").strip().upper()
        if s in {"NO_PLAY", "NO PLAY", "NOPLAY"}:
            return "NO PLAY"
        if s in {"ANALYSIS_ONLY", "ANALYSIS ONLY"}:
            # keep as a reporting status if it ever appears in history
            return "ANALYSIS_ONLY"
        return s or "UNKNOWN"

    @staticmethod
    def _norm_player(v: str) -> str:
        s = (v or "").strip().lower()
        # remove punctuation and collapse whitespace
        s = re.sub(r"[^a-z0-9\s]", "", s)
        s = re.sub(r"\s+", " ", s).strip()
        return s

    @staticmethod
    def _norm_stat(v: str) -> str:
        return (v or "").strip().lower()

    @staticmethod
    def _norm_direction(v: str) -> str:
        s = (v or "").strip().lower()
        if s in {"over", "higher", "hi", "h"}:
            return "higher"
        if s in {"under", "lower", "lo", "l"}:
            return "lower"
        return s

    @staticmethod
    def _safe_float(v: object) -> Optional[float]:
        try:
            if v is None:
                return None
            s = str(v).strip()
            if not s:
                return None
            return float(s)
        except Exception:
            return None

    @staticmethod
    def _prob_to_unit(p: float) -> float:
        # tolerate 0..100 inputs
        if p > 1.0:
            p = p / 100.0
        return max(0.0, min(1.0, p))

    def _build_key(self, *, player: str, stat: str, direction: str, line: float) -> str:
        # Line is used to disambiguate common OCR collisions
        return f"{self._norm_player(player)}|{self._norm_stat(stat)}|{self._norm_direction(direction)}|{line:.3f}"

    def _load_analysis_index_for_date(self, date_str: str) -> Dict[str, dict]:
        """Load and index picks from *_RISK_FIRST_YYYYMMDD*.json outputs for a given date."""
        if date_str in self._analysis_index_by_date:
            return self._analysis_index_by_date[date_str]

        idx: Dict[str, dict] = {}
        yyyymmdd = date_str.replace("-", "").strip()
        if not yyyymmdd or len(yyyymmdd) != 8:
            self._analysis_index_by_date[date_str] = idx
            return idx

        if not self.outputs_dir.exists():
            self._analysis_index_by_date[date_str] = idx
            return idx

        candidates = sorted(self.outputs_dir.glob(f"*RISK_FIRST*{yyyymmdd}*.json"))
        for p in candidates:
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                results = data.get("results") if isinstance(data, dict) else None
                if not isinstance(results, list):
                    continue
                for pick in results:
                    if not isinstance(pick, dict):
                        continue
                    player = pick.get("player", "")
                    stat = pick.get("stat", "")
                    direction = pick.get("direction", "")
                    line_f = self._safe_float(pick.get("line"))
                    if not player or not stat or line_f is None:
                        continue
                    key = self._build_key(player=player, stat=stat, direction=direction, line=line_f)
                    # prefer first hit; file ordering is stable by glob sort
                    if key not in idx:
                        idx[key] = pick
            except Exception:
                continue

        self._analysis_index_by_date[date_str] = idx
        return idx

    def _try_enrich_from_outputs(self, row: dict) -> dict:
        """Best-effort enrich a calibration_history row with predicted_prob/decision from outputs."""
        date_str = (row.get("date") or "").strip()
        player = row.get("player", "")
        stat = row.get("stat", "")
        direction = row.get("direction", "")
        line_f = self._safe_float(row.get("line"))
        if not date_str or not player or not stat or line_f is None:
            return {}

        idx = self._load_analysis_index_for_date(date_str)
        if not idx:
            return {}

        key = self._build_key(player=player, stat=stat, direction=direction, line=line_f)
        pick = idx.get(key)
        if not pick:
            return {}

        # In analysis JSON, effective_confidence is in percent (0..100)
        prob = pick.get("effective_confidence")
        if prob is None:
            prob = pick.get("confidence")

        return {
            "predicted_prob": prob,
            "decision": pick.get("decision"),
        }
    
    def _load_history(self):
        if not self.history_path.exists():
            self.history_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.history_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "date", "player", "stat", "line", "direction",
                    "predicted_prob", "decision", "actual_result",
                    "role", "gate_warnings", "stat_type"
                ])
            self.history = []
            return
        
        with open(self.history_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            # Load all rows; resolution filtering is done in run_calibration().
            # This avoids silently dropping legacy rows (e.g., 'hit'/'miss').
            self.history = [row for row in reader]
    
    def add_result(self, date: str, player: str, stat: str, line: float,
                   direction: str, predicted_prob: float, decision: str,
                   actual_result: str, role: str = "", gate_warnings: str = "", stat_type: str = ""):
        row = {
            "date": date, "player": player, "stat": stat, "line": str(line),
            "direction": direction, "predicted_prob": str(predicted_prob),
            "decision": decision, "actual_result": actual_result,
            "role": role, "gate_warnings": gate_warnings, "stat_type": stat_type
        }
        with open(self.history_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=row.keys())
            writer.writerow(row)
        self.history.append(row)
    
    def run_calibration(self, bucket_size: float = 0.05) -> BacktestResult:
        result = BacktestResult()
        result.generated_at = datetime.now().isoformat()
        result.total_picks = len(self.history)
        
        if not self.history:
            return result
        
        n_buckets = int(1.0 / bucket_size)
        buckets = [CalibrationBucket(predicted_low=i*bucket_size, predicted_high=(i+1)*bucket_size) for i in range(n_buckets)]
        
        tier_data = defaultdict(lambda: {"total": 0, "hits": 0, "sum_prob": 0.0})
        stat_data = defaultdict(lambda: {"total": 0, "hits": 0, "sum_prob": 0.0})
        
        total_brier = 0.0
        total_hits = 0
        resolved_outcomes = 0
        scored = 0
        
        for row in self.history:
            try:
                actual_norm = self._norm_actual(row.get("actual_result", ""))
                if actual_norm not in ("HIT", "MISS"):
                    continue

                resolved_outcomes += 1

                # predicted prob may be missing in calibration_history.csv (legacy OCR-only rows).
                # Try to enrich from analysis outputs for the same date.
                prob_raw = row.get("predicted_prob")
                decision_raw = row.get("decision")
                if (prob_raw is None or str(prob_raw).strip() == "") or (decision_raw is None or str(decision_raw).strip() == ""):
                    enrich = self._try_enrich_from_outputs(row)
                    if enrich:
                        prob_raw = enrich.get("predicted_prob", prob_raw)
                        decision_raw = enrich.get("decision", decision_raw)

                prob_f = self._safe_float(prob_raw)
                if prob_f is None:
                    # Can't score calibration without a probability
                    continue

                prob = self._prob_to_unit(prob_f)

                hit = 1 if actual_norm == "HIT" else 0
                decision = self._norm_tier(str(decision_raw or ""))
                stat = row.get("stat", "unknown")

                scored += 1
                total_hits += hit
                brier = (prob - hit) ** 2
                total_brier += brier
                
                bucket_idx = min(int(prob / bucket_size), n_buckets - 1)
                bucket_idx = max(0, bucket_idx)
                buckets[bucket_idx].total += 1
                buckets[bucket_idx].hits += hit
                buckets[bucket_idx].sum_predicted += prob
                buckets[bucket_idx].sum_squared_error += brier
                
                tier_data[decision]["total"] += 1
                tier_data[decision]["hits"] += hit
                tier_data[decision]["sum_prob"] += prob
                
                stat_data[stat]["total"] += 1
                stat_data[stat]["hits"] += hit
                stat_data[stat]["sum_prob"] += prob
            except Exception:
                continue

        result.total_resolved = resolved_outcomes
        result.total_scored = scored
        result.calibration_buckets = [b for b in buckets if b.total > 0]
        result.overall_brier = total_brier / scored if scored > 0 else 0.0
        result.overall_hit_rate = total_hits / scored if scored > 0 else 0.0
        
        for tier, data in tier_data.items():
            n = data["total"]
            result.tier_stats[tier] = {
                "total": n, "hits": data["hits"],
                "hit_rate": data["hits"] / n if n > 0 else 0.0,
                "avg_predicted": data["sum_prob"] / n if n > 0 else 0.0
            }
        
        for stat, data in stat_data.items():
            n = data["total"]
            result.stat_stats[stat] = {
                "total": n, "hits": data["hits"],
                "hit_rate": data["hits"] / n if n > 0 else 0.0,
                "avg_predicted": data["sum_prob"] / n if n > 0 else 0.0
            }
        
        return result
    
    def generate_report(self, result: Optional[BacktestResult] = None) -> str:
        if result is None:
            result = self.run_calibration()
        
        lines = ["=" * 70, "CALIBRATION BACKTEST REPORT", f"Generated: {result.generated_at}", "=" * 70, ""]
        lines.append(f"Total Picks: {result.total_picks} | Resolved: {result.total_resolved} | Scored: {result.total_scored}")
        lines.append(f"Overall Hit Rate: {result.overall_hit_rate:.1%}")
        lines.append(f"Brier Score: {result.overall_brier:.4f} (lower=better, 0.25=random)")
        lines.append("")
        lines.append("-" * 70)
        lines.append("CALIBRATION CURVE")
        lines.append(f"{'Predicted':<12} {'Actual':<10} {'N':<8} {'Error':<10}")

        if not result.calibration_buckets:
            lines.append("(no resolved picks yet)")
        else:
            for bucket in result.calibration_buckets:
                mid = (bucket.predicted_low + bucket.predicted_high) / 2
                lines.append(
                    f"{mid:.0%}".ljust(12)
                    + f"{bucket.hit_rate:.1%}".ljust(10)
                    + f"{bucket.total}".ljust(8)
                    + f"{bucket.calibration_error:+.1%}"
                )
        
        lines.append("")
        lines.append("-" * 70)
        lines.append("BY TIER")

        if not result.tier_stats:
            if result.total_resolved > 0 and result.total_scored == 0:
                lines.append("  (resolved outcomes found, but missing predicted_prob/decision; cannot score by tier)")
                lines.append("  Tip: ensure results resolver matches picks to the correct *_RISK_FIRST_YYYYMMDD*.json file")
            else:
                lines.append("  (no resolved picks yet)")
        else:
            preferred = ["PLAY", "LEAN", "NO PLAY", "BLOCKED", "ANALYSIS_ONLY", "UNKNOWN"]
            seen = set(result.tier_stats.keys())
            ordered = [t for t in preferred if t in seen]
            ordered += sorted([t for t in seen if t not in set(preferred)])
            for tier in ordered:
                d = result.tier_stats[tier]
                lines.append(
                    f"  {tier}: Pred={d['avg_predicted']:.1%} Actual={d['hit_rate']:.1%} N={d['total']}"
                )
        
        return "\n".join(lines)


def run_calibration_report(output_path: Optional[Path] = None) -> BacktestResult:
    engine = BacktestEngine()
    result = engine.run_calibration()
    report = engine.generate_report(result)
    
    if output_path is None:
        output_path = PROJECT_ROOT / "outputs" / f"calibration_report_{datetime.now().strftime('%Y%m%d')}.txt"
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report, encoding="utf-8")
    print(f"\n[BACKTEST] Calibration report: {output_path}")
    return result
