"""
FUOOM Health Check Layer
========================
System health monitoring and alerting.

Usage:
    from observability import health
    
    # Check overall system health
    status = health.check_all()
    
    # Register custom health checks
    health.register("my_service", lambda: check_my_service())
"""

import threading
from datetime import datetime, timedelta
from typing import Dict, Any, Callable, Optional, List
from pathlib import Path
from enum import Enum


class HealthStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class HealthCheck:
    """Individual health check result."""
    
    def __init__(self, name: str, status: HealthStatus, 
                 message: str = "", details: Optional[Dict] = None):
        self.name = name
        self.status = status
        self.message = message
        self.details = details or {}
        self.checked_at = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status.value,
            "message": self.message,
            "details": self.details,
            "checked_at": self.checked_at.isoformat(),
        }


class HealthChecker:
    """
    Central health monitoring for FUOOM system.
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
        self._checks: Dict[str, Callable[[], HealthCheck]] = {}
        self._last_results: Dict[str, HealthCheck] = {}
        
        # Register default checks
        self._register_default_checks()
    
    def _register_default_checks(self):
        """Register built-in health checks."""
        self.register("cache_directory", self._check_cache_dir)
        self.register("outputs_directory", self._check_outputs_dir)
        self.register("calibration_data", self._check_calibration)
        self.register("config_files", self._check_config)
    
    def register(self, name: str, check_fn: Callable[[], HealthCheck]):
        """Register a health check."""
        self._checks[name] = check_fn
    
    def _check_cache_dir(self) -> HealthCheck:
        """Check cache directory health."""
        cache_path = Path("cache")
        if not cache_path.exists():
            return HealthCheck(
                "cache_directory",
                HealthStatus.UNHEALTHY,
                "Cache directory missing"
            )
        
        # Check for stale cache files (older than 24 hours)
        stale_files = []
        for f in cache_path.glob("*.json"):
            if datetime.fromtimestamp(f.stat().st_mtime) < datetime.now() - timedelta(hours=24):
                stale_files.append(f.name)
        
        if len(stale_files) > 10:
            return HealthCheck(
                "cache_directory",
                HealthStatus.DEGRADED,
                f"{len(stale_files)} stale cache files",
                {"stale_files": stale_files[:5]}
            )
        
        return HealthCheck(
            "cache_directory",
            HealthStatus.HEALTHY,
            "Cache directory OK"
        )
    
    def _check_outputs_dir(self) -> HealthCheck:
        """Check outputs directory health."""
        outputs_path = Path("outputs")
        if not outputs_path.exists():
            return HealthCheck(
                "outputs_directory",
                HealthStatus.UNHEALTHY,
                "Outputs directory missing"
            )
        
        # Check recent output count
        recent_outputs = list(outputs_path.glob("*.txt")) + list(outputs_path.glob("*.json"))
        today = datetime.now().date()
        todays_outputs = [
            f for f in recent_outputs 
            if datetime.fromtimestamp(f.stat().st_mtime).date() == today
        ]
        
        return HealthCheck(
            "outputs_directory",
            HealthStatus.HEALTHY,
            f"{len(todays_outputs)} outputs today",
            {"total_files": len(recent_outputs), "today": len(todays_outputs)}
        )
    
    def _check_calibration(self) -> HealthCheck:
        """Check calibration data health."""
        cal_file = Path("calibration_history.csv")
        if not cal_file.exists():
            return HealthCheck(
                "calibration_data",
                HealthStatus.DEGRADED,
                "Calibration history not found"
            )
        
        # Check file age
        mod_time = datetime.fromtimestamp(cal_file.stat().st_mtime)
        age_days = (datetime.now() - mod_time).days
        
        if age_days > 7:
            return HealthCheck(
                "calibration_data",
                HealthStatus.DEGRADED,
                f"Calibration data {age_days} days old",
                {"last_updated": mod_time.isoformat()}
            )
        
        return HealthCheck(
            "calibration_data",
            HealthStatus.HEALTHY,
            "Calibration data current",
            {"last_updated": mod_time.isoformat()}
        )
    
    def _check_config(self) -> HealthCheck:
        """Check configuration files."""
        required_configs = [
            "config/thresholds.py",
            "config/sport_registry.json",
        ]
        
        missing = [c for c in required_configs if not Path(c).exists()]
        
        if missing:
            return HealthCheck(
                "config_files",
                HealthStatus.UNHEALTHY,
                f"Missing configs: {', '.join(missing)}",
                {"missing": missing}
            )
        
        return HealthCheck(
            "config_files",
            HealthStatus.HEALTHY,
            "All config files present"
        )
    
    def check(self, name: str) -> HealthCheck:
        """Run a specific health check."""
        if name not in self._checks:
            return HealthCheck(name, HealthStatus.UNHEALTHY, "Check not found")
        
        try:
            result = self._checks[name]()
            self._last_results[name] = result
            return result
        except Exception as e:
            result = HealthCheck(
                name, 
                HealthStatus.UNHEALTHY,
                f"Check failed: {str(e)}"
            )
            self._last_results[name] = result
            return result
    
    def check_all(self) -> Dict[str, HealthCheck]:
        """Run all health checks."""
        results = {}
        for name in self._checks:
            results[name] = self.check(name)
        return results
    
    def get_overall_status(self) -> HealthStatus:
        """Get overall system health status."""
        results = self.check_all()
        
        statuses = [r.status for r in results.values()]
        
        if HealthStatus.UNHEALTHY in statuses:
            return HealthStatus.UNHEALTHY
        if HealthStatus.DEGRADED in statuses:
            return HealthStatus.DEGRADED
        return HealthStatus.HEALTHY
    
    def print_status(self):
        """Print formatted health status."""
        results = self.check_all()
        overall = self.get_overall_status()
        
        status_icons = {
            HealthStatus.HEALTHY: "🟢",
            HealthStatus.DEGRADED: "🟡",
            HealthStatus.UNHEALTHY: "🔴",
        }
        
        print("\n" + "=" * 60)
        print(f"  💊 SYSTEM HEALTH: {status_icons[overall]} {overall.value.upper()}")
        print("=" * 60)
        
        for name, check in sorted(results.items()):
            icon = status_icons[check.status]
            print(f"\n{icon} {name}")
            print(f"   Status: {check.status.value}")
            print(f"   Message: {check.message}")
            if check.details:
                for key, value in check.details.items():
                    print(f"   {key}: {value}")
        
        print("\n" + "=" * 60)
    
    def to_dict(self) -> Dict[str, Any]:
        """Export health status as dictionary."""
        results = self.check_all()
        return {
            "overall": self.get_overall_status().value,
            "checked_at": datetime.now().isoformat(),
            "checks": {name: check.to_dict() for name, check in results.items()}
        }


# Singleton accessor
_health_instance: Optional[HealthChecker] = None

def get_health_checker() -> HealthChecker:
    """Get the singleton health checker instance."""
    global _health_instance
    if _health_instance is None:
        _health_instance = HealthChecker()
    return _health_instance
