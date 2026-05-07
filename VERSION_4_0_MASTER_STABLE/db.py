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
    abs_path = os.path.abspath(secrets_file)
    if not os.path.exists(secrets_file):
        print("\n" + "!"*60)
        print(f"CRITICAL ERROR: secrets.txt NOT FOUND at {abs_path}")
        print("Format required:")
        print("  DELTA_API_KEY=your_key")
        print("  DELTA_API_SECRET=your_secret")
        print("  TELEGRAM_TOKEN=your_bot_token")
        print("  TELEGRAM_CHAT_ID=your_chat_id")
        print("  UPSTOX_ACCESS_TOKEN=your_upstox_token   ← Nifty ke liye")
        print("!"*60 + "\n")
        return False

    # Key name normalisation map
    # secrets.txt key → DB key
    _key_map = {
        'telegram_token':      'telegram_bot_token',
        'upstox_access_token': 'upstox_access_token',  # Nifty / Upstox
        'upstox_token':        'upstox_access_token',  # alias
        'upstox_api_token':    'upstox_access_token',  # alias
    }

    loaded = []
    with open(secrets_file, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            parts = line.split('=', 1)
            if len(parts) != 2:
                continue
            k = parts[0].strip().lower()
            v = parts[1].strip()
            db_key = _key_map.get(k, k)   # use mapped key, else raw key
            if k == 'trade_mode':
                v = v.upper()
            set_param(db_key, v)
            loaded.append(db_key)

    print(f"[secrets] Loaded {len(loaded)} keys: {loaded}")
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
