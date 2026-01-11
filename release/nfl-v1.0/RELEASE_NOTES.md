# NFL v1.0 - Locked Release

Status: LOCKED

This release marks the NFL pipeline as SOP v1.0 - frozen for calibration and production runs.

Key points:
- `validate_output.py` implemented and enforced by CI
- `.vscode/tasks.json` contains the canonical run order (HARD GATE enforcement)
- SOP files added: `docs/SOP.md` and `system_prompts/core_guardrails.md`

Merge policy: changes to NFL engine must be accompanied by a `SOP-approval` label and an explicit review by the owners.
