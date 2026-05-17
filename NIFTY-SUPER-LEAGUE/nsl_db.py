"""
nsl_db.py — NIFTY SUPER LEAGUE | LEGO 3: Database
====================================================
NSL state stored in nsl_trader.db (SQLite).
Credentials auto-loaded from parent folder:
  1. ../.streamlit/secrets.toml  (primary)
  2. ../trading_app.db           (fallback)

REMOVED: anchor_price, anchor_date, anchor_source,
         manual_anchor, signal_buffer_pct, profit_target_pct,
         paper_trade — all gone. SuperTrend state replaces them.
"""

import sqlite3
import os
import nsl_config as cfg

_DB      = cfg.DB_FILE
_PARENT  = os.path.join(os.path.dirname(__file__), "..")
_TOML    = os.path.join(_PARENT, ".streamlit", "secrets.toml")
_MAIN_DB = os.path.join(_PARENT, "trading_app.db")


# ─── NSL own DB ───────────────────────────────────────────────
def _conn():
    conn = sqlite3.connect(_DB, check_same_thread=False)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key   TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    conn.commit()
    return conn


def get(key: str, default: str = "") -> str:
    """Get a value from NSL DB."""
    try:
        conn = _conn()
        cur  = conn.execute("SELECT value FROM settings WHERE key=?", (key,))
        row  = cur.fetchone()
        conn.close()
        return row[0] if row else default
    except Exception:
        return default


def set(key: str, value) -> None:
    """Persist a key-value pair in NSL DB."""
    try:
        conn = _conn()
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?,?)",
            (key, str(value))
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


# ─── Load credentials from shared secrets ─────────────────────
def load_shared_secrets() -> bool:
    """
    Reads credentials from parent folder's secrets.toml or trading_app.db.
    Loads: upstox_access_token, telegram_bot_token,
           telegram_chat_id, upstox_proxy (optional VPN).
    """
    loaded = []

    # ── Source 1: secrets.toml ─────────────────────────────
    toml_key_map = {
        "upstox_access_token":      "upstox_access_token",
        "upstox_api_key":           "upstox_api_key",
        "upstox_api_secret":        "upstox_api_secret",
        "upstox_redirect_uri":      "upstox_redirect_uri",
        "telegram_token":           "telegram_bot_token",
        "telegram_bot_token":       "telegram_bot_token",
        "telegram_chat_id":         "telegram_chat_id",
        "selling_telegram_token":   "telegram_bot_token",
        "selling_telegram_chat_id": "telegram_chat_id",
        "upstox_proxy":             "upstox_proxy",
    }
    if os.path.exists(_TOML):
        with open(_TOML, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or line.startswith("[") or "=" not in line:
                    continue
                k, _, v = line.partition("=")
                k = k.strip().lower()
                v = v.strip().strip('"').strip("'")
                db_key = toml_key_map.get(k)
                if db_key and v:
                    set(db_key, v)
                    loaded.append(db_key)

    # ── Source 2: parent trading_app.db fallback ───────────
    try:
        if os.path.exists(_MAIN_DB):
            conn = sqlite3.connect(_MAIN_DB, check_same_thread=False)
            for col_key in ["upstox_access_token", "telegram_bot_token",
                             "telegram_chat_id", "upstox_proxy"]:
                if not get(col_key):
                    cur = conn.execute(
                        "SELECT value FROM settings WHERE key=?", (col_key,)
                    )
                    row = cur.fetchone()
                    if row and row[0]:
                        set(col_key, row[0])
                        loaded.append(col_key)
            conn.close()
    except Exception as e:
        print(f"[NSL-DB] Could not read parent trading_app.db: {e}")

    if loaded:
        unique = list(dict.fromkeys(loaded))
        print(f"[NSL-DB] Credentials loaded: {unique}")
        return True

    print("[NSL-DB] WARNING: No credentials found.")
    return False


# ─── Proxy helper ─────────────────────────────────────────────
def get_proxy() -> dict | None:
    """
    Returns requests-compatible proxy dict if upstox_proxy is set.
    Format: http://user:pass@ip:port  or  http://ip:port
    Returns None = direct connection (no proxy).
    """
    proxy_url = get("upstox_proxy", "")
    if not proxy_url:
        return None
    return {"http": proxy_url, "https": proxy_url}


# ─── Setup check ──────────────────────────────────────────────
def is_setup_complete() -> bool:
    """True if minimum credentials are present."""
    return (
        bool(get("upstox_access_token")) and
        bool(get("telegram_bot_token"))  and
        bool(get("telegram_chat_id"))
    )


# ─── Initialize defaults ──────────────────────────────────────
def init_defaults() -> None:
    """
    1. Load credentials from shared secrets.
    2. Write trading param defaults ONLY if not already set.
    """
    load_shared_secrets()

    defaults = {
        # Trading params
        "lots":                  str(cfg.DEFAULT_LOTS),
        "lot_size":              str(cfg.DEFAULT_LOT_SIZE),
        "premium_min":           str(cfg.DEFAULT_PREMIUM_MIN),
        "premium_max":           str(cfg.DEFAULT_PREMIUM_MAX),
        "stop_loss_pct":         str(cfg.DEFAULT_STOP_LOSS_PCT),
        # SuperTrend params
        "st_period":             str(cfg.DEFAULT_ST_PERIOD),
        "st_multiplier":         str(cfg.DEFAULT_ST_MULTIPLIER),
        # Engine state
        "algo_running":          "ON",
        "trade_active":          "NO",
        "active_symbol":         "NONE",
        "active_option_type":    "NONE",
        "entry_premium":         "0",
        "entry_time":            "",
        "entry_timestamp_epoch": "0",
        "last_candle_time":      "",
        "signal":                "NONE",
        "last_signal":           "NONE",
        # SuperTrend state
        "st_direction":          "NONE",   # BULLISH / BEARISH / NONE
        "st_value":              "0",      # SuperTrend line price
        "st_health":             "OK",     # OK / STALE / ERROR
        "st_last_update":        "",       # timestamp of last ST compute
        # Live price state
        "current_ltp":           "0",
        "current_option_ltp":    "0",
        "unrealized_pnl_pct":    "0",
    }
    for k, v in defaults.items():
        if not get(k):
            set(k, v)
