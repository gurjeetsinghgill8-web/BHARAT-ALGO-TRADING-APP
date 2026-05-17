#!/bin/bash
# ============================================================
# NSL VPS SETUP SCRIPT
# Runs on VPS: Ubuntu/Debian
# Sets up: Engine + Dashboard as permanent services
# ============================================================

set -e
REMOTE_DIR="/root/nsl-engine"
cd "$REMOTE_DIR"

echo ""
echo "============================================================"
echo "  NIFTY SUPER LEAGUE — VPS SETUP"
echo "============================================================"
echo ""

# ── Step 1: Install dependencies ─────────────────────────
echo "[1/6] Installing Python packages..."
pip3 install -q requests pytz streamlit pyOpenSSL --break-system-packages 2>/dev/null || \
pip3 install -q requests pytz streamlit pyOpenSSL
echo "     Done!"

# ── Step 2: Write credentials to DB ──────────────────────
echo "[2/6] Writing credentials to DB..."
python3 - <<'PYEOF'
import sys
sys.path.insert(0, '/root/nsl-engine')
import nsl_db as db

db.init_defaults()

# These are injected by the deploy script
import os
creds = {
    "upstox_api_key":     os.environ.get("NSL_API_KEY", ""),
    "upstox_api_secret":  os.environ.get("NSL_API_SECRET", ""),
    "upstox_access_token":os.environ.get("NSL_ACCESS_TOKEN", ""),
    "upstox_redirect_uri":os.environ.get("NSL_REDIRECT_URI", "https://127.0.0.1"),
    "telegram_bot_token": os.environ.get("NSL_TG_TOKEN", ""),
    "telegram_chat_id":   os.environ.get("NSL_TG_CHAT", ""),
    "manual_anchor":      os.environ.get("NSL_ANCHOR", "0"),
    "lots":               os.environ.get("NSL_LOTS", "1"),
    "lot_size":           os.environ.get("NSL_LOT_SIZE", "65"),
    "premium_min":        os.environ.get("NSL_PREM_MIN", "100"),
    "premium_max":        os.environ.get("NSL_PREM_MAX", "120"),
    "profit_target_pct":  os.environ.get("NSL_TP_PCT", "50"),
    "upstox_proxy":       "",  # No proxy on VPS - static IP used
    "trade_active":       "NO",
    "active_symbol":      "NONE",
    "algo_running":       "ON",
}
for k, v in creds.items():
    if v:
        db.set(k, v)
        print(f"  Set: {k}")

print("  Credentials written!")
PYEOF
echo "     Done!"

# ── Step 3: Create Systemd service for ENGINE ─────────────
echo "[3/6] Creating NSL Engine service..."
cat > /etc/systemd/system/nsl_engine.service <<'EOF'
[Unit]
Description=Nifty Super League Engine
After=network.target
Wants=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/nsl-engine
ExecStart=/usr/bin/python3 /root/nsl-engine/nsl_engine.py
Restart=always
RestartSec=10
StandardOutput=append:/root/nsl-engine/nsl_engine.log
StandardError=append:/root/nsl-engine/nsl_engine.log
Environment=PYTHONUNBUFFERED=1
Environment=PYTHONIOENCODING=utf-8

[Install]
WantedBy=multi-user.target
EOF
echo "     Done!"

# ── Step 4: Create Systemd service for DASHBOARD ──────────
echo "[4/6] Creating NSL Dashboard service..."
cat > /etc/systemd/system/nsl_dashboard.service <<'EOF'
[Unit]
Description=Nifty Super League Dashboard
After=network.target
Wants=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/nsl-engine
ExecStart=/usr/bin/python3 -m streamlit run /root/nsl-engine/nsl_dashboard.py \
    --server.port 8502 \
    --server.address 0.0.0.0 \
    --server.headless true \
    --browser.gatherUsageStats false \
    --server.enableCORS false \
    --server.enableXsrfProtection false
Restart=always
RestartSec=10
Environment=PYTHONUNBUFFERED=1
Environment=PYTHONIOENCODING=utf-8

[Install]
WantedBy=multi-user.target
EOF
echo "     Done!"

# ── Step 5: Enable & start services ──────────────────────
echo "[5/6] Starting services..."
systemctl daemon-reload
systemctl enable nsl_engine nsl_dashboard
systemctl restart nsl_engine
sleep 3
systemctl restart nsl_dashboard
sleep 3
echo "     Done!"

# ── Step 6: Open firewall for port 8502 ──────────────────
echo "[6/6] Opening firewall port 8502..."
ufw allow 8502/tcp 2>/dev/null || iptables -I INPUT -p tcp --dport 8502 -j ACCEPT 2>/dev/null || true
echo "     Done!"

echo ""
echo "============================================================"
echo "  SETUP COMPLETE!"
echo ""
echo "  ENGINE  : $(systemctl is-active nsl_engine)"
echo "  DASHBOARD: $(systemctl is-active nsl_dashboard)"
echo ""
VPS_IP=$(curl -s ifconfig.me 2>/dev/null || hostname -I | awk '{print $1}')
echo "  DASHBOARD URL (PERMANENT):"
echo "  http://$VPS_IP:8502"
echo ""
echo "  Open this URL on your mobile Chrome."
echo "  Tap 3-dot menu > Add to Home Screen"
echo "  Works 24/7 without laptop!"
echo "============================================================"
echo ""
