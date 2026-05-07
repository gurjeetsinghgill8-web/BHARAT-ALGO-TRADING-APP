#!/bin/bash
# ====================================================
#   BHARAT ALGOVERSE v4.0 - SURGICAL DEPLOYMENT
# ====================================================

echo "🩺 Initiating Surgical Masterstroke..."

# 1. KILL ALL LEGACY PROCESSES
echo "🛑 Stopping all Python & Streamlit processes..."
sudo pkill -9 python3 2>/dev/null || true
sudo pkill -9 streamlit 2>/dev/null || true

# 2. DEFINE ISLANDS
ISLAND_5M="/root/BHARAT-BUYING-5M"
ISLAND_15M="/root/BHARAT-BUYING-15M"

# 3. START 5M ISLAND
echo "🏗️ Starting Island 1 (5m) on Port 8501..."
if [ -d "$ISLAND_5M" ]; then
    cd $ISLAND_5M
    # Ensure venv exists
    if [ ! -d "venv" ]; then
        python3 -m venv venv
        source venv/bin/activate
        pip install -r requirements.txt
    fi
    nohup venv/bin/python3 main.py > engine_5m.log 2>&1 &
    nohup venv/bin/python3 -m streamlit run app.py --server.port 8501 --server.address 0.0.0.0 > dash_5m.log 2>&1 &
else
    echo "❌ Error: $ISLAND_5M not found!"
fi

# 4. START 15M ISLAND
echo "🏗️ Starting Island 2 (15m) on Port 8502..."
if [ -d "$ISLAND_15M" ]; then
    cd $ISLAND_15M
    # Ensure venv exists
    if [ ! -d "venv" ]; then
        python3 -m venv venv
        source venv/bin/activate
        pip install -r requirements.txt
    fi
    nohup venv/bin/python3 main.py > engine_15m.log 2>&1 &
    nohup venv/bin/python3 -m streamlit run app.py --server.port 8502 --server.address 0.0.0.0 > dash_15m.log 2>&1 &
else
    echo "❌ Error: $ISLAND_15M not found!"
fi

# 5. FIREWALL
sudo ufw allow 8501/tcp
sudo ufw allow 8502/tcp

echo "===================================================="
echo "✅ DEPLOYMENT COMPLETE!"
echo "📍 5M Island (Aggressive): Port 8501"
echo "📍 15M Island (Deep ITM): Port 8502"
echo "===================================================="
