#!/usr/bin/env python3
"""
Torrent Hybrid - Flask backend
Serves Telegram Mini App + REST API
Protected by Telegram HMAC or daemon API key
"""
from flask import Flask, render_template, jsonify, request, abort, redirect
import requests, json, shutil, hmac, hashlib, urllib.parse, logging, os
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__, template_folder="templates")
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

BASE        = Path.home() / "torrent-hybrid"
READY_DIR   = Path("/mnt/torrents/ready")
STATE_FILE  = BASE / "config" / "transfer-state.json"
LOG_FILE    = BASE / "logs" / "app.log"
QBIT_URL    = "http://localhost:6969/api/v2"

# ── helpers ──────────────────────────────────────────────────────────────────

def load_config():
    return {
        "bot_token"      : os.getenv("BOT_TOKEN"),
        "chat_id"        : os.getenv("CHAT_ID"),
        "app_url"        : os.getenv("APP_URL"),
        "qbit_user"      : os.getenv("QBIT_USER"),
        "qbit_pass"      : os.getenv("QBIT_PASS"),
        "daemon_api_key" : os.getenv("DAEMON_API_KEY")
    }

def load_state():
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"files": {}}

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

def get_disk():
    s = shutil.disk_usage("/mnt/torrents")
    return {
        "total_gb" : round(s.total / 1024**3, 2),
        "used_gb"  : round(s.used  / 1024**3, 2),
        "free_gb"  : round(s.free  / 1024**3, 2),
        "used_pct" : round((s.used / s.total) * 100, 1),
    }

def get_torrents():
    try:
        cfg  = load_config()
        resp = requests.get(
            f"{QBIT_URL}/torrents/info", timeout=5,
            auth=(cfg["qbit_user"], cfg["qbit_pass"])
        )
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        log.warning(f"qBit unreachable: {e}")
    return []

def verify_telegram_hmac(init_data: str, bot_token: str) -> bool:
    """
    Verify Telegram Mini App initData per official spec:
    https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
    """
    try:
        parsed        = dict(urllib.parse.parse_qsl(init_data, strict_parsing=True))
        received_hash = parsed.pop("hash", None)
        if not received_hash:
            return False
        data_check = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
        secret_key  = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
        expected    = hmac.new(secret_key, data_check.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, received_hash)
    except Exception:
        return False

def require_auth():
    """Allow Telegram Mini App users OR local daemon with API key."""
    cfg = load_config()

    # Daemon authentication (machine-to-machine)
    api_key = request.headers.get("X-API-Key", "")
    if api_key and hmac.compare_digest(api_key, cfg.get("daemon_api_key", "")):
        return

    # Telegram Mini App authentication — check header, then JSON body, then query param
    init_data = (
        request.headers.get("X-Telegram-Init-Data")
        or (request.get_json(silent=True) or {}).get("initData")
        or request.args.get("initData")
        or ""
    )
    if not init_data:
        abort(401, "No auth")
    if not verify_telegram_hmac(init_data, cfg["bot_token"]):
        abort(403, "Invalid Telegram signature")

# ── routes ───────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return redirect("/app")

@app.route("/app")
def miniapp():
    return render_template("miniapp.html")

@app.route("/api/status")
def api_status():
    require_auth()
    state = load_state()
    return jsonify({
        "files"     : list(state["files"].values()),
        "disk"      : get_disk(),
        "torrents"  : get_torrents(),
        "timestamp" : datetime.now().isoformat(),
    })

@app.route("/api/approve/<path:filename>", methods=["POST"])
def api_approve(filename):
    require_auth()
    state = load_state()
    if filename not in state["files"]:
        abort(404, "File not found")
    if state["files"][filename]["status"] not in ("ready", "skipped"):
        abort(400, "File not in approvable state")
    state["files"][filename]["status"]      = "approved"
    state["files"][filename]["approved_at"] = datetime.now().isoformat()
    save_state(state)
    log.info(f"Approved: {filename}")
    return jsonify({"ok": True})

@app.route("/api/skip/<path:filename>", methods=["POST"])
def api_skip(filename):
    require_auth()
    state = load_state()
    if filename not in state["files"]:
        abort(404)
    state["files"][filename]["status"] = "skipped"
    save_state(state)
    return jsonify({"ok": True})

@app.route("/api/delete/<path:filename>", methods=["POST"])
def api_delete(filename):
    """Remove a completed/skipped file from the ready dir and state."""
    require_auth()
    state = load_state()
    if filename not in state["files"]:
        abort(404)
    # Only allow deleting done/skipped entries
    if state["files"][filename]["status"] not in ("done", "skipped"):
        abort(400, "Can only delete done or skipped files")
    target = READY_DIR / filename
    if target.exists():
        if target.is_dir():
            import shutil as sh
            sh.rmtree(target)
        else:
            target.unlink()
    del state["files"][filename]
    save_state(state)
    return jsonify({"ok": True})

@app.route("/api/progress", methods=["POST"])
def api_progress():
    """
    Called by the local daemon to push transfer progress updates.
    Body: { filename, status, progress_pct, speed_mbps, eta_seconds }
    """
    require_auth()
    data     = request.get_json(force=True)
    filename = data.get("filename")
    state    = load_state()
    if filename not in state["files"]:
        abort(404)
    entry = state["files"][filename]
    entry.update({
        "status"      : data.get("status", "transferring"),
        "progress_pct": data.get("progress_pct", entry.get("progress_pct", 0)),
        "speed_mbps"  : data.get("speed_mbps", 0),
        "eta_seconds" : data.get("eta_seconds"),
    })
    if data.get("status") == "done":
        entry["completed_at"] = datetime.now().isoformat()
    save_state(state)
    return jsonify({"ok": True})

if __name__ == "__main__":
    READY_DIR.mkdir(parents=True, exist_ok=True)
    # Bind to localhost only — cloudflared handles the public side
    app.run(host="127.0.0.1", port=5000, debug=False)
