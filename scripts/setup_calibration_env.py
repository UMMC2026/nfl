"""
Environment Setup Helper
Configures .env file for calibration tracking
"""
import sys
from pathlib import Path

def setup_environment():
    """Interactive setup for calibration tracking environment"""
    
    print("\n" + "=" * 70)
    print("CALIBRATION SYSTEM - ENVIRONMENT SETUP")
    print("=" * 70)
    print()
    
    env_file = Path(".env")
    
    # Check if .env exists
    if env_file.exists():
        with open(env_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if "ENABLE_CALIBRATION_TRACKING" in content:
            print("✅ Calibration tracking already configured in .env")
            print()
            
            # Show current value
            for line in content.split('\n'):
                if 'ENABLE_CALIBRATION_TRACKING' in line:
                    print(f"Current setting: {line}")
            
            print()
            try:
                modify = input("Modify setting? [y/N]: ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                modify = 'n'
            
            if modify != 'y':
                print("\nNo changes made.")
                return
    else:
        print("Creating new .env file...")
    
    print()
    print("CALIBRATION TRACKING OPTIONS:")
    print()
    print("  [1] ENABLE  - Capture predictions with lambda (RECOMMENDED)")
    print("  [2] DISABLE - Skip calibration tracking")
    print()
    
    try:
        choice = input("Choose option [1]: ").strip() or "1"
    except (EOFError, KeyboardInterrupt):
        choice = "1"
    
    if choice == "1":
        setting = "ENABLE_CALIBRATION_TRACKING=1"
        status = "ENABLED ✅"
    else:
        setting = "ENABLE_CALIBRATION_TRACKING=0"
        status = "DISABLED"
    
    # Update or create .env
    if env_file.exists():
        with open(env_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # Remove old ENABLE_CALIBRATION_TRACKING lines
        new_lines = [l for l in lines if 'ENABLE_CALIBRATION_TRACKING' not in l]
        
        # Add new setting
        new_lines.append(f"\n# Calibration System\n{setting}\n")
        
        with open(env_file, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)
    else:
        with open(env_file, 'w', encoding='utf-8') as f:
            f.write(f"# UNDERDOG ANALYSIS - Environment Configuration\n\n")
            f.write(f"# Calibration System\n{setting}\n")
    
    print()
    print("=" * 70)
    print(f"✅ Calibration tracking: {status}")
    print("=" * 70)
    print()
    
    if choice == "1":
        print("Next steps:")
        print("  1. Run analysis: .venv\\Scripts\\python.exe menu.py → [2] Analyze Slate")
        print("  2. Predictions will be saved to calibration/picks.csv with lambda values")
        print("  3. After games: menu.py → [6] → [A] Auto-fetch results")
        print("  4. Run diagnostic: menu.py → [DG] NBA Diagnostic")
    else:
        print("Calibration tracking is disabled.")
        print("Enable it anytime by running this script again.")
    
    print()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Configure calibration tracking environment")
    parser.add_argument("--enable", action="store_true", help="Enable tracking without prompts")
    parser.add_argument("--disable", action="store_true", help="Disable tracking without prompts")
    
    args = parser.parse_args()
    
    if args.enable:
        # Non-interactive enable
        env_file = Path(".env")
        if env_file.exists():
            with open(env_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            new_lines = [l for l in lines if 'ENABLE_CALIBRATION_TRACKING' not in l]
            new_lines.append(f"\n# Calibration System\nENABLE_CALIBRATION_TRACKING=1\n")
            with open(env_file, 'w', encoding='utf-8') as f:
                f.writelines(new_lines)
        else:
            with open(env_file, 'w', encoding='utf-8') as f:
                f.write(f"# UNDERDOG ANALYSIS - Environment Configuration\n\n")
                f.write(f"# Calibration System\nENABLE_CALIBRATION_TRACKING=1\n")
        print("✅ Calibration tracking ENABLED")
    
    elif args.disable:
        # Non-interactive disable
        env_file = Path(".env")
        if env_file.exists():
            with open(env_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            new_lines = [l for l in lines if 'ENABLE_CALIBRATION_TRACKING' not in l]
            new_lines.append(f"\n# Calibration System\nENABLE_CALIBRATION_TRACKING=0\n")
            with open(env_file, 'w', encoding='utf-8') as f:
                f.writelines(new_lines)
        print("✅ Calibration tracking DISABLED")
    
    else:
        # Interactive mode
        setup_environment()
