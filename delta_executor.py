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

def find_gill_crypto_option(asset, direction):
    log_crypto(f"Finding best {direction} option for {asset}...")
    chain = fetch_delta_option_chain(asset)
    if not chain:
        log_crypto("Chain is empty!")
        return None
    
    target_type = 'call_options' if direction == "BUY" else 'put_options'
    
    # Filter for target type and valid mark prices
    options = [o for o in chain if o.get('contract_type') == target_type and float(o.get('mark_price', 0)) > 0]
    if not options:
        log_crypto(f"No liquid {target_type} found.")
        return None
    
    # Sort by expiry date (ascending) to get the nearest one
    options.sort(key=lambda x: x.get('expiry_date', '9999-12-31'))
    nearest_expiry = options[0].get('expiry_date')
    
    # Filter for only the nearest expiry
    near_options = [o for o in options if o.get('expiry_date') == nearest_expiry]
    log_crypto(f"Found {len(near_options)} options for nearest expiry: {nearest_expiry}")
    
    # Get Spot Price (try spot_price first, then underlying_price, then spot_index price if available)
    spot_price = 0
    for o in near_options:
        spot_price = float(o.get('spot_price') or o.get('underlying_price') or 0)
        if spot_price > 0: break
    
    if spot_price == 0:
        log_crypto("Could not determine spot price.")
        return None
    
    log_crypto(f"Current Spot: {spot_price}")
    
    # Find strike closest to spot
    best_opt = min(near_options, key=lambda x: abs(float(x.get('strike_price', 0)) - spot_price))
    
    available_strikes = sorted([float(o.get('strike_price', 0)) for o in near_options])
    log_crypto(f"Available strikes: {available_strikes}")
    log_crypto(f"SELECTED: {best_opt['symbol']} (Strike: {best_opt['strike_price']}, Mark: {best_opt['mark_price']})")
    
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
            for p in positions:
                if float(p.get('size', 0)) != 0:
                    db.set_param("crypto_active_symbol", p.get('product', {}).get('symbol', ''))
                    db.set_param("crypto_active_product_id", str(p.get('product_id')))
                    return
            db.set_param("crypto_active_symbol", "")
            db.set_param("crypto_active_product_id", "")
    except: pass

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

def execute_crypto_trade(asset, direction):
    from main import log_terminal
    mode = db.get_param('trade_mode', 'PAPER')
    log_crypto(f"EXECUTE ({mode}): {direction} {asset}")
    square_off_crypto()
    
    opt = find_gill_crypto_option(asset, direction)
    if not opt:
        log_terminal(f"TRADE FAILED: No active option chain found for {asset}. Market might be illiquid or API blocked.", "ERROR")
        return
        
    symbol, price, strike, expiry, pid = opt
    qty = db.get_param('crypto_trade_size', '1')
    
    if mode == "LIVE":
        try:
            url = "https://api.india.delta.exchange/v2/orders"
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
