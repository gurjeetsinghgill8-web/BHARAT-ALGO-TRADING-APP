#!/bin/bash
# ====================================================
#   BHARAT ALGO-PRO v3.0 - SINGLE BOT SURGICAL DEPLOY
# ====================================================

# 1. KILL ALL LEGACY PROCESSES
echo "🛑 Killing all rogue bots..."
sudo pkill -9 streamlit 2>/dev/null || true
sudo pkill -9 python3 2>/dev/null || true

# 2. CLEANUP OLD SERVICES
echo "🧹 Removing legacy systemd services..."
sudo systemctl stop bharat_buying_engine bharat_buying_dash bharat_selling_engine bharat_selling_dash 2>/dev/null || true
sudo systemctl disable bharat_buying_engine bharat_buying_dash bharat_selling_engine bharat_selling_dash 2>/dev/null || true
rm -f /etc/systemd/system/bharat_*.service

# 3. DEEP RESET FOLDERS (Except the current deployment repo)
echo "🗑️ Deleting all variant folders..."
# We keep BHARAT-ALGO-TRADING-APP as the main engine base
rm -rf /root/BHARAT-BUYING*
rm -rf /root/BHARAT-SELLING*
rm -rf /root/BHARAT-ALGO-PRO

# 4. SETUP ENVIRONMENT in current folder
echo "🏗️ Hardening Virtual Environment..."
# Check if secrets.txt exists, if not, try to find it in root backup
if [ ! -f secrets.txt ] && [ -f /root/secrets.txt ]; then
    cp /root/secrets.txt .
fi

python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 5. CREATE AND ENABLE SINGLE-BOT SERVICES
echo "🚀 Configuring System Services..."

# Engine Service
cat > /etc/systemd/system/bharat_pro_engine.service << EOF
[Unit]
Description=Bharat Algo-Pro Engine
After=network.target

[Service]
User=root
WorkingDirectory=$(pwd)
ExecStart=$(pwd)/venv/bin/python3 main.py
Restart=always
RestartSec=15

[Install]
WantedBy=multi-user.target
EOF

# Dashboard Service
cat > /etc/systemd/system/bharat_pro_dash.service << EOF
[Unit]
Description=Bharat Algo-Pro Dashboard
After=network.target

[Service]
User=root
WorkingDirectory=$(pwd)
ExecStart=$(pwd)/venv/bin/python3 -m streamlit run app.py --server.port 8501 --server.address 0.0.0.0
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Start services
systemctl daemon-reload
systemctl enable bharat_pro_engine bharat_pro_dash
systemctl restart bharat_pro_engine bharat_pro_dash

echo ""
echo "===================================================="
echo "  ✅ SURGERY COMPLETE: Single-Bot is LIVE!"
echo "  Dashboard: http://46.224.133.16:8501"
echo "===================================================="
