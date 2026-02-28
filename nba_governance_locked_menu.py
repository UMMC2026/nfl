from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

# Reuse the existing, battle-tested helpers.
from risk_first_slate_menu import (
    RunSettings,
    _list_raw_inputs,
    _safe_input,
    _safe_int,
    _pause,
    _print_header,
    _parse_raw_to_json,
    _analyze_json_slate,
)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _is_parsed_slate_json(path: Path) -> bool:
    """Return True if file looks like a parsed slate with a non-empty 'plays' list.

    Note: This intentionally excludes risk-first results JSONs, which do not contain a top-level
    'plays' array.
    """
    try:
        data = _load_json(path)
        plays = data.get("plays")
        return isinstance(plays, list) and len(plays) > 0
    except Exception:
        return False


def _list_parsed_slate_json(outputs_dir: Path) -> list[Path]:
    if not outputs_dir.exists():
        return []
    files = sorted(outputs_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    out: list[Path] = []
    for p in files:
        if not p.is_file():
            continue
        if _is_parsed_slate_json(p):
            out.append(p)
    return out


def main() -> None:
    inputs_dir = Path("inputs")
    outputs_dir = Path("outputs")
    settings = RunSettings()

    selected_raw: Optional[Path] = None
    selected_slate_json: Optional[Path] = None

    while True:
        _print_header()
        print("LOCKED GOVERNANCE PIPELINE (NBA)")
        print("This menu enforces: parse -> analyze -> governance exports")
        print("-" * 70)
        print("Selected raw:", str(selected_raw) if selected_raw else "(none)")
        print("Selected json:", str(selected_slate_json) if selected_slate_json else "(none)")
        print("")
        print("1) Choose raw input file (inputs/*.txt)")
        print("2) Choose parsed slate JSON (outputs/*.json)")
        print("3) RUN LOCKED PIPELINE NOW")
        print("0) Exit")

        try:
            choice = _safe_input("\nSelect option: ").strip().lower()
        except EOFError:
            return

        if choice == "0":
            print("\nExiting.")
            return

        if choice == "1":
            raws = _list_raw_inputs(inputs_dir)
            if not raws:
                print("\nNo raw inputs found under inputs/*.txt")
                _pause()
                continue

            print("\nAvailable raw inputs (newest first)")
            print("-" * 70)
            for i, p in enumerate(raws, 1):
                print(f"{i:2d}) {p.name}")

            try:
                idx = _safe_int(_safe_input("\nChoose file number: "), 0)
            except EOFError:
                return
            if idx < 1 or idx > len(raws):
                print("Invalid selection.")
                _pause()
                continue

            selected_raw = raws[idx - 1]
            selected_slate_json = None
            print(f"\nSelected raw: {selected_raw}")
            _pause()
            continue

        if choice == "2":
            slates = _list_parsed_slate_json(outputs_dir)
            if not slates:
                print("\nNo parsed slate JSONs found under outputs/*.json")
                print("Tip: a parsed slate JSON must contain a top-level 'plays' array.")
                _pause()
                continue

            print("\nAvailable parsed slate JSONs (newest first)")
            print("-" * 70)
            for i, p in enumerate(slates, 1):
                print(f"{i:2d}) {p.name}")

            try:
                idx = _safe_int(_safe_input("\nChoose file number: "), 0)
            except EOFError:
                return
            if idx < 1 or idx > len(slates):
                print("Invalid selection.")
                _pause()
                continue

            selected_slate_json = slates[idx - 1]
            selected_raw = None
            print(f"\nSelected json: {selected_slate_json}")
            _pause()
            continue

        if choice == "3":
            if (not selected_raw) and (not selected_slate_json):
                print("\nSelect either a raw input (option 1) OR a parsed slate JSON (option 2).")
                _pause()
                continue

            # If running from raw, we still allow overriding the date for reproducibility.
            override_date: Optional[str] = None
            if selected_raw:
                try:
                    override_date = _safe_input("Override date (YYYY-MM-DD) or blank: ").strip() or None
                except EOFError:
                    return

            try:
                slate_json = selected_slate_json
                if selected_raw:
                    slate_json = _parse_raw_to_json(selected_raw, override_date=override_date)

                assert slate_json is not None
                out_json, out_txt = _analyze_json_slate(slate_json, settings)

                print("\nLOCKED PIPELINE COMPLETE")
                print(f"Input slate : {slate_json}")
                print(f"Results JSON: {out_json}")
                if out_txt:
                    print(f"AI report   : {out_txt}")
                print("Governance  : outputs/governance_config.json")
                print("Summary     : outputs/governance_summary.txt")
                print("Allowed     : outputs/allowed_edges.json")
                print("Blocked     : outputs/blocked_edges.json")
            except Exception as e:
                print(f"\nLOCKED pipeline failed: {e}")

            _pause()
            continue

        print("\nUnknown option.")
        _pause()


if __name__ == "__main__":
    main()
