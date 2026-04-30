"""
delta_executor.py - "GILL CRYPTO" Professional Option Engine
============================================================
Rules (from Dr. Saab's conversations):
- Asset: BTC (Delta Exchange)
- Supertrend (10, 1.5) on 1h candles - 24/7
- Signal: Supertrend FLIP + ADX > 25 (ADX Filter)
- Mandatory Square Off of existing position before new entry
- Strike Selection: ATM (At-The-Money)
- Expiry: Next Friday (7-day weekly cycle)
- Order: LIMIT at mark_price * 1.02 (2% buffer for fast fill)
- Paper Mode: $20,000 virtual balance (default)
- Live Mode: Requires Delta API Key + Secret from DB
"""

import time
import requests
import datetime
import sqlite3
import hmac
import hashlib
import db

# ─────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────

def log_crypto(msg):
    """Safe logger — no emoji to avoid Windows encoding errors."""
    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] [CRYPTO] {msg}")

# ─────────────────────────────────────────────────────────────────
# STEP 0: AUTHENTICATION
# ─────────────────────────────────────────────────────────────────

def get_delta_auth_headers(method="GET", endpoint="", payload=""):
    """
    Builds authenticated headers for Delta Exchange API.
    Reference: https://docs.delta.exchange/#authentication
    """
    api_key = db.get_param('delta_api_key', '')
    api_secret = db.get_param('delta_api_secret', '')

    if not api_key or not api_secret:
        # Public access only (no auth needed for market data)
        return {'Accept': 'application/json', 'Content-Type': 'application/json'}

    timestamp = str(int(time.time()))
    # Delta Exchange signature format: METHOD + timestamp + path + query_string + body
    # Since we have no query string for POST orders, it's empty.
    signature_data = method + timestamp + endpoint + payload
    signature = hmac.new(
        api_secret.encode('utf-8'),
        signature_data.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

    return {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
        'api-key': api_key,
        'signature': signature,
        'timestamp': timestamp
    }

def get_delta_balance():
    """
    Fetches the actual USDT balance from Delta India account.
    """
    try:
        url = "https://api.india.delta.exchange/v2/wallet/balances"
        headers = get_delta_auth_headers(method="GET", endpoint="/v2/wallet/balances")
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            balances = resp.json().get('result', [])
            for b in balances:
                if b.get('asset_symbol') == 'USDT' or b.get('asset_symbol') == 'USD':
                    return float(b.get('available_balance', 0))
        return 0.0
    except:
        return 0.0

# ─────────────────────────────────────────────────────────────────
# STEP 1: EXPIRY CALCULATION (Next Friday)
# ─────────────────────────────────────────────────────────────────

def get_next_friday_expiry():
    """
    Delta Exchange options expire every Friday.
    This returns the date string for the NEXT Friday in DD-MM-YYYY format
    (which is what the Delta Exchange API expects).
    """
    today = datetime.date.today()
    days_ahead = (4 - today.weekday()) % 7  # 4 = Friday
    if days_ahead == 0:
        days_ahead = 7  # If today IS Friday, go to NEXT Friday
    expiry = today + datetime.timedelta(days=days_ahead)
    log_crypto(f"Expiry Target: {expiry.strftime('%d-%m-%Y')} (Next Friday)")
    return expiry.strftime('%d-%m-%Y')

# ─────────────────────────────────────────────────────────────────
# STEP 2: FETCH OPTION CHAIN FROM DELTA EXCHANGE
# ─────────────────────────────────────────────────────────────────

def fetch_delta_option_chain(asset="BTC", expiry_date=None):
    """
    Fetches the full option chain for BTC or ETH from Delta India Exchange.
    - Public API: No auth needed for market data.
    - Endpoint: GET /v2/tickers
    - contract_types: 'call_options,put_options'
    
    Returns a list of option dicts with keys:
      symbol, strike_price, mark_price, contract_type, underlying_price
    """
    if not expiry_date:
        expiry_date = get_next_friday_expiry()

    url = "https://api.india.delta.exchange/v2/tickers"
    params = {
        'contract_types': 'call_options,put_options',
        'underlying_asset_symbols': asset,
        'expiry_date': expiry_date
    }

    try:
        resp = requests.get(url, params=params, timeout=10)
        if resp.status_code == 200:
            data = resp.json().get('result', [])
            log_crypto(f"Chain fetched: {len(data)} contracts for {asset} expiry {expiry_date}")
            return data
        else:
            log_crypto(f"Delta API Error: {resp.status_code} - {resp.text[:100]}")
    except requests.Timeout:
        log_crypto("Timeout fetching option chain. Will retry next cycle.")
    except Exception as e:
        log_crypto(f"Fetch Error: {e}")
    return []

# ─────────────────────────────────────────────────────────────────
# STEP 3: SELECT ATM/ITM OPTION (HYBRID KING RULE)
# ─────────────────────────────────────────────────────────────────

def find_gill_crypto_option(asset, direction):
    """
    Implements the "HYBRID KING Rule":
    - Find the ATM (At-The-Money) or slightly ITM option.
    - BUY signal  -> CALL option closest to spot
    - SELL signal -> PUT option closest to spot

    Returns: (symbol, limit_price, strike_price, expiry_date) or None
    """
    expiry_date = get_next_friday_expiry()
    chain = fetch_delta_option_chain(asset, expiry_date)

    if not chain:
        log_crypto("Chain empty. Cannot select option.")
        return None

    # Get spot price from the first chain item (spot_price field)
    spot = 0.0
    for item in chain:
        if item.get('spot_price'):
            spot = float(item['spot_price'])
            break

    if spot == 0:
        log_crypto("Could not determine spot price from chain.")
        return None

    log_crypto(f"{asset} Spot Price: ${spot:,.2f}")

    # Filter by option type
    option_type = "call_options" if direction == "BUY" else "put_options"
    options = [o for o in chain if o.get('contract_type') == option_type]
    
    if not options:
        log_crypto(f"No {option_type} found in chain.")
        return None

    # Find the option with strike closest to spot (ATM)
    target = min(options, key=lambda x: abs(float(x.get('strike_price', 0)) - spot))
    
    mark_price = float(target.get('mark_price', 0))
    strike = float(target.get('strike_price', 0))
    symbol = target.get('symbol', '')
    product_id = target.get('product_id', 0)

    if mark_price <= 0:
        log_crypto(f"Invalid mark price ({mark_price}) for {symbol}. Skipping.")
        return None

    # Apply 2% buffer for guaranteed fill
    limit_price = round(mark_price * 1.02, 2)

    log_crypto(f"SELECTED HYBRID KING ATM: {symbol} | Strike: ${strike:,.0f} | Mark: ${mark_price} | Limit: ${limit_price}")
    return symbol, limit_price, strike, expiry_date, product_id

# ─────────────────────────────────────────────────────────────────
# STEP 4: SQUARE OFF EXISTING POSITION
# ─────────────────────────────────────────────────────────────────

def sync_delta_position():
    """Fetches real-time position from Delta and syncs DB state."""
    mode = db.get_param('crypto_mode', 'Paper')
    if mode != "Live": return
    
    try:
        url = "https://api.india.delta.exchange/v2/positions"
        headers = get_delta_auth_headers(method="GET", endpoint="/v2/positions")
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            positions = resp.json().get('result', [])
            for p in positions:
                if float(p.get('size', 0)) != 0:
                    prod_id = p.get('product_id')
                    symbol = p.get('product', {}).get('symbol', 'Active')
                    side = p.get('side', '').upper() # BUY or SELL
                    db.set_param("crypto_active_product_id", str(prod_id))
                    db.set_param("crypto_active_symbol", symbol)
                    db.set_param("crypto_active_side", side)
                    log_crypto(f"Synced Active Position: {symbol} | Side: {side}")
                    return
            # If no open positions
            db.set_param("crypto_active_product_id", "")
            db.set_param("crypto_active_symbol", "")
            db.set_param("crypto_active_side", "")
    except Exception as e:
        log_crypto(f"Position Sync Error: {e}")

def square_off_crypto():
    """Closes any existing open crypto position."""
    sync_delta_position() # Ensure we have the latest product_id
    active_symbol = db.get_param("crypto_active_symbol", "")
    active_product_id = db.get_param("crypto_active_product_id", "")
    mode = db.get_param('crypto_mode', 'Paper')

    if not active_symbol or not active_product_id:
        return

    log_crypto(f"SQUARING OFF: {active_symbol} (Product ID: {active_product_id})")

    if mode == "Live":
        try:
            url = "https://api.india.delta.exchange/v2/orders"
            # To close, we place a sell order for the position size. 
            # Assuming 1 contract size for now.
            payload = '{"product_id":' + str(active_product_id) + ',"size":1,"side":"sell","order_type":"market_order","close_on_trigger":true}'
            headers = get_delta_auth_headers(method="POST", endpoint="/v2/orders", payload=payload)
            resp = requests.post(url, headers=headers, data=payload, timeout=10)
            log_crypto(f"Square Off API Response: {resp.status_code} - {resp.text[:150]}")
        except Exception as e:
            log_crypto(f"Square Off Exception: {e}")

    # Clear memory
    db.set_param("crypto_active_symbol", "")
    db.set_param("crypto_active_strike", "")
    db.set_param("crypto_active_expiry", "")
    db.set_param("crypto_active_product_id", "")
    log_crypto("Position cleared from memory.")

# ─────────────────────────────────────────────────────────────────
# STEP 5: MAIN EXECUTION FUNCTION
# ─────────────────────────────────────────────────────────────────

def execute_crypto_trade(asset, direction):
    """
    Full 'ADX Filter' execution workflow:
    1. Square off any existing position.
    2. Find the ATM option (CE or PE).
    3. Place LIMIT order with 2% buffer.
    4. Log everything to DB with full detail.
    """
    log_crypto(f"=== SIGNAL: {direction} | Asset: {asset} ===")

    mode = db.get_param('crypto_mode', 'Paper')

    # Step 1: Square off
    square_off_crypto()

    # Step 2: Find ATM option
    result = find_gill_crypto_option(asset, direction)

    if not result:
        # Paper fallback if API fails
        log_crypto("Using PAPER FALLBACK (API unavailable).")
        symbol = f"{asset}-PAPER-{direction}-ATM"
        limit_price = 100.0
        strike = 0.0
        expiry_date = get_next_friday_expiry()
        product_id = 0
        mode_status = "PAPER_FALLBACK"
    else:
        symbol, limit_price, strike, expiry_date, product_id = result
        mode_status = f"{mode}_TRADE"

    # Get Dynamic Size from Risk Management
    size = int(db.get_param('crypto_trade_size', '1'))

    if mode == "Live":
        try:
            url = "https://api.india.delta.exchange/v2/orders"
            payload = '{"product_id":' + str(product_id) + ',"size":' + str(size) + ',"side":"buy","order_type":"limit_order","limit_price":"' + str(limit_price) + '"}'
            headers = get_delta_auth_headers(method="POST", endpoint="/v2/orders", payload=payload)
            resp = requests.post(url, headers=headers, data=payload, timeout=10)
            log_crypto(f"Order Placement API Response: {resp.status_code} - {resp.text[:150]}")
            if resp.status_code == 200:
                db.set_param("crypto_active_entry_price", str(limit_price))
        except Exception as e:
            log_crypto(f"Order Placement Exception: {e}")

    # Step 3: Save position to memory
    db.set_param("crypto_active_symbol", symbol)
    db.set_param("crypto_active_strike", str(strike))
    db.set_param("crypto_active_expiry", expiry_date)
    db.set_param("crypto_active_product_id", str(product_id))

    # Step 4: Log trade to DB
    conn = sqlite3.connect(db.DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        '''INSERT INTO trades (timestamp, symbol, direction, entry_price, status)
           VALUES (?, ?, ?, ?, ?)''',
        (
            datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            f"{symbol} [Exp:{expiry_date}]",
            f"CRYPTO {direction}",
            limit_price,
            mode_status
        )
    )
    conn.commit()
    conn.close()

    log_crypto(f"Trade Logged: {symbol} | Strike: {strike} | Expiry: {expiry_date} | ${limit_price} | Mode: {mode}")
    return True

# SUPREME CLOUD SYNC: 2026-04-30
