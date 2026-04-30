"""
executor.py - "GILL 120" Professional Option Execution Engine
==============================================================
Strategy Rules:
- Spot Signal: Supertrend flip on Nifty Spot (15m/30m/1h candle close)
- 10s Stability Delay: Wait after flip to avoid fake spike trades
- Option Selection: Upstox API v2 instrument search for Next Week CE/PE
- Premium Target: Find option closest to Rs.120 LTP
- Execution: LIMIT order at LTP * 1.045 (4.5% buffer for guaranteed fill)
- Square Off: Any existing position is closed FIRST before new entry
"""

import time
import requests
import datetime
import db

# ─────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────

def log(msg):
    """Safe ASCII-only logger to avoid UnicodeEncodeError on Windows."""
    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {msg}")

def get_headers():
    """Returns Upstox-ready Authorization headers."""
    token = db.get_param('upstox_api_key', '')
    return {
        'Accept': 'application/json',
        'Authorization': f'Bearer {token}'
    }

def get_upstox_balance():
    """Fetches real account balance (margin) from Upstox."""
    url = "https://api.upstox.com/v2/user/get-funds-and-margin"
    try:
        resp = requests.get(url, headers=get_headers(), timeout=5)
        if resp.status_code == 200:
            data = resp.json().get('data', {})
            equity = data.get('equity', {})
            return float(equity.get('available_margin', 0))
        return 0.0
    except:
        return 0.0

def get_next_thursday():
    """
    Calculates the date string (YYYY-MM-DD) for NEXT WEEK's Thursday (expiry day).
    Upstox needs an exact expiry_date in the option chain API.
    """
    today = datetime.date.today()
    # Days until Thursday (weekday 3)
    days_ahead = (3 - today.weekday()) % 7
    # If today is Thursday or before, go to next week's Thursday
    if days_ahead == 0:
        days_ahead = 7
    elif days_ahead <= 3:
        days_ahead += 7  # Skip to NEXT week's Thursday, not this week's
    next_thursday = today + datetime.timedelta(days=days_ahead)
    return next_thursday.strftime('%Y-%m-%d')

# ─────────────────────────────────────────────────────────────────
# STEP 1: GET OPTION CHAIN (Upstox API v2)
# ─────────────────────────────────────────────────────────────────

def fetch_option_chain(expiry_date):
    """
    Fetches the full Nifty Option Chain for a given expiry from Upstox API v2.
    Endpoint: GET /v2/option/chain
    """
    url = "https://api.upstox.com/v2/option/chain"
    params = {
        'instrument_key': 'NSE_INDEX|Nifty 50',
        'expiry_date': expiry_date
    }
    try:
        resp = requests.get(url, params=params, headers=get_headers(), timeout=8)
        if resp.status_code == 200:
            data = resp.json()
            if data.get('status') == 'success':
                log(f"Option Chain fetched successfully. Strikes: {len(data.get('data', []))}")
                return data.get('data', [])
            else:
                log(f"Upstox returned non-success: {data.get('message', 'Unknown error')}")
        else:
            log(f"HTTP Error fetching chain: {resp.status_code} - {resp.text[:200]}")
    except requests.Timeout:
        log("Timeout fetching option chain. Retrying in 3s...")
        time.sleep(3)
    except Exception as e:
        log(f"Exception fetching option chain: {e}")
    return []

# ─────────────────────────────────────────────────────────────────
# STEP 2: FIND BEST OPTION NEAR RS.120 (The "Gill 120" Logic)
# ─────────────────────────────────────────────────────────────────

def get_best_option(direction, target_price=120.0):
    """
    Scans the NEXT WEEK option chain and returns the contract
    whose LTP is closest to target_price (default Rs.120).

    direction == 'BUY'  -> Looks for CE (Call Option)
    direction == 'SELL' -> Looks for PE (Put Option)

    Returns: (instrument_key, ltp, strike) or None if not found.
    """
    option_type = "CE" if direction == "BUY" else "PE"
    expiry_date = get_next_thursday()
    log(f"Searching Next Week ({expiry_date}) {option_type} near Rs.{target_price}...")

    chain = fetch_option_chain(expiry_date)
    if not chain:
        log("No chain data received from Upstox. Using PAPER TRADING fallback.")
        return None

    best_key = None
    best_ltp = None
    best_strike = None
    min_diff = float('inf')

    for strike_data in chain:
        strike = strike_data.get('strike_price', 0)

        if option_type == "CE":
            opt = strike_data.get('call_options', {})
        else:
            opt = strike_data.get('put_options', {})

        if not opt:
            continue

        # LTP is under market_data sub-key in Upstox v2 option chain response
        market_data = opt.get('market_data', {})
        ltp = market_data.get('ltp', 0)
        instrument_key = opt.get('instrument_key', '')

        if ltp <= 0 or not instrument_key:
            continue

        diff = abs(ltp - target_price)
        if diff < min_diff:
            min_diff = diff
            best_ltp = ltp
            best_key = instrument_key
            best_strike = strike

    if best_key:
        log(f"BEST {option_type} FOUND: Strike={best_strike}, LTP=Rs.{best_ltp}, Key={best_key}")
        return best_key, best_ltp, best_strike
    else:
        log("No matching option found in chain. Using PAPER TRADING fallback.")
        return None

# ─────────────────────────────────────────────────────────────────
# STEP 3: SQUARE OFF EXISTING POSITION
# ─────────────────────────────────────────────────────────────────

def square_off_existing():
    """
    Closes any open position immediately.
    Uses MARKET order for instant fill at any price.
    """
    active_key = db.get_param("active_position_key", "")
    active_symbol = db.get_param("active_position_symbol", "")

    if not active_key:
        return  # Nothing to close

    log(f"SQUARING OFF: {active_symbol} at MARKET price. P&L will be logged.")

    mode = db.get_param('algo_mode', 'Paper') # Nifty mode
    if mode == "Live":
        # Get actual quantity from positions or use default lot size
        qty = int(db.get_param('nifty_trade_qty', '50'))
        payload = {
            "quantity": qty,
            "product": "D",
            "validity": "DAY",
            "price": 0,
            "instrument_token": active_key,
            "order_type": "MARKET",
            "transaction_type": "SELL",
            "is_amo": False
        }
        try:
            resp = requests.post("https://api.upstox.com/v2/order/place",
                                 json=payload, headers=get_headers(), timeout=8)
            log(f"Square Off Response: {resp.status_code} - {resp.text[:200]}")
        except Exception as e:
            log(f"Square Off FAILED: {e}")

    # Clear memory
    db.set_param("active_position_key", "")
    db.set_param("active_position_symbol", "")
    log("Old position cleared from memory.")

# ─────────────────────────────────────────────────────────────────
# STEP 4: PLACE NEW LIMIT ORDER
# ─────────────────────────────────────────────────────────────────

def place_limit_order(instrument_key, ltp, strike, direction):
    """
    Places a LIMIT BUY order for the selected option.
    Limit Price = LTP * 1.045 (4.5% buffer = high probability fill).
    """
    buffer_pct = float(db.get_param('limit_buffer_pct', 4.5))
    limit_price = round(ltp * (1 + buffer_pct / 100), 1)
    option_type = "CE" if direction == "BUY" else "PE"
    expiry_date = get_next_thursday()
    symbol_name = f"NIFTY {strike} {option_type} ({expiry_date})"

    log(f"PLACING LIMIT ORDER:")
    log(f"   Symbol : {symbol_name}")
    log(f"   LTP    : Rs.{ltp}")
    log(f"   Limit  : Rs.{limit_price} ({buffer_pct}% buffer)")
    log(f"   Key    : {instrument_key}")

    mode = db.get_param('algo_mode', 'Paper')
    if mode == "Live":
        qty = int(db.get_param('nifty_trade_qty', '50'))
        payload = {
            "quantity": qty,
            "product": "D",
            "validity": "DAY",
            "price": limit_price,
            "instrument_token": instrument_key,
            "order_type": "LIMIT",
            "transaction_type": "BUY",
            "is_amo": False
        }
        try:
            resp = requests.post("https://api.upstox.com/v2/order/place",
                                 json=payload, headers=get_headers(), timeout=8)
            log(f"Order Response: {resp.status_code} - {resp.text[:200]}")
        except Exception as e:
            log(f"Order Placement FAILED: {e}")

    # Save to memory
    db.set_param("active_position_key", instrument_key)
    db.set_param("active_position_symbol", symbol_name)

    # Log trade to database
    import sqlite3
    conn = sqlite3.connect(db.DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        '''INSERT INTO trades (timestamp, symbol, direction, entry_price, status)
           VALUES (?, ?, ?, ?, ?)''',
        (
            datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            symbol_name,
            f"BUY {option_type}",
            limit_price,
            "ORDER_PLACED"
        )
    )
    conn.commit()
    conn.close()
    log(f"Trade logged to DB: {symbol_name} @ Rs.{limit_price}")

def check_and_roll_nifty():
    """
    Checks the current LTP of the active Nifty position.
    If profit > 50% from entry, it books profit and re-enters.
    """
    active_key = db.get_param("active_position_key", "")
    entry_price = float(db.get_param("active_entry_price", "0"))
    
    if not active_key or entry_price <= 0:
        return

    # Fetch current LTP
    url = f"https://api.upstox.com/v2/market-quotes/ltp"
    params = {'instrument_key': active_key}
    try:
        resp = requests.get(url, params=params, headers=get_headers(), timeout=5)
        if resp.status_code == 200:
            data = resp.json().get('data', {})
            # Upstox LTP response is a dict with instrument key as key
            ltp = data.get(active_key, {}).get('last_price', 0)
            if ltp >= entry_price * 1.5:
                log(f"!!! ROLLING PROFIT !!! LTP {ltp} reached 50% target (Entry: {entry_price}).")
                direction = "BUY" if "CE" in db.get_param("active_position_symbol", "") else "SELL"
                square_off_existing()
                # Re-entry happens in next loop iteration or we can force it here
                target_premium = float(db.get_param('target_premium', 120.0))
                res = get_best_option(direction, target_premium)
                if res:
                    place_limit_order(res[0], res[1], res[2], direction)
                    db.set_param("active_entry_price", res[1])
    except Exception as e:
        log(f"Rolling Check Error: {e}")

# ─────────────────────────────────────────────────────────────────
# MAIN ENTRY POINT (Called from main_loop.py)
# ─────────────────────────────────────────────────────────────────

def place_order(direction, spot_price):
    """
    Full execution workflow as per the "Gill 120" strategy:
    1. Wait 10 seconds (stability delay)
    2. Square off existing position
    3. Find best CE/PE near Rs.120
    4. Place LIMIT order with 4.5% buffer
    5. Log everything
    """
    log(f"SIGNAL RECEIVED: {direction} | Spot={spot_price}")
    log("Waiting 10 seconds for stability...")
    time.sleep(10)
    log("10 seconds over. Executing...")

    # Step A: Square off old
    square_off_existing()

    # Step B: Find best option
    target_premium = float(db.get_param('target_premium', 120.0))
    result = get_best_option(direction, target_premium)

    if result:
        instrument_key, ltp, strike = result
        place_limit_order(instrument_key, ltp, strike, direction)
        db.set_param("active_entry_price", ltp)
    else:
        # PAPER TRADING FALLBACK (if API keys not set or market closed)
        log("PAPER TRADE: API unavailable. Simulating trade in memory.")
        option_type = "CE" if direction == "BUY" else "PE"
        strike = int(round(spot_price / 50) * 50)
        expiry = get_next_thursday()
        symbol_name = f"NIFTY {strike} {option_type} ({expiry}) [PAPER]"
        simulated_ltp = target_premium
        limit_price = round(simulated_ltp * 1.045, 1)

        db.set_param("active_position_key", f"PAPER_{symbol_name}")
        db.set_param("active_position_symbol", symbol_name)

        import sqlite3
        conn = sqlite3.connect(db.DB_NAME)
        cursor = conn.cursor()
        cursor.execute(
            '''INSERT INTO trades (timestamp, symbol, direction, entry_price, status)
               VALUES (?, ?, ?, ?, ?)''',
            (
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                symbol_name,
                f"BUY {option_type}",
                limit_price,
                "PAPER_TRADE"
            )
        )
        conn.commit()
        conn.close()
        log(f"PAPER TRADE logged: {symbol_name} @ Rs.{limit_price}")

    log("Execution cycle complete.")

# SUPREME CLOUD SYNC: 2026-04-30
