# Checklist for Stat Integration and Reporting

## 1. Stat Definition
- [ ] Define new stat/market (e.g., "1Q Points", "Double Doubles").
- [ ] Identify data sources for historical and projection data.

## 2. Simulation Logic
- [ ] Implement simulation for new stat (see `engine/stat_sim_starters.py`).
- [ ] Validate output: mean, std, tails, context.

## 3. Governance Gate Integration
- [ ] Pass simulation output through governance gate (`engine/governance_gate.py`).
- [ ] Use template in `engine/stat_integration_template.py`.

## 4. Reporting & Output
- [ ] Update reporting/cheat sheet/export logic to include new stat type.
- [ ] Display ESS, tier, and gating reason for each surfaced pick.

## 5. Audit & Calibration
- [ ] Track FAS tags for new stat in post-game audits.
- [ ] Adjust ESS penalties if stat shows high volatility or failure rates.

## 6. Best Practices
- [ ] Apply same risk-first logic to all new markets.
- [ ] Document integration and update governance guide.
