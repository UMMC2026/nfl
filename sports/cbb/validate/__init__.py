"""
CBB Validation Module

Render Gate + Schema Validation
If any fail → ABORT REPORT
"""
from .render_gate import apply_render_gate, RenderGateError
from .schema_validator import validate_edge_schema

__all__ = ["apply_render_gate", "validate_edge_schema", "RenderGateError"]
