# 🎯 QUICK REFERENCE - TIER 1 FIXES DEPLOYED

## WHAT CHANGED (2026-01-24)

### Fix #1: L5/L10 Blend Weight
```
BEFORE: 0.65 (65% L5, 35% L10) → TOO REACTIVE
AFTER:  0.40 (40% L5, 60% L10) → MORE STABLE
```

**Where**: [analysis_config.py](analysis_config.py#L206) + [.analysis_config.json](.analysis_config.json#L9)

---

### Fix #2: Market Alignment Gate (R6)
```
NEW GATE: Blocks picks when |model_prob - market_prob| > 10%
LOCATION: risk_gates.py (Gate R6, runs after R1-R5)
MODULE:   market_alignment_gate.py
```

**Example**:
- Maxey AST OVER 6.5: Model 55.8% vs Market 43.2% (Δ=12.6%) → ❌ BLOCKED
- PG13 AST OVER 3.5: Model 57.9% vs Market 61.0% (Δ=3.1%) → ✅ PASSED

---

## HOW TO USE

### Running Analysis (No Changes Needed)
Just run your normal pipeline - fixes are automatic:
```bash
# Your existing workflow continues to work
python risk_first_slate_menu.py
```

### Checking Market Gate Results
Look for `R6_MARKET_ALIGN` in output JSON:
```json
{
  "gate": "R6_MARKET_ALIGN",
  "passed": false,
  "reason": "❌ MARKET CONFLICT: Model 55.8% vs Market 43.2% (Δ=12.6% > 10.0%)",
  "market_prob": 43.2,
  "divergence": 12.6,
  "threshold": 10.0
}
```

### Testing Market Gate
```bash
python test_market_gate.py
```

---

## NEXT ACTIONS (TIER 2)

1. **Calibration Backtest** - Check if assists accuracy improved
2. **Bayesian Market Blend** - Blend model + market probabilities (70/30 split)
3. **Defensive Adjustments** - Add opponent-specific suppression factors

---

## SETTINGS (If You Want to Tune)

### Adjust Market Threshold
Edit [risk_gates.py](risk_gates.py):
```python
threshold_pct=10.0  # Change to 12.0 or 15.0 if too strict
```

### Adjust L5/L10 Blend
Edit [.analysis_config.json](.analysis_config.json):
```json
"hybrid_blend": 0.40  // Change to 0.35 or 0.45 if needed
```

---

## FILES MODIFIED

✅ [analysis_config.py](analysis_config.py) - Blend weight 0.65→0.40  
✅ [.analysis_config.json](.analysis_config.json) - Config JSON updated  
✅ [risk_gates.py](risk_gates.py) - Added R6 market gate  
🆕 [market_alignment_gate.py](market_alignment_gate.py) - New gate module  
🆕 [test_market_gate.py](test_market_gate.py) - Validation tests  
📄 [TIER1_FIXES_COMPLETE.md](TIER1_FIXES_COMPLETE.md) - Full documentation

---

**Status**: 🟢 READY TO USE  
**No breaking changes** - backward compatible with all existing scripts
