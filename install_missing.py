import subprocess
import sys

packages = [
    "python-telegram-bot",
    "stripe",
    "cryptography",
]

print("Installing missing packages...\n")

for pkg in packages:
    print(f"Installing {pkg}...")
    result = subprocess.run([sys.executable, "-m", "pip", "install", pkg, "-q"])
    if result.returncode == 0:
        print(f"  ✅ {pkg}")
    else:
        print(f"  ❌ {pkg} failed")

print("\nDone!")
