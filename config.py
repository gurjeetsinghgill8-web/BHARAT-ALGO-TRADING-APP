# --- BHARAT ALGOVERSE v3.0 | ENGINE CONFIGURATION ---
# This file controls the behavior of the specific instance.
# Physical Isolation Rule: One folder = One config = One strategy.

import os

# 1. STRATEGY SETTINGS
# Options: "BUYING" or "SELLING"
STRATEGY_MODE = "BUYING"

# 2. CANDLE SETTINGS
TIMEFRAME = "5m"
STABLE_CANDLE_ONLY = True  # True = Use iloc[-2] (Closed), False = iloc[-1] (Live)

# 3. NIFTY SETTINGS
NIFTY_LOT_SIZE = 65        # Strict 2026 Rule

# 4. DATABASE SETTINGS
# Each instance MUST have its own database file
DB_NAME = "buying.db" if STRATEGY_MODE == "BUYING" else "selling.db"

# 5. UI & PORT SETTINGS
PORT = 8501 if STRATEGY_MODE == "BUYING" else 8502

# 6. NOTIFICATION SETTINGS
# Prefix for Telegram messages to identify the bot instance
TELEGRAM_PREFIX = "🟢 [BUYING BOT]" if STRATEGY_MODE == "BUYING" else "🔴 [SELLING BOT]"

# 7. LOGGING
LOG_FILE = "buying_trades.log" if STRATEGY_MODE == "BUYING" else "selling_trades.log"
