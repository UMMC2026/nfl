from enum import Enum

class ExecutionMode(Enum):
    TRUTH = "truth"
    EXECUTION = "execution"

class ExecutionState(Enum):
    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"
