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

def fetch_delta_candles(symbol, resolution, limit=100):
    base = "https://api.india.delta.exchange"
    end_ts = int(time.time())
    start_ts = end_ts - (int(limit) * 300) # 5m default
    
    url = f"{base}/v2/history/candles"
    params = {"symbol": f"{symbol}USDT", "resolution": resolution, "start": start_ts, "end": end_ts}
    try:
        resp = requests.get(url, params=params, timeout=10)
        if resp.status_code == 200:
            df = pd.DataFrame(resp.json().get('result', []))
            df = df.rename(columns={'o': 'open', 'h': 'high', 'l': 'low', 'c': 'close', 'v': 'volume', 't': 'time'})
            df = df.sort_values('time', ascending=True)
            return df.reset_index(drop=True), ""
    except Exception as e: return pd.DataFrame(), str(e)
    return pd.DataFrame(), "Fetch failed"

def fetch_delta_option_chain(asset="BTC"):
    base = "https://api.india.delta.exchange"
    products = {}
    try:
        url = f"{base}/v2/products?underlying_asset_symbols={asset}&contract_types=call_options,put_options"
        resp = requests.get(url, timeout=10)
        for p in resp.json().get('result', []):
            products[p['id']] = {'expiry': p.get('settlement_time','').split('T')[0], 'strike': float(p.get('strike_price',0)), 'symbol': p['symbol'], 'type': p['contract_type']}
        
        tickers_url = f"{base}/v2/tickers?underlying_asset_symbols={asset}"
        t_resp = requests.get(tickers_url, timeout=10)
        chain = []
        for t in t_resp.json().get('result', []):
            pid = t.get('product_id')
            if pid in products:
                t.update(products[pid])
                chain.append(t)
        return chain
    except: return []

def find_gill_option(asset, direction):
    chain = fetch_delta_option_chain(asset)
    if not chain: return None
    
    target_type = 'call_options' if direction == "BUY" else 'put_options'
    today = datetime.datetime.utcnow().date().strftime('%Y-%m-%d')
    valid = [o for o in chain if o['type'] == target_type and o['expiry'] > today and float(o.get('mark_price',0)) > 0]
    if not valid: return None
    
    valid.sort(key=lambda x: x['expiry'])
    best_expiry = valid[0]['expiry']
    near = [o for o in valid if o['expiry'] == best_expiry]
    
    spot = float(near[0].get('spot_price') or near[0].get('underlying_price') or 0)
    near.sort(key=lambda x: abs(x['strike'] - spot))
    best = near[0]
    return best['symbol'], best['product_id'], best['mark_price']

def sync_delta_position():
    path = "/v2/positions"
    query = "?underlying_asset_symbol=BTC"
    url = f"https://api.india.delta.exchange{path}{query}"
    try:
        resp = requests.get(url, headers=get_delta_auth_headers("GET", path, query_string=query), timeout=10)
        if resp.status_code == 200:
            call_sym, put_sym = "NONE", "NONE"
            for p in resp.json().get('result', []):
                if abs(float(p.get('size', 0))) > 0:
                    sym = p.get('product', {}).get('symbol', '').upper()
                    if "-C-" in sym or "CALL" in sym: call_sym = sym
                    elif "-P-" in sym or "PUT" in sym: put_sym = sym
            db.set_param("active_call_symbol", call_sym)
            db.set_param("active_put_symbol", put_sym)
            return True
    except: pass
    return False

def square_off_crypto(target_pid=None):
    path = "/v2/positions"
    query = "?underlying_asset_symbol=BTC"
    try:
        resp = requests.get(f"https://api.india.delta.exchange{path}{query}", 
                            headers=get_delta_auth_headers("GET", path, query_string=query), timeout=10)
        if resp.status_code == 200:
            for p in resp.json().get('result', []):
                pid = p.get('product_id')
                if target_pid and int(pid) != int(target_pid): continue
                size = abs(float(p.get('size', 0)))
                if size > 0:
                    side = "buy" if float(p.get('size', 0)) < 0 else "sell"
                    payload = json.dumps({"product_id": int(pid), "size": int(size), "side": side, "order_type": "market_order", "reduce_only": True})
                    requests.post("https://api.india.delta.exchange/v2/orders", headers=get_delta_auth_headers("POST", "/v2/orders", payload=payload), data=payload, timeout=10)
            db.set_param("local_trade_active", "NO")
            return True
    except: pass
    return False

def execute_crypto_trade(asset, direction):
    best = find_gill_option(asset, direction)
    if not best: return
    
    symbol, pid, price = best
    qty = config.CRYPTO_LOT_SIZE
    
    payload = json.dumps({"product_id": int(pid), "size": int(qty), "side": "buy", "order_type": "market_order"})
    try:
        resp = requests.post("https://api.india.delta.exchange/v2/orders", headers=get_delta_auth_headers("POST", "/v2/orders", payload=payload), data=payload, timeout=10)
        if resp.status_code in [200, 201]:
            log_terminal(f"✅ {direction} SUCCESS: {symbol} | Qty: {qty}", "TRADE")
            send_telegram_msg(f"✅ ENTRY: {symbol}\nSide: {direction}\nLots: {qty}")
            db.set_param("local_trade_active", "YES")
    except Exception as e: log_terminal(f"⚠️ ENTRY ERROR: {e}", "ERROR")

def reconcile_bracket_orders():
    pass
