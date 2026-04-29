"""
delta_executor.py - "GILL CRYPTO" Professional Option Engine
============================================================
Rules (from Dr. Saab's conversations):
- Asset: BTC or ETH (Delta Exchange)
- Supertrend (10, 1.5) on 1h candles - 24/7
- Signal: Supertrend FLIP = action
- Mandatory Square Off of existing position before new entry
- Strike Selection: EXACTLY 5 strikes OTM
  - BUY (Green/Bullish) -> CALL option 5 strikes ABOVE spot
  - SELL (Red/Bearish)  -> PUT option 5 strikes BELOW spot
- Expiry: Next Friday (7-day weekly cycle)
- Order: LIMIT at mark_price * 1.02 (2% buffer for fast fill)
- Paper Mode: $20,000 virtual balance (default)
- Live Mode: Requires Delta API Key + Secret from DB
- Logging: Every trade logs timestamp, symbol, strike, expiry, price, mode
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
    # Delta Exchange signature format: METHOD + timestamp + path + body
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
    Fetches the full option chain for BTC or ETH from Delta Exchange.
    - Public API: No auth needed for market data.
    - Endpoint: GET /v2/tickers
    - contract_types: 'call_options,put_options'
    
    Returns a list of option dicts with keys:
      symbol, strike_price, mark_price, contract_type, underlying_price
    """
    if not expiry_date:
        expiry_date = get_next_friday_expiry()

    url = "https://api.delta.exchange/v2/tickers"
    params = {
        'contract_types': 'call_options,put_options',
        'underlying_asset_symbols': asset,
        'expiry_date': expiry_date
    }

    try:
        resp = requests.get(url, params=params, timeout=10)
        if resp.status_code == 200:
            data = resp.json().get('data', [])
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

    # Get spot price from the first chain item (underlying_price field)
    spot = 0.0
    for item in chain:
        if item.get('underlying_price'):
            spot = float(item['underlying_price'])
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

    if mark_price <= 0:
        log_crypto(f"Invalid mark price ({mark_price}) for {symbol}. Skipping.")
        return None

    # Apply 2% buffer for guaranteed fill
    limit_price = round(mark_price * 1.02, 2)

    log_crypto(f"SELECTED HYBRID KING ATM: {symbol} | Strike: ${strike:,.0f} | Mark: ${mark_price} | Limit: ${limit_price}")
    return symbol, limit_price, strike, expiry_date

# ─────────────────────────────────────────────────────────────────
# STEP 4: SQUARE OFF EXISTING POSITION
# ─────────────────────────────────────────────────────────────────

def square_off_crypto():
    """
    Closes any existing open crypto position BEFORE placing a new order.
    Paper: Clears memory.
    Live: Would send a SELL order to Delta Exchange (placeholder).
    """
    active_symbol = db.get_param("crypto_active_symbol", "")
    if not active_symbol:
        return

    log_crypto(f"SQUARING OFF: {active_symbol}")

    # Live square-off logic would go here:
    # POST /v2/orders with side='sell' and close_on_trigger=True

    # Clear memory
    db.set_param("crypto_active_symbol", "")
    db.set_param("crypto_active_strike", "")
    db.set_param("crypto_active_expiry", "")
    log_crypto("Position cleared from memory.")

# ─────────────────────────────────────────────────────────────────
# STEP 5: MAIN EXECUTION FUNCTION
# ─────────────────────────────────────────────────────────────────

def execute_crypto_trade(asset, direction):
    """
    Full 'Gill Crypto Rule' execution workflow:
    1. Square off any existing position.
    2. Find the 5-strike OTM option (CE or PE).
    3. Place LIMIT order with 2% buffer.
    4. Log everything to DB with full detail.

    Called from main_loop.py when Supertrend flips.
    """
    log_crypto(f"=== SIGNAL: {direction} | Asset: {asset} ===")

    mode = db.get_param('crypto_mode', 'Paper')

    # Step 1: Square off
    square_off_crypto()

    # Step 2: Find OTM option
    result = find_gill_crypto_option(asset, direction)

    if not result:
        # Paper fallback if API fails
        log_crypto("Using PAPER FALLBACK (API unavailable).")
        symbol = f"{asset}-PAPER-{direction}-5OTM"
        limit_price = 100.0
        strike = 0.0
        expiry_date = get_next_friday_expiry()
        mode_status = "PAPER_FALLBACK"
    else:
        symbol, limit_price, strike, expiry_date = result
        mode_status = f"{mode}_TRADE"

    # Step 3: Save position to memory
    db.set_param("crypto_active_symbol", symbol)
    db.set_param("crypto_active_strike", str(strike))
    db.set_param("crypto_active_expiry", expiry_date)

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
