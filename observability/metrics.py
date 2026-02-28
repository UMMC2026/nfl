"""
FUOOM Metrics Layer
==================
Prometheus-compatible metrics for production observability.

Tracks:
- Edges generated/rejected by sport, market, tier
- Validation gate pass/fail rates
- Processing times per sport
- API call success/failure rates
- Calibration drift indicators
"""

import time
import threading
from datetime import datetime
from typing import Dict, Any, Optional, List
from collections import defaultdict
from pathlib import Path
import json

try:
    from prometheus_client import Counter, Histogram, Gauge, Info, CollectorRegistry, generate_latest
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False


class FUOOMMetrics:
    """
    Central metrics collector for FUOOM system.
    Works with or without Prometheus installed.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self._initialized = True
        self._start_time = datetime.now()
        
        # In-memory metrics (always available)
        self._counters: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self._histograms: Dict[str, List[float]] = defaultdict(list)
        self._gauges: Dict[str, float] = {}
        
        # Prometheus metrics (if available)
        if PROMETHEUS_AVAILABLE:
            self._init_prometheus_metrics()
        
        # Metrics file for persistence
        self._metrics_file = Path("observability/metrics_history.json")
        self._metrics_file.parent.mkdir(exist_ok=True)
    
    def _init_prometheus_metrics(self):
        """Initialize Prometheus metric collectors."""
        self.registry = CollectorRegistry()
        
        # Edge Generation Metrics
        self.edges_generated = Counter(
            'fuoom_edges_generated_total',
            'Total edges generated',
            ['sport', 'market', 'tier'],
            registry=self.registry
        )
        
        self.edges_rejected = Counter(
            'fuoom_edges_rejected_total', 
            'Total edges rejected by governance',
            ['sport', 'market', 'rejection_reason'],
            registry=self.registry
        )
        
        # Validation Gate Metrics
        self.gate_passes = Counter(
            'fuoom_gate_passes_total',
            'Validation gate passes',
            ['sport', 'gate_name'],
            registry=self.registry
        )
        
        self.gate_failures = Counter(
            'fuoom_gate_failures_total',
            'Validation gate failures',
            ['sport', 'gate_name', 'failure_type'],
            registry=self.registry
        )
        
        # Processing Time Metrics
        self.processing_time = Histogram(
            'fuoom_processing_seconds',
            'Processing time in seconds',
            ['sport', 'operation'],
            buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0],
            registry=self.registry
        )
        
        # API Call Metrics
        self.api_calls = Counter(
            'fuoom_api_calls_total',
            'External API calls',
            ['api_name', 'status'],
            registry=self.registry
        )
        
        self.api_latency = Histogram(
            'fuoom_api_latency_seconds',
            'API call latency',
            ['api_name'],
            buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
            registry=self.registry
        )
        
        # Calibration Metrics
        self.calibration_error = Gauge(
            'fuoom_calibration_error_percent',
            'Current calibration error percentage',
            ['sport'],
            registry=self.registry
        )
        
        self.win_rate = Gauge(
            'fuoom_win_rate_percent',
            'Current win rate percentage',
            ['sport', 'tier'],
            registry=self.registry
        )
        
        # System Health Metrics
        self.active_circuits_open = Gauge(
            'fuoom_circuits_open',
            'Number of open circuit breakers',
            registry=self.registry
        )
        
        self.cache_hit_rate = Gauge(
            'fuoom_cache_hit_rate',
            'Cache hit rate percentage',
            ['cache_name'],
            registry=self.registry
        )
    
    # ========== EDGE METRICS ==========
    
    def record_edge_generated(self, sport: str, market: str, tier: str):
        """Record an edge being generated."""
        key = f"edges_generated_{sport}_{market}_{tier}"
        self._counters["edges_generated"][(sport, market, tier)] += 1
        
        if PROMETHEUS_AVAILABLE:
            self.edges_generated.labels(sport=sport, market=market, tier=tier).inc()
    
    def record_edge_rejected(self, sport: str, market: str, reason: str):
        """Record an edge being rejected."""
        self._counters["edges_rejected"][(sport, market, reason)] += 1
        
        if PROMETHEUS_AVAILABLE:
            self.edges_rejected.labels(sport=sport, market=market, rejection_reason=reason).inc()
    
    # ========== GATE METRICS ==========
    
    def record_gate_pass(self, sport: str, gate_name: str):
        """Record a validation gate pass."""
        self._counters["gate_passes"][(sport, gate_name)] += 1
        
        if PROMETHEUS_AVAILABLE:
            self.gate_passes.labels(sport=sport, gate_name=gate_name).inc()
    
    def record_gate_failure(self, sport: str, gate_name: str, failure_type: str):
        """Record a validation gate failure."""
        self._counters["gate_failures"][(sport, gate_name, failure_type)] += 1
        
        if PROMETHEUS_AVAILABLE:
            self.gate_failures.labels(sport=sport, gate_name=gate_name, failure_type=failure_type).inc()
    
    # ========== TIMING METRICS ==========
    
    def record_processing_time(self, sport: str, operation: str, duration: float):
        """Record processing duration."""
        self._histograms[f"processing_{sport}_{operation}"].append(duration)
        
        if PROMETHEUS_AVAILABLE:
            self.processing_time.labels(sport=sport, operation=operation).observe(duration)
    
    def time_operation(self, sport: str, operation: str):
        """Context manager to time an operation."""
        return _TimingContext(self, sport, operation)
    
    # ========== API METRICS ==========
    
    def record_api_call(self, api_name: str, success: bool, latency: float):
        """Record an external API call."""
        status = "success" if success else "failure"
        self._counters["api_calls"][(api_name, status)] += 1
        self._histograms[f"api_latency_{api_name}"].append(latency)
        
        if PROMETHEUS_AVAILABLE:
            self.api_calls.labels(api_name=api_name, status=status).inc()
            self.api_latency.labels(api_name=api_name).observe(latency)
    
    # ========== CALIBRATION METRICS ==========
    
    def set_calibration_error(self, sport: str, error_percent: float):
        """Set current calibration error."""
        self._gauges[f"calibration_error_{sport}"] = error_percent
        
        if PROMETHEUS_AVAILABLE:
            self.calibration_error.labels(sport=sport).set(error_percent)
    
    def set_win_rate(self, sport: str, tier: str, rate_percent: float):
        """Set current win rate."""
        self._gauges[f"win_rate_{sport}_{tier}"] = rate_percent
        
        if PROMETHEUS_AVAILABLE:
            self.win_rate.labels(sport=sport, tier=tier).set(rate_percent)
    
    # ========== REPORTING ==========
    
    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of all metrics."""
        return {
            "uptime_seconds": (datetime.now() - self._start_time).total_seconds(),
            "edges_generated": dict(self._counters["edges_generated"]),
            "edges_rejected": dict(self._counters["edges_rejected"]),
            "gate_passes": dict(self._counters["gate_passes"]),
            "gate_failures": dict(self._counters["gate_failures"]),
            "api_calls": dict(self._counters["api_calls"]),
            "gauges": dict(self._gauges),
        }
    
    def print_summary(self):
        """Print a formatted summary to console."""
        summary = self.get_summary()
        
        print("\n" + "=" * 60)
        print("  📊 FUOOM OBSERVABILITY SUMMARY")
        print("=" * 60)
        
        print(f"\n⏱️  Uptime: {summary['uptime_seconds']:.1f} seconds")
        
        # Edge stats
        total_generated = sum(summary['edges_generated'].values())
        total_rejected = sum(summary['edges_rejected'].values())
        print(f"\n📈 Edges Generated: {total_generated}")
        print(f"🚫 Edges Rejected: {total_rejected}")
        
        if total_generated > 0:
            reject_rate = total_rejected / (total_generated + total_rejected) * 100
            print(f"📉 Rejection Rate: {reject_rate:.1f}%")
        
        # Gate stats
        total_passes = sum(summary['gate_passes'].values())
        total_failures = sum(summary['gate_failures'].values())
        if total_passes + total_failures > 0:
            gate_pass_rate = total_passes / (total_passes + total_failures) * 100
            print(f"\n🚦 Gate Pass Rate: {gate_pass_rate:.1f}%")
        
        # Top rejection reasons
        if summary['edges_rejected']:
            print("\n🔴 Top Rejection Reasons:")
            sorted_rejections = sorted(
                summary['edges_rejected'].items(),
                key=lambda x: x[1],
                reverse=True
            )[:5]
            for (sport, market, reason), count in sorted_rejections:
                print(f"   • {reason} ({sport}/{market}): {count}")
        
        # API health
        api_stats = summary['api_calls']
        if api_stats:
            print("\n🌐 API Health:")
            apis = set(api for api, _ in api_stats.keys())
            for api in apis:
                success = api_stats.get((api, 'success'), 0)
                failure = api_stats.get((api, 'failure'), 0)
                total = success + failure
                if total > 0:
                    rate = success / total * 100
                    status = "✅" if rate >= 95 else "⚠️" if rate >= 80 else "🔴"
                    print(f"   {status} {api}: {rate:.1f}% success ({total} calls)")
        
        print("\n" + "=" * 60)
    
    def export_prometheus(self) -> bytes:
        """Export metrics in Prometheus format."""
        if PROMETHEUS_AVAILABLE:
            return generate_latest(self.registry)
        return b""
    
    def save_snapshot(self):
        """Save current metrics to file."""
        snapshot = {
            "timestamp": datetime.now().isoformat(),
            "metrics": self.get_summary()
        }
        
        # Load existing history
        history = []
        if self._metrics_file.exists():
            try:
                with open(self._metrics_file) as f:
                    history = json.load(f)
            except:
                pass
        
        history.append(snapshot)
        
        # Keep last 1000 snapshots
        history = history[-1000:]
        
        with open(self._metrics_file, 'w') as f:
            json.dump(history, f, indent=2)


class _TimingContext:
    """Context manager for timing operations."""
    
    def __init__(self, metrics: FUOOMMetrics, sport: str, operation: str):
        self.metrics = metrics
        self.sport = sport
        self.operation = operation
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time
        self.metrics.record_processing_time(self.sport, self.operation, duration)


# Singleton accessor
_metrics_instance: Optional[FUOOMMetrics] = None

def get_metrics() -> FUOOMMetrics:
    """Get the singleton metrics instance."""
    global _metrics_instance
    if _metrics_instance is None:
        _metrics_instance = FUOOMMetrics()
    return _metrics_instance
