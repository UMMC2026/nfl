#!/usr/bin/env python3
"""
Automated Tennis Hotfix Deployment Script
SOP v2.1 Compliant - Emergency Patch Application

This script:
1. Backs up original tennis_edge_detector.py
2. Applies the confidence mapping hotfix
3. Runs validation tests
4. Creates audit log entry
"""

import os
import sys
import shutil
from datetime import datetime
from pathlib import Path
import hashlib
import json


# ============================================================================
# CONFIGURATION
# ============================================================================

WORKSPACE_ROOT = Path(__file__).parent.parent
TENNIS_MODULE = WORKSPACE_ROOT / "tennis" / "tennis_edge_detector.py"
BACKUP_DIR = WORKSPACE_ROOT / "backups" / "tennis_hotfix"
AUDIT_LOG = WORKSPACE_ROOT / "logs" / "hotfix_audit.json"

HOTFIX_CODE = '''
# ============================================================================
# TENNIS CONFIDENCE HOTFIX - Applied {timestamp}
# SOP v2.1 Section 2.4 Compliance
# ============================================================================

from config.thresholds import CONFIDENCE_CAPS

# Emergency mapping: Tennis legacy confidence to canonical thresholds
TENNIS_CONFIDENCE_MAP = {{
    'HIGH': 'core',           # Maps to 0.75 (SLAM tier)
    'MEDIUM': 'volume_micro', # Maps to 0.65 (STRONG tier)  
    'LOW': 'sequence_early'   # Maps to 0.60 (LEAN tier)
}}

'''

HOTFIX_METHOD = '''
    def _assign_tier(self, confidence: str, prob: float) -> str:
        """
        Assign tier based on confidence and probability
        
        HOTFIX: Maps tennis confidence strings to canonical thresholds
        SOP v2.1 Section 2.4 - "Confidence Is Earned, Not Assumed"
        
        Applied: {timestamp}
        """
        # Map tennis confidence to canonical key
        canonical_key = TENNIS_CONFIDENCE_MAP.get(confidence, 'event_binary')
        threshold = CONFIDENCE_CAPS.get(canonical_key, 0.55)
        
        # SOP v2.1 Section 5 - Rule C2: Tier Alignment
        if confidence == "HIGH" and prob > threshold:
            tier = "SLAM"
        elif confidence == "MEDIUM" and prob > threshold:
            tier = "STRONG"  
        elif confidence == "LOW" and prob > threshold:
            tier = "LEAN"
        else:
            tier = "NO PLAY"
        
        # Validation: Ensure tier matches probability range
        if tier == "SLAM" and prob < 0.75:
            tier = "STRONG"
        elif tier == "STRONG" and prob < 0.65:
            tier = "LEAN"
        
        return tier
'''


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def calculate_file_hash(filepath: Path) -> str:
    """Calculate SHA-256 hash of file"""
    sha256 = hashlib.sha256()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b''):
            sha256.update(chunk)
    return sha256.hexdigest()


def create_backup(source: Path, backup_dir: Path) -> Path:
    """Create timestamped backup of file"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    backup_name = f"{source.stem}_backup_{timestamp}{source.suffix}"
    backup_path = backup_dir / backup_name
    
    shutil.copy2(source, backup_path)
    print(f"✅ Backup created: {backup_path}")
    
    return backup_path


def log_audit_entry(action: str, details: dict):
    """Log hotfix application to audit trail (SOP Section 7.1)"""
    AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
    
    audit_entry = {
        "timestamp": datetime.now().isoformat(),
        "action": action,
        "entity": "tennis_edge_detector",
        "user": "hotfix_script",
        **details
    }
    
    # Append to audit log
    if AUDIT_LOG.exists():
        with open(AUDIT_LOG, 'r') as f:
            audit_data = json.load(f)
    else:
        audit_data = []
    
    audit_data.append(audit_entry)
    
    with open(AUDIT_LOG, 'w') as f:
        json.dump(audit_data, f, indent=2)
    
    print(f"✅ Audit entry logged: {AUDIT_LOG}")


# ============================================================================
# MAIN DEPLOYMENT
# ============================================================================

def apply_hotfix():
    """Main hotfix application logic"""
    
    print("\n" + "="*70)
    print("TENNIS CONFIDENCE HOTFIX DEPLOYMENT")
    print("SOP v2.1 Section 2.4 Compliance - Emergency Patch")
    print("="*70 + "\n")
    
    # Step 1: Verify tennis module exists
    if not TENNIS_MODULE.exists():
        print(f"❌ ERROR: Tennis module not found at {TENNIS_MODULE}")
        sys.exit(1)
    
    print(f"📂 Target file: {TENNIS_MODULE}")
    
    # Step 2: Calculate original hash
    original_hash = calculate_file_hash(TENNIS_MODULE)
    print(f"🔐 Original hash: {original_hash[:16]}...")
    
    # Step 3: Create backup
    backup_path = create_backup(TENNIS_MODULE, BACKUP_DIR)
    
    # Step 4: Read original content
    with open(TENNIS_MODULE, 'r') as f:
        original_content = f.read()
    
    # Step 5: Check if already patched
    if "TENNIS_CONFIDENCE_MAP" in original_content:
        print("⚠️  WARNING: Hotfix already applied!")
        response = input("Reapply anyway? (y/n): ")
        if response.lower() != 'y':
            print("❌ Hotfix cancelled")
            sys.exit(0)
    
    # Step 6: Find insertion point for hotfix code
    # Insert after imports (look for first class definition)
    import_end = original_content.find("class ")
    if import_end == -1:
        print("❌ ERROR: Could not find insertion point (no class definition)")
        sys.exit(1)
    
    # Step 7: Apply hotfix code
    timestamp = datetime.now().isoformat()
    hotfix_code = HOTFIX_CODE.format(timestamp=timestamp)
    
    modified_content = (
        original_content[:import_end] +
        hotfix_code +
        original_content[import_end:]
    )
    
    # Step 8: Replace _assign_tier method
    # Find the method definition
    method_start = modified_content.find("def _assign_tier(")
    if method_start == -1:
        print("❌ ERROR: Could not find _assign_tier method")
        sys.exit(1)
    
    # Find the end of the method (next method or class end)
    method_end = modified_content.find("\n    def ", method_start + 1)
    if method_end == -1:
        method_end = modified_content.find("\n\nclass", method_start)
    if method_end == -1:
        method_end = len(modified_content)
    
    # Replace method
    hotfix_method = HOTFIX_METHOD.format(timestamp=timestamp)
    modified_content = (
        modified_content[:method_start] +
        hotfix_method +
        modified_content[method_end:]
    )
    
    # Step 9: Write modified content
    with open(TENNIS_MODULE, 'w') as f:
        f.write(modified_content)
    
    modified_hash = calculate_file_hash(TENNIS_MODULE)
    print(f"✅ Hotfix applied successfully")
    print(f"🔐 Modified hash: {modified_hash[:16]}...")
    
    # Step 10: Create audit log entry
    log_audit_entry(
        action="TENNIS_CONFIDENCE_HOTFIX_APPLIED",
        details={
            "original_hash": original_hash,
            "modified_hash": modified_hash,
            "backup_path": str(backup_path),
            "hotfix_version": "Option_1_Emergency",
            "sop_reference": "Section_2.4_Confidence_Tiers"
        }
    )
    
    # Step 11: Run validation (optional but recommended)
    print("\n" + "="*70)
    print("VALIDATION PHASE")
    print("="*70 + "\n")
    
    try:
        # Try to import and test
        sys.path.insert(0, str(WORKSPACE_ROOT))
        
        # Simplified validation test
        test_code = """
from tennis.tennis_edge_detector import TENNIS_CONFIDENCE_MAP
from config.thresholds import CONFIDENCE_CAPS

# Test 1: Mapping exists
assert 'HIGH' in TENNIS_CONFIDENCE_MAP
assert 'MEDIUM' in TENNIS_CONFIDENCE_MAP
assert 'LOW' in TENNIS_CONFIDENCE_MAP
print("✅ Test 1: Confidence mapping exists")

# Test 2: Mapped keys exist in CONFIDENCE_CAPS
for conf, key in TENNIS_CONFIDENCE_MAP.items():
    assert key in CONFIDENCE_CAPS, f"Key '{key}' not in CONFIDENCE_CAPS"
print("✅ Test 2: All mapped keys valid")

print("\\n✅ ALL VALIDATION TESTS PASSED")
"""
        exec(test_code)
        
    except Exception as e:
        print(f"⚠️  WARNING: Validation failed: {e}")
        print("Consider running full test suite manually")
    
    # Final summary
    print("\n" + "="*70)
    print("HOTFIX DEPLOYMENT COMPLETE")
    print("="*70)
    print(f"\n✅ Backup created: {backup_path}")
    print(f"✅ Hotfix applied to: {TENNIS_MODULE}")
    print(f"✅ Audit logged to: {AUDIT_LOG}")
    print("\n📋 Next Steps:")
    print("   1. Run full test suite: pytest tests/test_tennis_confidence.py")
    print("   2. Verify tennis pipeline: python run_tennis_analysis.py")
    print("   3. Deploy to production if tests pass")
    print("\n⚠️  To rollback: cp {backup_path} {TENNIS_MODULE}")
    print("="*70 + "\n")


# ============================================================================
# ROLLBACK FUNCTION
# ============================================================================

def rollback_hotfix():
    """Rollback to most recent backup"""
    
    print("\n" + "="*70)
    print("TENNIS HOTFIX ROLLBACK")
    print("="*70 + "\n")
    
    if not BACKUP_DIR.exists():
        print("❌ ERROR: No backups found")
        sys.exit(1)
    
    # Find most recent backup
    backups = sorted(BACKUP_DIR.glob("tennis_edge_detector_backup_*.py"), reverse=True)
    
    if not backups:
        print("❌ ERROR: No backups found in backup directory")
        sys.exit(1)
    
    latest_backup = backups[0]
    print(f"📂 Latest backup: {latest_backup}")
    
    response = input("Restore this backup? (y/n): ")
    if response.lower() != 'y':
        print("❌ Rollback cancelled")
        sys.exit(0)
    
    # Restore backup
    shutil.copy2(latest_backup, TENNIS_MODULE)
    print(f"✅ Restored from backup: {latest_backup}")
    
    # Log rollback
    log_audit_entry(
        action="TENNIS_CONFIDENCE_HOTFIX_ROLLBACK",
        details={
            "backup_restored": str(latest_backup),
            "restored_hash": calculate_file_hash(TENNIS_MODULE)
        }
    )
    
    print("✅ Rollback complete")


# ============================================================================
# CLI
# ============================================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Tennis Confidence Hotfix Deployment")
    parser.add_argument(
        'action',
        choices=['apply', 'rollback'],
        help="Action to perform"
    )
    
    args = parser.parse_args()
    
    if args.action == 'apply':
        apply_hotfix()
    elif args.action == 'rollback':
        rollback_hotfix()
