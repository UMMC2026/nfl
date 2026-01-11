# NFL Reporting Standard v1.0 (NFL_FOOTBALL_REALISTIC)

## Overview
This document codifies the institutional-grade reporting standard for NFL prop analysis, portfolio construction, and deployment, as implemented in this project. All future NFL slate reports must adhere to this structure, logic, and audit rigor.

---

## 7 Pillars of NFL Reporting
1. **Slate Context**: Game count, spread, totals, script flags
2. **Matchup Advantage Logic**: Scheme vs scheme, defensive tendencies
3. **Usage / Role Shift Triggers**: Injuries, rotations, script flips
4. **Primary Edge Declaration**: Best angle per game, with rationale
5. **Confidence Quantification**: Bayesian, penalty-driven, fully auditable
6. **Portfolio Construction Rules**: Correlation-aware, NFL-specific
7. **Deployment Readiness**: All gates passed, broadcast-safe

---

## Template Reference
See `nfl_report_template.md` for the drop-in report structure. All curly-brace fields must be filled with pipeline output and game context.

---

## Compliance Gates
- **NFL_FOOTBALL_REALISTIC mode enforced**
- Composite stats derived, not hydrated
- All penalties (roster, composite, script) surfaced in output
- Confidence never inflated; all penalties explicit
- Portfolio rules: max 1 player per game in 3-pick, avoid same-team QB+WR unless trailing script, prefer cross-game independence
- Exposure summary capped for variance
- Methodology section must explain probability engine and penalty logic

---

## Output Requirements
- All picks must include: player, team, stat, line, direction, recent values, mu/sigma, game ID, opponent, probability, z-score, confidence tier, stat class
- Composite and roster audit fields must be present if penalized
- Final probability must reflect all penalties, floored at 50%
- Tier 1 SLAMS: ≥75% confidence after penalties, clean hydration, script-aligned
- All entries must be broadcast-safe and ready for deployment

---

## Version
**Locked as NFL_FOOTBALL_REALISTIC v1.0**

---

*This standard is now the baseline for all NFL reporting, analysis, and portfolio construction in this project.*
