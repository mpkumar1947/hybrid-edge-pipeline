#!/usr/bin/env python3
import os
import shutil
import json
from pathlib import Path
from datetime import datetime

DOWNLOAD_DIR = Path.home() / "torrent-hybrid" / "downloads"
COMPLETED_DIR = Path.home() / "torrent-hybrid" / "completed"
LOG_FILE = Path.home() / "torrent-hybrid" / "logs" / "disk-manager.log"
STATE_FILE = Path.home() / "torrent-hybrid" / "config" / "disk-state.json"

WARN_THRESHOLD = 5  # GB — warn when disk free < 5GB
CRITICAL_THRESHOLD = 2  # GB — force cleanup when disk free < 2GB

def log(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_msg = f"[{timestamp}] {msg}"
    print(log_msg)
    with open(LOG_FILE, "a") as f:
        f.write(log_msg + "\n")

def get_disk_usage():
    """Return dict with disk stats in GB"""
    stat = shutil.disk_usage("/")
    return {
        "total_gb": stat.total / (1024**3),
        "used_gb": stat.used / (1024**3),
        "free_gb": stat.free / (1024**3),
    }

def cleanup_completed():
    """Delete files from DOWNLOAD_DIR that are in COMPLETED_DIR"""
    completed_files = set(f.name for f in COMPLETED_DIR.glob("*"))
    deleted_size = 0
    
    for item in DOWNLOAD_DIR.iterdir():
        if item.name in completed_files and item.is_file():
            size = item.stat().st_size / (1024**3)
            item.unlink()
            deleted_size += size
            log(f"DELETED: {item.name} ({size:.2f} GB)")
    
    return deleted_size

def main():
    disk = get_disk_usage()
    log(f"DISK STATUS: {disk['free_gb']:.2f}GB free / {disk['total_gb']:.2f}GB total")
    
    if disk['free_gb'] < CRITICAL_THRESHOLD:
        log(f"CRITICAL: Free disk < {CRITICAL_THRESHOLD}GB — forcing cleanup")
        freed = cleanup_completed()
        log(f"Freed {freed:.2f}GB after cleanup")
        disk = get_disk_usage()
        log(f"NEW STATUS: {disk['free_gb']:.2f}GB free")
    
    elif disk['free_gb'] < WARN_THRESHOLD:
        log(f"WARNING: Free disk < {WARN_THRESHOLD}GB")
    
    # Save state
    with open(STATE_FILE, "w") as f:
        json.dump(disk, f, indent=2)

if __name__ == "__main__":
    main()
