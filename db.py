import sqlite3
from datetime import datetime

DB_NAME = "trading_app.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    # Flexible Settings Table
    cursor.execute('''CREATE TABLE IF NOT EXISTS settings 
                      (key TEXT PRIMARY KEY, value TEXT)''')
    # Detailed Trade Logs
    cursor.execute('''CREATE TABLE IF NOT EXISTS trades 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, 
                       symbol TEXT, direction TEXT, entry_price REAL, 
                       exit_price REAL, status TEXT, pnl REAL)''')
    # Daily Risk Management Ledger
    cursor.execute('''CREATE TABLE IF NOT EXISTS daily_stats 
                      (date TEXT PRIMARY KEY, total_pnl REAL, status TEXT)''')
    conn.commit()
    conn.close()

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

# Initialize on load
init_db()
