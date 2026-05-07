import time
import hmac
import hashlib
import requests
import datetime
import socket
import db
import pandas as pd
import json
import config
from utils import log_terminal, send_telegram_msg

# --- FORCE IPv4 GLOBALLY ---
import requests.packages.urllib3.util.connection as urllib3_cn
def allowed_gai_family():
    return socket.AF_INET
urllib3_cn.allowed_gai_family = allowed_gai_family

def log_crypto(msg):
    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] [CRYPTO] {msg}")

def get_delta_auth_headers(method, path, payload="", query_string=""):
    api_key = db.get_param('delta_api_key', '')
    api_secret = db.get_param('delta_api_secret', '')
    timestamp = str(int(time.time()))
    signature_data = method + timestamp + path + query_string + payload
    signature = hmac.new(api_secret.encode('utf-8'), signature_data.encode('utf-8'), hashlib.sha256).hexdigest()
    return {
        'api-key': api_key,
        'signature': signature,
        'timestamp': timestamp,
        'Content-Type': 'application/json'
    }

def fetch_delta_option_chain(asset="BTC"):
    base_url = "https://api.india.delta.exchange"
    products = {}
    try:
        url = f"{base_url}/v2/products?underlying_asset_symbols={asset}&contract_types=call_options,put_options"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            for p in resp.json().get('result', []):
                products[p['id']] = {
                    'expiry': p.get('settlement_time', '').split('T')[0],
                    'strike': float(p.get('strike_price', 0)),
                    'symbol': p.get('symbol', ''),
                    'type': p.get('contract_type', '')
                }
    except: pass

    chain = []
    try:
        url = f"{base_url}/v2/tickers?underlying_asset_symbols={asset}"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            for ticker in resp.json().get('result', []):
                pid = ticker.get('product_id')
                if pid in products:
                    ticker.update(products[pid])
                    chain.append(ticker)
    except: pass
    return chain

def find_best_option(asset, direction):
    """Finds ATM/Slight OTM option for Buying."""
    chain = fetch_delta_option_chain(asset)
    if not chain: return None
    
    target_type = 'call_options' if direction == "BUY" else 'put_options'
    today = datetime.datetime.utcnow().date().strftime('%Y-%m-%d')
    
    # Filter for future expiries and liquid options
    valid = [o for o in chain if o['type'] == target_type and o['expiry'] > today and float(o.get('mark_price', 0)) > 0]
    if not valid: return None
    
    # Sort by expiry
    valid.sort(key=lambda x: x['expiry'])
    best_expiry = valid[0]['expiry']
    near_expiry_options = [o for o in valid if o['expiry'] == best_expiry]
    
    # Get spot
    spot = float(near_expiry_options[0].get('spot_price') or near_expiry_options[0].get('underlying_price') or 0)
    if spot == 0: return None
    
    # Find closest to spot (ATM)
    near_expiry_options.sort(key=lambda x: abs(x['strike'] - spot))
    best = near_expiry_options[0]
    
    return best['symbol'], best['product_id'], best['mark_price']

def sync_delta_position():
    """Checks for active positions on Delta Exchange."""
    path = "/v2/positions"
    query = "?underlying_asset_symbol=BTC"
    url = f"https://api.india.delta.exchange{path}{query}"
    
    try:
        headers = get_delta_auth_headers("GET", path, query_string=query)
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            positions = resp.json().get('result', [])
            call_sym = "NONE"
            put_sym = "NONE"
            
            for p in positions:
                size = abs(float(p.get('size', 0)))
                if size > 0:
                    sym = p.get('product', {}).get('symbol', '').upper()
                    if "-C-" in sym or "CALL" in sym: call_sym = sym
                    elif "-P-" in sym or "PUT" in sym: put_sym = sym
            
            db.set_param("active_call_symbol", call_sym)
            db.set_param("active_put_symbol", put_sym)
            return True
    except: pass
    return False

def square_off_crypto(target_pid=None):
    """Closes all or specific BTC positions."""
    path = "/v2/positions"
    query = "?underlying_asset_symbol=BTC"
    url = f"https://api.india.delta.exchange{path}{query}"
    
    try:
        headers = get_delta_auth_headers("GET", path, query_string=query)
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            for p in resp.json().get('result', []):
                pid = p.get('product_id')
                if target_pid and int(pid) != int(target_pid): continue
                
                size = abs(float(p.get('size', 0)))
                if size > 0:
                    raw_size = float(p.get('size', 0))
                    side = "buy" if raw_size < 0 else "sell"
                    
                    payload = json.dumps({
                        "product_id": int(pid),
                        "size": int(size),
                        "side": side,
                        "order_type": "market_order",
                        "reduce_only": True
                    })
                    requests.post("https://api.india.delta.exchange/v2/orders", 
                                  headers=get_delta_auth_headers("POST", "/v2/orders", payload=payload),
                                  data=payload, timeout=10)
            db.set_param("local_trade_active", "NO")
            return True
    except: pass
    return False

def execute_crypto_trade(asset, direction):
    """Executes a 6-lot market buy for the selected option."""
    log_crypto(f"Executing {direction} trade for {asset}...")
    
    best_opt = find_best_option(asset, direction)
    if not best_opt:
        log_terminal("❌ Could not find suitable option!", "ERROR")
        return
    
    symbol, pid, price = best_opt
    qty = config.CRYPTO_LOT_SIZE # STRICT 6 LOTS
    
    payload = json.dumps({
        "product_id": int(pid),
        "size": int(qty),
        "side": "buy",
        "order_type": "market_order"
    })
    
    try:
        resp = requests.post("https://api.india.delta.exchange/v2/orders",
                             headers=get_delta_auth_headers("POST", "/v2/orders", payload=payload),
                             data=payload, timeout=10)
        if resp.status_code in [200, 201]:
            log_terminal(f"✅ {direction} ENTRY SUCCESS: {symbol} | Qty: {qty}", "TRADE")
            send_telegram_msg(f"✅ ENTRY: {symbol}\nSide: {direction}\nLots: {qty}")
            db.set_param("local_trade_active", "YES")
        else:
            log_terminal(f"❌ ENTRY FAILED: {resp.text}", "ERROR")
    except Exception as e:
        log_terminal(f"⚠️ ENTRY EXCEPTION: {e}", "ERROR")

def reconcile_bracket_orders():
    pass # Brackets not strictly required for this simple version if main loop handles SL/TP
