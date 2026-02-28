"""
FAILURE_PATTERNS_LINTER.PY — Common Failure Patterns Detector

Detects and prevents common contributor mistakes:
1. Duplicate probability shaping (same adjustment applied twice)
2. Mixing player-level and game-level variance
3. Silent defaults (missing required parameters)
4. NO PLAY treated as failure (cultural issue)

Run this before PRs to catch governance violations.
"""
import json
import ast
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

# =============================================================================
# CONFIGURATION
# =============================================================================

PROJECT_ROOT = Path(__file__).parent.parent

# Files that modify probability (watch for duplicate adjustments)
PROBABILITY_MODIFIERS = [
    "engine/monte_carlo.py",
    "engine/tiers.py",
    "ufa/analysis/prob.py",
    "engine/pace_adjustment.py",
    "engine/correlation.py",
]

# Required parameters that must be explicit (never silently default)
REQUIRED_EXPLICIT_PARAMS = {
    "surface": ["tennis/", "TENNIS"],
    "injury_status": ["engine/", "ufa/"],
    "minutes_expectation": ["engine/", "ufa/"],
    "weather": ["nfl/", "NFL"],
}

# Adjustment stages (only one adjustment per stage allowed)
VALID_ADJUSTMENT_STAGES = ["INJURY", "CONTEXT", "MARKET", "PACE", "CORRELATION"]

# =============================================================================
# LINT RULES
# =============================================================================

@dataclass
class LintError:
    """Lint error with location and severity."""
    file: str
    line: int
    rule: str
    message: str
    severity: str  # ERROR, WARNING, INFO

    def __str__(self):
        return f"[{self.severity}] {self.file}:{self.line} - {self.rule}: {self.message}"


def lint_duplicate_probability_shaping(file_path: Path) -> List[LintError]:
    """
    Detect duplicate probability adjustments in same file.
    
    Pattern: Multiple calls to adjust_probability(), apply_factor(), etc.
    without stage declaration.
    """
    errors = []
    
    if not file_path.exists():
        return errors
    
    content = file_path.read_text(encoding='utf-8')
    lines = content.split('\n')
    
    # Track adjustment calls
    adjustment_patterns = [
        r'adjust_probability\s*\(',
        r'apply_factor\s*\(',
        r'probability\s*\*=',
        r'probability\s*\+=',
        r'confidence\s*\*=',
        r'confidence\s*\+=',
    ]
    
    adjustment_calls = []
    for i, line in enumerate(lines, 1):
        for pattern in adjustment_patterns:
            if re.search(pattern, line):
                # Check if stage is declared
                if 'adjustment_stage' not in line and 'stage=' not in line:
                    adjustment_calls.append((i, line.strip()))
    
    if len(adjustment_calls) > 1:
        errors.append(LintError(
            file=str(file_path.relative_to(PROJECT_ROOT)),
            line=adjustment_calls[0][0],
            rule="DUPLICATE_ADJUSTMENT",
            message=f"Multiple probability adjustments ({len(adjustment_calls)}) without stage declaration. Risk of double-penalization.",
            severity="WARNING"
        ))
    
    return errors


def lint_mixed_variance(file_path: Path) -> List[LintError]:
    """
    Detect mixing of player-level and game-level variance adjustments.
    
    Pattern: Player props adjusted, then game pace applied again.
    """
    errors = []
    
    if not file_path.exists():
        return errors
    
    content = file_path.read_text(encoding='utf-8')
    
    has_player_variance = any(x in content for x in [
        'player_variance', 'player_std', 'player_volatility',
        'usage_rate', 'minutes_variance'
    ])
    
    has_game_variance = any(x in content for x in [
        'game_pace', 'pace_adjustment', 'game_variance', 'total_variance',
        'game_volatility'
    ])
    
    if has_player_variance and has_game_variance:
        # Check if there's explicit handling
        if 'variance_source' not in content and 'SINGLE_VARIANCE' not in content:
            # Find approximate line
            for i, line in enumerate(content.split('\n'), 1):
                if 'variance' in line.lower():
                    errors.append(LintError(
                        file=str(file_path.relative_to(PROJECT_ROOT)),
                        line=i,
                        rule="MIXED_VARIANCE",
                        message="Both player-level and game-level variance detected. Risk of variance inflation.",
                        severity="WARNING"
                    ))
                    break
    
    return errors


def lint_silent_defaults(file_path: Path) -> List[LintError]:
    """
    Detect silent defaults for required parameters.
    
    Pattern: if param is None: param = default_value (without logging)
    """
    errors = []
    
    if not file_path.exists():
        return errors
    
    content = file_path.read_text(encoding='utf-8')
    lines = content.split('\n')
    
    # Check which params apply to this file
    applicable_params = []
    file_str = str(file_path)
    for param, patterns in REQUIRED_EXPLICIT_PARAMS.items():
        if any(p in file_str for p in patterns):
            applicable_params.append(param)
    
    for param in applicable_params:
        # Look for silent default patterns
        patterns = [
            rf'{param}\s*=\s*[^=].*if\s+{param}\s+is\s+None',  # param = X if param is None
            rf'if\s+{param}\s+is\s+None:\s*\n\s*{param}\s*=',  # if param is None:\n  param =
            rf'{param}\s*=\s*{param}\s+or\s+',  # param = param or default
            rf'\.get\([\'\"]{param}[\'\"],\s*[^)]+\)',  # .get('param', default)
        ]
        
        for i, line in enumerate(lines, 1):
            for pattern in patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    # Check if there's logging nearby
                    context = '\n'.join(lines[max(0, i-3):i+3])
                    if 'log' not in context.lower() and 'print' not in context.lower():
                        errors.append(LintError(
                            file=str(file_path.relative_to(PROJECT_ROOT)),
                            line=i,
                            rule="SILENT_DEFAULT",
                            message=f"Parameter '{param}' may be silently defaulting without logging.",
                            severity="ERROR"
                        ))
                        break
    
    return errors


def lint_no_play_handling(file_path: Path) -> List[LintError]:
    """
    Detect if NO_PLAY is being treated as failure instead of valid decision.
    
    Pattern: NO_PLAY in error/failure context, missing NO_PLAY tracking
    """
    errors = []
    
    if not file_path.exists():
        return errors
    
    content = file_path.read_text(encoding='utf-8')
    lines = content.split('\n')
    
    for i, line in enumerate(lines, 1):
        # Check for NO_PLAY in error/failure context
        if 'NO_PLAY' in line or 'NO PLAY' in line or 'AVOID' in line:
            lower_line = line.lower()
            if any(x in lower_line for x in ['error', 'fail', 'reject', 'invalid', 'bad']):
                errors.append(LintError(
                    file=str(file_path.relative_to(PROJECT_ROOT)),
                    line=i,
                    rule="NO_PLAY_AS_FAILURE",
                    message="NO_PLAY/AVOID treated as failure. It's a valid decision, not an error.",
                    severity="WARNING"
                ))
    
    return errors


def lint_tier_threshold_hardcoding(file_path: Path) -> List[LintError]:
    """
    Detect hardcoded tier thresholds (should use config/thresholds.py).
    """
    errors = []
    
    if not file_path.exists():
        return errors
    
    # Skip the thresholds.py file itself
    if 'thresholds.py' in str(file_path):
        return errors
    
    content = file_path.read_text(encoding='utf-8')
    lines = content.split('\n')
    
    # Patterns that indicate hardcoded thresholds
    patterns = [
        r'>=?\s*0\.8[05].*SLAM',
        r'>=?\s*0\.6[05].*STRONG',
        r'>=?\s*0\.5[05].*LEAN',
        r'SLAM.*0\.8[05]',
        r'STRONG.*0\.6[05]',
        r'LEAN.*0\.5[05]',
    ]
    
    for i, line in enumerate(lines, 1):
        for pattern in patterns:
            if re.search(pattern, line, re.IGNORECASE):
                errors.append(LintError(
                    file=str(file_path.relative_to(PROJECT_ROOT)),
                    line=i,
                    rule="HARDCODED_THRESHOLD",
                    message="Hardcoded tier threshold detected. Use config/thresholds.py instead.",
                    severity="ERROR"
                ))
                break
    
    return errors


def lint_missing_adjustment_stage(file_path: Path) -> List[LintError]:
    """
    Detect probability adjustments missing stage declaration.
    """
    errors = []
    
    if not file_path.exists():
        return errors
    
    content = file_path.read_text(encoding='utf-8')
    
    # Look for adjustment dictionaries/objects
    if 'adjustment' in content.lower():
        # Check if adjustment_stage is declared
        if 'adjustment_stage' not in content:
            # Find first adjustment line
            for i, line in enumerate(content.split('\n'), 1):
                if 'adjustment' in line.lower() and ('=' in line or ':' in line):
                    errors.append(LintError(
                        file=str(file_path.relative_to(PROJECT_ROOT)),
                        line=i,
                        rule="MISSING_ADJUSTMENT_STAGE",
                        message="Adjustment without 'adjustment_stage' declaration. Required: INJURY|CONTEXT|MARKET|PACE|CORRELATION",
                        severity="WARNING"
                    ))
                    break
    
    return errors


# =============================================================================
# MAIN LINTER
# =============================================================================

def lint_file(file_path: Path) -> List[LintError]:
    """Run all lint rules on a file."""
    errors = []
    
    errors.extend(lint_duplicate_probability_shaping(file_path))
    errors.extend(lint_mixed_variance(file_path))
    errors.extend(lint_silent_defaults(file_path))
    errors.extend(lint_no_play_handling(file_path))
    errors.extend(lint_tier_threshold_hardcoding(file_path))
    errors.extend(lint_missing_adjustment_stage(file_path))
    
    return errors


def lint_directory(dir_path: Path, extensions: List[str] = None) -> List[LintError]:
    """Lint all files in a directory."""
    extensions = extensions or ['.py']
    errors = []
    
    for ext in extensions:
        for file_path in dir_path.rglob(f'*{ext}'):
            # Skip __pycache__, venv, etc.
            if any(x in str(file_path) for x in ['__pycache__', '.venv', 'venv', '.git']):
                continue
            errors.extend(lint_file(file_path))
    
    return errors


def lint_changed_files(changed_files: List[str]) -> List[LintError]:
    """Lint only changed files (for PR checks)."""
    errors = []
    
    for file_str in changed_files:
        file_path = PROJECT_ROOT / file_str
        if file_path.suffix == '.py':
            errors.extend(lint_file(file_path))
    
    return errors


# =============================================================================
# CLI INTERFACE
# =============================================================================

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Common failure patterns linter")
    parser.add_argument("--dir", type=str, help="Directory to lint (default: entire project)")
    parser.add_argument("--file", type=str, help="Single file to lint")
    parser.add_argument("--severity", type=str, default="WARNING", 
                        choices=["ERROR", "WARNING", "INFO"],
                        help="Minimum severity to report")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    
    args = parser.parse_args()
    
    if args.file:
        errors = lint_file(Path(args.file))
    elif args.dir:
        errors = lint_directory(Path(args.dir))
    else:
        # Lint key directories
        errors = []
        for subdir in ['engine', 'ufa', 'tennis', 'nfl', 'sports', 'calibration', 'gating']:
            dir_path = PROJECT_ROOT / subdir
            if dir_path.exists():
                errors.extend(lint_directory(dir_path))
    
    # Filter by severity
    severity_order = {"ERROR": 0, "WARNING": 1, "INFO": 2}
    min_sev = severity_order.get(args.severity, 1)
    errors = [e for e in errors if severity_order.get(e.severity, 2) <= min_sev]
    
    if args.json:
        output = [{"file": e.file, "line": e.line, "rule": e.rule, 
                   "message": e.message, "severity": e.severity} for e in errors]
        print(json.dumps(output, indent=2))
    else:
        if errors:
            print(f"\n{'='*60}")
            print(f"FAILURE PATTERNS LINTER: {len(errors)} issues found")
            print(f"{'='*60}\n")
            
            for error in sorted(errors, key=lambda e: (e.file, e.line)):
                icon = "❌" if error.severity == "ERROR" else "⚠️" if error.severity == "WARNING" else "ℹ️"
                print(f"{icon} {error}")
            
            print(f"\n{'='*60}")
            error_count = len([e for e in errors if e.severity == "ERROR"])
            warning_count = len([e for e in errors if e.severity == "WARNING"])
            print(f"Summary: {error_count} errors, {warning_count} warnings")
            
            if error_count > 0:
                exit(1)
        else:
            print("✅ No failure patterns detected.")


if __name__ == "__main__":
    main()
