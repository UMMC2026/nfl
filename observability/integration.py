"""
FUOOM Observability Integration
==============================
Helper functions to integrate observability into existing pipelines.

Usage:
    from observability.integration import (
        instrument_api_call,
        instrument_gate,
        instrument_edge_generation,
        wrap_pipeline
    )
    
    # Wrap API calls
    @instrument_api_call("espn_api")
    def fetch_espn_data():
        ...
    
    # Or manually in existing code:
    with instrument_gate("NBA", "eligibility"):
        result = check_eligibility(edge)
        if not result:
            raise GateFailure("Low probability")
"""

import functools
import time
from typing import Callable, Any, Optional
from contextlib import contextmanager

from .metrics import get_metrics
from .circuit_breaker import get_circuit_breaker, CircuitOpenError
from .tracer import get_tracer


def instrument_api_call(api_name: str, fallback: Optional[Callable] = None):
    """
    Decorator to instrument an API call with metrics and circuit breaker.
    
    Usage:
        @instrument_api_call("espn_api")
        def fetch_player_stats(player_id):
            return requests.get(f"https://api.espn.com/...")
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            metrics = get_metrics()
            cb = get_circuit_breaker()
            tracer = get_tracer()
            
            # Check circuit breaker
            if not cb.can_execute(api_name):
                if fallback:
                    return fallback(*args, **kwargs)
                raise CircuitOpenError(f"Circuit '{api_name}' is open")
            
            start_time = time.time()
            
            with tracer.span(f"api_call_{api_name}", api=api_name) as span:
                try:
                    result = func(*args, **kwargs)
                    
                    latency = time.time() - start_time
                    metrics.record_api_call(api_name, success=True, latency=latency)
                    cb.record_success(api_name)
                    
                    span.set_attribute("latency_ms", latency * 1000)
                    span.set_attribute("success", True)
                    
                    return result
                    
                except Exception as e:
                    latency = time.time() - start_time
                    metrics.record_api_call(api_name, success=False, latency=latency)
                    cb.record_failure(api_name, e)
                    
                    span.set_attribute("latency_ms", latency * 1000)
                    span.set_error(e)
                    
                    raise
        
        return wrapper
    return decorator


@contextmanager
def instrument_gate(sport: str, gate_name: str):
    """
    Context manager to instrument a validation gate.
    
    Usage:
        with instrument_gate("NBA", "eligibility"):
            if probability < 0.55:
                raise GateFailure("Low probability")
    """
    metrics = get_metrics()
    tracer = get_tracer()
    
    with tracer.span(f"gate_{gate_name}", sport=sport, gate=gate_name) as span:
        try:
            yield span
            metrics.record_gate_pass(sport, gate_name)
            span.set_attribute("passed", True)
        except Exception as e:
            failure_type = type(e).__name__
            metrics.record_gate_failure(sport, gate_name, failure_type)
            span.set_attribute("passed", False)
            span.set_error(e)
            raise


def instrument_edge_generation(sport: str, market: str):
    """
    Decorator to instrument edge generation.
    
    Usage:
        @instrument_edge_generation("NBA", "PTS")
        def generate_points_edges(players):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            metrics = get_metrics()
            tracer = get_tracer()
            
            with metrics.time_operation(sport, f"generate_{market}_edges"):
                with tracer.span(f"generate_edges", sport=sport, market=market) as span:
                    result = func(*args, **kwargs)
                    
                    # Count edges by tier
                    if isinstance(result, list):
                        span.set_attribute("edge_count", len(result))
                        for edge in result:
                            tier = edge.get("tier", "UNKNOWN")
                            metrics.record_edge_generated(sport, market, tier)
                    
                    return result
        
        return wrapper
    return decorator


def record_edge_rejection(sport: str, market: str, reason: str, player: str = None):
    """
    Record when an edge is rejected by governance.
    
    Usage:
        if probability < 0.55:
            record_edge_rejection("NBA", "PTS", "LOW_PROBABILITY", player="LeBron")
            continue
    """
    metrics = get_metrics()
    tracer = get_tracer()
    
    metrics.record_edge_rejected(sport, market, reason)
    
    # Add to current trace if active
    current = tracer.get_current_trace()
    if current is not None:
        tracer.span("edge_rejected", sport=sport, market=market, reason=reason, player=player or "unknown")


def wrap_pipeline(sport: str):
    """
    Decorator to wrap an entire pipeline run with tracing.
    
    Usage:
        @wrap_pipeline("NBA")
        def run_daily_analysis():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            metrics = get_metrics()
            tracer = get_tracer()
            
            # Start new trace for this pipeline run
            trace_id = tracer.start_trace()
            
            with metrics.time_operation(sport, "full_pipeline"):
                with tracer.span(f"pipeline_{sport}", sport=sport) as span:
                    try:
                        result = func(*args, **kwargs)
                        span.add_event("pipeline_complete")
                        return result
                    except Exception as e:
                        span.set_error(e)
                        raise
                    finally:
                        # End trace and save
                        summary = tracer.end_trace()
                        if summary:
                            span.set_attribute("trace_saved", True)
                        
                        # Save metrics snapshot
                        metrics.save_snapshot()
        
        return wrapper
    return decorator


# Quick integration for existing code
def quick_metric(name: str, value: float = 1.0, labels: dict = None):
    """
    Quick way to record a metric from anywhere.
    
    Usage:
        quick_metric("picks_generated", 15, {"sport": "NBA", "tier": "STRONG"})
    """
    metrics = get_metrics()
    labels = labels or {}
    
    sport = labels.get("sport", "unknown")
    market = labels.get("market", "general")
    
    if "edge" in name.lower():
        tier = labels.get("tier", "UNKNOWN")
        for _ in range(int(value)):
            metrics.record_edge_generated(sport, market, tier)
    elif "reject" in name.lower():
        reason = labels.get("reason", "unknown")
        for _ in range(int(value)):
            metrics.record_edge_rejected(sport, market, reason)


def get_observability_summary() -> dict:
    """Get full observability summary for reports."""
    from .health import get_health_checker
    
    metrics = get_metrics()
    cb = get_circuit_breaker()
    health = get_health_checker()
    
    return {
        "metrics": metrics.get_summary(),
        "circuits": cb.get_status(),
        "health": health.to_dict(),
    }
