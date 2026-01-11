# DUAL-DOMAIN FRAMEWORK: QUICK REFERENCE CARD

**Status:** ✅ OPERATIONAL  
**Date:** January 1, 2026

---

## Classification at a Glance

| Type | Domain 1 | Domain 2 | Deploy | Example |
|------|----------|----------|--------|---------|
| 🎯 **HYBRID** | ✅ 3pt+ edge | ✅ 60%+ confidence | 3-5x | Jamal Murray (μ=21.5, line=18.5, 72%) |
| 🔒 **CONVICTION** | ❌ No/bad μ | ✅ 60%+ confidence | 2-3x | Bam Adebayo (no μ, 65% confidence) |
| 💎 **VALUE** | ✅ 3pt+ edge | ❌ <60% confidence | 1-2x | Cade (μ=27.8, 55% confidence) |
| ❌ **REJECT** | ❌ Weak edge | ❌ <60% confidence | 0x | Wiggins (μ=15.2, 49% confidence) |

---

## Thresholds (Non-Negotiable)

```
μ Ranges:
  Points: 5-35 ppg
  Rebounds: 2-16 rpg
  Assists: 1-12 apg
  
Hard Rejections:
  μ > 1000 (data corruption)
  σ > 50 (unreliable variance)
  Multiple conflicting lines (unclear)

Domain 1 Gate:
  VALUE_EDGE = μ_gap ≥ 3.0 points

Domain 2 Gate:
  CONVICTION = confidence_pct ≥ 60%
```

---

## Decision Tree (Simplified)

```
1. Check μ validity
   ├─ INVALID (or > 1000)
   │  └─ confidence ≥ 60%? → CONVICTION : REJECT
   └─ VALID
      └─ gap ≥ 3pt?
         ├─ YES
         │  └─ confidence ≥ 60%? → HYBRID : VALUE
         └─ NO
            └─ REJECT
```

---

## Code Usage

### Classify a Single Pick
```python
from ufa.analysis.domain_validator import classify_pick

result = classify_pick(
    player="Jamal Murray",
    stat="points O 18.5",
    line=18.5,
    mu=21.8,
    sigma=3.2,
    confidence_pct=72.0
)
# → DomainValidation(play_type='HYBRID', reasoning='...')
```

### Classify Multiple Picks
```python
from ufa.analysis.domain_validator import batch_classify

results = batch_classify([
    {'player': '...', 'stat': '...', 'line': ..., ...},
    {'player': '...', 'stat': '...', 'line': ..., ...},
])
```

### Format for Telegram
```python
from telegram_template_with_domains import build_game_message

message = build_game_message(
    game_name="MIA @ DET",
    picks=picks_with_domains,
    capital_allocation={'HYBRID': 6, 'CONVICTION': 8, 'VALUE': 5}
)
```

---

## Tonight's Result (Jan 1, 2026)

```
Total Picks:    5
HYBRID:         0 (0%)       → 0 units
CONVICTION:     2 (40%)      → 4 units
VALUE:          0 (0%)       → 0 units
REJECT:         3 (60%)      → 0 units
────────────────────────────────
DEPLOY:         4 units (4% utilization)
DRY POWDER:     96 units
```

**Picks to Send:**
- 🔒 Bam Adebayo | pts+reb+ast O 27.5 (65% CONVICTION)
- 🔒 Jalen Duren | rebounds O 10.5 (65% CONVICTION)

---

## File Reference

| Purpose | File | Size |
|---------|------|------|
| Core Logic | `ufa/analysis/domain_validator.py` | 116 lines |
| Rules & SOP | `SOP_DUAL_DOMAIN_ACCURACY.md` | 580+ lines |
| Template | `telegram_template_with_domains.py` | 130 lines |
| Report | `generate_nightly_report.py` | 105 lines |
| Example Send | `send_mia_det_telegram_with_domains.py` | 260 lines |
| Integration | `INTEGRATION_DUAL_DOMAIN.md` | 280+ lines |

---

## Common Scenarios

### Scenario 1: Good Data, High Confidence
```
Player: "Player A"
μ = 22.5, line = 19.5 (+3pt gap)
confidence = 68%

Result: 🎯 HYBRID
Deploy: 3-5 units
Why: Both domains strong
```

### Scenario 2: No Data, High Confidence
```
Player: "Player B"
μ = None, no recent games
confidence = 65%

Result: 🔒 CONVICTION
Deploy: 2-3 units
Why: Regime strong, data weak
```

### Scenario 3: Good Data, Low Confidence
```
Player: "Player C"
μ = 18.5, line = 15.5 (+3pt gap)
confidence = 52%

Result: 💎 VALUE
Deploy: 1-2 units
Why: Edge strong, conviction weak
```

### Scenario 4: Bad Data, Low Confidence
```
Player: "Player D"
μ = 1250 (aggregation error)
confidence = 48%

Result: ❌ REJECT
Deploy: 0 units
Why: Both domains weak (data corruption + low confidence)
```

---

## Capital Allocation

**Portfolio Recommendation:**
```
Total Bankroll: 100 units

Allocation:
  HYBRID:      40-50% (when available)
  CONVICTION:  20-30% (regime-heavy slates)
  VALUE:       15-25% (contrarian plays)
  REJECT:      0% (never deploy)
  DRY POWDER:  70% (maintain reserves)

Example (Tonight):
  Deploy:      4 units (4%)
  Dry Powder:  96 units (96%)
```

---

## Monitoring Checklist

Before sending to Telegram:
- [ ] All picks classified (no exceptions)
- [ ] Each has documented reasoning
- [ ] REJECT picks excluded from send
- [ ] Domain labels included (🎯🔒💎❌)
- [ ] Capital allocation calculated
- [ ] No encoding errors (Windows-compatible)
- [ ] Confidence levels reviewed (is 60% threshold met?)

---

## FAQ

**Q: Why reject a pick with good μ data but 55% confidence?**  
A: Domain 2 gate is 60%. At 55%, conviction is below threshold. It becomes VALUE if μ_gap ≥ 3pt.

**Q: Can we lower the 3pt threshold?**  
A: No. Hard threshold locked in SOP. Changes require documented review.

**Q: What if μ is missing?**  
A: Classify by confidence alone. If confidence ≥ 60%, it's CONVICTION. Otherwise REJECT.

**Q: How often is the framework updated?**  
A: Monthly audit (first Monday of month). Changes documented before deployment.

---

## Resources

- **SOP:** `SOP_DUAL_DOMAIN_ACCURACY.md` (complete rules)
- **Integration:** `INTEGRATION_DUAL_DOMAIN.md` (code examples)
- **Deployment:** `PRODUCTION_DEPLOYMENT_COMPLETE.md` (status)
- **Validator:** `ufa/analysis/domain_validator.py` (source)

---

**Framework Version:** 1.0 (Locked)  
**Status:** ✅ OPERATIONAL  
**Last Updated:** Jan 1, 2026 16:45 UTC
