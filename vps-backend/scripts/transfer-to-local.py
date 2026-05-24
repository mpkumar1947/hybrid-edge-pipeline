#!/usr/bin/env python3
import os
import subprocess
import json
from pathlib import Path
from datetime import datetime

COMPLETED_DIR = Path.home() / "torrent-hybrid" / "completed"
LOG_FILE = Path.home() / "torrent-hybrid" / "logs" / "transfer.log"
TRANSFER_STATE = Path.home() / "torrent-hybrid" / "config" / "transfer-state.json"

# Configuration — UPDATE THESE
LOCAL_USER = "nodelessperson"
LOCAL_IP = "192.168.1.1"
LOCAL_DOWNLOAD_PATH = "/home/nodelessperson/Downloads/torrent-downloads"
SSH_KEY = Path.home() / ".ssh" / "torrent-sync-key"

def log(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_msg = f"[{timestamp}] {msg}"
    print(log_msg)
    with open(LOG_FILE, "a") as f:
        f.write(log_msg + "\n")

def transfer_file(filename):
    """Transfer single file via rsync over SSH"""
    src = COMPLETED_DIR / filename
    dest = f"{LOCAL_USER}@{LOCAL_IP}:{LOCAL_DOWNLOAD_PATH}/"
    
    cmd = [
        "rsync",
        "-avz",
        "--progress",
        "-e", f"ssh -i {SSH_KEY} -o StrictHostKeyChecking=no",
        str(src) + "/",
        dest
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=7200)
        if result.returncode == 0:
            log(f"✓ TRANSFERRED: {filename}")
            return True
        else:
            log(f"✗ FAILED: {filename} — {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        log(f"✗ TIMEOUT: {filename} (transfer took >2h)")
        return False
    except Exception as e:
        log(f"✗ ERROR: {filename} — {str(e)}")
        return False

def main():
    if not COMPLETED_DIR.exists():
        log("No completed directory found")
        return
    
    # Get list of completed files
    completed_files = [f.name for f in COMPLETED_DIR.iterdir() if f.is_file()]
    
    if not completed_files:
        log("No completed files to transfer")
        return
    
    log(f"Found {len(completed_files)} files to transfer")
    
    for filename in completed_files:
        if transfer_file(filename):
            # Mark as transferred in state file
            with open(TRANSFER_STATE, "a") as f:
                f.write(f"{filename}\n")

if __name__ == "__main__":
    main()
