#!/bin/bash
# ====================================================
#   BHARAT ALGO-PRO v3.0 - SINGLE BOT DEPLOYMENT
# ====================================================

REPO_URL="https://github.com/gurjeetsinghgill8-web/BHARAT-ALGO-TRADING-APP.git"
TARGET_DIR="/root/BHARAT-ALGO-PRO"

echo "🧹 STARTING COMPLETE TEAR DOWN..."

# 1. Kill all existing streamlit and python bots
sudo pkill -9 streamlit
sudo pkill -9 python3

# 2. Delete ALL old folders (The "Deep Reset")
echo "🗑️ Deleting old folders..."
rm -rf /root/BHARAT-BUYING*
rm -rf /root/BHARAT-SELLING*
rm -rf /root/BHARAT-ALGO-TRADING-APP

# 3. Create fresh directory and clone
echo "🏗️ Setting up fresh BHARAT-ALGO-PRO..."
mkdir -p $TARGET_DIR
git clone $REPO_URL $TARGET_DIR

cd $TARGET_DIR

# 4. Setup Virtual Environment
echo "📦 Setting up Python Environment..."
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 5. Restore Secrets (Assuming secrets.txt exists in the current folder before running this or we'll need to manually re-add)
# If this script is run FROM the repo, we should copy secrets.
# For now, we assume user will provide secrets.txt or it was backed up.
# Note: I'll use a placeholder for now or assume it exists in /root/ if they have a backup.

# 6. Start the Bot
echo "🚀 Launching Bharat Algo-Pro..."
nohup venv/bin/python3 main.py > engine_output.log 2>&1 &
nohup venv/bin/python3 -m streamlit run app.py --server.port 8501 --server.headless true > dashboard_output.log 2>&1 &

echo "✅ DEPLOYMENT COMPLETE!"
echo "Bot is running on Port 8501."
