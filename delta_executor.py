import time
import hmac
import hashlib
import requests
import datetime
import db

def log_crypto(msg):
    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] [CRYPTO] {msg}")

def get_delta_auth_headers(method, endpoint, payload=""):
    api_key = db.get_param('delta_api_key', '')
    api_secret = db.get_param('delta_api_secret', '')
    timestamp = str(int(time.time()))
    signature_data = method + timestamp + endpoint + payload
    signature = hmac.new(api_secret.encode('utf-8'), signature_data.encode('utf-8'), hashlib.sha256).hexdigest()
    return {
        'api-key': api_key,
        'signature': signature,
        'timestamp': timestamp,
        'Content-Type': 'application/json'
    }

def get_next_friday_expiry():
    today = datetime.date.today()
    days_until_friday = (4 - today.weekday()) % 7
    if days_until_friday == 0: days_until_friday = 7
    next_friday = today + datetime.timedelta(days=days_until_friday)
    return next_friday.strftime('%Y-%m-%d')

def fetch_delta_option_chain(asset="BTC"):
    base_urls = ["https://api.india.delta.exchange", "https://api.delta.exchange"]
    
    # 1. Fetch Product Definitions (for Expiry and Strike info)
    products = {}
    for base in base_urls:
        try:
            url = f"{base}/v2/products?underlying_asset_symbols={asset}&contract_types=call_options,put_options"
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                for p in resp.json().get('result', []):
                    products[p['id']] = {
                        'expiry': p.get('settlement_time', '').split('T')[0],
                        'strike': float(p.get('strike_price', 0)),
                        'symbol': p.get('symbol', ''),
                        'type': p.get('contract_type', '')
                    }
                if products: break
        except: continue

    # 2. Fetch Tickers (for live Mark Price)
    chain = []
    for base in base_urls:
        url = f"{base}/v2/tickers?underlying_asset_symbols={asset}"
        try:
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                res = resp.json().get('result', [])
                if res:
                    # Enrich tickers with product info
                    for ticker in res:
                        pid = ticker.get('product_id')
                        if pid in products:
                            ticker['expiry_date'] = products[pid]['expiry']
                            ticker['strike_price'] = products[pid]['strike']
                            ticker['contract_type'] = products[pid]['type']
                            chain.append(ticker)
                    if chain: return chain
        except: continue
            
    return []

def filter_options_by_expiry(options, days_threshold=3):
    """
    Lego Block 2: The 3-Day Expiry Rule
    Filters out options that expire too soon to avoid heavy theta decay.
    """
    today = datetime.date.today()
    min_expiry = today + datetime.timedelta(days=days_threshold)
    
    valid_options = []
    for opt in options:
        try:
            expiry_dt = datetime.datetime.strptime(opt['expiry_date'], '%Y-%m-%d').date()
            if expiry_dt >= min_expiry:
                valid_options.append(opt)
        except:
            continue
    return valid_options

def find_atm_strike(spot_price, options_list):
    """
    Lego Block 3: ATM Strike Selection (Strike Picker)
    Finds the strike price in options_list with the minimum difference from the current spot_price.
    Returns the full option dictionary.
    """
    if not options_list: return None
    return min(options_list, key=lambda x: abs(float(x.get('strike_price', 0)) - spot_price))

def find_gill_crypto_option(asset, direction):
    from main import send_telegram_msg
    log_crypto(f"Finding best {direction} option for {asset} (3-Day ATM Rule)...")
    chain = fetch_delta_option_chain(asset)
    if not chain:
        log_crypto("Chain is empty!")
        return None
    
    target_type = 'call_options' if direction == "BUY" else 'put_options'
    
    # Filter for target type and liquidity
    options = [o for o in chain if o.get('contract_type') == target_type and float(o.get('mark_price', 0)) > 0]
    
    # Lego Block 2: 3-Day Expiry Rule
    valid_options = filter_options_by_expiry(options, days_threshold=3)
                
    if not valid_options:
        log_crypto(f"No liquid {target_type} found with >= 3 days expiry. Checking nearest available...")
        valid_options = options # Fallback to nearest if no 3-day option exists
        if not valid_options: return None

    # Get the nearest expiry date from the valid options
    valid_options.sort(key=lambda x: x.get('expiry_date', '9999-12-31'))
    best_expiry = valid_options[0].get('expiry_date')
    
    # Filter for options with that expiry
    near_options = [o for o in valid_options if o.get('expiry_date') == best_expiry]
    
    # Get Spot Price
    spot_price = 0
    for o in near_options:
        spot_price = float(o.get('spot_price') or o.get('underlying_price') or 0)
        if spot_price > 0: break
    
    if spot_price == 0:
        log_crypto("Could not determine spot price.")
        return None
    
    # Lego Block 3: ATM Selection (Min difference from Spot)
    best_opt = find_atm_strike(spot_price, near_options)
    
    if not best_opt: return None

    return (
        best_opt['symbol'], 
        float(best_opt['mark_price']), 
        float(best_opt['strike_price']), 
        best_opt['expiry_date'], 
        best_opt['product_id']
    )

def sync_delta_position():
    mode = db.get_param('trade_mode', 'PAPER')
    if mode != "LIVE": return
    try:
        url = "https://api.india.delta.exchange/v2/positions"
        headers = get_delta_auth_headers("GET", "/v2/positions")
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            positions = resp.json().get('result', [])
            found = False
            for p in positions:
                if float(p.get('size', 0)) != 0:
                    db.set_param("crypto_active_symbol", p.get('product', {}).get('symbol', ''))
                    db.set_param("crypto_active_product_id", str(p.get('product_id')))
                    found = True
                    break
            if not found:
                db.set_param("crypto_active_symbol", "")
                db.set_param("crypto_active_product_id", "")
    except Exception as e:
        print(f"[SYNC ERROR] {e}")

def square_off_crypto():
    sync_delta_position()
    symbol = db.get_param("crypto_active_symbol", "")
    pid = db.get_param("crypto_active_product_id", "")
    mode = db.get_param('trade_mode', 'PAPER')
    if not symbol or not pid: return
    
    log_crypto(f"SQUARING OFF: {symbol}")
    if mode == "LIVE":
        try:
            url = "https://api.india.delta.exchange/v2/orders"
            payload = '{"product_id":' + str(pid) + ',"size":1,"side":"sell","order_type":"market_order","close_on_trigger":true}'
            headers = get_delta_auth_headers("POST", "/v2/orders", payload)
            requests.post(url, headers=headers, data=payload, timeout=10)
        except: pass
    db.set_param("crypto_active_symbol", "")

def get_dynamic_quantity(option_price):
    try:
        url = "https://api.india.delta.exchange/v2/wallet/balances"
        headers = get_delta_auth_headers("GET", "/v2/wallet/balances")
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            balances = resp.json().get('result', [])
            # Sum up USDT and DETO (Delta's token) as usable margin
            total_usdt = sum(float(b.get('balance', 0)) for b in balances if b.get('asset_symbol') in ['USDT', 'DETO'])
            
            if total_usdt > 0:
                # Use 20% of account balance
                trade_budget = total_usdt * 0.20
                
                # Lego Block: Minimum Deployment Rule
                # Minimum 200 Rupees is approx $2.40 USDT
                min_budget_usdt = 2.40 
                if trade_budget < min_budget_usdt and total_usdt >= min_budget_usdt:
                    trade_budget = min_budget_usdt
                    log_crypto(f"Budget adjusted to minimum: ${trade_budget:.2f} (approx ₹200)")
                
                # On Delta, BTC options contract size is usually 0.001 BTC. 
                qty = int(trade_budget / (option_price * 0.001))
                
                if qty < 1: qty = 1
                log_crypto(f"Dynamic Qty Calculated: {qty} contracts (Budget: ${trade_budget:.2f})")
                return qty
    except Exception as e:
        log_crypto(f"Qty calculation failed: {e}")
    return 1 # Fallback to 1 unit

def execute_crypto_trade(asset, direction):
    from main import log_terminal, send_telegram_msg
    mode = db.get_param('trade_mode', 'PAPER')
    
    api_key = db.get_param('delta_api_key', '')
    if not api_key:
        send_telegram_msg("❌ CRITICAL: API Key missing in DB! Check dashboard/secrets.")
        return

    log_crypto(f"EXECUTE ({mode}): {direction} {asset}")
    square_off_crypto()
    
    opt = find_gill_crypto_option(asset, direction)
    if not opt:
        # Debugging message already sent in find_gill_crypto_option
        return
        
    symbol, price, strike, expiry, pid = opt
    
    # DYNAMIC QUANTITY LOGIC
    if mode == "LIVE":
        qty = get_dynamic_quantity(price)
    else:
        qty = int(db.get_param('crypto_trade_size', '1'))
    
    if mode == "LIVE":
        try:
            url = "https://api.india.delta.exchange/v2/orders"
            # Qty must be integer for contracts
            payload = '{"product_id":' + str(pid) + ',"size":' + str(qty) + ',"side":"buy","order_type":"limit_order","limit_price":"' + str(price*1.02) + '"}'
            headers = get_delta_auth_headers("POST", "/v2/orders", payload)
            resp = requests.post(url, headers=headers, data=payload, timeout=10)
            
            if resp.status_code == 200 or resp.status_code == 201:
                log_terminal(f"LIVE ORDER SUCCESS: {symbol} @ {price} (Qty: {qty})", "TRADE")
                db.set_param("crypto_active_symbol", symbol)
                db.set_param("crypto_active_product_id", str(pid))
                db.set_param("crypto_active_entry_price", str(price))
            elif resp.status_code == 401:
                log_terminal("LIVE ORDER FAILED: IP Not Whitelisted! Add VPS IP to Delta API settings.", "ERROR")
                log_terminal(f"VPS IP: 46.224.133.16 and 2a01:4f8:c012:e9bb::1", "ALERT")
            else:
                log_terminal(f"LIVE ORDER FAILED: {resp.status_code} - {resp.text[:100]}", "ERROR")
        except Exception as e:
            log_terminal(f"API EXCEPTION: {e}", "ERROR")
    else:
        # Paper Trade
        log_terminal(f"PAPER TRADE PLACED: {symbol} @ {price} (Qty: {qty})", "TRADE")
        db.set_param("crypto_active_symbol", symbol)
        db.set_param("crypto_active_product_id", str(pid))
        db.set_param("crypto_active_entry_price", str(price))
    
    log_crypto(f"Execution Step Finished for {symbol}")

