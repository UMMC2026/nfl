from typing import List, Dict, Any, Set

def validate_participants(props: List[Dict[str, Any]], participants: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Filter props to only include those with players/participants present in the official participants list.
    Adds a 'participant_valid' field to each prop for traceability.
    
    TEMP FIX: If participants list is empty or validation would filter everything,
    return all props with validation disabled flag.
    """
    import os
    
    # Allow bypassing validation via env var
    if os.getenv("ODDS_API_SKIP_PARTICIPANT_VALIDATION") == "1":
        print("[PARTICIPANT VALIDATION] Skipped (env var set)")
        for prop in props:
            prop["participant_valid"] = True
        return props
    
    # Build a set of valid participant names (case-insensitive)
    valid_names: Set[str] = set()
    for p in participants:
        name = p.get("name")
        if name:
            valid_names.add(name.strip().lower())

    # If empty participants list, log warning and return all props
    if not valid_names:
        print(f"[PARTICIPANT VALIDATION] WARNING: Participants list is empty, returning all {len(props)} props unvalidated")
        for prop in props:
            prop["participant_valid"] = False  # Mark as unvalidated
        return props

    filtered = []
    for prop in props:
        player = prop.get("player")
        if player and player.strip().lower() in valid_names:
            prop["participant_valid"] = True
            filtered.append(prop)
        else:
            prop["participant_valid"] = False
            # Optionally, include invalids for audit, or skip
            # filtered.append(prop)
    
    # If validation would filter everything, disable it and return all
    if not filtered and props:
        print(f"[PARTICIPANT VALIDATION] WARNING: Would filter ALL {len(props)} props, disabling validation")
        print(f"  Sample prop player names: {[p.get('player') for p in props[:3]]}")
        print(f"  Sample participant names: {list(valid_names)[:3]}")
        for prop in props:
            prop["participant_valid"] = False
        return props
    
    if filtered:
        print(f"[PARTICIPANT VALIDATION] ✓ Validated {len(filtered)}/{len(props)} props against {len(valid_names)} participants")
    
    return filtered
