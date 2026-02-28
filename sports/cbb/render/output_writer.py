"""
CBB Output Writer

Writes reports to disk in JSON and text formats.
"""
from typing import Dict
from pathlib import Path
from datetime import datetime
from dataclasses import asdict
import json

from .report_generator import CBBReport, format_report_text


OUTPUT_DIR = Path("outputs/cbb")


def write_output(report: CBBReport) -> Dict[str, Path]:
    """
    Write CBB report to output files.
    
    Creates:
    - cbb_report_YYYYMMDD.json (structured data)
    - cbb_report_YYYYMMDD.txt (human readable)
    
    Returns:
        Dict mapping format to file path
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    date_str = report.date.replace("-", "")
    
    # Write JSON
    json_path = OUTPUT_DIR / f"cbb_report_{date_str}.json"
    with open(json_path, "w") as f:
        json.dump(asdict(report), f, indent=2)
    
    # Write text
    text_path = OUTPUT_DIR / f"cbb_report_{date_str}.txt"
    with open(text_path, "w") as f:
        f.write(format_report_text(report))
    
    # Also write latest symlinks
    latest_json = OUTPUT_DIR / "cbb_report_latest.json"
    latest_txt = OUTPUT_DIR / "cbb_report_latest.txt"
    
    # Copy to latest (Windows doesn't always support symlinks)
    with open(latest_json, "w") as f:
        json.dump(asdict(report), f, indent=2)
    with open(latest_txt, "w") as f:
        f.write(format_report_text(report))
    
    return {
        "json": json_path,
        "text": text_path,
        "latest_json": latest_json,
        "latest_text": latest_txt,
    }


def load_latest_report() -> CBBReport:
    """Load the most recent CBB report."""
    latest_json = OUTPUT_DIR / "cbb_report_latest.json"
    
    if not latest_json.exists():
        raise FileNotFoundError("No CBB report found")
    
    with open(latest_json) as f:
        data = json.load(f)
    
    return CBBReport(**data)


def list_reports(limit: int = 10) -> list:
    """List available CBB reports."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    reports = []
    for f in sorted(OUTPUT_DIR.glob("cbb_report_*.json"), reverse=True):
        if "latest" not in f.name:
            reports.append({
                "file": f.name,
                "path": str(f),
                "date": f.stem.replace("cbb_report_", ""),
            })
            if len(reports) >= limit:
                break
    
    return reports
