"""Easy integration helpers for the production Ollama validator."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

# Ensure src/ is on sys.path so imports work when running as a script
ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ollama_integration.production_validator import (  # type: ignore
    OllamaProductionValidator,
    ValidationResult,
    ValidationStatus,
)


_PRODUCTION_VALIDATOR: OllamaProductionValidator | None = None


def get_validator() -> OllamaProductionValidator:
    """Get or create a global validator instance."""

    global _PRODUCTION_VALIDATOR
    if _PRODUCTION_VALIDATOR is None:
        # Default to a model that is already present on this machine (override with OLLAMA_MODEL)
        model = os.getenv("OLLAMA_MODEL", "mistral")
        max_workers = int(os.getenv("OLLAMA_MAX_WORKERS", "4"))
        _PRODUCTION_VALIDATOR = OllamaProductionValidator(
            model=model,
            max_workers=max_workers,
        )
        _PRODUCTION_VALIDATOR.warmup_cache()
    return _PRODUCTION_VALIDATOR


def generate_validation_report(
    picks: List[Dict[str, Any]],
    output_file: str = "ollama_validation_report.json",
) -> Dict[str, Any]:
    """Validate a batch of picks and write a JSON report."""

    validator = get_validator()
    print(f"🔍 Validating {len(picks)} picks with Ollama…")

    results = validator.validate_batch(picks)

    summary = {
        "total_picks": len(picks),
        "valid": len([r for r in results if r.validation_status == ValidationStatus.VALID]),
        "questionable": len(
            [r for r in results if r.validation_status == ValidationStatus.QUESTIONABLE]
        ),
        "invalid": len([r for r in results if r.validation_status == ValidationStatus.INVALID]),
        "timeouts": len([r for r in results if r.validation_status == ValidationStatus.TIMEOUT]),
        "errors": len([r for r in results if r.validation_status == ValidationStatus.ERROR]),
    }

    report: Dict[str, Any] = {
        "summary": summary,
        "detailed_results": [r.to_dict() for r in results],
        "metrics": validator.get_system_metrics(),
        "timestamp": datetime.now().isoformat(),
    }

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"✅ Validation complete. Report saved to {output_file}")
    if summary["total_picks"]:
        print("\n📊 Validation Summary:")
        print(f"   Valid: {summary['valid']} ({summary['valid']/summary['total_picks']*100:.1f}%)")
        print(f"   Questionable: {summary['questionable']}")
        print(f"   Invalid: {summary['invalid']}")
        print(f"   Timeouts: {summary['timeouts']}")

    invalid_picks = [
        r
        for r in results
        if r.validation_status in (ValidationStatus.INVALID, ValidationStatus.QUESTIONABLE)
    ]
    if invalid_picks:
        print("\n⚠️  Picks needing review (first 5):")
        for pick in invalid_picks[:5]:
            print(f"   - {pick.player}: {pick.reasoning}")

    return report


def validate_single_player(player_name: str, stat_type: str = "points") -> ValidationResult:
    """Validate a single player (for quick manual checks)."""

    validator = get_validator()
    pick = {"player": player_name, "stat": stat_type, "mu": 15.0, "team": "UNK"}
    return validator.validate_pick_sync(pick)


def get_validation_metrics() -> Dict[str, Any]:
    """Expose current system metrics."""

    validator = get_validator()
    return validator.get_system_metrics()


def clear_cache() -> None:
    """Clear validation cache on disk."""

    cache_db = Path("cache/ollama/validation_cache.db")
    if cache_db.exists():
        conn = sqlite3.connect(cache_db)
        cur = conn.cursor()
        cur.execute("DELETE FROM validation_cache")
        conn.commit()
        conn.close()
        print("✅ Cache cleared")
    else:
        print("⚠️  Cache database not found")


def _cli() -> None:
    parser = argparse.ArgumentParser(description="Ollama Production Validation CLI")
    parser.add_argument("--validate", type=str, help="Validate a specific player")
    parser.add_argument("--stat", type=str, default="points", help="Stat type to validate")
    parser.add_argument("--metrics", action="store_true", help="Show validation metrics")
    parser.add_argument("--clear-cache", action="store_true", help="Clear validation cache")
    parser.add_argument("--report", action="store_true", help="Generate validation report")
    args = parser.parse_args()

    if args.validate:
        result = validate_single_player(args.validate, args.stat)
        print(f"\n🧠 Validation for {args.validate} ({args.stat}):")
        print(f"   Status: {result.validation_status.value}")
        print(f"   Confidence: {result.confidence:.1%}")
        if result.reasoning:
            print(f"   Reasoning: {result.reasoning}")
        if result.corrected_value is not None:
            print(f"   Suggested value: {result.corrected_value}")
        if result.corrected_team:
            print(f"   Correct team: {result.corrected_team}")
    elif args.metrics:
        metrics = get_validation_metrics()
        print("\n📊 Ollama Validation Metrics:")
        for k, v in metrics.items():
            print(f"   {k}: {v}")
    elif args.clear_cache:
        clear_cache()
    elif args.report:
        with open("picks_hydrated.json", "r", encoding="utf-8") as f:
            picks = json.load(f)
        generate_validation_report(picks[:20])
    else:
        print("Ollama Production Validator - Ready for integration")
        print("\nUsage:")
        print("  --validate <player>     Validate specific player")
        print("  --metrics               Show validation metrics")
        print("  --clear-cache           Clear validation cache")
        print("  --report                Generate validation report")


if __name__ == "__main__":
    _cli()
