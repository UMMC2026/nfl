# utils/audit.py
import csv
from datetime import datetime

AUDIT_FILE = "outputs/pipeline_failures.csv"

def write_pipeline_audit(stage: str, error: Exception, rows: int | None = None):
    with open(AUDIT_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            datetime.now().isoformat(),
            stage,
            str(error),
            rows if rows is not None else ""
        ])
