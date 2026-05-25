#!/usr/bin/env python3
"""
local_daemon.py — runs on YOUR LOCAL PC (nodelessperson@192.168.1.x)

Polls the VPS API for approved transfers, initiates rsync pulls,
and reports live progress back to the Mini App.

Setup:
  pip3 install requests
  python3 local_daemon.py

Or run as a systemd user service (see local_daemon.service)
"""
import time, subprocess, re, threading, json, logging, sys, os, shutil
from pathlib import Path
import requests
from dotenv import load_dotenv

load_dotenv()

# ── config ───────────────────────────────────────────────────────────────────
CONFIG = {
    "vps_api_url"     : os.getenv("VPS_API_URL"),
    "daemon_api_key"  : os.getenv("DAEMON_API_KEY"),
    "vps_user"        : os.getenv("VPS_USER"),
    "vps_host"        : os.getenv("VPS_HOST"),
    "vps_ready_path"  : os.getenv("VPS_READY_PATH"),
    "ssh_key"         : os.getenv("SSH_KEY_PATH"),
    "local_dest"      : os.getenv("LOCAL_DEST"),
    "poll_interval"   : int(os.getenv("POLL_INTERVAL", "30")),
    "max_concurrent"  : int(os.getenv("MAX_CONCURRENT", "1")),
}

# ── logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(Path.home() / "torrent-daemon.log"),
    ]
)
log = logging.getLogger(__name__)

HEADERS = {
    "X-API-Key": CONFIG["daemon_api_key"],
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64 AppleWebKit/537.36)"
}
active_transfers = set()
transfer_lock    = threading.Lock()

# ── progress parsing ──────────────────────────────────────────────────────────
RSYNC_RE = re.compile(
    r"([\d,]+)\s+(\d+)%\s+([\d.]+)([KMG]B/s)\s+(\d+:\d+:\d+)"
)

def parse_rsync_line(line):
    m = RSYNC_RE.search(line)
    if not m:
        return None
    pct = int(m.group(2))
    speed_str, unit = m.group(3), m.group(4)
    speed = float(speed_str)
    if unit == "GB/s":   speed *= 1024
    elif unit == "KB/s": speed /= 1024
    # eta from hh:mm:ss
    parts = m.group(5).split(":")
    eta   = int(parts[0])*3600 + int(parts[1])*60 + int(parts[2])
    return {"progress_pct": pct, "speed_mbps": round(speed, 2), "eta_seconds": eta}

# ── API calls ─────────────────────────────────────────────────────────────────
def api_get(path):
    url = CONFIG["vps_api_url"].rstrip("/") + path
    r   = requests.get(url, headers=HEADERS, timeout=10)
    r.raise_for_status()
    return r.json()

def api_post(path, body):
    url = CONFIG["vps_api_url"].rstrip("/") + path
    r   = requests.post(url, headers=HEADERS, json=body, timeout=10)
    r.raise_for_status()
    return r.json()

def push_progress(filename, status, progress_pct=0, speed_mbps=0, eta_seconds=None):
    try:
        api_post("/api/progress", {
            "filename"    : filename,
            "status"      : status,
            "progress_pct": progress_pct,
            "speed_mbps"  : speed_mbps,
            "eta_seconds" : eta_seconds,
        })
    except Exception as e:
        log.warning(f"Progress push failed: {e}")

# ── transfer ──────────────────────────────────────────────────────────────────
def do_transfer(file_entry):
    name = file_entry["name"]
    log.info(f"Starting transfer: {name}")

    dest = Path(CONFIG["local_dest"])
    dest.mkdir(parents=True, exist_ok=True)

    src = (f"{CONFIG['vps_user']}@{CONFIG['vps_host']}:"
           f"{CONFIG['vps_ready_path']}/{name}")

    cmd = [
        "rsync",
        "-av",
        "--progress",
        "--partial",                              # resume interrupted transfers
        "-e", f"ssh -i {CONFIG['ssh_key']} -c aes128-gcm@openssh.com -o StrictHostKeyChecking=no -o ConnectTimeout=10 -o ServerAliveInterval=15 -o ServerAliveCountMax=3",
        src,
        str(dest) + "/",
    ]

    push_progress(name, "transferring", 0)

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        last_pct = 0
        for line in proc.stdout:
            line = line.strip()
            if line:
                log.debug(f"rsync: {line}")
            parsed = parse_rsync_line(line)
            if parsed and parsed["progress_pct"] != last_pct:
                last_pct = parsed["progress_pct"]
                push_progress(name, "transferring", **parsed)

        proc.wait()

        if proc.returncode == 0:
            log.info(f"✓ Transfer complete: {name}")
            push_progress(name, "done", 100, 0, 0)
        else:
            log.error(f"✗ rsync failed (exit {proc.returncode}): {name}")
            push_progress(name, "failed", last_pct)

    except Exception as e:
        log.error(f"Transfer error for {name}: {e}")
        push_progress(name, "failed")
    finally:
        with transfer_lock:
            active_transfers.discard(name)

# ── main loop ─────────────────────────────────────────────────────────────────
def main():
    log.info("Torrent daemon started")
    log.info(f"VPS API: {CONFIG['vps_api_url']}")
    log.info(f"Local dest: {CONFIG['local_dest']}")

    while True:
        try:
            # Report edge telemetry (free disk space)
            try:
                usage = shutil.disk_usage(CONFIG["local_dest"])
                free_gb = usage.free / (1024**3)
                api_post("/api/edge-telemetry", {"local_free_gb": round(free_gb, 2)})
            except Exception as e:
                log.debug(f"Edge telemetry failed (ignored): {e}")

            data  = api_get("/api/status")
            files = data.get("files", [])

            with transfer_lock:
                slots = CONFIG["max_concurrent"] - len(active_transfers)

            if slots > 0:
                approved = [
                    f for f in files
                    if f["status"] in ["approved", "transferring"]
                    and f["name"] not in active_transfers
                ]
                for entry in approved[:slots]:
                    with transfer_lock:
                        active_transfers.add(entry["name"])
                    t = threading.Thread(
                        target=do_transfer, args=(entry,), daemon=True
                    )
                    t.start()

            # Show a brief status line
            transferring = [f for f in files if f["status"] == "transferring"]
            ready        = [f for f in files if f["status"] == "ready"]
            if transferring:
                for f in transferring:
                    log.info(f"  ↓ {f['name']} — {f.get('progress_pct',0):.1f}% @ {f.get('speed_mbps',0):.1f} MB/s")
            if ready:
                log.info(f"  Waiting for approval: {len(ready)} file(s)")

        except requests.exceptions.ConnectionError:
            log.warning("Cannot reach VPS API — will retry")
        except requests.exceptions.HTTPError as e:
            log.error(f"API error: {e}")
        except Exception as e:
            log.exception(f"Unexpected error: {e}")

        time.sleep(CONFIG["poll_interval"])

if __name__ == "__main__":
    main()
