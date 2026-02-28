"""
FUOOM Circuit Breaker Layer
===========================
Prevents cascade failures when external APIs fail.

Usage:
    from observability import circuit_breaker
    
    @circuit_breaker.protect("espn_api")
    def fetch_from_espn():
        ...
    
    # Check circuit state
    if circuit_breaker.is_open("espn_api"):
        use_fallback_data()
"""

import time
import threading
import functools
from typing import Dict, Callable, Optional, Any
from datetime import datetime
from enum import Enum


class CircuitState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Circuit tripped, blocking calls
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitStats:
    """Statistics for a single circuit."""
    
    def __init__(self, name: str):
        self.name = name
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.last_success_time: Optional[datetime] = None
        self.opened_at: Optional[datetime] = None
        self.total_calls = 0
        self.total_failures = 0
        self.consecutive_failures = 0


class CircuitBreakerManager:
    """
    Manages circuit breakers for all external services.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    # Default settings
    DEFAULT_FAIL_THRESHOLD = 3      # Open after 3 consecutive failures
    DEFAULT_RESET_TIMEOUT = 60      # Seconds before half-open
    DEFAULT_HALF_OPEN_MAX = 1       # Test calls in half-open state
    
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
        self._circuits: Dict[str, CircuitStats] = {}
        self._settings: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()
        
        # Pre-configure known APIs
        self._configure_default_circuits()
    
    def _configure_default_circuits(self):
        """Pre-configure circuit breakers for known APIs."""
        known_apis = [
            ("espn_api", {"fail_threshold": 3, "reset_timeout": 60}),
            ("basketball_reference", {"fail_threshold": 5, "reset_timeout": 120}),
            ("underdog_api", {"fail_threshold": 3, "reset_timeout": 30}),
            ("nba_api", {"fail_threshold": 3, "reset_timeout": 60}),
            ("tennis_api", {"fail_threshold": 5, "reset_timeout": 90}),
            ("telegram_api", {"fail_threshold": 5, "reset_timeout": 60}),
            ("serpapi", {"fail_threshold": 3, "reset_timeout": 120}),
        ]
        
        for api_name, settings in known_apis:
            self.configure(api_name, **settings)
    
    def configure(self, name: str, 
                  fail_threshold: int = DEFAULT_FAIL_THRESHOLD,
                  reset_timeout: int = DEFAULT_RESET_TIMEOUT,
                  half_open_max: int = DEFAULT_HALF_OPEN_MAX):
        """Configure a circuit breaker."""
        self._settings[name] = {
            "fail_threshold": fail_threshold,
            "reset_timeout": reset_timeout,
            "half_open_max": half_open_max,
        }
        if name not in self._circuits:
            self._circuits[name] = CircuitStats(name)
    
    def _get_circuit(self, name: str) -> CircuitStats:
        """Get or create a circuit."""
        if name not in self._circuits:
            self._circuits[name] = CircuitStats(name)
        return self._circuits[name]
    
    def _get_settings(self, name: str) -> Dict[str, Any]:
        """Get settings for a circuit."""
        return self._settings.get(name, {
            "fail_threshold": self.DEFAULT_FAIL_THRESHOLD,
            "reset_timeout": self.DEFAULT_RESET_TIMEOUT,
            "half_open_max": self.DEFAULT_HALF_OPEN_MAX,
        })
    
    def _check_state(self, circuit: CircuitStats) -> CircuitState:
        """Check and potentially transition circuit state."""
        if circuit.state == CircuitState.OPEN:
            settings = self._get_settings(circuit.name)
            
            # Check if reset timeout has passed
            if circuit.opened_at:
                elapsed = (datetime.now() - circuit.opened_at).total_seconds()
                if elapsed >= settings["reset_timeout"]:
                    circuit.state = CircuitState.HALF_OPEN
                    return CircuitState.HALF_OPEN
        
        return circuit.state
    
    def is_open(self, name: str) -> bool:
        """Check if a circuit is open (blocking calls)."""
        circuit = self._get_circuit(name)
        state = self._check_state(circuit)
        return state == CircuitState.OPEN
    
    def can_execute(self, name: str) -> bool:
        """Check if a call can be executed."""
        circuit = self._get_circuit(name)
        state = self._check_state(circuit)
        return state != CircuitState.OPEN
    
    def record_success(self, name: str):
        """Record a successful call."""
        with self._lock:
            circuit = self._get_circuit(name)
            circuit.success_count += 1
            circuit.total_calls += 1
            circuit.consecutive_failures = 0
            circuit.last_success_time = datetime.now()
            
            # Reset to closed if in half-open
            if circuit.state == CircuitState.HALF_OPEN:
                circuit.state = CircuitState.CLOSED
                circuit.failure_count = 0
                print(f"🟢 Circuit '{name}' CLOSED (recovered)")
    
    def record_failure(self, name: str, error: Optional[Exception] = None):
        """Record a failed call."""
        with self._lock:
            circuit = self._get_circuit(name)
            settings = self._get_settings(name)
            
            circuit.failure_count += 1
            circuit.total_failures += 1
            circuit.total_calls += 1
            circuit.consecutive_failures += 1
            circuit.last_failure_time = datetime.now()
            
            # Check if threshold reached
            if circuit.consecutive_failures >= settings["fail_threshold"]:
                if circuit.state != CircuitState.OPEN:
                    circuit.state = CircuitState.OPEN
                    circuit.opened_at = datetime.now()
                    print(f"🔴 Circuit '{name}' OPENED after {circuit.consecutive_failures} failures")
            
            # If in half-open and failed, reopen
            elif circuit.state == CircuitState.HALF_OPEN:
                circuit.state = CircuitState.OPEN
                circuit.opened_at = datetime.now()
                print(f"🔴 Circuit '{name}' REOPENED (test failed)")
    
    def protect(self, name: str, fallback: Optional[Callable] = None):
        """
        Decorator to protect a function with a circuit breaker.
        
        Usage:
            @circuit_breaker.protect("espn_api")
            def fetch_espn_data():
                ...
        """
        def decorator(func: Callable) -> Callable:
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                if not self.can_execute(name):
                    if fallback:
                        print(f"⚠️  Circuit '{name}' open, using fallback")
                        return fallback(*args, **kwargs)
                    raise CircuitOpenError(f"Circuit '{name}' is OPEN")
                
                try:
                    result = func(*args, **kwargs)
                    self.record_success(name)
                    return result
                except Exception as e:
                    self.record_failure(name, e)
                    raise
            
            return wrapper
        return decorator
    
    def get_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all circuits."""
        status = {}
        for name, circuit in self._circuits.items():
            state = self._check_state(circuit)
            settings = self._get_settings(name)
            
            status[name] = {
                "state": state.value,
                "failure_count": circuit.failure_count,
                "success_count": circuit.success_count,
                "total_calls": circuit.total_calls,
                "consecutive_failures": circuit.consecutive_failures,
                "fail_threshold": settings["fail_threshold"],
                "reset_timeout": settings["reset_timeout"],
                "last_failure": circuit.last_failure_time.isoformat() if circuit.last_failure_time else None,
                "last_success": circuit.last_success_time.isoformat() if circuit.last_success_time else None,
            }
        
        return status
    
    def print_status(self):
        """Print formatted circuit breaker status."""
        status = self.get_status()
        
        print("\n" + "=" * 60)
        print("  🔌 CIRCUIT BREAKER STATUS")
        print("=" * 60)
        
        for name, info in sorted(status.items()):
            state = info["state"]
            if state == "closed":
                icon = "🟢"
            elif state == "open":
                icon = "🔴"
            else:
                icon = "🟡"
            
            success_rate = 0
            if info["total_calls"] > 0:
                success_rate = (info["success_count"] / info["total_calls"]) * 100
            
            print(f"\n{icon} {name}")
            print(f"   State: {state.upper()}")
            print(f"   Success Rate: {success_rate:.1f}%")
            print(f"   Total Calls: {info['total_calls']}")
            print(f"   Consecutive Failures: {info['consecutive_failures']}/{info['fail_threshold']}")
        
        print("\n" + "=" * 60)
    
    def reset(self, name: str):
        """Manually reset a circuit to closed state."""
        with self._lock:
            if name in self._circuits:
                circuit = self._circuits[name]
                circuit.state = CircuitState.CLOSED
                circuit.failure_count = 0
                circuit.consecutive_failures = 0
                print(f"🔄 Circuit '{name}' manually reset to CLOSED")
    
    def reset_all(self):
        """Reset all circuits to closed state."""
        with self._lock:
            for name in self._circuits:
                self.reset(name)


class CircuitOpenError(Exception):
    """Raised when trying to call through an open circuit."""
    pass


# Singleton accessor
_cb_instance: Optional[CircuitBreakerManager] = None

def get_circuit_breaker() -> CircuitBreakerManager:
    """Get the singleton circuit breaker manager."""
    global _cb_instance
    if _cb_instance is None:
        _cb_instance = CircuitBreakerManager()
    return _cb_instance
