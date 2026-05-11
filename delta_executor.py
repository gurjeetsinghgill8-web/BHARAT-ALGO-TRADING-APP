import requests
import hmac
import hashlib
import time
import datetime
import json
import db
from utils import log_terminal, send_telegram_msg

# --- CONFIG ---
def get_delta_auth_headers(method, path, query_string="", payload=""):
    api_key = db.get_param('delta_api_key')
    api_secret = db.get_param('delta_api_secret')
    if not api_key or not api_secret: return {}
    timestamp = str(int(time.time()))
    signature_data = method + timestamp + path + query_string + payload
    signature = hmac.new(api_secret.encode('utf-8'), signature_data.encode('utf-8'), hashlib.sha256).hexdigest()
    return {
        "api-key": api_key,
        "timestamp": timestamp,
        "signature": signature,
        "Content-Type": "application/json"
    }

def fetch_delta_candles(symbol, timeframe="1m", limit=100):
    try:
        url = f"https://api.india.delta.exchange/v2/history/candles?symbol={symbol}&resolution={timeframe}&limit={limit}"
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            import pandas as pd
            data = r.json().get('result', [])
            df = pd.DataFrame(data)
            if not df.empty:
                df['time'] = pd.to_datetime(df['time'], unit='s')
                df = df.sort_values('time')
                return df, True
    except: pass
    return None, False

def fetch_delta_option_chain(asset):
    try:
        url = f"https://api.india.delta.exchange/v2/products?underlying_asset_symbol={asset}&type=interest_bearing_option"
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            return r.json().get('result', [])
    except: pass
    return []

def find_atm_strike(spot_price, options_list, direction, strike_selection="ATM"):
    options_list = sorted(options_list, key=lambda x: float(x.get('strike_price', 0)))
    if not options_list: return None
    
    # Find ATM index
    atm_idx = 0
    min_diff = float('inf')
    for i, opt in enumerate(options_list):
        diff = abs(float(opt['strike_price']) - spot_price)
        if diff < min_diff:
            min_diff = diff
            atm_idx = i
            
    # Offset logic
    offset = 0
    if "ITM 4" in strike_selection: offset = -4 if direction == "BUY" else 4
    elif "ITM 3" in strike_selection: offset = -3 if direction == "BUY" else 3
    elif "ITM 2" in strike_selection: offset = -2 if direction == "BUY" else 2
    elif "ITM 1" in strike_selection: offset = -1 if direction == "BUY" else 1
    elif "OTM 1" in strike_selection: offset = 1 if direction == "BUY" else -1
    elif "OTM 2" in strike_selection: offset = 2 if direction == "BUY" else -2
    elif "OTM 3" in strike_selection: offset = 3 if direction == "BUY" else -3
    elif "OTM 4" in strike_selection: offset = 4 if direction == "BUY" else -4
    elif "OTM 5" in strike_selection: offset = 5 if direction == "BUY" else -5
    
    target_idx = max(0, min(len(options_list) - 1, atm_idx + offset))
    return options_list[target_idx]

def find_gill_crypto_option(asset, direction):
    chain = fetch_delta_option_chain(asset)
    if not chain: return None
    
    target_type = 'put_options' if direction == "BUY" else 'call_options'
    all_typed_options = [o for o in chain if o.get('contract_type') == target_type and float(o.get('mark_price', 0)) > 0]
    if not all_typed_options: return None

    today = datetime.date.today().strftime('%Y-%m-%d')
    expiry_sel = db.get_param('expiry_selection', 'Next Day')
    valid_expiries = sorted(list(set([o['expiry_date'] for o in all_typed_options if o['expiry_date'] > today])))
    if not valid_expiries: return None
    
    best_expiry = valid_expiries[1] if (expiry_sel == "Next Day" and len(valid_expiries) > 1) else valid_expiries[0]
    near_options = [o for o in all_typed_options if o.get('expiry_date') == best_expiry]
    
    spot_price = 0
    for o in near_options:
        spot_price = float(o.get('spot_price') or o.get('underlying_price') or 0)
        if spot_price > 0: break
    if spot_price == 0: return None
    
    strike_selection = db.get_param('strike_selection', 'ATM')
    best_opt = find_atm_strike(spot_price, near_options, direction, strike_selection=strike_selection)
    if not best_opt: return None

    return (best_opt['symbol'], float(best_opt['mark_price']), float(best_opt['strike_price']), best_opt['expiry_date'], best_opt['product_id'])

def sync_delta_position():
    try:
        path = "/v2/positions"
        query = "?underlying_asset_symbol=BTC"
        url = f"https://api.india.delta.exchange{path}{query}"
        headers = get_delta_auth_headers("GET", path, query_string=query)
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            positions = resp.json().get('result', [])
            if not positions:
                db.set_param("active_call_symbol", "NONE")
                db.set_param("active_put_symbol", "NONE")
                db.set_param("crypto_active_symbol", "NONE")
                return True
            for p in positions:
                sym = p.get('product', {}).get('symbol', 'NONE')
                pid = str(p.get('product_id', ''))
                if "-P-" in sym:
                    db.set_param("active_put_symbol", sym)
                    db.set_param("active_put_pid", pid)
                else:
                    db.set_param("active_call_symbol", sym)
                    db.set_param("active_call_pid", pid)
                db.set_param("crypto_active_symbol", sym)
            return True
    except: pass
    return False

def square_off_crypto(target_pid=None):
    sync_delta_position()
    pids = [target_pid] if target_pid else [db.get_param("active_call_pid"), db.get_param("active_put_pid")]
    for pid in pids:
        if not pid or pid == "NONE": continue
        try:
            # Re-fetch size and side
            path = "/v2/positions"
            url = f"https://api.india.delta.exchange{path}?underlying_asset_symbol=BTC"
            r = requests.get(url, headers=get_delta_auth_headers("GET", path, query_string="?underlying_asset_symbol=BTC"), timeout=10)
            if r.status_code == 200:
                for p in r.json().get('result', []):
                    if str(p.get('product_id')) == str(pid):
                        size = float(p.get('size', 0))
                        if size == 0: continue
                        side = "buy" if size < 0 else "sell"
                        payload = json.dumps({"product_id": int(pid), "size": int(abs(size)), "side": side, "order_type": "market_order", "reduce_only": True})
                        requests.post("https://api.india.delta.exchange/v2/orders", headers=get_delta_auth_headers("POST", "/v2/orders", payload=payload), data=payload, timeout=10)
                        send_telegram_msg(f"✅ Closed Position: {pid}")
        except: pass
    db.set_param("active_call_symbol", "NONE")
    db.set_param("active_put_symbol", "NONE")
    db.set_param("crypto_active_symbol", "NONE")

def execute_crypto_trade(asset, direction):
    mode = db.get_param('trade_mode', 'PAPER')
    if mode != "LIVE":
        log_terminal(f"PAPER ENTRY: {direction} {asset}", "TRADE")
        return
    
    opt = find_gill_crypto_option(asset, direction)
    if not opt: return
    
    symbol, price, strike, expiry, pid = opt
    qty = int(db.get_param('crypto_trade_size', '1'))
    
    payload = json.dumps({"product_id": int(pid), "size": qty, "side": "sell", "order_type": "market_order"})
    resp = requests.post("https://api.india.delta.exchange/v2/orders", headers=get_delta_auth_headers("POST", "/v2/orders", payload=payload), data=payload, timeout=10)
    
    if resp.status_code in [200, 201]:
        log_terminal(f"✅ LIVE SELL SUCCESS: {symbol}", "TRADE")
        sync_delta_position()
    else:
        log_terminal(f"❌ ENTRY FAILED: {resp.text}", "ERROR")

def reconcile_bracket_orders(): pass # Placeholder
