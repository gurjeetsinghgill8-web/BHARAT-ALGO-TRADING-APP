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

def fetch_delta_candles(symbol, resolution, limit=100):
    """Fetches OHLC data directly from Delta Exchange."""
    symbol_variants = [f"{symbol}USDT", f"{symbol}USD", f"MARK:{symbol}USDT", f"MARK:{symbol}USD"]
    res_variants = [resolution, resolution.replace('m', ''), str(int(resolution.replace('m', ''))*60) if 'm' in resolution else resolution]
    base_urls = ["https://api.india.delta.exchange", "https://api.delta.exchange"]
    
    end_ts = int(time.time())
    # Approximation for start time
    res_int = 300 if '5m' in resolution else (900 if '15m' in resolution else 3600)
    start_ts = end_ts - (int(limit) * res_int)

    for base in base_urls:
        for sym in symbol_variants:
            for res in res_variants:
                try:
                    url = f"{base}/v2/history/candles"
                    params = {"symbol": sym, "resolution": res, "start": start_ts, "end": end_ts}
                    resp = requests.get(url, params=params, timeout=5)
                    if resp.status_code == 200:
                        data = resp.json().get('result', [])
                        if data:
                            df = pd.DataFrame(data)
                            rename_map = {'o': 'open', 'h': 'high', 'l': 'low', 'c': 'close', 'v': 'volume', 't': 'time'}
                            df = df.rename(columns=rename_map)
                            for col in ['open', 'high', 'low', 'close']:
                                if col in df.columns: df[col] = pd.to_numeric(df[col])
                            if 'time' in df.columns: df = df.sort_values('time', ascending=True)
                            return df.reset_index(drop=True), ""
                except: continue
    return pd.DataFrame(), "Failed to fetch candles"

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
    base_urls = ["https://api.india.delta.exchange", "https://api.delta.exchange"]
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

    chain = []
    for base in base_urls:
        url = f"{base}/v2/tickers?underlying_asset_symbols={asset}"
        try:
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                res = resp.json().get('result', [])
                for ticker in res:
                    pid = ticker.get('product_id')
                    if pid in products:
                        ticker.update(products[pid])
                        ticker['expiry_date'] = products[pid]['expiry']
                        ticker['strike_price'] = products[pid]['strike']
                        ticker['contract_type'] = products[pid]['type']
                        chain.append(ticker)
                if chain: return chain
        except: continue
    return []

def find_itm_strike(spot_price, options_list, direction, deep_level=0):
    """
    Finds ITM strike. 
    deep_level=0: ATM/Slightly ITM
    deep_level=5: 5-6 strikes Deep ITM
    """
    if not options_list: return None
    
    itm_options = []
    if direction == "BUY": # Call (ITM is Strike < Spot)
        itm_options = [o for o in options_list if float(o.get('strike_price', 0)) <= spot_price]
        itm_options.sort(key=lambda x: float(x.get('strike_price', 0)), reverse=True) # Nearest spot first
    else: # Put (ITM is Strike > Spot)
        itm_options = [o for o in options_list if float(o.get('strike_price', 0)) >= spot_price]
        itm_options.sort(key=lambda x: float(x.get('strike_price', 0)), reverse=False) # Nearest spot first
        
    if not itm_options:
        options_list.sort(key=lambda x: abs(float(x.get('strike_price', 0)) - spot_price))
        return options_list[0]
        
    idx = min(deep_level, len(itm_options) - 1)
    return itm_options[idx]

def find_gill_crypto_option(asset, direction):
    chain = fetch_delta_option_chain(asset)
    if not chain: return None
    
    target_type = 'call_options' if direction == "BUY" else 'put_options'
    all_typed = [o for o in chain if o.get('contract_type') == target_type and float(o.get('mark_price', 0)) > 0]
    
    if not all_typed: return None

    # Expiry Rule (3 days threshold for Buying)
    today = datetime.datetime.utcnow().date()
    min_expiry_dt = today + datetime.timedelta(days=3)
    min_expiry_str = min_expiry_dt.strftime('%Y-%m-%d')
    
    valid_expiries = sorted(list(set([o['expiry_date'] for o in all_typed if o['expiry_date'] >= min_expiry_str])))
    if not valid_expiries:
        valid_expiries = sorted(list(set([o['expiry_date'] for o in all_typed if o['expiry_date'] > today.strftime('%Y-%m-%d')])))
    
    if not valid_expiries: return None
    best_expiry = valid_expiries[0] 
    
    near_options = [o for o in all_typed if o.get('expiry_date') == best_expiry]
    spot_price = float(near_options[0].get('spot_price') or near_options[0].get('underlying_price') or 0)
    
    deep_level = getattr(config, 'DEEP_ITM_LEVEL', 0)
    best_opt = find_itm_strike(spot_price, near_options, direction, deep_level=deep_level)
    
    if not best_opt: return None

    return (best_opt['symbol'], float(best_opt['mark_price']), float(best_opt['strike_price']), best_opt['expiry_date'], best_opt['product_id'])

def sync_delta_position():
    api_key = db.get_param('delta_api_key', '')
    if not api_key: return False
    
    path = "/v2/positions"
    query = "?underlying_asset_symbol=BTC"
    url = f"https://api.india.delta.exchange{path}{query}"
    
    try:
        headers = get_delta_auth_headers("GET", path, query_string=query)
        resp = requests.get(url, headers=headers, timeout=10)

        if resp.status_code == 200:
            positions = resp.json().get('result', [])
            call_sym, call_pid = "NONE", ""
            put_sym, put_pid = "NONE", ""
            unrealized_pnl = 0
            
            for p in positions:
                size = abs(float(p.get('size', 0)))
                if size > 0:
                    symbol = (p.get('product', {}).get('symbol') or p.get('symbol') or "").upper()
                    pid = str(p.get('product_id') or p.get('id') or "")
                    unrealized_pnl += float(p.get('unrealized_pnl', 0))
                    
                    if "-C-" in symbol or "CALL" in symbol:
                        call_sym, call_pid = symbol, pid
                    elif "-P-" in symbol or "PUT" in symbol:
                        put_sym, put_pid = symbol, pid

            db.set_param("active_call_symbol", call_sym)
            db.set_param("active_call_pid", call_pid)
            db.set_param("active_put_symbol", put_sym)
            db.set_param("active_put_pid", put_pid)
            db.set_param("unrealized_pnl", str(unrealized_pnl))
            
            active_sym = call_sym if call_sym != "NONE" else (put_sym if put_sym != "NONE" else "NONE")
            db.set_param("crypto_active_symbol", active_sym)
            return True 
    except: pass
    return False

def square_off_crypto(target_pid=None):
    mode = db.get_param('trade_mode', 'PAPER')
    pids_to_close = []
    
    if target_pid:
        pids_to_close = [str(target_pid)]
    else:
        # Fetch all open BTC/ETH positions
        for asset in ["BTC", "ETH"]:
            path = "/v2/positions"
            query = f"?underlying_asset_symbol={asset}"
            try:
                resp = requests.get(f"https://api.india.delta.exchange{path}{query}", 
                                    headers=get_delta_auth_headers("GET", path, query_string=query), timeout=10)
                if resp.status_code == 200:
                    for p in resp.json().get('result', []):
                        if abs(float(p.get('size', 0))) > 0:
                            pids_to_close.append(str(p.get('product_id')))
            except: pass

    if not pids_to_close:
        db.set_param("local_trade_active", "NO")
        return True
    
    for pid in pids_to_close:
        if mode == "LIVE":
            try:
                # Get current size and side
                query = "?underlying_asset_symbol=BTC"
                r = requests.get(f"https://api.india.delta.exchange/v2/positions{query}", 
                                 headers=get_delta_auth_headers("GET", "/v2/positions", query_string=query))
                size, side = 0, "sell"
                if r.status_code == 200:
                    for p in r.json().get('result', []):
                        if str(p.get('product_id')) == pid:
                            raw_size = float(p.get('size', 0))
                            size = abs(raw_size)
                            side = "buy" if raw_size < 0 else "sell"
                            break
                
                if size > 0:
                    payload = json.dumps({"product_id": int(pid), "size": int(size), "side": side, "order_type": "market_order", "reduce_only": True})
                    requests.post("https://api.india.delta.exchange/v2/orders", 
                                  headers=get_delta_auth_headers("POST", "/v2/orders", payload=payload), data=payload, timeout=10)
            except: pass
    
    db.set_param("local_trade_active", "NO")
    db.set_param("crypto_active_symbol", "NONE")
    return True

def execute_crypto_trade(asset, direction):
    mode = db.get_param('trade_mode', 'PAPER')
    if not sync_delta_position(): return
    
    # 1. Clean Slate: If signal is opposite or something else is open, close it
    has_call = db.get_param("active_call_symbol", "NONE") != "NONE"
    has_put = db.get_param("active_put_symbol", "NONE") != "NONE"
    
    if (direction == "BUY" and has_put) or (direction == "SELL" and has_call):
        log_terminal("🧹 CLEAN SLATE: Flipping position...", "TRADE")
        square_off_crypto()
        time.sleep(1)
        sync_delta_position()

    if (direction == "BUY" and has_call) or (direction == "SELL" and has_put):
        return # Already in position

    # 2. Find Option
    opt = find_gill_crypto_option(asset, direction)
    if not opt: return
    symbol, price, strike, expiry, pid = opt
    
    qty = getattr(config, 'LOT_SIZE', 1)
    
    if mode == "LIVE":
        try:
            payload = json.dumps({"product_id": int(pid), "size": int(qty), "side": "buy", "order_type": "market_order"})
            resp = requests.post("https://api.india.delta.exchange/v2/orders", 
                                 headers=get_delta_auth_headers("POST", "/v2/orders", payload=payload), data=payload, timeout=10)
            if resp.status_code in [200, 201]:
                log_terminal(f"🚀 LIVE ENTRY: {symbol} @ {price}", "TRADE")
                db.set_param("local_trade_active", "YES")
                send_telegram_msg(f"{config.TELEGRAM_PREFIX} 🚀 ENTRY: {symbol} @ {price} | Qty: {qty}")
        except: pass
    else:
        log_terminal(f"PAPER ENTRY: {symbol} @ {price}", "TRADE")
        db.set_param("crypto_active_symbol", symbol)
        db.set_param("local_trade_active", "YES")
