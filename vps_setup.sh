#!/bin/bash

echo "🩺 BHARAT ALGOVERSE: VPS PERMANENT CURE SETUP..."
echo "------------------------------------------------"

# 1. Setup Systemd Service for the Dashboard
DASH_CMD="streamlit run app.py --server.port 8501 --server.address 0.0.0.0"
if [ -f "$(pwd)/venv/bin/streamlit" ]; then
    DASH_CMD="$(pwd)/venv/bin/streamlit run app.py --server.port 8501 --server.address 0.0.0.0"
fi

echo "[Unit]
Description=Bharat AlgoVerse Dashboard
After=network.target

[Service]
User=$USER
WorkingDirectory=$(pwd)
ExecStart=$DASH_CMD
Restart=always

[Install]
WantedBy=multi-user.target" | sudo tee /etc/systemd/system/bharat_dashboard.service

# 2. Setup Systemd Service for the Trading Engine
ENGINE_CMD="python3 main.py"
if [ -f "$(pwd)/venv/bin/python3" ]; then
    ENGINE_CMD="$(pwd)/venv/bin/python3 main.py"
fi

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
