import socket
import subprocess
import os
import time
from pathlib import Path

# Constants
PORT = 9222
HOST = "127.0.0.1"
REPO_ROOT = Path("/Users/zhouhongyuan/Desktop/finer")
SHADOW_PROFILE = REPO_ROOT / ".agents/scratch/chrome_shadow_profile"
CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
RECOVERY_SCRIPT = REPO_ROOT / "scripts/bootstrap/browser_recovery.sh"
SYNC_SCRIPT = REPO_ROOT / "scripts/bootstrap/sync_chrome_identity.sh"

def is_port_open(host, port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        return s.connect_ex((host, port)) == 0

def run_script(path):
    print(f"Executing {path.name}...")
    subprocess.run(["bash", str(path)], check=True)

def start_shadow_chrome():
    print("🚀 Launching Shadow Chrome in headless mode...")
    cmd = [
        CHROME_PATH,
        f"--user-data-dir={SHADOW_PROFILE}",
        f"--remote-debugging-port={PORT}",
        "--headless=new",
        "--disable-gpu",
        "--no-first-run",
        "--allow-file-access-from-files",
        "--disable-web-security",
    ]
    # Start as a background process
    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    # Wait for startup
    attempts = 0
    while attempts < 10:
        if is_port_open(HOST, PORT):
            print(f"✅ Shadow Chrome is now listening on port {PORT}")
            return True
        time.sleep(1)
        attempts += 1
    
    print("❌ Failed to start Shadow Chrome after 10 seconds.")
    return False

def doctor_check():
    print(f"🕵️ Checking Shadow Chrome health on port {PORT}...")
    
    if is_port_open(HOST, PORT):
        print("✅ Shadow Chrome is active and healthy.")
        return True
    
    print("⚠️  Shadow Chrome is DOWN. Initiating recovery...")
    
    try:
        # Step 1: Recover environment (kills zombies, cleans locks)
        run_script(RECOVERY_SCRIPT)
        
        # Step 2: Sync identity
        run_script(SYNC_SCRIPT)
        
        # Step 3: Launch
        if start_shadow_chrome():
            return True
        else:
            return False
            
    except Exception as e:
        print(f"🚨 Doctor failed to heal the patient: {e}")
        return False

if __name__ == "__main__":
    success = doctor_check()
    if not success:
        exit(1)
