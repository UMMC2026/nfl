# Governance Integration Guide

This document summarizes the integration points for the new governance modules:

## 1. Edge Stability Score (ESS) Calculator
- **File:** `engine/edge_stability_engine.py`
- **Integration:**
  - After simulation, before surfacing picks, call `EdgeStabilityEngine.calculate_ess()`.
  - Use `get_tier()` to gate picks. If tier is "SKIP", do not surface the pick.
  - Log ESS, tier, and gating reason for transparency.

## 2. Chaos Stress Test
- **File:** `engine/chaos_stress_test.py`
- **Integration:**
  - Run as a standalone script to validate ESS thresholds.
  - Review tier distribution and adjust ESS logic if too many "SLAM" picks appear in chaos.

## 3. Coaching/Minute Stability Logic
- **Files:**
  - `engine/minute_stability.py` (minute stability calculation)
  - `engine/blowout_risk.py` (blowout risk analysis)
  - `engine/governance_gate.py` (final governance check)
- **Integration:**
  - Use `calculate_minute_stability()` and `blowout_risk_analysis()` in your simulation context.
  - Feed FAS audit data back into simulation to auto-penalize fragile archetypes.
  - Use `final_governance_check()` as the last step before ESS gating.

## 4. Next Steps
- Set up a feedback loop: Use FAS audit results to auto-penalize categories with high failure rates.
- Build a dashboard to visualize failure heatmaps and ESS gating.
- Continue tuning based on Chaos Stress Test results.
