"""
nsl_config.py — BANK NIFTY SUPER LEAGUE (BNSL) | LEGO 1: Configuration
=======================================================================
All constants in one place. No logic here.
Engine and dashboard read these as fallback values.
DB settings always override at runtime.

BNSL-SPECIFIC RULES:
  • Instrument  : Bank Nifty (NSE_INDEX|Nifty Bank)
  • Lot size    : 30 units (revised Jan 2026, was 35)
  • Expiry      : MONTHLY ONLY — last Tuesday of month
                  (weekly discontinued Nov 20, 2024 by SEBI)
  • Premium     : ₹180 – ₹250 (lower side)
  • SuperTrend  : Period=10, Multiplier=1.0 (same as NSL)
  • Candle      : 5-minute closed candles only
  • Port        : 8504 (NSL=8502, BTC=8503 — no conflict)
  • Lock port   : 47211 (NSL=47210 — no conflict)
  • DB          : bnsl_trader.db (separate from NSL)
"""

# ─── Identity ─────────────────────────────────────────────────
APP_NAME    = "BANK NIFTY SUPER LEAGUE"
APP_VERSION = "v1.0"
APP_EMOJI   = "🏦"

# ─── Market windows (IST 24h) ─────────────────────────────────
MARKET_OPEN_H   = 9
MARKET_OPEN_M   = 16   # Engine starts at 9:16 AM
MARKET_CLOSE_H  = 15
MARKET_CLOSE_M  = 10   # Market window stays open till 3:10 (squareoff buffer)

# ─── Squareoff time (force close all positions) ───────────────
SQUAREOFF_H = 15
SQUAREOFF_M = 0    # Force close at 3:00 PM sharp

# ─── Lot settings ─────────────────────────────────────────────
DEFAULT_LOTS     = 1
DEFAULT_LOT_SIZE = 30   # Bank Nifty lot size (Jan 2026 revision)

# ─── Strike selection (premium range in ₹) ────────────────────
# Bank Nifty options are much more expensive than Nifty 50.
# Target: ₹180–₹250 lower side strikes.
DEFAULT_PREMIUM_MIN = 180
DEFAULT_PREMIUM_MAX = 250

# ─── Exit rules ───────────────────────────────────────────────
# Profit target: REMOVED — engine holds until SuperTrend flips.
# Stop loss: 0 = disabled. User can change from dashboard.
DEFAULT_STOP_LOSS_PCT = 0

# ─── SuperTrend Parameters ────────────────────────────────────
# Same as NSL: Period=10, Multiplier=1.0 — confirmed.
DEFAULT_ST_PERIOD     = 10
DEFAULT_ST_MULTIPLIER = 1.0

# Minimum closed candles needed before SuperTrend is valid.
ST_MIN_CANDLES = 12

# ─── Candle timeframe ─────────────────────────────────────────
ST_CANDLE_MINUTES = 5   # 5-minute candles (same as NSL)
CANDLE_INTERVAL   = "5minute"

# ─── API endpoints ────────────────────────────────────────────
UPSTOX_BASE    = "https://api.upstox.com/v2"
NIFTY_INST_KEY = "NSE_INDEX|Nifty Bank"   # ← Bank Nifty (not Nifty 50)

# ─── Expiry mode ──────────────────────────────────────────────
# MONTHLY = last Tuesday of current month (Bank Nifty only has monthly)
# WEEKLY  = next Thursday (NSL Nifty 50 mode — NOT for BNSL)
EXPIRY_MODE = "MONTHLY"

# ─── DB file ──────────────────────────────────────────────────
DB_FILE = "bnsl_trader.db"   # Completely separate from NSL's nsl_trader.db

# ─── Singleton port (prevents double-start) ───────────────────
LOCK_PORT = 47211   # NSL uses 47210 — different port, no conflict

# ─── Dashboard port ───────────────────────────────────────────
DASHBOARD_PORT = 8504   # NSL=8502 | BTC=8503 | BNSL=8504

# ─── Telegram ─────────────────────────────────────────────────
TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"

# ─── Grace period after entry (seconds) ───────────────────────
ENTRY_GRACE_PERIOD_SECS = 120

# ─── Lot integrity: NEVER allow more than this ────────────────
MAX_ALLOWED_LOTS = 1
