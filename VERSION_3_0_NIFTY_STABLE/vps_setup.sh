#!/bin/bash
echo "===================================================="
echo "  BHARAT ALGOVERSE v3.0 - AUTO-HEAL + DEPLOY"
echo "===================================================="

# ── 1. Nuclear Clean ────────────────────────────────────
sudo pkill -9 python3   2>/dev/null || true
sudo pkill -9 streamlit 2>/dev/null || true
rm -f /root/BHARAT-ALGO-TRADING-APP/bot.lock

# ── 2. Auto-Reset Bot Memory in DB ─────────────────────
/usr/bin/python3 -c "
import sqlite3
conn = sqlite3.connect('/root/BHARAT-ALGO-TRADING-APP/trading_app.db')
c = conn.cursor()
resets = [
    ('crypto_active_symbol','NONE'),
    ('active_call_symbol','NONE'),
    ('active_put_symbol','NONE'),
    ('local_trade_active','NO'),
    ('order_pending','NO'),
]
for key, val in resets:
    c.execute(\"INSERT OR REPLACE INTO settings (key,value) VALUES (?,?)\", (key, val))
conn.commit()
conn.close()
print('DB memory cleared.')
" || echo "DB reset skipped (first run?)"

# ── 3. Install/Update Python Dependencies ───────────────
cd /root/BHARAT-ALGO-TRADING-APP
source venv/bin/activate
pip install -q --upgrade pip
pip install -q -r requirements.txt
echo "Dependencies installed."

# ── 4. Open Firewall for Dashboard ──────────────────────
sudo ufw allow 8501/tcp 2>/dev/null || true

# ── 5. Create systemd service: Dashboard ────────────────
cat > /etc/systemd/system/bharat_dashboard.service << 'EOF'
[Unit]
Description=Bharat AlgoVerse Dashboard v3.0
After=network.target

[Service]
User=root
WorkingDirectory=/root/BHARAT-ALGO-TRADING-APP
ExecStart=/root/BHARAT-ALGO-TRADING-APP/venv/bin/python3 -m streamlit run app.py --server.port 8501 --server.address 0.0.0.0
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# ── 6. Create systemd service: Crypto Engine ────────────
cat > /etc/systemd/system/bharat_engine.service << 'EOF'
[Unit]
Description=Bharat AlgoVerse Crypto Engine v3.0
After=network.target

[Service]
User=root
WorkingDirectory=/root/BHARAT-ALGO-TRADING-APP
ExecStart=/root/BHARAT-ALGO-TRADING-APP/venv/bin/python3 main.py
Restart=always
RestartSec=15

[Install]
WantedBy=multi-user.target
EOF

# ── 7. Create systemd service: Nifty Engine ─────────────
cat > /etc/systemd/system/bharat_nifty.service << 'EOF'
[Unit]
Description=Bharat AlgoVerse Nifty Engine v3.0
After=network.target

[Service]
User=root
WorkingDirectory=/root/BHARAT-ALGO-TRADING-APP
ExecStart=/root/BHARAT-ALGO-TRADING-APP/venv/bin/python3 nifty_main.py
Restart=always
RestartSec=15

[Install]
WantedBy=multi-user.target
EOF

# ── 8. Reload + Enable + Start all services ─────────────
sudo systemctl daemon-reload

sudo systemctl enable  bharat_dashboard
sudo systemctl enable  bharat_engine
sudo systemctl enable  bharat_nifty

sudo systemctl restart bharat_dashboard
sudo systemctl restart bharat_engine
# NOTE: Nifty engine started but will auto-sleep outside 9:25AM-3:10PM IST
sudo systemctl restart bharat_nifty

echo "===================================================="
echo "  AUTO-HEAL COMPLETE! System is now LIVE."
echo ""
echo "  Dashboard : http://46.224.133.16:8501"
echo "  Crypto Bot: systemctl status bharat_engine"
echo "  Nifty Bot : systemctl status bharat_nifty"
echo ""
echo "  IMPORTANT: If secrets.txt is missing on VPS,"
echo "  create it manually:"
echo "    nano /root/BHARAT-ALGO-TRADING-APP/secrets.txt"
echo "===================================================="
