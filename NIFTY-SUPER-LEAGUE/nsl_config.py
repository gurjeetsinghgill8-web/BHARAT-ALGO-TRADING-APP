"""
nsl_config.py — NIFTY SUPER LEAGUE | LEGO 1: Configuration
============================================================
All constants in one place. No logic here.
Engine and dashboard read these as fallback values.
DB settings always override at runtime.

RULES:
  • Anchor system: FULLY REMOVED. Never add it back.
  • Paper trade:   FULLY REMOVED. Never add it back.
  • Profit target: REMOVED. Engine holds until SuperTrend flip.
  • Stop Loss:     Dashboard-only manual cut. Default = disabled.
  • Market hours:  9:16 AM start | 3:00 PM force close.
  • Signal logic:  Price above ST line = BUY CALL | below = BUY PUT.
"""

# ─── Identity ─────────────────────────────────────────────────
APP_NAME    = "NIFTY SUPER LEAGUE"
APP_VERSION = "v4.1"
APP_EMOJI   = "🏆"

# ─── Market windows (IST 24h) ─────────────────────────────────
MARKET_OPEN_H   = 9
MARKET_OPEN_M   = 16   # Engine starts at 9:16 AM
MARKET_CLOSE_H  = 15
MARKET_CLOSE_M  = 10   # Market window stays open till 3:10 (so squareoff can fire)

# ─── Squareoff time (force close all positions) ───────────────
SQUAREOFF_H = 15
SQUAREOFF_M = 0    # Force close at 3:00 PM sharp

# ─── Lot settings ─────────────────────────────────────────────
DEFAULT_LOTS     = 1
DEFAULT_LOT_SIZE = 65   # NSE Nifty 50 standard lot

# ─── Strike selection (premium range in ₹) ────────────────────
DEFAULT_PREMIUM_MIN = 100
DEFAULT_PREMIUM_MAX = 120

# ─── Exit rules ───────────────────────────────────────────────
# Profit target: REMOVED — engine holds until SuperTrend flips.
# Stop loss: 0 = disabled. User can change from dashboard.
DEFAULT_STOP_LOSS_PCT = 0

# ─── SuperTrend Parameters ────────────────────────────────────
# 5-minute closed candles only (never the forming candle).
# Period=10, Multiplier=1.0 — confirmed default.
DEFAULT_ST_PERIOD     = 10
DEFAULT_ST_MULTIPLIER = 1.0

# Minimum closed candles needed before SuperTrend is valid.
# ATR needs `period` candles → +1 for first ST value = 11 minimum.
# We use 12 for a small safety margin.
ST_MIN_CANDLES = 12

# ─── Candle timeframe ─────────────────────────────────────────
ST_CANDLE_MINUTES = 5   # 5-minute candles (production)
CANDLE_INTERVAL   = "5minute"

# ─── API endpoints ────────────────────────────────────────────
UPSTOX_BASE    = "https://api.upstox.com/v2"
NIFTY_INST_KEY = "NSE_INDEX|Nifty 50"

# ─── DB file ──────────────────────────────────────────────────
DB_FILE = "nsl_trader.db"

# ─── Singleton port (prevents double-start) ───────────────────
LOCK_PORT = 47210

# ─── Telegram ─────────────────────────────────────────────────
TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"

# ─── Grace period after entry (seconds) ───────────────────────
# Exchange takes up to 30s to reflect a filled order.
# Lot guard is skipped during this window.
ENTRY_GRACE_PERIOD_SECS = 120

# ─── Lot integrity: NEVER allow more than this ────────────────
MAX_ALLOWED_LOTS = 1
