"""
Tennis Render Report
====================
Produces final human-readable output from validated edges.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List

TENNIS_DIR = Path(__file__).parent.parent
OUTPUTS_DIR = TENNIS_DIR / "outputs"


def render_edge_text(edge: Dict) -> str:
    """Render single edge to text format."""
    tier = edge.get("tier", "?")
    tier_emoji = {"STRONG": "🔥", "LEAN": "📈", "NO_PLAY": "⏸️", "BLOCKED": "🚫"}.get(tier, "❓")
    
    market = edge.get("market", "?")
    direction = edge.get("direction", "?")
    line = edge.get("line", "?")
    prob = edge.get("probability")
    prob_str = f"{prob:.1%}" if prob else "N/A"
    edge_val = edge.get("edge")
    edge_str = f"{edge_val:+.1%}" if edge_val else "N/A"
    
    # Player names
    if "players" in edge:
        players = " vs ".join(edge["players"])
    elif "player" in edge:
        players = f"{edge['player']} (vs {edge.get('opponent', '?')})"
    else:
        players = "Unknown"
    
    surface = edge.get("surface", "?")
    best_of = edge.get("best_of", "?")
    
    return (
        f"{tier_emoji} [{tier}] {market}\n"
        f"   {players} | {surface} | Bo{best_of}\n"
        f"   {direction} {line} | P={prob_str} | edge={edge_str}"
    )


def render_report(data: Dict, output_format: str = "text") -> str:
    """Render full report."""
    
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    
    if output_format == "text":
        lines = []
        lines.append("=" * 60)
        lines.append("TENNIS MODULE — DAILY REPORT")
        lines.append(f"Generated: {timestamp}")
        lines.append("=" * 60)
        
        # Check if merged format
        if "engines" in data:
            for engine_name, engine_data in data["engines"].items():
                edges = engine_data.get("edges", [])
                playable = [e for e in edges if e.get("tier") in ("STRONG", "LEAN")]
                
                lines.append(f"\n--- {engine_name} ---")
                lines.append(f"Playable: {len(playable)}")
                
                for e in playable:
                    lines.append("")
                    lines.append(render_edge_text(e))
        else:
            edges = data.get("edges", [])
            playable = [e for e in edges if e.get("tier") in ("STRONG", "LEAN")]
            
            lines.append(f"\nPlayable edges: {len(playable)}")
            
            for e in playable:
                lines.append("")
                lines.append(render_edge_text(e))
        
        lines.append("\n" + "=" * 60)
        lines.append("END REPORT")
        lines.append("=" * 60)
        
        return "\n".join(lines)
    
    elif output_format == "markdown":
        lines = []
        lines.append("# Tennis Module — Daily Report")
        lines.append(f"*Generated: {timestamp}*")
        lines.append("")
        
        if "engines" in data:
            for engine_name, engine_data in data["engines"].items():
                edges = engine_data.get("edges", [])
                playable = [e for e in edges if e.get("tier") in ("STRONG", "LEAN")]
                
                lines.append(f"## {engine_name}")
                lines.append(f"**Playable:** {len(playable)}")
                lines.append("")
                
                if playable:
                    lines.append("| Tier | Market | Match | Line | P | Edge |")
                    lines.append("|------|--------|-------|------|---|------|")
                    
                    for e in playable:
                        tier = e.get("tier")
                        market = e.get("market")
                        if "players" in e:
                            match = " vs ".join(e["players"])
                        elif "player" in e:
                            match = f"{e['player']} vs {e.get('opponent', '?')}"
                        else:
                            match = "?"
                        
                        direction = e.get("direction", "?")
                        line = e.get("line", "?")
                        prob = e.get("probability")
                        prob_str = f"{prob:.1%}" if prob else "N/A"
                        edge_val = e.get("edge")
                        edge_str = f"{edge_val:+.1%}" if edge_val else "N/A"
                        
                        lines.append(f"| {tier} | {market} | {match} | {direction} {line} | {prob_str} | {edge_str} |")
                    
                    lines.append("")
        else:
            edges = data.get("edges", [])
            playable = [e for e in edges if e.get("tier") in ("STRONG", "LEAN")]
            
            lines.append(f"**Playable edges:** {len(playable)}")
            lines.append("")
            
            if playable:
                lines.append("| Tier | Market | Match | Line | P | Edge |")
                lines.append("|------|--------|-------|------|---|------|")
                
                for e in playable:
                    tier = e.get("tier")
                    market = e.get("market")
                    if "players" in e:
                        match = " vs ".join(e["players"])
                    elif "player" in e:
                        match = f"{e['player']} vs {e.get('opponent', '?')}"
                    else:
                        match = "?"
                    
                    direction = e.get("direction", "?")
                    line = e.get("line", "?")
                    prob = e.get("probability")
                    prob_str = f"{prob:.1%}" if prob else "N/A"
                    edge_val = e.get("edge")
                    edge_str = f"{edge_val:+.1%}" if edge_val else "N/A"
                    
                    lines.append(f"| {tier} | {market} | {match} | {direction} {line} | {prob_str} | {edge_str} |")
        
        return "\n".join(lines)
    
    else:
        return json.dumps(data, indent=2)


def main():
    parser = argparse.ArgumentParser(description="Tennis Report Renderer")
    parser.add_argument("--edges", required=True, help="Path to validated edges JSON")
    parser.add_argument("--format", choices=["text", "markdown", "json"], default="text")
    parser.add_argument("--output", help="Output file path")
    
    args = parser.parse_args()
    
    edges_path = Path(args.edges)
    if not edges_path.exists():
        print(f"Error: File not found: {edges_path}")
        return 1
    
    data = json.loads(edges_path.read_text(encoding="utf-8"))
    
    report = render_report(data, args.format)
    
    if args.output:
        out_path = Path(args.output)
        out_path.write_text(report, encoding="utf-8")
        print(f"Report written to: {out_path}")
    else:
        print(report)
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
