#!/bin/bash
# setup_cloudflare.sh — run once on VPS after:
#   cloudflared tunnel login
#   cloudflared tunnel create torrent-hybrid
# Then paste the tunnel UUID below.

set -e
TUNNEL_UUID="PASTE_YOUR_TUNNEL_UUID_HERE"
TUNNEL_NAME="torrent-hybrid"
HOME_DIR="$HOME"
CF_DIR="$HOME/.cloudflared"

echo "==> Writing cloudflared config"
cat > "$CF_DIR/config.yml" << EOF
tunnel: $TUNNEL_UUID
credentials-file: $CF_DIR/$TUNNEL_UUID.json
ingress:
  - hostname: $TUNNEL_NAME.YOUR_CF_ACCOUNT.workers.dev
    service: http://127.0.0.1:5000
  - service: http_status:404
EOF

echo "==> Writing cloudflared systemd service"
sudo tee /etc/systemd/system/cloudflared.service > /dev/null << EOF
[Unit]
Description=Cloudflare Tunnel
After=network.target

[Service]
User=$USER
ExecStart=/usr/bin/cloudflared tunnel --config $CF_DIR/config.yml run
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

echo "==> Writing Flask dashboard systemd service"
sudo tee /etc/systemd/system/torrent-dashboard.service > /dev/null << EOF
[Unit]
Description=Torrent Hybrid Dashboard
After=network.target

[Service]
User=$USER
WorkingDirectory=$HOME_DIR/torrent-hybrid
ExecStart=/usr/bin/python3 $HOME_DIR/torrent-hybrid/app.py
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

echo "==> Enabling and starting services"
sudo systemctl daemon-reload
sudo systemctl enable --now cloudflared
sudo systemctl enable --now torrent-dashboard

echo ""
echo "✓ Done. Check status with:"
echo "  sudo systemctl status cloudflared"
echo "  sudo systemctl status torrent-dashboard"
echo ""
echo "Your Mini App URL will be:"
echo "  https://$TUNNEL_NAME.YOUR_CF_ACCOUNT.workers.dev/app"
echo ""
echo "Put that URL in config/config.json as 'app_url'"
