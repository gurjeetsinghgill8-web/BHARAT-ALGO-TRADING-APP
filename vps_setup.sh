#!/bin/bash
echo "🩺 BHARAT ALGOVERSE: AUTO-HEAL PROTOCOL STARTING..."
echo "------------------------------------------------"

# 1. Nuclear Clean
sudo pkill -9 python3
sudo pkill -9 streamlit
rm -f /root/BHARAT-ALGO-TRADING-APP/bot.lock

# 2. Auto-Reset Bot Memory (Doing it myself!)
/usr/bin/python3 -c "import sqlite3; conn=sqlite3.connect('/root/BHARAT-ALGO-TRADING-APP/trading_app.db'); c=conn.cursor(); c.execute(\"UPDATE settings SET value='NONE' WHERE key='crypto_active_symbol'\"); c.execute(\"UPDATE settings SET value='NONE' WHERE key='active_call_symbol'\"); c.execute(\"UPDATE settings SET value='NONE' WHERE key='active_put_symbol'\"); c.execute(\"UPDATE settings SET value='NO' WHERE key='local_trade_active'\"); conn.commit(); conn.close()" || echo "DB reset skipped"

# 3. Open Firewall
sudo ufw allow 8501/tcp || echo "Firewall skipped"

# 4. Setup Dashboard Service (Absolute Path)
echo "[Unit]
Description=Bharat AlgoVerse Dashboard
After=network.target

[Service]
User=root
WorkingDirectory=/root/BHARAT-ALGO-TRADING-APP
ExecStart=/root/BHARAT-ALGO-TRADING-APP/venv/bin/python3 -m streamlit run app.py --server.port 8501 --server.address 0.0.0.0
Restart=always

[Install]
WantedBy=multi-user.target" | sudo tee /etc/systemd/system/bharat_dashboard.service

# 5. Setup Engine Service (Absolute Path)
echo "[Unit]
Description=Bharat AlgoVerse Trading Engine
After=network.target

[Service]
User=root
WorkingDirectory=/root/BHARAT-ALGO-TRADING-APP
ExecStart=/root/BHARAT-ALGO-TRADING-APP/venv/bin/python3 main.py
Restart=always

[Install]
WantedBy=multi-user.target" | sudo tee /etc/systemd/system/bharat_engine.service

# 6. Start Everything
sudo systemctl daemon-reload
sudo systemctl enable bharat_dashboard
sudo systemctl enable bharat_engine
sudo systemctl restart bharat_dashboard
sudo systemctl restart bharat_engine

echo "------------------------------------------------"
echo "✅ AUTO-HEAL COMPLETE! Your System is now LIVE."
echo "Dashboard: http://46.224.133.16:8501"
echo "------------------------------------------------"
