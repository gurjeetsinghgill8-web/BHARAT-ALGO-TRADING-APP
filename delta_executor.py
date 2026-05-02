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

def fetch_delta_option_chain(asset="BTC", expiry_date=None):
    if not expiry_date: expiry_date = get_next_friday_expiry()
    url = "https://api.india.delta.exchange/v2/tickers"
    params = {'contract_types': 'call_options,put_options', 'underlying_asset_symbols': asset, 'expiry_date': expiry_date}
    try:
        resp = requests.get(url, params=params, timeout=10)
        if resp.status_code == 200:
            return resp.json().get('result', [])
    except: pass
    return []

def find_gill_crypto_option(asset, direction):
    chain = fetch_delta_option_chain(asset)
    if not chain: return None
    
    # Simple logic: closest to spot
    spot_price = float(chain[0].get('underlying_price', 0))
    target_type = 'call_options' if direction == "BUY" else 'put_options'
    
    options = [o for o in chain if o.get('contract_type') == target_type]
    if not options: return None
    
    best_opt = min(options, key=lambda x: abs(float(x.get('strike_price', 0)) - spot_price))
    return (best_opt['symbol'], float(best_opt['mark_price']), float(best_opt['strike_price']), best_opt['expiry_date'], best_opt['id'])

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
    mode = db.get_param('trade_mode', 'PAPER')
    log_crypto(f"EXECUTE ({mode}): {direction} {asset}")
    square_off_crypto()
    
    opt = find_gill_crypto_option(asset, direction)
    if not opt: return
    symbol, price, strike, expiry, pid = opt
    
    qty = db.get_param('crypto_trade_size', '1')
    
    if mode == "LIVE":
        try:
            url = "https://api.india.delta.exchange/v2/orders"
            # Use configurable size
            payload = '{"product_id":' + str(pid) + ',"size":' + str(qty) + ',"side":"buy","order_type":"limit_order","limit_price":"' + str(price*1.02) + '"}'
            headers = get_delta_auth_headers("POST", "/v2/orders", payload)
            requests.post(url, headers=headers, data=payload, timeout=10)
        except: pass
    
    db.set_param("crypto_active_symbol", symbol)
    db.set_param("crypto_active_product_id", str(pid))
    db.set_param("crypto_active_entry_price", str(price))
    log_crypto(f"Order Placed: {symbol} @ {price} (Qty: {qty})")
