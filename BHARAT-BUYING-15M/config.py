# --- BHARAT ALGOVERSE v4.0 | ENGINE CONFIGURATION ---
# Instance: 15m Option Buying (Conservative / Deep ITM)

STRATEGY_MODE = "BUYING"
TIMEFRAME = "15m"
STABLE_CANDLE_ONLY = True
DB_NAME = "buying_15m.db"
PORT = 8502
TELEGRAM_PREFIX = "💎 [BUYING-15M]"
LOG_FILE = "buying_15m.log"
DEEP_ITM_LEVEL = 5 # 5-6 strikes deep ITM
LOT_SIZE = 2
