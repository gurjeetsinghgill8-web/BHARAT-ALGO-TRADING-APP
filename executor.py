import sqlite3
import time
import requests
from datetime import datetime
import db

# Upstox API Base URL
UPSTOX_API_URL = "https://api.upstox.com/v2"

def get_headers():
    access_token = db.get_param('upstox_access_token', 'YOUR_ACCESS_TOKEN')
    return {
        'Authorization': f'Bearer {access_token}',
        'Accept': 'application/json'
    }

def find_strike_and_expiry(spot_price, direction):
    """
    Selects Nearest OTM (Delta ~0.35) and Expiry (e.g., NEXT_WEEK).
    """
    expiry_pref = db.get_param('expiry_pref', 'NEXT_WEEK')
    
    # Logic: Round Nifty spot to nearest 50. 
    # For ~0.35 Delta OTM: Move 100-150 points away from Spot
    if direction == 'BUY':  # Supertrend Green -> Buy CE
        strike = round(spot_price / 50) * 50 + 100
        symbol = f"NIFTY {strike} CE ({expiry_pref})"
    else:  # Supertrend Red -> Buy PE
        strike = round(spot_price / 50) * 50 - 100
        symbol = f"NIFTY {strike} PE ({expiry_pref})"
        
    return symbol

def get_ltp(instrument_token):
    """Fetch Last Traded Price from Upstox (Mocked)."""
    # In production, this will hit: GET {UPSTOX_API_URL}/market-quote/quotes
    return 120.50

def log_trade(symbol, direction, entry_price, status):
    """Logs the trade execution into the db.py trades table."""
    conn = sqlite3.connect(db.DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO trades (timestamp, symbol, direction, entry_price, exit_price, status, pnl)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), symbol, direction, entry_price, 0.0, status, 0.0))
    conn.commit()
    conn.close()

def place_order(direction, spot_price):
    """
    Core Execution Engine. Places LIMIT order with Buffer & Retries.
    """
    symbol = find_strike_and_expiry(spot_price, direction)
    
    # 1. Fetching parameters from db.py
    buffer_pct = float(db.get_param('limit_buffer_pct', 15.0)) / 100.0
    product_type = db.get_param('product_type', 'INTRADAY')
    square_off_if_fails = db.get_param('square_off_if_fails', 'YES')
    qty = int(db.get_param('lot_size', 50))
    
    # 2. Price Logic with Buffer
    current_opt_price = get_ltp(symbol)
    limit_price = current_opt_price * (1 + buffer_pct)  # Upstox Limit Price Buffer
    
    payload = {
        "quantity": qty,
        "product": product_type,
        "validity": "DAY",
        "price": round(limit_price, 2),
        "tag": "algo_trade",
        "instrument_token": symbol,  # Actual token string required in live API
        "order_type": "LIMIT",
        "transaction_type": "BUY",  # Option buying strategy
        "disclosed_quantity": 0,
        "trigger_price": 0,
        "is_amo": False
    }

    # 3. Retry Logic (Up to 3 times)
    retries = 3
    order_status = "FAILED"
    
    for attempt in range(retries):
        try:
            # LIVE API CALL:
            # response = requests.post(f"{UPSTOX_API_URL}/order/place", headers=get_headers(), json=payload)
            # data = response.json()
            
            # Simulating Success
            order_status = "OPEN"
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Order Executed: {symbol} at Limit {limit_price:.2f}")
            break
        except Exception as e:
            print(f"Order Failed (Attempt {attempt+1}/{retries}): {str(e)}")
            time.sleep(2)  # Wait before retrying
            
    # 4. Square Off / Failsafe Logic
    if order_status == "FAILED" and square_off_if_fails == 'YES':
        print("Safety Switch: Order entry failed. Halting to prevent bad entries.")
        order_status = "SQUARED_OFF"
        
    # 5. Log back to DB
    log_trade(symbol, direction, limit_price, order_status)
    return order_status
