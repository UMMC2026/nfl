# SPORTS BETTING R&D SOP — v2.1 (TRUTH-ENFORCED)

**Document ID:** SOP-SBRD-2.1  
**Effective Date:** January 29, 2026  
**Status:** ACTIVE — SUPERSEDES ALL PRIOR VERSIONS  
**Classification:** PROPRIETARY

---

## SCOPE

**Markets:** NFL, NBA, WNBA, CFB, CBB, Boxing, Tennis, future markets  
**Purpose:** Build, validate, and operate quantitative betting systems that produce **defensible probabilistic edges**, not narratives.

---

## 1. OBJECTIVE

Design and deploy betting systems that:

- Learn only from **verified final outcomes**
- Produce **explainable, auditable decisions**
- Fail fast when truth cannot be established

> **Short-term profit is subordinate to truthful learning.**

---

## 2. CORE PRINCIPLES (NON-NEGOTIABLE)

### 2.1 Research Before Automation

No automation without completing the validation pipeline:

```
Research → Backtest → Out-of-Sample → Review → Deploy
```

### 2.2 Data Integrity

Models learn **only** from:

- FINAL game status
- Cross-verified stats (≥2 sources)
- Cooldown elapsed (stat correction window)

**Failure at any step blocks learning.**

### 2.3 Separation of Concerns

The following stages are isolated and gated:

```
Ingestion → Features → Edges → Scoring → Validation → Render
```

**No stage may be skipped.**

### 2.4 Confidence Is Earned

All picks are probability-based and tiered numerically.  
No intuition. No overrides.

---

## 3. EDGE-FIRST ARCHITECTURE (CRITICAL)

### Rule A1 — Edge Definition

```
EDGE = unique(player, game_id, stat_type, direction)
LINE = market expression of the same EDGE
```

The system ranks **EDGES**, not lines.

### Rule A2 — Edge Collapse (MANDATORY)

If multiple lines exist for the same EDGE:

```
→ exactly ONE PRIMARY line
→ all others = CORRELATED_ALTERNATIVES
```

**Violation = hard fail.**

### Rule A3 — Canonical Line Selection

```
OVER  → highest reasonable line (most conservative)
UNDER → lowest reasonable line (most conservative)
```

Outlier / contingency lines excluded.

---

## 4. CORRELATION & EXPOSURE CONTROL

### Rule B1 — One Player, One Bet

Default:

```
Max 1 PRIMARY bet per player per game per stat type
```

Exceptions require explicit flags:

```
ALLOW_CORRELATED = TRUE
RISK_TAG = CORRELATED
```

### Rule B2 — Correlated Handling

Correlated alternatives:

- Are visually separated in output
- Are excluded from tier rankings
- Are excluded from parlays

---

## 5. CONFIDENCE INTEGRITY

### Rule C1 — Compression

If projection is far from line:

```
|projection − line| > 2.5 × std_dev → confidence ≤ 65%
```

This prevents fake high-confidence picks on extreme outliers.

### Rule C2 — Tier Alignment

| Tier    | Probability Range |
|---------|-------------------|
| SLAM    | ≥ 75%             |
| STRONG  | 65% – 74%         |
| LEAN    | 55% – 64%         |
| NO PLAY | < 55%             |

**Tier/probability mismatch = SOP violation.**

---

## 6. RENDER GATE (FAIL-FAST RULE)

Before any report is generated, the system MUST assert:

```
✔ No duplicate EDGES
✔ No player appears twice as PRIMARY
✔ No correlated line is tiered
✔ Tier labels match probabilities
✔ Confidence compression applied where required
✔ All edges have ≥2 data sources
```

If **any check fails**:

```
RAISE ERROR
ABORT OUTPUT
```

**No silent failures. No partial reports.**

---

## 7. REQUIRED RUN ORDER

```bash
1. ingest_data.py        # Load and verify raw data
2. generate_edges.py     # Create raw lines from model
3. collapse_edges.py     # Collapse to unique edges
4. score_edges.py        # Apply confidence scoring
5. validate_output.py    # HARD GATE — must pass
6. render_report.py      # Generate output
```

**Running `render_report.py` directly is forbidden.**

---

## 8. VS CODE PRE-RUN CHECKLIST

Before execution:

```
[ ] Clear outputs/
[ ] Clear logs/
[ ] Confirm injury_feed_health = HEALTHY
[ ] Confirm EDGE mode enabled
[ ] Confirm render_gate = TRUE
[ ] Run validate_output.py and confirm PASSED
```

**Skipping this guarantees repeat errors.**

---

## 9. GOVERNANCE

- Every run produces an immutable audit log
- Model changes are versioned with Git tags
- Historical decisions are never rewritten
- Failed experiments are retained for learning

---

## 10. FINAL RULE

> **If the system cannot explain why it made a pick, it is not allowed to make the pick.**

Explanation must include:

1. Edge definition (player + game + stat + direction)
2. Data sources (with timestamps)
3. Feature drivers (quantitative)
4. Probability math (how confidence was calculated)
5. Risk classification (tier + any flags)

---

## 11. VIOLATION CONSEQUENCES

| Severity   | Example                          | Consequence                    |
|------------|----------------------------------|--------------------------------|
| MINOR      | Missing documentation            | Warning, 24-hour halt          |
| MODERATE   | Single data source used          | Model retraining required      |
| MAJOR      | Duplicate edges in output        | Model retirement, audit        |
| CRITICAL   | Bypassing validation gate        | System-wide shutdown           |

---

## DOCUMENT CONTROL

**Version History:**
- v1.0 (2025-12-01): Initial draft
- v2.0 (2026-01-03): Technical specifications added
- v2.1 (2026-01-29): Truth-Enforced — Hard constraints added

**Review Schedule:** Weekly (Next: February 5, 2026)

**Storage:** Repository `/docs/SOP_v2.1.md` with access control

---

**END OF DOCUMENT**
