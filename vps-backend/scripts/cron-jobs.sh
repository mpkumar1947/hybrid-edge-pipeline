#!/bin/bash

# Install cron jobs for torrent hybrid system

# Every 5 minutes: Check disk usage and cleanup if needed
(crontab -l 2>/dev/null; echo "*/5 * * * * /usr/bin/python3 $HOME/torrent-hybrid/scripts/disk-manager.py") | crontab -

# Every 30 minutes: Transfer completed downloads to local machine
(crontab -l 2>/dev/null; echo "*/30 * * * * /usr/bin/python3 $HOME/torrent-hybrid/scripts/transfer-to-local.py") | crontab -

# Every hour: Check qBittorrent daemon is running
(crontab -l 2>/dev/null; echo "0 * * * * $HOME/torrent-hybrid/scripts/start-qbittorrent.sh") | crontab -

echo "✓ Cron jobs installed"
crontab -l
