# ORACLE > IMPLEMENTATION GUIDE

## Step 1: Install Dependencies

```bash
pip install numpy pandas scipy scikit-learn xgboost lightgbm
```

---

## Step 2: Run Probability Calculations

```python
from oracle.engine.probability_calculator import expected_value, kelly_fraction
```

Use this for:

* Edge validation
* Bet sizing
* Risk gating

---

## Step 3: Train ML Models

```python
from oracle.engine.sports_ml_model import SportsEnsembleModel
```

Rules:

* Time-series split only
* No future leakage
* Calibrate outputs

---

## Step 4: Enforce Decision Thresholds

Minimum requirements:

* Probability 1> 55%
* Edge 1> 3%
* Brier score < 0.20

If not met 1> **NO PLAY**

---

## Step 5: Post-Game Review

Log:

* Prediction vs outcome
* Brier score
* ROI
* Model drift

Weekly recalibration mandatory.

---

## Golden Rule

If Oracle cannot explain *why* a bet exists, the bet does not exist.
