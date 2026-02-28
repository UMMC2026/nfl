"""
CBB Render Module

Produces final output: JSON + text reports
Same professional surface as NFL/NBA
"""
from .report_generator import generate_report
from .output_writer import write_output

__all__ = ["generate_report", "write_output"]
