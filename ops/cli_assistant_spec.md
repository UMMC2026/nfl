# CLI Assistant Spec (Read-Only)

## Scope
Natural-language front-end to query existing outputs and logs. No mutations of picks, stats, or confidences.

## Supported Queries (examples)
- "Why were no SLAM plays generated?" → List gating reasons (injury degraded, no ≥75% edges).
- "Show blocked UNDERS by injury" → List blocked picks with `hard_rule_rejection` or injury UNKNOWN.
- "Explain Horford PRA edge" → Render via the explanation interface (JSON → blurb).
- "What changed today?" → Summarize deltas from the latest summary JSON.

## Data Sources
- outputs/*cheatsheet*_SUMMARY.json
- outputs/ground_truth_official.json
- Verification/local validation reports

## Output Rules
- Read-only, neutral-professional tone.
- Include data health flags (e.g., injury feed degraded, UNKNOWN statuses).
- Never alter numbers/direction/confidence; only describe.

## Refusals
If asked to generate picks, probabilities, or injury calls: respond with a refusal and point to the core engine.

## Logging
Log queries/responses with timestamps and source file versions for audit.
