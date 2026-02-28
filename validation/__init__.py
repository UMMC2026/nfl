"""
FUOOM Validation Module
=======================
Output validation gates for SOP v2.1 compliance.
"""

from .validate_output import (
    EdgeValidator,
    ValidationResult,
    ValidationSeverity,
    TierConfig,
)

__all__ = [
    'EdgeValidator',
    'ValidationResult',
    'ValidationSeverity',
    'TierConfig',
]
