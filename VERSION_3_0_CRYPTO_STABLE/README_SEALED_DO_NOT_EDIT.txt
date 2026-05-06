╔══════════════════════════════════════════════════════════════════════╗
║          BHARAT ALGOVERSE v3.0 — CRYPTO MODULE STABLE BACKUP        ║
║                   ⛔ DO NOT MODIFY THIS FOLDER ⛔                    ║
╚══════════════════════════════════════════════════════════════════════╝

SEALED ON  : 2026-05-06
SEALED BY  : Antigravity AI + Dr. Saab 🩺
VERSION    : 3.0 — CRYPTO STABLE
STATUS     : ✅ PRODUCTION VERIFIED — LIVE ON VPS 46.224.133.16:8501

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📁 FILES IN THIS BACKUP
========================
  app.py              → Streamlit Dashboard (Crypto page only)
  main.py             → Crypto Trading Engine (Always-In-Trade SAR)
  logic.py            → Supertrend Signal Calculator
  delta_executor.py   → Delta Exchange API (BTC Options)
  executor.py         → Legacy executor (backup reference)
  db.py               → SQLite Database Manager + secrets loader
  utils.py            → Telegram alerts + logging
  requirements.txt    → Python package list
  DEPLOY_NOW.bat      → One-click deploy to VPS (Windows)
  vps_setup.sh        → Auto-install & systemd setup on VPS
  deploy.sh           → Basic deploy script
  emergency_close.py  → Emergency square-off tool

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🧠 SYSTEM ARCHITECTURE (Crypto Module)
========================================
  Signal Source  : Delta Exchange V2 API (OHLCV candles)
  Strategy       : Supertrend SAR — Always-In-Trade
  Timeframes     : 5m, 15m, 1h, 4h (configurable from dashboard)
  Instrument     : BTC Perpetual Options
  Lot Control    : "Clean Slate" rule — max 1 active position
  SL/TP          : In-code monitoring (40% SL / 100% TP by default)
  Execution      : Delta Exchange Bracket Orders
  DB Keys Prefix : crypto_, trade_, sl_, tp_, st_

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔑 SECRETS.TXT FORMAT (VPS only — never commit to git)
========================================================
  DELTA_API_KEY=your_key
  DELTA_API_SECRET=your_secret
  TELEGRAM_TOKEN=your_bot_token
  TELEGRAM_CHAT_ID=your_chat_id
  TRADE_MODE=LIVE

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🚀 HOW TO RESTORE THIS VERSION
================================
  1. Copy all files from this folder to the main project folder
  2. Run: DEPLOY_NOW.bat
  3. Done — VPS will auto-restart with this version

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️  IMPORTANT RULES FOR THIS BACKUP
======================================
  1. NEVER edit files inside this folder
  2. NEVER use this folder as a working directory
  3. Only COPY FROM here when restoring
  4. To restore: copy to main folder → DEPLOY_NOW.bat
  5. Nifty module files are NOT here (they are in VERSION_3_0_NIFTY_STABLE)
  6. This folder is the "ground truth" for Crypto v3.0

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🤖 FOR ANTIGRAVITY AI — READ THIS FIRST
==========================================
  If you are helping with the CRYPTO module and something breaks:
    → RESTORE FROM: VERSION_3_0_CRYPTO_STABLE/
    → DO NOT mix Nifty files into crypto logic
    → DB keys for crypto start with: crypto_, trade_, st_, sl_, tp_
    → The crypto bot runs: main.py (systemd: bharat_engine)
    → The dashboard runs: app.py (systemd: bharat_dashboard)
    → Port 47200 is the crypto bot singleton lock port
    → Delta Exchange API base: https://api.delta.exchange
    → VPS IP: 46.224.133.16 | Dashboard: http://46.224.133.16:8501
