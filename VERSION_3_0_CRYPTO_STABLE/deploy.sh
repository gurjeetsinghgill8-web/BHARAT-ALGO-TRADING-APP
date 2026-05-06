#!/bin/bash

echo "🚀 BHARAT ALGOVERSE: VPS DEPLOYMENT STARTING..."
echo "-----------------------------------------------"

# 1. Update System
sudo apt-get update && sudo apt-get upgrade -y

# 2. Install Python and Dependencies
sudo apt-get install python3-pip python3-venv screen -y

# 3. Setup Virtual Environment
python3 -m venv venv
source venv/bin/activate

# 4. Install Requirements
pip install --upgrade pip
pip install -r requirements.txt

echo "-----------------------------------------------"
echo "✅ DEPLOYMENT SUCCESSFUL!"
echo "Next Steps:"
echo "1. Create 'secrets.txt' with your API keys."
echo "2. Run 'screen -S bharat_bot python3 main.py' to start in background."
echo "-----------------------------------------------"
