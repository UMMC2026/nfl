from dataclasses import dataclass
from datetime import datetime
from .execution_mode import ExecutionMode, ExecutionState

@dataclass
class ExecutionContext:
    mode: ExecutionMode
    state: ExecutionState
    platform: str                # underdog | prizepicks | sleeper
    snapshot_id: str             # market snapshot cohesion ID
    publish_time: datetime
    max_confidence_cap: float
    allow_soft_failures: bool

def assert_publish_allowed(ctx: ExecutionContext):
    if ctx.mode != ExecutionMode.EXECUTION:
        raise RuntimeError("Publishing from TRUTH mode is forbidden")
