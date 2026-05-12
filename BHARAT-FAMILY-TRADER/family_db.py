import sqlite3
import os

DB_FILE = "family_trader.db"

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    conn.commit()
    return conn

def get_param(key, default=""):
    try:
        conn = get_db()
        cur = conn.execute("SELECT value FROM settings WHERE key=?", (key,))
        row = cur.fetchone()
        conn.close()
        return row[0] if row else default
    except:
        return default

def set_param(key, value):
    try:
        conn = get_db()
        conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?,?)", (key, str(value)))
        conn.commit()
        conn.close()
    except:
        pass

def load_secrets():
    """Load API keys from DB"""
    return bool(get_param("delta_api_key"))

def is_setup_complete():
    return (
        bool(get_param("delta_api_key")) and
        bool(get_param("delta_api_secret")) and
        bool(get_param("telegram_bot_token")) and
        bool(get_param("telegram_chat_id"))
    )
