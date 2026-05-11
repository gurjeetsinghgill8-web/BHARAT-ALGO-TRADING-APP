import db

# --- BHARAT ALGOVERSE v3.0 | STABLE V3 CONFIGURATION ---
# RESTORED MASTER VERSION: Pure Option Buying | 5-Minute | 6 Lots

STRATEGY_MODE = "BUYING"
TIMEFRAME = "5m"
STABLE_CANDLE_ONLY = True 

# MASTER LOT SETTINGS (Dr. Saab's Strict Rule)
CRYPTO_LOT_SIZE = 6

# DATABASE & UI
DB_NAME = "buying.db"
PORT = 8501
TELEGRAM_PREFIX = "🚀 [BHARAT V3 STABLE]"

# LOGGING
LOG_FILE = "buying_trades.log"

def get_param(key, default="0"):
    """Wrapper for V3 compatibility with DB-based settings."""
    return db.get_param(key, default)

def set_param(key, value):
    """Wrapper for V3 compatibility with DB-based settings."""
    return db.set_param(key, value)
