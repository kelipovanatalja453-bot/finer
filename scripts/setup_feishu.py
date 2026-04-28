#!/usr/bin/env python3
"""
Setup Feishu — Initialize and verify Feishu file management configuration.
"""

import subprocess
import json
import os
import shutil
from pathlib import Path

def run_command(cmd):
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, shell=True)
        if result.returncode == 0:
            return result.stdout.strip()
        else:
            return None
    except Exception:
        return None

def check_lark_cli():
    print("Checking lark-cli...")
    path = shutil.which("lark-cli")
    if not path:
        # Check common brew location on Mac
        if os.path.exists("/opt/homebrew/bin/lark-cli"):
            path = "/opt/homebrew/bin/lark-cli"
        elif os.path.exists("/usr/local/bin/lark-cli"):
            path = "/usr/local/bin/lark-cli"
            
    if path:
        print(f"✅ lark-cli found at {path}")
        doctor = run_command(f"{path} doctor")
        if doctor:
            try:
                status = json.loads(doctor)
                if status.get("ok"):
                    print("✅ Feishu authentication verified.")
                    return True
                else:
                    print("❌ Feishu authentication failed. Please run 'lark-cli auth login'.")
            except:
                print("❌ Could not parse lark-cli doctor output.")
    else:
        print("❌ lark-cli not found. Please install it with 'npm install -g @larksuite/cli'.")
    return False

def check_nlm_cli():
    print("\nChecking nlm-cli...")
    path = shutil.which("nlm")
    if path:
        print(f"✅ nlm-cli found at {path}")
        return True
    else:
        print("❌ nlm-cli not found.")
    return False

def main():
    print("=== Finer Feishu Setup ===\n")
    lark_ok = check_lark_cli()
    nlm_ok = check_nlm_cli()
    
    config_path = Path("configs/feishu.yaml")
    if not config_path.exists():
        print(f"\n⚠️  {config_path} not found.")
        print("Please run: cp configs/feishu.yaml.example configs/feishu.yaml")
    
    print("\nSetup verification complete.")
    if lark_ok and nlm_ok:
        print("\n🚀 Ready to run 'finer feishu-sync'.")
    else:
        print("\n⚠️ Please fix the issues above before running sync.")

if __name__ == "__main__":
    main()
