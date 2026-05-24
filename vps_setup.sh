#!/bin/bash

# ==============================================================================
# HYBRID-EDGE MEDIA ORCHESTRATION PIPELINE - VPS PROVISIONING SCRIPT
# Author: Manemoni Pavan Kumar
# Targeted Environment: Azure B1s (1 vCPU, 1 GiB RAM) / Ubuntu 24.04
# ==============================================================================
#
# DESIGN PHILOSOPHY:
# This script automates the deployment of a high-performance media backend on 
# resource-constrained hardware. It prioritizes native Linux services over 
# containerization (Docker) to eliminate bridge networking overhead and 
# preserve RAM for I/O operations.
#
# ==============================================================================

set -e # Exit on error

# --- 1. RESOURCE OPTIMIZATION (SWAP) ---
# Azure B1s instances (1GB RAM) will OOM (Out of Memory) during heavy torrent 
# I/O or multi-process Flask handling. We provision a 4GB swap to buffer peaks.
if [ ! -f /swapfile ]; then
    echo "[*] Provisioning 4GB Swap for memory stability..."
    sudo fallocate -l 4G /swapfile
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile
    sudo swapon /swapfile
    echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/etc/fstab
fi

# --- 2. CORE DEPENDENCIES ---
echo "[*] Updating system and installing core dependencies..."
sudo apt-get update && sudo apt-get install -y \
    qbittorrent-nox \
    python3-pip \
    python3-venv \
    python3-dotenv \
    rsync \
    curl \
    ufw

# --- 3. DIRECTORY ARCHITECTURE ---
echo "[*] Initializing project structure..."
mkdir -p ~/torrent-hybrid/{config,logs,scripts,templates,ready}
sudo mkdir -p /mnt/torrents
sudo chown -R $USER:$USER /mnt/torrents

# --- 4. QBITTORRENT-NOX CONFIGURATION ---
# Running qBit as a headless daemon. 
# Note: Initial run is required to generate the config file.
echo "[*] Configuring qBittorrent-nox..."
if ! pgrep -x "qbittorrent-nox" > /dev/null; then
    nohup qbittorrent-nox > /dev/null 2>&1 &
    sleep 5
    pkill -x "qbittorrent-nox"
fi

# --- 5. SYSTEMD SERVICE GENERATION (Flask Backend) ---
echo "[*] Deploying Flask Backend as a Persistent Linux Service..."
sudo tee /etc/systemd/system/torrent-dashboard.service <<EOF
[Unit]
Description=Hybrid-Edge Torrent Dashboard
After=network.target

[Service]
User=$USER
WorkingDirectory=$HOME/torrent-hybrid
ExecStart=/usr/bin/python3 app.py
Restart=always
RestartSec=5
StandardOutput=append:$HOME/torrent-hybrid/logs/flask.log
StandardError=append:$HOME/torrent-hybrid/logs/flask.log

[Install]
WantedBy=multi-user.target
EOF

# --- 6. TELEGRAM BOT LISTENER SERVICE ---
echo "[*] Deploying Telegram Bot Listener Service..."
sudo tee /etc/systemd/system/torrent-bot.service <<EOF
[Unit]
Description=Hybrid-Edge Telegram Bot Listener
After=network.target

[Service]
User=$USER
WorkingDirectory=$HOME/torrent-hybrid
ExecStart=/usr/bin/python3 scripts/bot_listener.py
Restart=always
RestartSec=5
StandardOutput=append:$HOME/torrent-hybrid/logs/bot_listener.log
StandardError=append:$HOME/torrent-hybrid/logs/bot_listener.log

[Install]
WantedBy=multi-user.target
EOF

# --- 7. FIREWALL & NETWORK SECURITY ---
echo "[*] Hardening network with UFW..."
sudo ufw allow 22/tcp      # SSH
sudo ufw allow 6969/tcp    # qBit WebUI (Tunnel access)
sudo ufw allow 5000/tcp    # Flask API (Tunnel access)
sudo ufw --force enable

# --- 8. FINALIZATION ---
sudo systemctl daemon-reload
echo "=============================================================================="
echo " SETUP COMPLETE: HYBRID-EDGE BACKEND IS ARMED"
echo "=============================================================================="
echo " NEXT STEPS:"
echo " 1. Populate ~/torrent-hybrid/.env with your secrets."
echo " 2. Run 'sudo systemctl enable --now torrent-dashboard torrent-bot'"
echo " 3. Connect your Cloudflare Tunnel to port 5000."
echo "=============================================================================="
