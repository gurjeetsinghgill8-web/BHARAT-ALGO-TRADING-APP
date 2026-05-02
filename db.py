import os
import sqlite3
from datetime import datetime

DB_NAME = "trading_app.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS settings 
                      (key TEXT PRIMARY KEY, value TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS trades 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, 
                       symbol TEXT, direction TEXT, entry_price REAL, 
                       exit_price REAL, status TEXT, pnl REAL)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS daily_stats 
                      (date TEXT PRIMARY KEY, total_pnl REAL, status TEXT)''')
    conn.commit()
    conn.close()

def load_secrets():
    """STRICT SECURITY: Loads keys from local secrets.txt only."""
    secrets_file = "secrets.txt"
    abs_path = os.path.abspath(secrets_file)
    if not os.path.exists(secrets_file):
        print("\n" + "!"*60)
        print(f"CRITICAL ERROR: secrets.txt NOT FOUND at {abs_path}")
        print("Please create a file named 'secrets.txt' in this folder.")
        # ... existing help print ...
        print("Format:")
        print("DELTA_API_KEY=your_key")
        print("DELTA_API_SECRET=your_secret")
        print("TELEGRAM_TOKEN=your_bot_token")
        print("TELEGRAM_CHAT_ID=your_chat_id")
        print("!"*60 + "\n")
        return False

    with open(secrets_file, 'r') as f:
        for line in f:
            if '=' in line:
                key, value = line.strip().split('=', 1)
                # Map to internal DB keys
                db_key = key.lower()
                if db_key == 'telegram_token': db_key = 'telegram_bot_token'
                if db_key == 'delta_base_url': db_key = 'delta_base_url'
                if db_key == 'trade_mode': db_key = 'trade_mode'
                set_param(db_key, value.upper() if db_key == 'trade_mode' else value)
    return True

def set_param(key, value):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
    conn.commit()
    conn.close()

def get_param(key, default=None):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else default

def get_daily_loss():
    today = datetime.now().strftime('%Y-%m-%d')
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT total_pnl FROM daily_stats WHERE date = ?", (today,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else 0.0

init_db()
