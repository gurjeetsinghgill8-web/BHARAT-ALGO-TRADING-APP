# --- BHARAT ALGOVERSE v3.0 | SINGLE BOT CONFIGURATION ---
# STRICT RULE: Pure Option Buying | 5-Minute Timeframe | 6 Lots

STRATEGY_MODE = "BUYING"
TIMEFRAME = "5m"
STABLE_CANDLE_ONLY = True  # Always use iloc[-2] for stability

# LOT SETTINGS
CRYPTO_LOT_SIZE = 6        # Strict 6 Lots Rule

# DATABASE SETTINGS
DB_NAME = "buying.db"

# UI & PORT SETTINGS
PORT = 8501

# NOTIFICATION SETTINGS
TELEGRAM_PREFIX = "🚀 [BHARAT PRO 5M]"

# LOGGING
LOG_FILE = "buying_trades.log"
