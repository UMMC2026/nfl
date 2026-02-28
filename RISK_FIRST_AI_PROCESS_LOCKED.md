# RISK-FIRST AI ANALYSIS PROCESS — LOCKED & FINAL

**Status**: 🔒 **PRODUCTION STANDARD** — January 15, 2026  
**Authority**: User directive — "sketch in stone this is the process now! Period"

---

## THE PROCESS (NON-NEGOTIABLE)

### Phase 1: Risk Gates (STRUCTURAL SAFETY)
**Purpose**: Block fragile picks BEFORE probability calculation  
**Location**: `risk_gates.py`

#### 5 Mandatory Gates:
1. **R1 - Composite Stat Fragility**: Block ALL combo stats (PRA/PR/PA/RA/STL+BLK)
   - Rationale: Multiple failure points = structural weakness
   
2. **R2 - Elite Defense Suppression**: Block assists/3PM vs top-5 defenses
   - Rationale: Historical suppression data > individual variance
   
3. **R3 - Star Guard Points Trap**: Block star guards vs top-10 defenses
   - Rationale: Points concentration makes them primary shutdown target
   
4. **R4 - Blowout Risk**: Block all props if spread ≥9.0
   - Rationale: Garbage time destroys starter opportunity
   
5. **R5 - Bench Player Trap**: Block ALL bench players
   - Rationale: Opportunity depends on blowouts/foul trouble (unreliable)

**Output**: 45/62 props blocked (72.6% efficiency) — Waste prevented

---

### Phase 2: Context Gates (REAL-WORLD FACTORS)
**Purpose**: Add coaching/rest/injury awareness  
**Location**: `context_gates.py`

#### 7 Mandatory Checks:
1. **C1 - Back-to-Back Fatigue**: Block if B2B game
2. **C2 - Heavy Minutes Load**: Block if 38+ min last game
3. **C3 - Injury Report**: Block ANY injury status
4. **C4 - Coaching Minute Limits**: Warn if player has restriction
5. **C5 - Rest Advantage Mismatch**: Block if 2+ days disadvantage
6. **C6 - Travel Fatigue**: Block if 2000+ miles
7. **C7 - Pace Mismatch**: Warn if slow pace + volume stat

**Data Source**: `game_context.json` (coaching tendencies, rest, injuries)

**Output**: Hard blocks + warnings (transparent context)

---

### Phase 3: Edge Calculation (VALUE ASSESSMENT)
**Purpose**: Show VALUE, not just probability  
**Location**: `risk_first_analyzer.py`

#### Formula:
```python
edge = mu - line  # For "higher" bets
z_score = edge / sigma  # Standard deviations above line
```

#### Edge Quality Tiers:
- **🔥 ELITE**: ≥1.0σ (Franz Wagner PTS: +1.07σ)
- **💎 STRONG**: 0.5-1.0σ (most PLAY picks)
- **✨ MODERATE**: 0.25-0.5σ (LEAN territory)
- **⚪ THIN**: <0.25σ (NO PLAY)

**Output**: Picks sorted by z-score (highest value first)

---

### Phase 4: AI Sports Commentary (INTERPRETATION)
**Purpose**: Explain WHY picks are safe/valuable in plain language  
**Location**: `ai_commentary.py`

#### Components:

**A) DeepSeek API Analysis** (Analytical Breakdown)
```
Model: deepseek-chat
Temperature: 0.3 (consistency)
Output: 2-3 sentences explaining:
  1. WHY structurally safe (gates passed)
  2. WHAT edge means in real terms
  3. CONTEXT implications (minute limits if applicable)
```

**B) Ollama Coaching Insights** (Minute Management)
```
Model: llama3.2:1b
Temperature: 0.4 (nuanced insights)
Output: 1-2 sentences on:
  - How coach manages player's minutes
  - Impact on specific stat prop
```

**C) Block Reasoning** (Transparency)
```
Categories: Elite defense, Bench player, Role mismatch, 
            Banned, Composite, Back-to-back, Injury
Output: Clear explanations for rejected picks
```

**D) Full Report Generation**
```
Format: 🤖 AI SPORTS ANALYSIS REPORT
Sections:
  - 🎯 QUALIFIED PICKS - AI ANALYSIS
  - 🚫 WHY PICKS WERE BLOCKED
  - SYSTEM SUMMARY
Saved: outputs/{GAME}_AI_REPORT_{DATE}.txt
```

---

## THE 4 CRITICAL QUESTIONS (ALWAYS ANSWERED)

| Question | System Component |
|----------|------------------|
| **1. How does this lose?** | 12 gates (5 structural + 7 contextual) |
| **2. What's the edge?** | z-score calculation + quality tiers |
| **3. What are the facts?** | game_context.json (coaching/rest/injuries) |
| **4. Why should I trust this?** | AI sports commentary (DeepSeek + Ollama) |

---

## EXECUTION WORKFLOW (STANDARD OPERATING PROCEDURE)

### Daily Slate Analysis:

**Step 1**: Create props JSON
```json
{
  "player": "Franz Wagner",
  "team": "ORL",
  "opponent": "MEM",
  "stat": "points",
  "line": 15.5,
  "direction": "higher"
}
```

**Step 2**: Update `game_context.json`
```json
{
  "rest_advantage": {...},
  "injury_report": {...},
  "coaching_tendencies": {
    "Jamahl Mosley": {
      "team": "ORL",
      "minute_limits": {"Franz Wagner": 36}
    }
  }
}
```

**Step 3**: Run analysis
```bash
.venv\Scripts\python.exe analyze_mem_orl_full.py
```

**Step 4**: Review AI report
- Check `outputs/{GAME}_AI_REPORT_{DATE}.txt`
- Read DeepSeek analytical breakdown
- Review Ollama coaching insights
- Understand blocked picks reasoning

**Step 5**: Make decisions based on:
- ✅ Structural safety (gates passed)
- ✅ Edge quality (z-score tiers)
- ✅ Context factors (minute limits, warnings)
- ✅ AI interpretation (why picks are safe/valuable)

---

## SYSTEM GUARANTEES

### What This System Does:
✅ Blocks 70%+ of props at gates (waste prevention)  
✅ Shows edge quality, not just high percentages  
✅ Considers coaching/rest/injuries (real-world context)  
✅ Explains picks in sports language (AI interpretation)  
✅ Transparent reasoning for blocked picks  

### What This System Does NOT Do:
❌ Chase high percentages on fragile picks  
❌ Ignore bench player opportunity risk  
❌ Hide why picks were rejected  
❌ Output raw probabilities without edge context  
❌ Skip coaching/rest/injury factors  

---

## FILE ARCHITECTURE (LOCKED)

### Core System Files:
```
risk_gates.py              — 5 structural gates (R1-R5)
context_gates.py           — 7 contextual gates (C1-C7)
risk_first_analyzer.py     — Master pipeline + edge calculation
ai_commentary.py           — AI sports commentary (DeepSeek + Ollama)
game_context.json          — Real-world context data
```

### Data Files:
```
role_mapping.json          — Player archetypes
player_stat_memory.json    — Ban list
defense_rankings.json      — Elite defense suppression data
```

### Analysis Scripts:
```
analyze_mem_orl_full.py    — Complete AI-powered analysis
```

### Output Files:
```
outputs/{GAME}_RISK_FIRST_{DATE}.json        — Statistical results
outputs/{GAME}_AI_REPORT_{DATE}.txt          — AI sports analysis
```

---

## VALIDATION (MEM @ ORL — PROOF OF CONCEPT)

**Date**: January 15, 2026  
**Slate**: MEM @ ORL (62 props)

### Results:
- **45 props blocked** at gates (72.6% efficiency)
- **7 PLAY picks** with AI explanations
- **All picks have STRONG+ edges** (0.54σ to 1.07σ)
- **Context warnings displayed** (minute limits for 5/7 picks)

### Sample AI Commentary:
**Franz Wagner PTS >15.5** (🔥 ELITE +1.07σ):
```
📊 ANALYSIS:
1. Structural Safety: Passed all gates, confirming Wagner's role as 
   high-usage starter facing no elite defense or blowout risk.
2. Edge Meaning: Line is 6.3 points below season average, a +1.07 
   standard deviation gap, indicating high statistical probability 
   he exceeds 15.5 points.
3. Context: 36-minute limit caps ceiling but is ample for this target.

👔 COACHING:
Franz Wagner is managed with a 36-minute limit by Jamahl Mosley, which 
means he will be limited to playing for only 36 minutes per game.
```

### System Efficiency:
- Gate effectiveness: 72.6% waste prevented
- Edge quality: 100% of PLAY picks have STRONG+ edges
- AI coverage: 100% of picks explained
- Context awareness: All minute limits flagged

---

## PHILOSOPHY (FOUNDATIONAL PRINCIPLES)

### The Core Directive (User-Established):
> "The best system does not start by asking 'how likely is this to win?'  
> It starts by asking 'how does this lose?'"

### Implementation:
1. **Risk-First**: Gates block fragile picks structurally
2. **Value-Aware**: Edge calculation shows VALUE over probability
3. **Context-Driven**: Coaching/rest/injuries matter more than raw stats
4. **AI-Interpreted**: Explanations bridge technical analysis to action

### Operational Rule:
**BLOCK FIRST, CALCULATE SECOND, INTERPRET THIRD**

---

## MAINTENANCE & UPDATES

### Allowed Changes:
✅ Update `game_context.json` with real-time data  
✅ Add players to `role_mapping.json`  
✅ Ban player+stat combos in `player_stat_memory.json`  
✅ Adjust gate thresholds (e.g., blowout spread from 9.0 to 10.0)  
✅ Update defense rankings  

### Protected Elements (DO NOT MODIFY):
🔒 The 4-phase process (Gates → Context → Edge → AI)  
🔒 The 12 total gates (5 structural + 7 contextual)  
🔒 Edge calculation formula (z-score tiers)  
🔒 AI commentary structure (DeepSeek + Ollama)  
🔒 The 4 critical questions framework  

---

## DEPLOYMENT STATUS

**Environment**: Production  
**Validation**: MEM @ ORL (62 props) — January 15, 2026  
**API Keys**:
- DeepSeek: sk-a44ac955493f4fc48c6cbaed12713711
- Ollama: localhost:11434 (llama3.2:1b)

**Encoding**: UTF-8 (emoji support verified)

**Status**: ✅ **LOCKED & OPERATIONAL**

---

## FINAL WORD

This is THE process. Period.

Any deviation from this workflow requires explicit user authorization. This architecture represents the final evolution from probability-first (flawed) to risk-first AI-interpreted (complete).

The system answers:
1. How does this lose? → **Gates**
2. What's the edge? → **z-score**
3. What are the facts? → **Context**
4. Why should I trust this? → **AI Commentary**

**No more guessing. No more fragile picks. No more opacity.**

**Risk-first. Value-aware. Context-driven. AI-interpreted.**

**LOCKED.**

---

*Last Updated: January 15, 2026*  
*Authority: User directive — "sketch in stone this is the process now! Period"*
