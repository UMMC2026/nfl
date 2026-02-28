"""
CBB Report Generator

Produces structured reports from validated edges.
"""
from typing import Dict, List
from datetime import datetime
from dataclasses import dataclass, asdict


@dataclass
class CBBReport:
    """CBB daily report structure"""
    report_id: str
    date: str
    generated_at: str
    
    # Summary
    total_games: int
    total_edges: int
    primary_edges: int
    blocked_edges: int
    
    # Tier breakdown
    strong_count: int
    lean_count: int
    no_play_count: int
    
    # Edges by tier
    strong_edges: List[Dict]
    lean_edges: List[Dict]
    
    # Metadata
    calibration_status: str
    validation_status: str


def generate_report(
    edges: List,
    date: str,
    games: List[Dict]
) -> CBBReport:
    """
    Generate CBB report from validated edges.
    
    Args:
        edges: List of CBBEdge objects
        date: Report date (YYYY-MM-DD)
        games: List of game dictionaries
        
    Returns:
        CBBReport with all data
    """
    # Filter to primary, non-blocked edges
    primary_edges = [e for e in edges if e.is_primary and not e.is_blocked]
    blocked_edges = [e for e in edges if e.is_blocked]
    
    # Group by tier
    strong = [e for e in primary_edges if e.tier == "STRONG"]
    lean = [e for e in primary_edges if e.tier == "LEAN"]
    no_play = [e for e in primary_edges if e.tier == "NO_PLAY"]
    
    # Convert to dicts for output
    def edge_to_dict(edge) -> Dict:
        return {
            "edge_id": edge.edge_id,
            "player": edge.player_name,
            "team": edge.team,
            "opponent": edge.opponent,
            "stat": edge.stat,
            "line": edge.line,
            "direction": edge.direction,
            "probability": edge.probability,
            "tier": edge.tier,
            "is_conference": edge.is_conference_game,
            "sample_size": edge.sample_size,
            # v2.0 tags (optional; present when upstream populates them)
            "mean_source": getattr(edge, "mean_source", None),
            "confidence_flag": getattr(edge, "confidence_flag", None),
            "signal_flag": getattr(edge, "signal_flag", None),
        }
    
    report_id = f"cbb_{date.replace('-', '')}"
    
    return CBBReport(
        report_id=report_id,
        date=date,
        generated_at=datetime.now().isoformat(),
        
        total_games=len(games),
        total_edges=len(edges),
        primary_edges=len(primary_edges),
        blocked_edges=len(blocked_edges),
        
        strong_count=len(strong),
        lean_count=len(lean),
        no_play_count=len(no_play),
        
        strong_edges=[edge_to_dict(e) for e in strong],
        lean_edges=[edge_to_dict(e) for e in lean],
        
        calibration_status="PENDING",  # Updated after calibration check
        validation_status="PENDING",   # Updated after validation
    )


def format_report_text(report: CBBReport) -> str:
    """
    Format report as human-readable text.
    """
    lines = [
        "=" * 60,
        f"CBB REPORT — {report.date}",
        "=" * 60,
        "",
        f"Generated: {report.generated_at}",
        f"Games: {report.total_games}",
        f"Total Edges: {report.total_edges}",
        f"Primary Edges: {report.primary_edges}",
        f"Blocked: {report.blocked_edges}",
        "",
        "-" * 60,
        "TIER BREAKDOWN",
        "-" * 60,
        f"STRONG: {report.strong_count}",
        f"LEAN: {report.lean_count}",
        f"NO_PLAY: {report.no_play_count}",
        "",
    ]
    
    if report.strong_edges:
        lines.extend([
            "-" * 60,
            "🔥 STRONG EDGES",
            "-" * 60,
        ])
        for e in report.strong_edges:
            tags = []
            if e.get("mean_source"):
                tags.append(f"mean_source={e['mean_source']}")
            if e.get("confidence_flag"):
                tags.append(f"confidence={e['confidence_flag']}")
            if e.get("signal_flag"):
                tags.append(f"signal={e['signal_flag']}")
            tag_str = (" | " + " ".join(tags)) if tags else ""
            lines.append(
                f"  {e['player']} ({e['team']}) — {e['stat']} {e['direction'].upper()} {e['line']} "
                f"[{e['probability']:.1%}]{tag_str}"
            )
        lines.append("")
    
    if report.lean_edges:
        lines.extend([
            "-" * 60,
            "📊 LEAN EDGES",
            "-" * 60,
        ])
        for e in report.lean_edges:
            tags = []
            if e.get("mean_source"):
                tags.append(f"mean_source={e['mean_source']}")
            if e.get("confidence_flag"):
                tags.append(f"confidence={e['confidence_flag']}")
            if e.get("signal_flag"):
                tags.append(f"signal={e['signal_flag']}")
            tag_str = (" | " + " ".join(tags)) if tags else ""
            lines.append(
                f"  {e['player']} ({e['team']}) — {e['stat']} {e['direction'].upper()} {e['line']} "
                f"[{e['probability']:.1%}]{tag_str}"
            )
        lines.append("")
    
    lines.extend([
        "=" * 60,
        f"Validation: {report.validation_status}",
        f"Calibration: {report.calibration_status}",
        "=" * 60,
    ])
    
    return "\n".join(lines)
