#!/bin/bash
# Start qBittorrent daemon if not already running
if ! pgrep -x "qbittorrent-nox" > /dev/null; then
    qbittorrent-nox --daemon
    echo "[$(date)] qBittorrent started" >> ~/torrent-hybrid/logs/qbittorrent.log
else
    echo "[$(date)] qBittorrent already running" >> ~/torrent-hybrid/logs/qbittorrent.log
fi
