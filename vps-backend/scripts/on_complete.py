#!/usr/bin/env python3
"""
on_complete.py — fired by qBittorrent when a download finishes.

Configure in qBittorrent:
  Tools → Options → Downloads → "Run external program on torrent completion"
  Command: /usr/bin/python3 /home/spiderman_vm/torrent-hybrid/scripts/on_complete.py "%N" "%F" "%D" "%Z"

Arguments passed by qBit:
  %N = torrent name
  %F = file path (if single file)
  %D = save path (directory)
  %Z = size in bytes
"""
import sys, json, shutil, requests, logging, os
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

BASE       = Path.home() / "torrent-hybrid"
READY_DIR  = Path("/mnt/torrents/ready")
STATE_FILE = BASE / "config" / "transfer-state.json"
LOG_FILE   = BASE / "logs" / "on_complete.log"

logging.basicConfig(
    filename=str(LOG_FILE), level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(message)s"
)
log = logging.getLogger(__name__)

def load_config():
    return {
        "bot_token"      : os.getenv("BOT_TOKEN"),
        "chat_id"        : os.getenv("CHAT_ID"),
        "app_url"        : os.getenv("APP_URL")
    }

def load_state():
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"files": {}}

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

def send_notification(cfg, name, size_gb, app_url):
    """Send Telegram message with Mini App button."""
    token   = cfg["bot_token"]
    chat_id = cfg["chat_id"]

    size_str = f"{size_gb:.2f} GB" if size_gb >= 1 else f"{size_gb*1024:.0f} MB"
    text = (
        f"📥 *Download complete*\n\n"
        f"`{name}`\n\n"
        f"Size: *{size_str}*\n"
        f"Status: ready for transfer\n\n"
        f"Open the dashboard to approve ↓"
    )

    payload = {
        "chat_id"   : chat_id,
        "text"      : text,
        "parse_mode": "Markdown",
        "reply_markup": json.dumps({
            "inline_keyboard": [[{
                "text"        : "⚡ Open Transfer Dashboard",
                "web_app"     : {"url": app_url}
            }]]
        })
    }

    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data=payload, timeout=10
        )
        if resp.status_code == 200:
            log.info(f"Notification sent for: {name}")
        else:
            log.error(f"Telegram error {resp.status_code}: {resp.text}")
    except Exception as e:
        log.error(f"Notification failed: {e}")

def main():
    if len(sys.argv) < 4:
        log.error(f"Usage: on_complete.py <name> <file_path> <save_dir> [size_bytes]")
        sys.exit(1)

    name       = sys.argv[1]
    file_path  = Path(sys.argv[2])
    save_dir   = Path(sys.argv[3])
    size_bytes = int(sys.argv[4]) if len(sys.argv) > 4 else 0
    size_gb    = size_bytes / 1024**3

    log.info(f"Completion hook: name={name!r} path={file_path} size={size_gb:.2f}GB")

    cfg = load_config()
    READY_DIR.mkdir(parents=True, exist_ok=True)

    # Move torrent content to ready/
    # qBit may give us a file path or a directory (multi-file torrent)
    source = file_path if file_path.exists() else save_dir / name
    dest   = READY_DIR / name

    if not source.exists():
        log.error(f"Source not found: {source}")
        sys.exit(1)

    if dest.exists():
        log.warning(f"Already in ready/: {name} — skipping move")
    else:
        try:
            shutil.move(str(source), str(dest))
            log.info(f"Moved to ready/: {name}")
        except Exception as e:
            log.error(f"Move failed: {e}")
            sys.exit(1)

    # Update state
    state = load_state()
    state["files"][name] = {
        "name"     : name,
        "size_gb"  : round(size_gb, 3),
        "added_at" : datetime.now().isoformat(),
        "status"   : "ready",
        "progress_pct" : 0,
        "speed_mbps"   : 0,
        "eta_seconds"  : None,
        "approved_at"  : None,
        "completed_at" : None,
    }
    save_state(state)
    log.info(f"State updated: {name} → ready")

    # Send Telegram notification
    app_url = cfg.get("app_url", "")
    if app_url:
        send_notification(cfg, name, size_gb, app_url)
    else:
        log.warning("app_url not set in config — skipping notification")

if __name__ == "__main__":
    main()
