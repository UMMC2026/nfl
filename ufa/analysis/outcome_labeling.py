"""Authoritative outcome / labeling pass for calibration history.

This module is the single place where post-game labels are attached to a pick.

Inputs (conceptual):
  - pick_row: dict containing immutable + pre-game fields and an `outcome` value
  - outcome context that has already passed through `learning_gate.is_learning_ready`

This module is responsible ONLY for setting the learning-critical post-game fields:
  - learning_gate_passed
  - outcome_source
  - outcome_finalized_at
  - overtime_flag
  - terminal_state
  - failure_primary_cause
  - penalty_was_sufficient
  - learning_type
  - correction_risk

It also enforces invariants so that downstream learning is safe.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

# Locked enums (mirrors CALIBRATION_SCHEMA.md)
ALLOWED_FAILURE_CAUSES = {
    "MINUTES_CUT",
    "INJURY",
    "USAGE_COLLAPSE",
    "SMALL_SAMPLE",
    "VARIANCE",
    "GOVERNANCE_MISS",
    "LATE_SCRATCH_OR_REMOVAL",
}

# Causes that can meaningfully drive governance changes
GOVERNANCE_RELEVANT_CAUSES = {
    "MINUTES_CUT",
    "GOVERNANCE_MISS",
    "USAGE_COLLAPSE",
    "SMALL_SAMPLE",
}


@dataclass
class OutcomeContext:
    """Minimal context required for labeling a pick.

    All fields here are post-game and should be sourced from
    already-verified data (after learning_gate).
    """

    learning_gate_passed: bool
    outcome_source: str
    outcome_finalized_at: datetime
    overtime_flag: bool = False
    terminal_state: Optional[str] = None  # e.g., 'NO_GAME'
    failure_primary_cause: Optional[str] = None
    penalty_was_sufficient: Optional[bool] = None
    correction_risk: bool = False


def _determine_learning_type(
    *,
    outcome: str,
    ctx: OutcomeContext,
) -> str:
    """Determine learning_type given outcome and context.

    Rules:
      - Variance never triggers learning → learning_type='NONE'
      - No-game (terminal_state) never triggers learning
      - Late scratch / removal never triggers learning
      - Correction risk never triggers learning
      - Governance failure only triggers learning when penalty_was_sufficient is False
    """

    # Normalize
    outcome = (outcome or "").upper()
    cause = (ctx.failure_primary_cause or "").upper() or None

    # Anything with correction risk is excluded from learning
    if ctx.correction_risk:
        return "NONE"

    # Terminal non-game: treat as non-event
    if ctx.terminal_state:
        return "NONE"

    # If gate failed, no learning regardless
    if not ctx.learning_gate_passed:
        return "NONE"

    # No learning if we don't even know the outcome
    if outcome not in {"HIT", "MISS"}:
        return "NONE"

    # For hits, we treat as confirmation but low-priority; caller may ignore
    if outcome == "HIT":
        return "CONFIRM"

    # From here on, outcome == 'MISS'

    # Variance never triggers learning
    if cause == "VARIANCE":
        return "NONE"

    # Late scratch / removal is operational noise
    if cause == "LATE_SCRATCH_OR_REMOVAL":
        return "NONE"

    # If we don't have a cause, be conservative
    if cause is None:
        return "NONE"

    # Governance-related failures only trigger learning when penalty was insufficient
    if cause in GOVERNANCE_RELEVANT_CAUSES:
        if ctx.penalty_was_sufficient is False:
            return "REFUTE"  # Governance rule needs strengthening
        # Penalty was sufficient (or unknown) → we log but don't treat as learning
        return "EDGE_CASE"

    # Other non-governance causes (e.g., INJURY) do not trigger learning
    return "NONE"


def _assert_label_invariants(pick_row: Dict[str, Any], ctx: OutcomeContext, learning_type: str) -> None:
    """Mini-gate to freeze label semantics.

    Enforces that when learning_gate_passed=True, the required fields
    are present and that learning does not trigger on disallowed cases.
    """

    outcome = (pick_row.get("outcome") or "").upper()

    # If gate passed, certain fields must be non-null
    if ctx.learning_gate_passed:
        if not outcome:
            raise ValueError("Outcome labeling invariant: outcome must be set when learning_gate_passed is True")

        # If outcome is MISS, we must have exactly one primary cause
        if outcome == "MISS":
            if ctx.failure_primary_cause is None:
                raise ValueError("Outcome labeling invariant: failure_primary_cause required when outcome is MISS")
            if ctx.failure_primary_cause.upper() not in ALLOWED_FAILURE_CAUSES:
                raise ValueError(f"Outcome labeling invariant: invalid failure_primary_cause={ctx.failure_primary_cause}")

    # No learning (REFUTE/CONFIRM/EDGE_CASE) on terminal NO_GAME
    if ctx.terminal_state is not None and learning_type != "NONE":
        raise ValueError("Outcome labeling invariant: learning_type must be 'NONE' when terminal_state is set")

    # No learning on variance, late scratch, or correction risk
    cause = (ctx.failure_primary_cause or "").upper()
    if cause in {"VARIANCE", "LATE_SCRATCH_OR_REMOVAL"} or ctx.correction_risk:
        if learning_type != "NONE":
            raise ValueError(
                "Outcome labeling invariant: learning_type must be 'NONE' "
                "for VARIANCE, LATE_SCRATCH_OR_REMOVAL, or when correction_risk is True"
            )


def apply_outcome_labels(
    pick_row: Dict[str, Any],
    ctx: OutcomeContext,
) -> Dict[str, Any]:
    """Apply authoritative outcome labels to a pick_row.

    This function mutates and returns `pick_row`, setting ONLY the agreed
    learning-critical post-game fields and enforcing invariants.

    Fields set:
      - learning_gate_passed
      - outcome_source
      - outcome_finalized_at
      - overtime_flag
      - terminal_state
      - failure_primary_cause
      - penalty_was_sufficient
      - learning_type
      - correction_risk
    """

    # Determine learning_type based on outcome + context
    outcome = pick_row.get("outcome")
    learning_type = _determine_learning_type(outcome=outcome or "", ctx=ctx)

    # Freeze semantics (raise if inconsistent)
    _assert_label_invariants(pick_row, ctx, learning_type)

    # Apply labels (authoritative)
    pick_row["learning_gate_passed"] = ctx.learning_gate_passed
    pick_row["outcome_source"] = ctx.outcome_source
    pick_row["outcome_finalized_at"] = ctx.outcome_finalized_at.isoformat()
    pick_row["overtime_flag"] = ctx.overtime_flag
    if ctx.terminal_state is not None:
        pick_row["terminal_state"] = ctx.terminal_state
    if ctx.failure_primary_cause is not None:
        pick_row["failure_primary_cause"] = ctx.failure_primary_cause
    if ctx.penalty_was_sufficient is not None:
        pick_row["penalty_was_sufficient"] = ctx.penalty_was_sufficient
    pick_row["learning_type"] = learning_type
    pick_row["correction_risk"] = ctx.correction_risk

    return pick_row


def label_from_gate_and_human(
    pick_row: Dict[str, Any],
    *,
    gate_passed: bool,
    gate_correction_risk: bool,
    overtime_flag: bool,
    terminal_state: Optional[str],
    outcome_source: str,
    finalized_at: datetime,
    failure_primary_cause: Optional[str],
    penalty_was_sufficient: Optional[bool],
) -> Dict[str, Any]:
    """Convenience wrapper combining gate output + human review.

    This is the primary entry point that callers should use:
      - gate_* arguments come from `learning_gate.is_learning_ready` + helpers
      - failure_primary_cause and penalty_was_sufficient come from human review
    """

    ctx = OutcomeContext(
        learning_gate_passed=gate_passed,
        outcome_source=outcome_source,
        outcome_finalized_at=finalized_at,
        overtime_flag=overtime_flag,
        terminal_state=terminal_state,
        failure_primary_cause=failure_primary_cause,
        penalty_was_sufficient=penalty_was_sufficient,
        correction_risk=gate_correction_risk,
    )
    return apply_outcome_labels(pick_row, ctx)
