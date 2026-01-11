from dataclasses import dataclass
from typing import Dict

@dataclass(frozen=True)
class PayoutTable:
    # maps legs -> {k_hits: payout_multiplier_on_stake}
    payout_units: Dict[int, Dict[int, float]]

def power_table() -> PayoutTable:
    """
    Placeholder power-play multipliers.
    Replace these with what your Underdog app shows for your selected format.
    """
    return PayoutTable(
        payout_units={
            2: {2: 3.0},
            3: {3: 6.0},
            4: {4: 10.0},
            5: {5: 20.0},
            6: {6: 35.0},
            7: {7: 60.0},
            8: {8: 100.0},
        }
    )

def flex_table() -> PayoutTable:
    """
    Placeholder flex multipliers.
    Replace these with current Underdog flex tables.
    """
    return PayoutTable(
        payout_units={
            3: {3: 3.0, 2: 1.0},
            4: {4: 6.0, 3: 1.5},
            5: {5: 10.0, 4: 2.5},
            6: {6: 25.0, 5: 3.0, 4: 1.2},
            7: {7: 40.0, 6: 6.0, 5: 1.6},
            8: {8: 80.0, 7: 10.0, 6: 2.0},
        }
    )
