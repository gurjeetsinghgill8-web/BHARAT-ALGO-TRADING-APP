╔══════════════════════════════════════════════════════════════════════╗
║       BHARAT ALGOVERSE v3.0 — INVESTMENT MODULE STABLE BACKUP       ║
║           RS LEGOMASTER — Momentum Investment Intelligence           ║
║                   ⛔ DO NOT MODIFY THIS FOLDER ⛔                    ║
╚══════════════════════════════════════════════════════════════════════╝

SEALED ON  : 2026-05-06
SEALED BY  : Antigravity AI + Dr. Saab 🩺
VERSION    : 3.0 — INVESTMENT (RS LEGOMASTER) STABLE
STATUS     : ✅ LIVE ON VPS | Daily 8AM Telegram reports active

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📁 FILES IN THIS BACKUP
========================
  invest_rs_engine.py → Core LEGO engine (RS calc, sector scan, stock rank)
  invest_report.py    → Telegram report builder (Daily/Weekly/Monthly)
  invest_main.py      → Scheduler (8AM Mon-Fri, Sunday 7PM)
  app.py              → Full Dashboard (Crypto + Nifty + Investment pages)
  db.py               → Shared DB (invest_* key namespace)
  utils.py            → Shared Telegram + logging
  requirements.txt    → Python packages
  vps_setup.sh        → VPS deploy (includes bharat_invest service)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🧱 LEGO MODULE ARCHITECTURE
=============================
  LEGO 1: Market Pulse     → Nifty RSI(14) → Aggressive/Defensive mode
  LEGO 2: RS Engine        → RS = (Stock/Nifty) over N days — primary 55d
  LEGO 3: Sector Scanner   → All 20 NSE sector indices ranked by RS-55
  LEGO 4: Stock Ranker     → Top stocks per sector, Large→Mid→Small priority
  LEGO 5: Allocation Calc  → % allocation by RS strength (max 25% per stock)
  LEGO 6: Emerging/Weak    → Quarterly sector leaders & laggards
  LEGO 7: Full Daily Scan  → Master function combining all LEGOs

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 RS FORMULA (Core Logic)
===========================
  RS_55 = (Stock_Today / Stock_55d_ago) / (Nifty_Today / Nifty_55d_ago)
  RS > 1.0 = Outperforming Nifty ✅
  RS < 1.0 = Underperforming Nifty ❌

  Periods:  55d = Primary | 30d = Short-term | 110d = Long-term

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 DB KEY NAMESPACE (invest_* ONLY)
=====================================
  invest_nifty_rsi        → Latest Nifty RSI value (float string)
  invest_market_mode      → AGGRESSIVE or DEFENSIVE
  invest_rs_period        → 55 (or 30/110)
  invest_top_sectors_n    → 5
  invest_top_stocks_n     → 3
  invest_algo_running     → ON/OFF
  invest_last_scan_dt     → YYYY-MM-DD HH:MM
  invest_last_report_dt   → YYYY-MM-DD HH:MM
  invest_last_daily_date  → YYYY-MM-DD (for dedup)
  invest_last_weekly_wk   → YYYY-WWW (for dedup)
  invest_top_sectors      → JSON string list of top sector names

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⏰ REPORT SCHEDULE
===================
  Daily   : 8:00 AM IST — Mon to Fri — Full RS report
  Weekly  : Sunday 7:00 PM IST — Summary of week
  Monthly : 1st of month — Part of daily (same format)
  All via : Telegram (uses TELEGRAM_TOKEN + TELEGRAM_CHAT_ID from secrets.txt)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔑 SECRETS.TXT (No new keys needed — uses existing Telegram token)
====================================================================
  TELEGRAM_TOKEN=your_bot_token     ← Already in secrets.txt
  TELEGRAM_CHAT_ID=your_chat_id     ← Already in secrets.txt
  (No exchange API needed — yfinance is free and public)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🚨 ISOLATION RULES
===================
  ⛔ NO auto-trading — analysis + Telegram reports ONLY
  ⛔ NEVER mix invest_* DB keys with nifty_* or crypto_*
  ⛔ NEVER add exchange API calls to invest_rs_engine.py
  ✅ yfinance is the ONLY data source (free, public)
  ✅ Singleton port: 47202 (crypto=47200, nifty=47201)
  ✅ Systemd service: bharat_invest

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🤖 FOR ANTIGRAVITY AI — READ THIS FIRST
==========================================
  Investment module files: invest_rs_engine.py, invest_report.py, invest_main.py
  NEVER touch: main.py, delta_executor.py, logic.py (Crypto files)
  NEVER touch: nifty_*.py files (Nifty files)
  DB keys: ALL start with invest_
  Port lock: 47202
  Service: bharat_invest
  Dashboard: Page 3 "💹 Investment (RS)" in app.py
  No exchange APIs — pure analysis using yfinance (free)
  Restore from: VERSION_3_0_INVEST_STABLE/
