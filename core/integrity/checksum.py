import hashlib
import json

def model_integrity_checksum(payload: dict) -> str:
    critical = {
        "mu": payload["mu"],
        "sigma": payload["sigma"],
        "n": payload["n_games"],
        "prob": payload["prob_raw"],
        "line": payload["line"],
    }
    raw = json.dumps(critical, sort_keys=True).encode()
    return hashlib.sha256(raw).hexdigest()
