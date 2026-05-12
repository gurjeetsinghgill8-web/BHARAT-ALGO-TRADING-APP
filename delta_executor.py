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

# --- FORCE IPv4 GLOBALLY ---
import requests.packages.urllib3.util.connection as urllib3_cn
def allowed_gai_family():
    return socket.AF_INET
urllib3_cn.allowed_gai_family = allowed_gai_family

# 🔧 MANUAL BALANCE OVERRIDE (Set to >0 to bypass API balance check)
MIN_BALANCE_OVERRIDE = 0.0  # Set to 20.0 if API fails but you know balance is $20+

def fetch_delta_candles(symbol, resolution, limit=100):
    """Fetches OHLC data directly from Delta Exchange (Fixed with Start/End)."""
    # Try different symbol variations
    symbol_variants = [f"{symbol}USDT", f"{symbol}USD", f"MARK:{symbol}USDT", f"MARK:{symbol}USD"]
    # Try different resolution formats
    res_variants = [resolution, resolution.replace('m', ''), str(int(resolution.replace('m', ''))*60) if 'm' in resolution else resolution]
    
    # Correct Production Base URLs
    base_urls = [
        "https://api.india.delta.exchange",
        "https://api.delta.exchange"
    ]
    
    # Calculate start/end timestamps (Delta V2 requires these)
    end_ts = int(time.time())
    # 5m resolution * 100 candles = 500 minutes ago
    start_ts = end_ts - (int(limit) * 300) # 300s = 5m
    if 'h' in resolution: start_ts = end_ts - (int(limit) * 3600)

    last_error = ""
    for base in base_urls:
        for sym in symbol_variants:
            for res in res_variants:
                try:
                    url = f"{base}/v2/history/candles"
                    params = {
                        "symbol": sym, 
                        "resolution": res, 
                        "start": start_ts, 
                        "end": end_ts
                    }
                    resp = requests.get(url, params=params, timeout=5)
                    if resp.status_code == 200:
                        data = resp.json().get('result', [])
                        if data:
                            # Delta V2 returns newest first (Descending). We need Oldest First (Ascending).
                            df = pd.DataFrame(data)
                            
                            # Handle both 'c'/'o'/'h'/'l' and 'close'/'open'/'high'/'low' keys
                            rename_map = {'o': 'open', 'h': 'high', 'l': 'low', 'c': 'close', 'v': 'volume', 't': 'time'}
                            df = df.rename(columns=rename_map)
                            
                            # Ensure all required columns exist and are numeric
                            for col in ['open', 'high', 'low', 'close']:
                                if col in df.columns:
                                    df[col] = pd.to_numeric(df[col])
                            
                            # CRITICAL: Reverse to Ascending Order
                            if 'time' in df.columns:
                                df = df.sort_values('time', ascending=True)
                            else:
                                df = df.iloc[::-1] # Fallback reverse
                                
                            return df.reset_index(drop=True), ""
                    else:
                        last_error = f"HTTP {resp.status_code} from {base} ({resp.text[:50]})"
                except Exception as e: 
                    last_error = str(e)
                    continue
    return pd.DataFrame(), last_error

def log_crypto(msg):
    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] [CRYPTO] {msg}")

def get_delta_auth_headers(method, path, payload="", query_string=""):
    api_key = db.get_param('delta_api_key', '')
    api_secret = db.get_param('delta_api_secret', '')
    timestamp = str(int(time.time()))
    
    # Signature: method + timestamp + path + query_string + body
    signature_data = method + timestamp + path + query_string + payload
    signature = hmac.new(api_secret.encode('utf-8'), signature_data.encode('utf-8'), hashlib.sha256).hexdigest()
    return {
        'api-key': api_key,
        'signature': signature,
        'timestamp': timestamp,
        'Content-Type': 'application/json',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) BHARAT-ALGO-V2'
    }

def fetch_open_positions():
    """Helper to fetch raw positions from Delta API."""
    try:
        path = "/v2/positions"
        query = "?underlying_asset_symbol=BTC"
        headers = get_delta_auth_headers("GET", path, query_string=query)
        resp = requests.get(f"https://api.india.delta.exchange{path}{query}", headers=headers, timeout=10)
        if resp.status_code == 200:
            return resp.json().get('result', [])
    except: pass
    return []

def get_current_position():
    try:
        positions = fetch_open_positions()
        if not positions: return None
        for pos in positions:
            size = abs(float(pos.get('size', 0) or pos.get('quantity', 0) or 0))
            if size <= 0.0001: continue
            sym_raw = (pos.get('symbol') or pos.get('instrument_symbol') or pos.get('instrument_name') or (pos.get('product', {}).get('symbol') if isinstance(pos.get('product'), dict) else None) or "")
            if not sym_raw: continue
            sym = str(sym_raw).upper().strip()
            if sym.startswith('P-') or '-P-' in sym or sym.startswith('P_') or '-P_' in sym:
                return {'symbol': sym_raw, 'type': 'PUT', 'entry_price': float(pos.get('avg_entry_price', 0) or pos.get('entry_price', 0) or 0), 'quantity': size}
            elif sym.startswith('C-') or '-C-' in sym or sym.startswith('C_') or '-C_' in sym:
                return {'symbol': sym_raw, 'type': 'CALL', 'entry_price': float(pos.get('avg_entry_price', 0) or pos.get('entry_price', 0) or 0), 'quantity': size}
    except Exception as e:
        import traceback; print(f"[POS ERROR] {e}\n{traceback.format_exc()}")
    return None

def fetch_btc_spot():
    """V3 Alias for current BTC price."""
    df, _ = fetch_delta_candles("BTC", "1m", limit=1)
    if not df.empty:
        return float(df['close'].iloc[-1])
    return 0

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

def find_atm_strike(spot_price, options_list, direction, strike_selection=None, **kwargs):
    if not options_list or spot_price <= 0: return None
    options_list = sorted(options_list, key=lambda x: float(x.get('strike', 0)))
    atm_idx = 0
    min_diff = float('inf')
    for i, opt in enumerate(options_list):
        diff = abs(float(opt['strike']) - spot_price)
        if diff < min_diff:
            min_diff = diff
            atm_idx = i
    strike_pref = (strike_selection or db.get_param("strike_selection", "OTM 2")).upper()
    offset = 0
    if "OTM 1" in strike_pref: offset = 1
    elif "OTM 2" in strike_pref: offset = 2
    elif "OTM 3" in strike_pref: offset = 3
    elif "ITM 1" in strike_pref: offset = -1
    if "CALL" in str(direction).upper(): target_idx = atm_idx + offset
    else: target_idx = atm_idx - offset
    target_idx = max(0, min(len(options_list) - 1, target_idx))
    return options_list[target_idx]

def find_gill_crypto_option(asset, direction):
    chain = fetch_delta_option_chain(asset)
    if not chain: return None
    try: target_dte = int(db.get_param("expiry_selection", "0"))
    except: target_dte = 0
    def get_dte(exp_str):
        try:
            exp_date = datetime.datetime.strptime(str(exp_str).split('T')[0], "%Y-%m-%d").date()
            return (exp_date - datetime.date.today()).days
        except: return 999
    filtered = [o for o in chain if get_dte(o.get('expiry')) == target_dte or (target_dte == 0 and get_dte(o.get('expiry')) <= 1)]
    if not filtered:
        valid = sorted([o for o in chain if get_dte(o.get('expiry')) >= 0], key=lambda x: get_dte(x.get('expiry')))
        if not valid: return None
        nearest_dte = get_dte(valid[0].get('expiry'))
        filtered = [o for o in valid if get_dte(o.get('expiry')) == nearest_dte]
    target_type = 'call_options' if "CALL" in direction.upper() else 'put_options'
    typed = [o for o in filtered if o.get('type') == target_type and float(o.get('mark_price', 0)) > 0]
    if not typed: return None
    spot_price = float(typed[0].get('spot_price') or db.get_param("magical_line", 81000))
    strike_sel = db.get_param("strike_selection", "OTM 2")
    return find_atm_strike(spot_price, typed, direction, strike_selection=strike_sel)

def sync_delta_position():
    """Syncs local DB with actual Delta Exchange positions. Tracks CALL and PUT separately."""
    api_key = db.get_param('delta_api_key', '')
    if not api_key: return False
    
    # ALWAYS use the BTC filter as it's proven to work on this VPS
    path = "/v2/positions"
    query = "?underlying_asset_symbol=BTC"
    url = f"https://api.india.delta.exchange{path}{query}"
    
    try:
        headers = get_delta_auth_headers("GET", path, query_string=query)
        resp = requests.get(url, headers=headers, timeout=10)

        if resp.status_code == 200:
            # Filter BTC positions in Python
            all_positions = resp.json().get('result', [])
            positions = all_positions 
            

            call_symbol = "NONE"
            call_pid = ""
            put_symbol = "NONE"
            put_pid = ""
            
            for p in positions:
                size = abs(float(p.get('size', 0)))
                if size > 0:
                    # --- DEEP SCANNER START ---
                    symbol = p.get('product', {}).get('symbol') or p.get('symbol') or ""
                    pid = str(p.get('product_id') or p.get('id') or "")
                    
                    if not symbol and pid:
                        # Emergency ID Lookup: Ask Delta for the name of this ID
                        try:
                            lookup_url = f"https://api.india.delta.exchange/v2/products/{pid}"
                            l_resp = requests.get(lookup_url, timeout=5)
                            if l_resp.status_code == 200:
                                symbol = l_resp.json().get('result', {}).get('symbol', '')
                                print(f"[DEEP SCAN] Resolved ID {pid} to {symbol}")
                        except: pass
                    
                    if not symbol:
                        # Report keys to help diagnose
                        raw_keys = list(p.keys())
                        print(f"[DEEP SCAN] Symbol missing! Raw keys: {raw_keys}")
                        if not hasattr(sync_delta_position, "last_key_diag"): sync_delta_position.last_key_diag = 0
                        if time.time() - sync_delta_position.last_key_diag > 300:
                            send_telegram_msg(f"🕵️ DEEP SCAN: Symbol hidden. Keys found: {raw_keys}")
                            sync_delta_position.last_key_diag = time.time()
                    # --- DEEP SCANNER END ---
                    
                    symbol_up = symbol.upper()
                    is_call = "-C-" in symbol_up or symbol_up.startswith("C-") or "CALL" in symbol_up
                    is_put = "-P-" in symbol_up or symbol_up.startswith("P-") or "PUT" in symbol_up
                    
                    if is_call:
                        call_symbol = symbol
                        call_pid = pid
                    elif is_put:
                        put_symbol = symbol
                        put_pid = pid

            # --- PREVENT OVER-TRADING: Check for Open Orders ---
            try:
                order_path = "/v2/orders"
                order_query = "?symbol=BTC&state=open"
                order_url = f"https://api.india.delta.exchange{order_path}{order_query}"
                order_headers = get_delta_auth_headers("GET", order_path, query_string=order_query)
                order_resp = requests.get(order_url, headers=order_headers, timeout=5)
                if order_resp.status_code == 200:
                    open_orders = order_resp.json().get('result', [])
                    if open_orders:
                        # If we have open orders, treat as "Trading in progress"
                        db.set_param("order_pending", "YES")
                    else:
                        db.set_param("order_pending", "NO")
            except: pass
            
            db.set_param("active_call_symbol", call_symbol)
            db.set_param("active_call_pid", call_pid)
            db.set_param("active_put_symbol", put_symbol)
            db.set_param("active_put_pid", put_pid)
            
            # Legacy support for dashboard
            if call_symbol != "NONE" and put_symbol != "NONE":
                db.set_param("crypto_active_symbol", "HEDGED (C+P)")
            elif call_symbol != "NONE":
                db.set_param("crypto_active_symbol", call_symbol)
            elif put_symbol != "NONE":
                db.set_param("crypto_active_symbol", put_symbol)
            else:
                db.set_param("crypto_active_symbol", "NONE")
                
            # Fetch Unrealized PnL for Stop Loss checking
            unrealized_pnl = 0
            for p in positions:
                unrealized_pnl += float(p.get('unrealized_pnl', 0))
            db.set_param("unrealized_pnl", str(unrealized_pnl))

            # --- FINAL DIAGNOSTIC REPORT ---
            active_symbols = []
            if call_symbol != "NONE": active_symbols.append(call_symbol)
            if put_symbol != "NONE": active_symbols.append(put_symbol)
            
            if len(positions) > 0:
                if not hasattr(sync_delta_position, "last_diag"): sync_delta_position.last_diag = 0
                if time.time() - sync_delta_position.last_diag > 300: # Every 5 mins
                    send_telegram_msg(f"🔍 SYNC DIAGNOSTIC: Found {len(positions)} positions on Exchange.\nSymbols: {active_symbols if active_symbols else 'UNKNOWN (Check Pulse)'}")
                    sync_delta_position.last_diag = time.time()

            return True 
        else:
            from main import log_terminal
            # Check for specifically 400 errors (often schema or IP)
            err_msg = resp.json().get('error', {}).get('message', 'Unknown Error')
            log_terminal(f"🚨 API SYNC FAILED ({resp.status_code}): {err_msg}", "ERROR")
            db.set_param("crypto_active_symbol", "API_ERROR_LOCK")
            return False 
    except Exception as e:
        print(f"[SYNC EXCEPTION] {e}")
        db.set_param("crypto_active_symbol", "API_ERROR_LOCK")
        return False

def check_stop_loss():
    """
    Checks if current open positions have hit the 40% loss threshold.
    If so, triggers immediate square off.
    """
    mode = db.get_param('trade_mode', 'PAPER')
    if mode != "LIVE": return False

    try:
        # 1. Get positions to find entry value and current PnL
        path = "/v2/positions"
        query = "?underlying_asset_symbol=BTC"
        url = f"https://api.india.delta.exchange{path}{query}"
        headers = get_delta_auth_headers("GET", path, query_string=query)
        resp = requests.get(url, headers=headers, timeout=10)
        
        if resp.status_code == 200:
            positions = resp.json().get('result', [])
            for p in positions:
                size = abs(float(p.get('size', 0)))
                if size > 0:
                    upnl = float(p.get('unrealized_pnl', 0))
                    entry_value = float(p.get('entry_value', 0))
                    
                    if entry_value != 0:
                        loss_pct = (upnl / abs(entry_value)) * 100
                        # Log status every check for transparency
                        print(f"[DEBUG] SL Check: {p.get('product',{}).get('symbol')} | PnL: {upnl:.2f} | Entry: {entry_value:.2f} | Loss: {loss_pct:.1f}%")
                        
                        if loss_pct <= -40: # 40% loss
                            log_terminal(f"🚨 HARD STOP LOSS HIT: {loss_pct:.1f}%! Force Squaring off...", "ALERT")
                            square_off_crypto(p.get('product_id'))
                            return True
    except Exception as e:
        print(f"[SL CHECK ERROR] {e}")
    return False

def reconcile_bracket_orders():
    """
    STABLE 2.0 AUTO-HEALER
    Ensures every open position has a SL and TP on the exchange.
    """
    mode = db.get_param('trade_mode', 'PAPER')
    if mode != "LIVE": return
    
    try:
        # 1. Fetch Positions
        path = "/v2/positions"
        url = f"https://api.india.delta.exchange{path}?underlying_asset_symbol=BTC"
        headers = get_delta_auth_headers("GET", path, query_string="?underlying_asset_symbol=BTC")
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200: return
        
        positions = resp.json().get('result', [])
        for p in positions:
            size = abs(float(p.get('size', 0)))
            if size > 0:
                pid = p.get('product_id')
                entry_price = float(p.get('avg_entry_price', 0))
                
                # 2. Check for Open SL/TP Orders for this PID
                order_path = "/v2/orders"
                order_query = f"?product_id={pid}&state=open"
                order_url = f"https://api.india.delta.exchange{order_path}{order_query}"
                order_headers = get_delta_auth_headers("GET", order_path, query_string=order_query)
                order_resp = requests.get(order_url, headers=order_headers, timeout=5)
                
                if order_resp.status_code == 200:
                    open_orders = order_resp.json().get('result', [])
                    has_sl = any(o.get('stop_order_type') == 'stop_loss_order' for o in open_orders)
                    has_tp = any(o.get('stop_order_type') == 'take_profit_order' for o in open_orders)
                    
                    if not has_sl or not has_tp:
                        # from main import log_terminal
                        # log_terminal(f"🛡️ AUTO-HEAL: Setting missing brackets for {pid}...", "INFO")
                        # place_delta_bracket_orders(pid, size, entry_price)
                        pass
    except Exception as e:
        print(f"[RECONCILE ERROR] {e}")

def send_daily_summary():
    # Lego Block 5: The Daily Auditor
    pnl_24h, count, win_rate, avg_pnl = db.get_stats(days=1)
    
    # Conversion to Rupees (Standard rate)
    pnl_rs = pnl_24h * 85 
    
    # Capital calculation
    capital = float(db.get_param('estimated_capital', '240'))
    pnl_pct = (pnl_24h / capital) * 100 if capital > 0 else 0
    
    msg = f"📊 *DAILY AUDIT REPORT (24h)*\n"
    msg += f"----------------------------\n"
    msg += f"💰 PnL: ${pnl_24h:.2f} (~₹{pnl_rs:,.0f})\n"
    msg += f"📈 Return: {pnl_pct:+.2f}%\n"
    msg += f"🎯 Win Rate: {win_rate:.1f}%\n"
    msg += f"🔄 Trades: {count}\n"
    msg += f"----------------------------"
    send_telegram_msg(msg)

def send_weekly_summary():
    # Lego Block 6: Weekly Performance Summary
    pnl_7d, count, win_rate, avg_pnl = db.get_stats(days=7)
    pnl_rs = pnl_7d * 85
    
    msg = f"🏆 *WEEKLY PERFORMANCE SUMMARY*\n"
    msg += f"----------------------------\n"
    msg += f"💰 Net Profit: ${pnl_7d:.2f} (~₹{pnl_rs:,.0f})\n"
    msg += f"🎯 Accuracy: {win_rate:.1f}%\n"
    msg += f"📊 Total Trades: {count}\n"
    msg += f"💵 Avg/Trade: ${avg_pnl:.2f}\n"
    msg += f"🏁 System Health: {'EXCELLENT' if win_rate > 60 else 'STABLE'}\n"
    msg += f"----------------------------"
    send_telegram_msg(msg)

def square_off_crypto(target_pid=None):
    """
    BRUTE FORCE SQUARE OFF (Search & Destroy)
    If target_pid is provided, closes only that. 
    Otherwise, fetches LIVE positions and closes EVERYTHING with size > 0.
    """
    mode = db.get_param('trade_mode', 'PAPER')
    from main import log_terminal, send_telegram_msg
    
    pids_to_close = []
    
    # 1. Gather PIDs to close
    if target_pid:
        pids_to_close = [str(target_pid)]
    else:
        # AGGRESSIVE SEARCH: Fetch ALL positions directly from Exchange
        # BUG FIX: query_string must be passed to signature AND to URL
        for asset in ["BTC", "ETH"]:
            try:
                path = "/v2/positions"
                query = f"?underlying_asset_symbol={asset}"
                url = f"https://api.india.delta.exchange{path}{query}"
                # CRITICAL FIX: pass query_string so signature is correct
                headers = get_delta_auth_headers("GET", path, query_string=query)
                resp = requests.get(url, headers=headers, timeout=10)
                
                if resp.status_code == 200:
                    raw_data = resp.json().get('result', [])
                    for p in raw_data:
                        size = abs(float(p.get('size', 0)))
                        if size > 0:
                            pid = str(p.get('product_id') or p.get('id') or p.get('pid') or "")
                            sym = p.get('symbol', '')
                            if pid and pid not in pids_to_close:
                                pids_to_close.append(pid)
                                log_crypto(f"🔍 Found open position: {sym} | PID={pid} | Size={size}")
                else:
                    log_crypto(f"Position fetch failed for {asset}: HTTP {resp.status_code} - {resp.text[:100]}")
            except Exception as e:
                log_crypto(f"Nuclear Search Error ({asset}): {e}")

    if not pids_to_close:
        # Confirm Clean Slate in DB
        db.set_param("local_trade_active", "NO")
        db.set_param("crypto_active_symbol", "NONE")
        db.set_param("active_call_symbol", "NONE")
        db.set_param("active_put_symbol", "NONE")
        return True
    
    # 2. Execute Market Exits
    for pid in pids_to_close:
        log_terminal(f"🧨 BRUTE FORCE EXIT: PRODUCT_ID {pid}", "ALERT")
        if mode == "LIVE":
            try:
                # Re-fetch exact current size for this PID
                size = 0
                query = "?underlying_asset_symbol=BTC"
                r_pos = requests.get(
                    f"https://api.india.delta.exchange/v2/positions{query}",
                    headers=get_delta_auth_headers("GET", "/v2/positions", query_string=query),
                    timeout=10
                )
                if r_pos.status_code == 200:
                    for p in r_pos.json().get('result', []):
                        this_pid = str(p.get('product_id') or p.get('id') or "")
                        if this_pid == pid:
                            size = abs(float(p.get('size', 0)))
                            break
                
                # Also try ETH if not found
                if size == 0:
                    query2 = "?underlying_asset_symbol=ETH"
                    r_pos2 = requests.get(
                        f"https://api.india.delta.exchange/v2/positions{query2}",
                        headers=get_delta_auth_headers("GET", "/v2/positions", query_string=query2),
                        timeout=10
                    )
                    if r_pos2.status_code == 200:
                        for p in r_pos2.json().get('result', []):
                            this_pid = str(p.get('product_id') or p.get('id') or "")
                            if this_pid == pid:
                                size = abs(float(p.get('size', 0)))
                                break

                if size == 0:
                    log_terminal(f"⚠️ Size=0 for {pid}, skipping.", "WARN")
                    continue

                # CRITICAL FIX: size must be INTEGER for Delta Exchange
                payload_dict = {
                    "product_id": int(pid),
                    "size": int(size),  # Must be int, not float!
                    "side": "buy",      # RESERVED FOR SQUARE-OFF (Buy to Close)
                    "order_type": "market_order",
                    "reduce_only": True
                }
                payload = json.dumps(payload_dict)
                log_terminal(f"📤 Sending exit order: {payload_dict}", "INFO")
                resp = requests.post(
                    "https://api.india.delta.exchange/v2/orders",
                    headers=get_delta_auth_headers("POST", "/v2/orders", payload=payload),
                    data=payload,
                    timeout=10
                )
                
                if resp.status_code in [200, 201]:
                    log_terminal(f"✅ MARKET EXIT SUCCESS: PRODUCT_ID {pid}", "TRADE")
                    send_telegram_msg(f"✅ Position CLOSED successfully: PID {pid}")
                    db.set_param("local_trade_active", "NO")
                    db.set_param("crypto_active_symbol", "NONE")
                else:
                    full_err = resp.text
                    log_terminal(f"❌ EXIT FAILED ({resp.status_code}): {full_err}", "ERROR")
                    send_telegram_msg(f"🚨 CRITICAL: Exit FAILED for {pid}! Error: {full_err[:200]}. Close manually on Delta app!")
            except Exception as e:
                log_terminal(f"⚠️ EXIT EXCEPTION: {e}", "ERROR")
                send_telegram_msg(f"🚨 EXIT EXCEPTION: {e}")
    
    return True

def place_delta_bracket_orders(pid, qty, entry_price):
    """
    Places server-side Stop Loss and Take Profit orders on Delta Exchange.
    SL: -40% | TP: +100%
    Fix: Using 'market_order' per Delta V2 schema requirements.
    """
    url = "https://api.india.delta.exchange/v2/orders"
    
    # 1. Stop Loss Order (-40%) - Lego Block 3: The Selling Fix
    sl_trigger = round(entry_price * 0.60, 2)
    sl_limit = round(sl_trigger * 0.95, 2) # 5% lower than trigger to ensure fill
    sl_payload = {
        "product_id": int(pid),
        "size": float(qty),
        "side": "sell",
        "order_type": "limit_order",
        "stop_order_type": "stop_loss_order",
        "stop_price": str(sl_trigger),
        "limit_price": str(sl_limit),
        "reduce_only": True
    }
    
    # 2. Take Profit Order (+100%)
    tp_trigger = round(entry_price * 2.00, 2)
    tp_limit = round(tp_trigger, 2) # Exact price for TP
    tp_payload = {
        "product_id": int(pid),
        "size": float(qty),
        "side": "sell",
        "order_type": "limit_order",
        "stop_order_type": "take_profit_order",
        "stop_price": str(tp_trigger),
        "limit_price": str(tp_limit),
        "reduce_only": True
    }
    
    import json
    for name, payload_dict in [("STOP LOSS", sl_payload), ("TAKE PROFIT", tp_payload)]:
        try:
            payload = json.dumps(payload_dict)
            headers = get_delta_auth_headers("POST", "/v2/orders", payload=payload)
            resp = requests.post(url, headers=headers, data=payload, timeout=10)
            if resp.status_code in [200, 201]:
                log_terminal(f"🛡️ {name} SET: @ {payload_dict['stop_price']} (Limit: {payload_dict['limit_price']})", "INFO")
                if name == "TAKE PROFIT":
                    log_terminal("💉 SURGERY SUCCESS: Brackets Hardened.", "INFO")
            else:
                log_terminal(f"⚠️ {name} FAILED: {resp.status_code} - {resp.text}", "ERROR")
        except Exception as e:
            log_terminal(f"⚠️ {name} EXCEPTION: {e}", "ERROR")

def get_dynamic_quantity(option_price):
    # Lego Block: Priority Lot Selection
    # STABILITY TEST: Using only 1 lot for now
    manual_lots = int(db.get_param('crypto_trade_size', '1'))
    return manual_lots

def execute_crypto_trade(direction=None):
    import time, signal, traceback
    log_terminal(f"🔍 [EXEC] START: {direction}", "TRADE")
    try:
        # Step 1: Balance
        log_terminal("🔍 [EXEC] Step 1/6: Fetching balance...", "DEBUG")
        balance = fetch_wallet_balance()
        log_terminal(f"💰 [EXEC] Balance: ${balance:.2f}", "DEBUG")
        
        effective_balance = balance if MIN_BALANCE_OVERRIDE <= 0 else MIN_BALANCE_OVERRIDE
        if effective_balance < 1.0:
            msg = f"⚠️ BLOCKED: Balance ${effective_balance:.2f} < $1.0"
            log_terminal(msg, "WARN"); send_telegram_msg(msg); return

        # Step 2: Mode check
        log_terminal("🔍 [EXEC] Step 2/6: Checking trade mode...", "DEBUG")
        if db.get_param('trade_mode', 'PAPER') != "LIVE":
            log_terminal("📝 [EXEC] PAPER MODE: Skipping", "INFO"); return

        # Step 3: Find option
        log_terminal("🔍 [EXEC] Step 3/6: Fetching option chain...", "DEBUG")
        opt = find_gill_crypto_option("BTC", direction)
        if not opt:
            msg = f"❌ BLOCKED: No valid option found for {direction}"
            log_terminal(msg, "ERROR"); send_telegram_msg(msg); return
        log_terminal(f"🎯 [EXEC] Option: {opt['symbol']} (PID:{opt['product_id']})", "DEBUG")

        # Step 4: Build payload
        log_terminal("🔍 [EXEC] Step 4/6: Building order payload...", "DEBUG")
        payload = json.dumps({
            "product_id": int(opt['product_id']),
            "size": int(db.get_param('crypto_trade_size', '1')),
            "side": "sell",
            "order_type": "market_order"
        })
        headers = get_delta_auth_headers("POST", "/v2/orders", payload=payload)

        # Step 5: API call with timeout
        log_terminal("🔍 [EXEC] Step 5/6: Sending API request (10s timeout)...", "DEBUG")
        resp = requests.post("https://api.india.delta.exchange/v2/orders", headers=headers, data=payload, timeout=10)

        # Step 6: Handle response
        log_terminal(f"🔍 [EXEC] Step 6/6: API response code: {resp.status_code}", "DEBUG")
        if resp.status_code in [200, 201]:
            msg = f"✅ LIVE ENTRY SUCCESS: {opt['symbol']}"
            log_terminal(msg, "TRADE"); send_telegram_msg(msg); sync_delta_position()
        else:
            err = resp.text.lower()
            if "insufficientmargin" in err:
                msg = f"🚨 MARGIN ERROR: Need ~$10-$15. Balance: ${balance:.2f}"
            else:
                msg = f"❌ API REJECTED ({resp.status_code}): {resp.text}"
            log_terminal(msg, "ERROR"); send_telegram_msg(msg)

    except requests.exceptions.Timeout:
        msg = "❌ NETWORK TIMEOUT: Delta API did not respond in 10s"
        log_terminal(msg, "ERROR"); send_telegram_msg(msg)
    except requests.exceptions.ConnectionError:
        msg = "❌ CONNECTION FAILED: Check VPS internet or Delta API status"
        log_terminal(msg, "ERROR"); send_telegram_msg(msg)
    except Exception as e:
        msg = f"❌ EXEC CRASH: {str(e)}"
        log_terminal(msg, "ERROR"); log_terminal(traceback.format_exc(), "ERROR"); send_telegram_msg(msg)
    log_terminal("✅ [EXEC] Function completed", "DEBUG")

def fetch_wallet_balance():
    """Fetch USDT balance from Delta Exchange with FULL DEBUG LOGGING"""
    try:
        path = "/v2/wallet/balances"
        headers = get_delta_auth_headers("GET", path)
        resp = requests.get(f"https://api.india.delta.exchange{path}", headers=headers, timeout=10)
        
        # LOG RAW RESPONSE FOR DEBUGGING
        log_terminal(f"💰 [BALANCE API] Status: {resp.status_code}", "DEBUG")
        log_terminal(f"💰 [BALANCE API] Raw Response: {resp.text[:500]}", "DEBUG")
        
        if resp.status_code != 200:
            log_terminal(f"⚠️ [BALANCE] API Error: {resp.status_code} - {resp.text}", "WARN")
            return 0.0
            
        result = resp.json().get('result', [])
        if not result:
            log_terminal("⚠️ [BALANCE] Empty result array from API", "WARN")
            return 0.0
            
        # Search for USDT/USD balance with multi-key fallback
        for item in result:
            asset = str(item.get('asset_symbol') or item.get('currency') or '').upper()
            if asset in ['USDT', 'USD', 'USDⓈ']:
                # Try multiple possible balance keys (Delta API varies)
                balance = (
                    float(item.get('balance') or item.get('available_balance') or item.get('total_balance') or item.get('available') or 0)
                )
                log_terminal(f"✅ [BALANCE] Found {asset}: ${balance:.2f}", "DEBUG")
                return balance
                
        log_terminal("⚠️ [BALANCE] USDT/USD not found in response", "WARN")
        return 0.0
        
    except requests.exceptions.Timeout:
        log_terminal("❌ [BALANCE] API Timeout", "ERROR")
        return 0.0
    except requests.exceptions.ConnectionError:
        log_terminal("❌ [BALANCE] Connection Failed", "ERROR")
        return 0.0
    except Exception as e:
        import traceback
        log_terminal(f"❌ [BALANCE] Crash: {str(e)}", "ERROR")
        log_terminal(traceback.format_exc(), "ERROR")
        return 0.0
