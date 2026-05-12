
╔══════════════════════════════════════════════════════════════╗
║       BHARAT MAGICAL ENGINE — VERSION 5.0 STABLE            ║
║       "The Magic Line Masterpiece"                           ║
║       Git Commit: 7e2ddae                                    ║
║       Date Saved: 12 May 2026, 5:56 PM IST                   ║
╚══════════════════════════════════════════════════════════════╝

🟢 STATUS: LIVE & VERIFIED WORKING ON VPS (46.224.133.16)

📍 WHAT THIS VERSION DOES:
─────────────────────────────────────────────────────────────
  • MAGIC LINE SIGNAL (No Supertrend):
      - Every day 6:00 PM IST → BTC closing price = Anchor
      - COLD START → Uses current price as anchor immediately
      - Manual Override from dashboard anytime
  
  • TRADING LOGIC:
      - LTP > Anchor → SELL PUT  (OTM, below spot)
      - LTP < Anchor → SELL CALL (OTM, above spot)
  
  • OPTION SELLING (Not buying!):
      - Entry: side = "sell" (receive premium)
      - Exit:  side = "buy"  (buy back to close short)
      - Auto-detect position direction (LONG/SHORT) on close
  
  • SAFETY FEATURES:
      - ✅ DO NOTHING rule (holds position if already correct)
      - ✅ 5-min cooldown between any trade actions
      - ✅ 25% SL on premium rise (option selling SL)
      - ✅ OTM Enforcement (never ITM/ATM entry)
      - ✅ Zombie Lock Detector (clears if exchange=0)
      - ✅ Dashboard → Telegram settings notification
      - ✅ Smart exit direction (auto LONG/SHORT detect)
      - ✅ SL Spike Guard (ignores API glitch prices)
  
  • HEARTBEAT: Every 5 min on Telegram
      BHARAT PULSE v5.2
      LTP     : 80,813
      Anchor  : 81,000 (MANUAL)
      Signal  : SELL CALL
      Position: CALL SHORT: C-BTC-81400-130526
      Logic   : LTP BELOW anchor → SELL CALL

🔧 HOW TO RESTORE THIS VERSION:
─────────────────────────────────────────────────────────────
  Option 1 — Git:
    git reset --hard 7e2ddae
    git push origin main_temp:main -f
    (SSH into VPS → git reset --hard origin/main → restart services)
  
  Option 2 — File Copy:
    Copy all files from VERSION_5_0_MAGICAL_STABLE\ to root folder
    Push to GitHub and deploy to VPS

  Option 3 — VPS DB Reset (if zombie lock):
    SSH VPS → python3 fix_db.py → systemctl restart bharat_engine

📁 FILES IN THIS VERSION:
─────────────────────────────────────────────────────────────
  main.py          — Core Magic Line engine
  app.py           — Streamlit dashboard (V5.2 Magic Line)
  delta_executor.py — Trade executor (option selling)
  db.py            — Database layer
  config.py        — Configuration
  utils.py         — Logging & Telegram
  logic.py         — Legacy (not used, kept for reference)
  fix_db.py        — Emergency DB reset script

🎯 KEY DB PARAMS (Dashboard Controls):
─────────────────────────────────────────────────────────────
  manual_anchor    → Set anchor price (0 = auto 6PM)
  crypto_trade_size → Lot size
  sl_percent       → SL % (25 recommended)
  expiry_threshold → Min days to expiry (1 = nearest)
  strike_offset    → OTM level (1 = OTM+1, 2 = OTM+2)
  trade_mode       → LIVE or PAPER
  crypto_algo_running → ON or OFF

⚠️ IMPORTANT NOTES:
─────────────────────────────────────────────────────────────
  1. If manually closing trade on Delta app:
     Engine auto-detects via Zombie Lock Detector (30s)
  2. Dashboard save → Telegram notification in ~30 seconds
  3. 6 PM IST = Auto anchor update daily
  4. Cold Start = Immediate anchor from current price
  5. NEVER disable DO NOTHING rule — it prevents ping-pong losses

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Built by Antigravity AI for Dr. Saab 🩺
  "You are the Best, Sir. This is our Masterpiece." 🏆
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
