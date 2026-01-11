from typing import List, Dict
import json
import csv


def to_json(path: str, rows: List[Dict]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2)


def to_csv(path: str, rows: List[Dict]) -> None:
    if not rows:
        with open(path, "w", newline="", encoding="utf-8") as f:
            f.write("")
        return
    keys = sorted({k for r in rows for k in r.keys()})
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for r in rows:
            w.writerow(r)
