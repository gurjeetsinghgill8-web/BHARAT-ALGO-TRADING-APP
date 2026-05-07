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
    """Loads API keys from secrets.txt into DB. All keys lowercased automatically."""
    secrets_file = "secrets.txt"
    secrets_file = "secrets.txt"    # Key name normalisation map
    # secrets.txt key → DB key
    _key_map = {
        'telegram_token':      'telegram_bot_token',
        'upstox_access_token': 'upstox_access_token',  
        'upstox_token':        'upstox_access_token',  
        'upstox_api_token':    'upstox_access_token',
        'upstox_phone':        'upstox_phone',
        'upstox_pin':          'upstox_pin',
        'upstox_totp_secret':  'upstox_totp_secret',
        'upstox_api_key':      'upstox_api_key',
        'upstox_api_secret':   'upstox_api_secret',
        'upstox_redirect_uri': 'upstox_redirect_uri',
    }

    secrets_files = ["secrets.txt", ".streamlit/secrets.toml"]
    loaded = []
    
    for secrets_file in secrets_files:
        if os.path.exists(secrets_file):
            with open(secrets_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#') or line.startswith('[') or '=' not in line:
                        continue
                    parts = line.split('=', 1)
                    if len(parts) != 2:
                        continue
                    k = parts[0].strip().lower()
                    v = parts[1].strip().strip('"').strip("'")
                    db_key = _key_map.get(k, k)   # use mapped key, else raw key
                    if k == 'trade_mode':
                        v = v.upper()
                    set_param(db_key, v)
                    loaded.append(db_key)

    if not loaded:
        print("\nCRITICAL ERROR: No secrets found in secrets.txt or .streamlit/secrets.toml")
        return False
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

def log_trade(symbol, direction, entry_price, exit_price, pnl, status="CLOSED"):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute("""INSERT INTO trades (timestamp, symbol, direction, entry_price, exit_price, status, pnl) 
                      VALUES (?, ?, ?, ?, ?, ?, ?)""", 
                   (timestamp, symbol, direction, entry_price, exit_price, status, pnl))
    conn.commit()
    conn.close()

def get_stats(days=1):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Total PnL
    cursor.execute("SELECT SUM(pnl) FROM trades WHERE timestamp >= datetime('now', ?)", (f'-{days} days',))
    total_pnl = cursor.fetchone()[0] or 0.0
    
    # Total Trades Count
    cursor.execute("SELECT COUNT(*) FROM trades WHERE timestamp >= datetime('now', ?)", (f'-{days} days',))
    count = cursor.fetchone()[0] or 0
    
    # Winning Trades Count
    cursor.execute("SELECT COUNT(*) FROM trades WHERE pnl > 0 AND timestamp >= datetime('now', ?)", (f'-{days} days',))
    wins = cursor.fetchone()[0] or 0
    
    win_rate = (wins / count * 100) if count > 0 else 0.0
    avg_pnl = (total_pnl / count) if count > 0 else 0.0
    
    conn.close()
    return total_pnl, count, win_rate, avg_pnl

init_db()
