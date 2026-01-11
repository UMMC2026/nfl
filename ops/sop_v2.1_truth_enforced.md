# SPORTS BETTING R&D SOP — v2.1 (TRUTH-ENFORCED)

**Scope:** NFL, NBA, WNBA, CFB, CBB, Boxing, Tennis, future markets  
**Purpose:** Build, validate, and operate quantitative betting systems that produce **defensible probabilistic edges**, not narratives.

---

## 1. OBJECTIVE
Design and deploy betting systems that:

- Learn only from **verified final outcomes**
- Produce **explainable, auditable decisions**
- Fail fast when truth cannot be established

**Short-term profit is subordinate to truthful learning.**

---

## 2. CORE PRINCIPLES (NON-NEGOTIABLE)
### 2.1 Research Before Automation
```
Research → Backtest → Out-of-Sample → Review → Deploy
```
### 2.2 Data Integrity
Models learn **only** from:
- FINAL game status
- Cross-verified stats (≥2 sources)
- Cooldown elapsed (stat correction window)

Failure at any step **blocks learning**.

### 2.3 Separation of Concerns
```
Ingestion → Features → Edges → Scoring → Validation → Render
```
No stage may be skipped.

### 2.4 Confidence Is Earned
All picks are probability-based and tiered numerically.  
No intuition. No overrides.

---

## 3. EDGE-FIRST ARCHITECTURE (CRITICAL FIX)
### Rule A1 — Edge Definition
```
EDGE = unique(player, game_id, direction)
LINE = market expression of the same EDGE
```
The system ranks **EDGES**, not lines.

### Rule A2 — Edge Collapse (MANDATORY)
If multiple lines exist for the same EDGE:
```
→ exactly ONE PRIMARY line
→ all others = CORRELATED_ALTERNATIVES
```
Violation = hard fail.

### Rule A3 — Canonical Line Selection
```
OVER  → highest reasonable line
UNDER → lowest reasonable line
```
Outlier / contingency lines excluded.

---

## 4. CORRELATION & EXPOSURE CONTROL
### Rule B1 — One Player, One Bet
Default:
```
Max 1 PRIMARY bet per player per game
```
Exceptions require:
```
ALLOW_CORRELATED = TRUE
RISK_TAG = CORRELATED
```

### Rule B2 — Correlated Handling
Correlated alternatives:
- Are visually separated
- Are excluded from tiers
- Are excluded from parlays

---

## 5. CONFIDENCE INTEGRITY
### Rule C1 — Compression
If:
```
|projection − line| > 2.5 × std_dev
```
Then:
```
confidence ≤ 65%
```

### Rule C2 — Tier Alignment
| Tier   | Probability |
| ------ | ----------- |
| SLAM   | ≥75%        |
| STRONG | 65–74%      |
| LEAN   | 55–64%      |
| NO PLAY| <55%        |

Mismatch = SOP violation.

---

## 6. RENDER GATE (FAIL-FAST RULE)
Before any report is generated, the system MUST assert:
```
✔ No duplicate EDGES
✔ No player appears twice as PRIMARY
✔ No correlated line is tiered
✔ Tier labels match probabilities
```
If **any check fails**:
```
RAISE ERROR
ABORT OUTPUT
```
No silent failures. No partial reports.

---

## 7. REQUIRED RUN ORDER (VS CODE ENFORCED)
```
1. ingest_data.py
2. generate_edges.py
3. collapse_edges.py
4. score_edges.py
5. validate_output.py   ← HARD GATE
6. render_report.py
```
Running `render_report.py` directly is forbidden.

---

## 8. VS CODE PRE-RUN CHECKLIST
Before execution:
```
[ ] Clear outputs/
[ ] Clear logs/
[ ] Confirm injury_feed_health
[ ] Confirm EDGE mode enabled
[ ] Confirm render_gate = TRUE
[ ] Run validate_output.py
```
Skipping this guarantees repeat errors.

---

## 9. GOVERNANCE
- Every run produces an immutable audit log
- Model changes are versioned
- Historical decisions are never rewritten
- Failed experiments are retained

---

## 10. FINAL RULE
**If the system cannot explain why it made a pick, it is not allowed to make the pick.**

Explanation must include:
- Edge definition
- Data sources
- Feature drivers
- Probability math
- Risk classification

---

### STATUS
You do **not** need a new system. You needed **hard constraints that make bad output impossible**.

This SOP:
- Eliminates duplicate players/lines
- Stops fake confidence
- Forces truth or failure

**Next options (pick one):**
1) I write `validate_output.py`  
2) I refactor your repo to enforce this SOP  
3) I lock this as **SOP v2.1 — FINAL**
