╔══════════════════════════════════════════════════════════════════════╗
║           BHARAT ALGOVERSE v3.0 — NIFTY MODULE STABLE BACKUP        ║
║                   ⛔ DO NOT MODIFY THIS FOLDER ⛔                    ║
╚══════════════════════════════════════════════════════════════════════╝

SEALED ON  : 2026-05-06
SEALED BY  : Antigravity AI + Dr. Saab 🩺
VERSION    : 3.0 — NIFTY STABLE
STATUS     : ✅ PRODUCTION VERIFIED — LIVE ON VPS 46.224.133.16:8501
             ⚠️  LIVE mode requires UPSTOX_ACCESS_TOKEN in secrets.txt

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📁 FILES IN THIS BACKUP
========================
  nifty_logic.py      → Signal engine (yfinance + Supertrend for NSE)
  nifty_executor.py   → Upstox API: option chain, strike picker, orders
  nifty_main.py       → Nifty Bot Runner (9:25 AM - 3:10 PM IST only)
  app.py              → Full Dashboard (Crypto + Nifty pages)
  db.py               → Shared DB + secrets loader (loads Upstox token)
  utils.py            → Telegram + logging
  requirements.txt    → Python dependencies (includes upstox-python-sdk)
  vps_setup.sh        → VPS deploy script (includes bharat_nifty service)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🧠 SYSTEM ARCHITECTURE (Nifty Module)
========================================
  Signal Source  : NSE via yfinance (free, no subscription needed)
  Strategy       : Supertrend SAR — Positional (holds till flip)
  Timeframes     : 5m, 15m, 30m, 1h, 1d (configurable from dashboard)
  Instrument     : Nifty 50 Options (configurable to BankNifty etc.)
  Market Hours   : 9:25 AM – 3:10 PM IST, Mon–Fri ONLY
  Expiry Rule    : NEXT week's expiry (never current week — avoids theta)
  Expiry Day     : Configurable (default Tuesday = FinNifty)
                   Mon=0, Tue=1, Wed=2, Thu=3, Fri=4
  Strike Pick    : Nearest LTP to target premium (default ₹120)
  Lot Size       : 25 (Nifty 50 standard lot size)
  SL/TP          : Premium-based % monitoring (default 30% SL / 80% TP)
  Execution      : Upstox API v2
  DB Keys Prefix : nifty_
  Singleton Port : 47201 (crypto uses 47200 — no conflict)
  Systemd Service: bharat_nifty

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 KEY DB PARAMETERS (nifty_* namespace)
==========================================
  nifty_symbol          → ^NSEI (or ^NSEBANK, RELIANCE.NS, etc.)
  nifty_timeframe       → 15m
  nifty_st_period       → 10
  nifty_st_multiplier   → 1.5
  nifty_lots            → 1
  nifty_lot_size        → 25
  nifty_target_premium  → 120  (₹120 nearest strike)
  nifty_sl_percent      → 30   (30% loss on premium = exit)
  nifty_tp_percent      → 80   (80% profit on premium = exit)
  nifty_trade_mode      → LIVE (or PAPER for testing)
  nifty_expiry_weekday  → 1    (1=Tuesday, 3=Thursday, etc.)
  nifty_algo_running    → ON/OFF
  nifty_trade_active    → YES/NO
  nifty_active_symbol   → current instrument key (or NONE)
  nifty_last_direction  → BUY/SELL (or NONE)
  nifty_entry_premium   → float price paid for option
  nifty_expiry          → YYYY-MM-DD
  nifty_unrealized_pnl  → live % gain/loss

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔑 SECRETS.TXT FORMAT (VPS — add Upstox token to existing file)
=================================================================
  DELTA_API_KEY=your_delta_key          ← Crypto (already there)
  DELTA_API_SECRET=your_delta_secret    ← Crypto (already there)
  TELEGRAM_TOKEN=your_bot_token         ← Shared (already there)
  TELEGRAM_CHAT_ID=your_chat_id         ← Shared (already there)
  UPSTOX_ACCESS_TOKEN=your_upstox_token ← ADD THIS for Nifty LIVE

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🚀 HOW TO RESTORE THIS VERSION
================================
  1. Copy all files from this folder to the main project folder
  2. Run: DEPLOY_NOW.bat
  3. VPS auto-restarts all 3 services (dashboard + crypto + nifty)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️  IMPORTANT RULES FOR THIS BACKUP
======================================
  1. NEVER edit files inside this folder
  2. NEVER add Nifty logic to crypto files (keep them 100% separate)
  3. NEVER add crypto logic to Nifty files
  4. Nifty uses its OWN DB key namespace: nifty_*
  5. Crypto uses its OWN DB key namespace: crypto_*, trade_*, st_*
  6. Both share db.py, utils.py — DO NOT make them module-specific

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🤖 FOR ANTIGRAVITY AI — READ THIS FIRST
==========================================
  If you are helping with the NIFTY module and something breaks:
    → RESTORE FROM: VERSION_3_0_NIFTY_STABLE/
    → DO NOT touch main.py, delta_executor.py, logic.py (those are CRYPTO)
    → Nifty-specific files: nifty_logic.py, nifty_executor.py, nifty_main.py
    → Nifty DB keys ALL start with: nifty_
    → The nifty bot runs: nifty_main.py (systemd: bharat_nifty)
    → Market hours check: nifty_logic.is_market_open() → 9:25AM-3:10PM IST
    → Upstox API base: https://api.upstox.com/v2
    → Port 47201 is the Nifty bot singleton lock port
    → VPS IP: 46.224.133.16 | Dashboard: http://46.224.133.16:8501
    → Expiry is ALWAYS next week (skip_current_week=True) to avoid theta
