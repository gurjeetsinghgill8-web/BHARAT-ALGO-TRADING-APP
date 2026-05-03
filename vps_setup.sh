#!/bin/bash

echo "🩺 BHARAT ALGOVERSE: FORCING SYSTEM RECOVERY..."
# Fix Git Conflict
git fetch --all
git reset --hard origin/main

echo "🩺 BHARAT ALGOVERSE: VPS PERMANENT CURE SETUP..."
echo "------------------------------------------------"

# 0. Open Firewall for Dashboard
sudo ufw allow 8501/tcp || echo "Firewall skip..."

# 1. Setup Systemd Service for the Dashboard
DASH_CMD="python3 -m streamlit run app.py --server.port 8501 --server.address 0.0.0.0"

echo "[Unit]
Description=Bharat AlgoVerse Dashboard
After=network.target

[Service]
User=$USER
WorkingDirectory=$(pwd)
ExecStart=$DASH_CMD
Restart=always
" | sudo tee /etc/systemd/system/bharat_dashboard.service

# 2. Setup Systemd Service for the Trading Engine
PY_PATH=$(which python3 || echo "/usr/bin/python3")
ENGINE_CMD="$PY_PATH main.py"

echo "[Unit]
Description=Bharat AlgoVerse Trading Engine
After=network.target

[Service]
User=$USER
WorkingDirectory=$(pwd)
ExecStart=$ENGINE_CMD
Restart=always
" | sudo tee /etc/systemd/system/bharat_engine.service

# 3. Enable and Start Services
sudo systemctl daemon-reload
sudo systemctl enable bharat_dashboard
sudo systemctl enable bharat_engine
sudo systemctl restart bharat_dashboard
sudo systemctl restart bharat_engine

echo "------------------------------------------------"
echo "✅ SUCCESS! Your Private Hospital (VPS) is now AUTO-RUNNING."
echo "Dashboard: http://$(curl -s ifconfig.me):8501"
echo "------------------------------------------------"
