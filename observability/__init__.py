"""
FUOOM Observability Layer
========================
Production-grade metrics, tracing, and circuit breakers.

Usage:
    from observability import metrics, circuit_breaker, tracer
    
    # Record an edge generation
    metrics.record_edge_generated("NBA", "PTS", "STRONG")
    
    # Wrap API calls with circuit breaker
    @circuit_breaker.api_breaker
    def fetch_external_data():
        ...
    
    # Trace pipeline execution
    with tracer.span("analyze_slate"):
        ...
"""

from .metrics import FUOOMMetrics, get_metrics
from .circuit_breaker import CircuitBreakerManager, get_circuit_breaker
from .tracer import FUOOMTracer, get_tracer
from .health import HealthChecker, get_health_checker
from .cross_sport_audit import CrossSportAuditor, AuditResult, IsolationViolation

# Singleton instances
metrics = get_metrics()
circuit_breaker = get_circuit_breaker()
tracer = get_tracer()
health = get_health_checker()

__all__ = [
    'metrics',
    'circuit_breaker', 
    'tracer',
    'health',
    'FUOOMMetrics',
    'CircuitBreakerManager',
    'FUOOMTracer',
    'HealthChecker',
    'CrossSportAuditor',
    'AuditResult',
    'IsolationViolation',
]
