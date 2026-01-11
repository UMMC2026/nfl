# Repo SOP (Engineering + Execution Contract)

Purpose
-------
Governs what exists in the repo, how scripts run, and what blocks execution.

Canonical Directory Structure
-----------------------------
```
/project_root
│
├── data/
│   ├── raw/            # Immutable, write-once
│   ├── processed/      # Validated only
│   ├── features/       # Versioned feature sets
│   └── metadata.json   # Provenance + hashes
│
├── engine/
│   ├── ingest/
│   ├── features/
│   ├── edges/
│   ├── scoring/
│   ├── validation/     # HARD GATES LIVE HERE
│   └── render/
│
├── models/
│   ├── active/
│   ├── retired/
│   └── experiments/
│
├── scripts/
│   ├── run_daily.py
│   ├── validate_output.py   ← NON-BYPASSABLE
│   └── backfill.py
│
├── outputs/
│   ├── reports/
│   └── logs/
│
├── .vscode/
│   ├── tasks.json
│   └── launch.json
│
└── docs/
    └── SOP.md
```

Required Execution Order (Enforced)
----------------------------------
```
1. ingest_data.py
2. generate_features.py
3. generate_edges.py
4. collapse_edges.py
5. score_edges.py
6. validate_output.py  ← HARD STOP
7. render_report.py
```

`render_report.py` may NOT run unless `validate_output.py` returns success (code 0).

Validation Gates (Code-level)
-----------------------------
Before output is allowed:
- No duplicate EDGE IDs
- One PRIMARY edge per player per game
- Correlated lines flagged and excluded
- Probabilities match tier definitions
- FINAL game status confirmed
- Injury feed health = TRUE

Failure → process exits with non-zero code.

Signal Canonical Format (Locked)
--------------------------------
All sports output must conform to the following JSON schema:

```json
{
  "edge_id": "NFL_2026_W18_MAHOMES_PASS_YDS",
  "sport": "NFL",
  "game_id": "20260111_KC_BUF",
  "entity": "Patrick Mahomes",
  "market": "passing_yards",
  "line": 272.5,
  "direction": "OVER",
  "probability": 0.67,
  "tier": "STRONG",
  "data_sources": ["nflfastR", "ESPN"],
  "injury_verified": true,
  "correlated": false
}
```

Governance Rule (Final)
-----------------------
- If it cannot be validated by code, it is not real.
- If it cannot be explained numerically, it is not allowed.

This document is authoritative and enforces the master Sports Betting R&D SOP mechanically.

## CFB (COLLEGE FOOTBALL) CLONE
CFB must reuse the NFL pipeline scaffolding with the following adjustments:

- **Cooldown**: 60 minutes (see `cfb/cfb_config.yaml`)
- **Caps**: core_max=0.60, alt_max=0.55, td_max=0.45
- **Tolerances**: Increased; be conservative on injuries and partial box scores

Use `scripts/validate_cfb_output.py` to validate CFB outputs with the adjusted config.
