from typing import Optional, Dict, Any
from pydantic import BaseModel, Field

class StatRecord(BaseModel):
    sport: str
    event_id: str
    athlete_id: str
    stat_type: str
    value: float
    context: Dict[str, Any] = Field(default_factory=dict)

    def to_feature_vector(self) -> Dict[str, float]:
        """Minimal universal mapping for simulation-ready inputs.
        Ensures a variance placeholder is present (to be refined in feature_engine).
        """
        fv = {
            "value": float(self.value),
            "is_home": 1.0 if self.context.get("venue") == "home" else 0.0,
            "pace_unit": float(self.context.get("pace_unit", 1.0)),
        }
        return fv
