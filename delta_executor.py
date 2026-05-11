import time
import hmac
import hashlib
import requests
import datetime
import socket
import db
import pandas as pd
import json
from utils import log_terminal, send_telegram_msg

# --- FORCE IPv4 GLOBALLY (V3 Stable Feature) ---
import requests.packages.urllib3.util.connection as urllib3_cn
def allowed_gai_family():
    return socket.AF_INET
urllib3_cn.allowed_gai_family = allowed_gai_family

# --- V3 COMPATIBILITY HELPERS ---
def fetch_btc_spot():
    """V3 Alias for current BTC price."""
    df, _ = fetch_delta_candles("BTC", "1m", limit=1)
    if not df.empty:
        return float(df['close'].iloc[-1])
    return 0

def get_current_position():
    """V3 Alias for getting active position as a dict. Fixes P- prefix bug."""
    sync_delta_position()
    call = db.get_param("active_call_symbol", "NONE")
    put = db.get_param("active_put_symbol", "NONE")
    
    # Emergency Fix: Delta symbols like P-BTC-81800... start with P-
    if put != "NONE" and put.upper().startswith("P-"):
        return {'type': 'PUT', 'symbol': put}
    if call != "NONE":
        return {'type': 'CALL', 'symbol': call}
    return None
def fetch_delta_candles(symbol, resolution="1m", limit=100):
    symbol_variants = [f"{symbol}USDT", f"{symbol}USD", f"MARK:{symbol}USDT"]
    end_ts = int(time.time())
    start_ts = end_ts - (int(limit) * 300) 
    
    for sym in symbol_variants:
        try:
            url = "https://api.india.delta.exchange/v2/history/candles"
            params = {"symbol": sym, "resolution": resolution, "start": start_ts, "end": end_ts}
            resp = requests.get(url, params=params, timeout=5)
            if resp.status_code == 200:
                df = pd.DataFrame(resp.json().get('result', []))
                if not df.empty:
                    df = df.rename(columns={'o':'open','h':'high','l':'low','c':'close','t':'time'})
                    return df.sort_values('time'), ""
        except: continue
    return pd.DataFrame(), "Fetch Failed"

def get_delta_auth_headers(method, path, payload="", query_string=""):
    api_key = db.get_param('delta_api_key', '')
    api_secret = db.get_param('delta_api_secret', '')
    timestamp = str(int(time.time()))
    signature_data = method + timestamp + path + query_string + payload
    signature = hmac.new(api_secret.encode('utf-8'), signature_data.encode('utf-8'), hashlib.sha256).hexdigest()
    return {
        'api-key': api_key, 'signature': signature, 'timestamp': timestamp,
        'Content-Type': 'application/json', 'User-Agent': 'BHARAT-ALGO-V3'
    }

def fetch_delta_option_chain(asset="BTC"):
    products = {}
    try:
        url = f"https://api.india.delta.exchange/v2/products?underlying_asset_symbols={asset}&contract_types=call_options,put_options"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            for p in resp.json().get('result', []):
                products[p['id']] = {'expiry': p.get('settlement_time', '').split('T')[0], 'strike': float(p.get('strike_price', 0)), 'symbol': p.get('symbol', ''), 'type': p.get('contract_type', '')}
    except: pass
    
    chain = []
    try:
        url = f"https://api.india.delta.exchange/v2/tickers?underlying_asset_symbols={asset}"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            for ticker in resp.json().get('result', []):
                pid = ticker.get('product_id')
                if pid in products:
                    ticker.update(products[pid])
                    chain.append(ticker)
    except: pass
    return chain

def find_atm_strike(spot_price, options_list, direction, strike_selection="ATM"):
    options_list = sorted(options_list, key=lambda x: float(x.get('strike', 0)))
    if not options_list: return None
    
    atm_idx = 0
    min_diff = float('inf')
    for i, opt in enumerate(options_list):
        diff = abs(opt['strike'] - spot_price)
        if diff < min_diff:
            min_diff = diff
            atm_idx = i
            
    # Offset logic for Option Selling
    offset = 0
    if direction == "SELL": # We are selling a CALL
        if "ITM 4" in strike_selection: offset = -4
        elif "ITM 3" in strike_selection: offset = -3
        elif "ITM 2" in strike_selection: offset = -2
        elif "ITM 1" in strike_selection: offset = -1
        elif "OTM 1" in strike_selection: offset = 1
        elif "OTM 2" in strike_selection: offset = 2
    else: # We are selling a PUT (Signal BUY)
        if "ITM 4" in strike_selection: offset = 4
        elif "ITM 3" in strike_selection: offset = 3
        elif "ITM 2" in strike_selection: offset = 2
        elif "ITM 1" in strike_selection: offset = 1
        elif "OTM 1" in strike_selection: offset = -1
        elif "OTM 2" in strike_selection: offset = -2
    
    target_idx = max(0, min(len(options_list) - 1, atm_idx + offset))
    return options_list[target_idx]

def find_gill_crypto_option(asset, direction):
    chain = fetch_delta_option_chain(asset)
    if not chain: return None
    
    # SELL signal -> Bearish -> Sell Call | BUY signal -> Bullish -> Sell Put
    target_type = 'call_options' if direction == "SELL" else 'put_options'
    all_typed = [o for o in chain if o.get('type') == target_type and float(o.get('mark_price', 0)) > 0]
    
    today = datetime.date.today().strftime('%Y-%m-%d')
    valid_expiries = sorted(list(set([o['expiry'] for o in all_typed if o['expiry'] > today])))
    if not valid_expiries: return None
    
    best_expiry = valid_expiries[0]
    near_options = [o for o in all_typed if o.get('expiry') == best_expiry]
    
    spot_price = 0
    for o in near_options:
        spot_price = float(o.get('spot_price') or 0)
        if spot_price > 0: break
    if spot_price == 0: return None
    
    strike_sel = db.get_param('strike_selection', 'ATM')
    best_opt = find_atm_strike(spot_price, near_options, direction, strike_selection=strike_sel)
    return best_opt

def sync_delta_position():
    try:
        path = "/v2/positions"
        query = "?underlying_asset_symbol=BTC"
        headers = get_delta_auth_headers("GET", path, query_string=query)
        resp = requests.get(f"https://api.india.delta.exchange{path}{query}", headers=headers, timeout=10)
        if resp.status_code == 200:
            positions = resp.json().get('result', [])
            db.set_param("active_call_symbol", "NONE")
            db.set_param("active_put_symbol", "NONE")
            db.set_param("crypto_active_symbol", "NONE")
            for p in positions:
                size = abs(float(p.get('size', 0)))
                if size > 0:
                    sym = p.get('product', {}).get('symbol') or ""
                    pid = str(p.get('product_id', ''))
                    if "-P-" in sym.upper():
                        db.set_param("active_put_symbol", sym); db.set_param("active_put_pid", pid)
                    else:
                        db.set_param("active_call_symbol", sym); db.set_param("active_call_pid", pid)
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
            path = "/v2/positions"
            headers = get_delta_auth_headers("GET", path, query_string="?underlying_asset_symbol=BTC")
            r = requests.get(f"https://api.india.delta.exchange{path}?underlying_asset_symbol=BTC", headers=headers, timeout=10)
            if r.status_code == 200:
                for p in r.json().get('result', []):
                    if str(p.get('product_id')) == str(pid):
                        size = float(p.get('size', 0))
                        if size == 0: continue
                        side = "buy" if size < 0 else "sell"
                        payload = json.dumps({"product_id": int(pid), "size": int(abs(size)), "side": side, "order_type": "market_order", "reduce_only": True})
                        requests.post("https://api.india.delta.exchange/v2/orders", headers=get_delta_auth_headers("POST", "/v2/orders", payload=payload), data=payload, timeout=10)
        except: pass
    db.set_param("active_call_symbol", "NONE"); db.set_param("active_put_symbol", "NONE"); db.set_param("crypto_active_symbol", "NONE")

def execute_crypto_trade(asset, direction=None):
    # Support for V3-style calls: execute_crypto_trade("SELL_CALL")
    if direction is None:
        direction = asset
        asset = "BTC"
    
    # Map V3 strings to V4 directions
    if direction == "SELL_CALL": direction = "SELL"
    elif direction == "SELL_PUT": direction = "BUY"

    if db.get_param('trade_mode', 'PAPER') != "LIVE":
        log_terminal(f"PAPER ENTRY: {direction}", "TRADE"); return
    
    opt = find_gill_crypto_option(asset, direction)
    if not opt:
        log_terminal(f"ERROR: No {direction} option found.", "ERROR"); return
    
    payload = json.dumps({"product_id": int(opt['product_id']), "size": int(db.get_param('crypto_trade_size', '1')), "side": "sell", "order_type": "market_order"})
    headers = get_delta_auth_headers("POST", "/v2/orders", payload=payload)
    resp = requests.post("https://api.india.delta.exchange/v2/orders", headers=headers, data=payload, timeout=10)
    
    if resp.status_code in [200, 201]:
        log_terminal(f"✅ LIVE SELL: {opt['symbol']}", "TRADE")
        sync_delta_position()
    else:
        log_terminal(f"❌ FAILED: {resp.text}", "ERROR")

def reconcile_bracket_orders(): pass
