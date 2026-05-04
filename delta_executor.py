import time
import hmac
import hashlib
import requests
import datetime
import socket
import db
import pandas as pd
from utils import log_terminal, send_telegram_msg

# --- FORCE IPv4 GLOBALLY ---
import requests.packages.urllib3.util.connection as urllib3_cn
def allowed_gai_family():
    return socket.AF_INET
urllib3_cn.allowed_gai_family = allowed_gai_family

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

def find_atm_strike(spot_price, options_list, direction, offset=0):
    """
    Lego Block 3: Strike Selection (Strike Picker)
    Finds the strike price with min difference from spot, plus an optional OTM offset.
    offset=0: ATM
    offset=1: 1-strike OTM
    """
    if not options_list: return None
    
    # 1. Sort all by proximity to spot (ATM candidate is index 0)
    options_list.sort(key=lambda x: abs(float(x.get('strike_price', 0)) - spot_price))
    
    if offset == 0:
        return options_list[0]
    
    # 2. Filter for OTM strikes
    # For CALL: Strike > Spot
    # For PUT: Strike < Spot
    otm_options = []
    if direction == "BUY": # Call
        otm_options = [o for o in options_list if float(o.get('strike_price', 0)) > spot_price]
    else: # Put
        otm_options = [o for o in options_list if float(o.get('strike_price', 0)) < spot_price]
        
    if not otm_options:
        return options_list[0] # Fallback to ATM if no OTM found
        
    # 3. Sort OTM options by proximity to spot and pick the requested offset
    otm_options.sort(key=lambda x: abs(float(x.get('strike_price', 0)) - spot_price))
    
    target_idx = offset - 1 # offset 1 is index 0 of OTM list
    if target_idx < len(otm_options):
        return otm_options[target_idx]
    
    return otm_options[-1] # Pick furthest OTM if requested offset is out of bounds

def find_gill_crypto_option(asset, direction):
    from main import send_telegram_msg
    log_crypto(f"Scanning {direction} options for {asset} (Gill Supertrend Rule)...")
    chain = fetch_delta_option_chain(asset)
    if not chain:
        log_crypto("Chain is empty!")
        return None
    
    target_type = 'call_options' if direction == "BUY" else 'put_options'
    
    # 1. Filter for type and liquidity
    all_typed_options = [o for o in chain if o.get('contract_type') == target_type and float(o.get('mark_price', 0)) > 0]
    
    if not all_typed_options:
        log_crypto(f"No liquid {target_type} found at all.")
        return None

    # 2. Expiry Rule: Never same day. Pick nearest expiry AFTER today.
    today_str = datetime.date.today().strftime('%Y-%m-%d')
    valid_expiries = sorted(list(set([o['expiry_date'] for o in all_typed_options if o['expiry_date'] > today_str])))
    
    if not valid_expiries:
        log_crypto("No expiries found after today!")
        return None
        
    best_expiry = valid_expiries[0] # Nearest expiry that is NOT today
    log_crypto(f"Selected Expiry: {best_expiry} (Target: {target_type})")
    
    # 3. Filter for options with that specific expiry
    near_options = [o for o in all_typed_options if o.get('expiry_date') == best_expiry]
    
    # 4. Get Spot Price
    spot_price = 0
    for o in near_options:
        spot_price = float(o.get('spot_price') or o.get('underlying_price') or 0)
        if spot_price > 0: break
    
    if spot_price == 0:
        log_crypto("Could not determine spot price.")
        return None
    
    # 5. Strike Selection: ATM or 1-strike OTM
    # offset=0 is ATM, offset=1 is 1-strike OTM
    offset = int(db.get_param('strike_offset', '1')) # Defaulting to 1 (slight OTM) per user request
    best_opt = find_atm_strike(spot_price, near_options, direction, offset=offset)
    
    if not best_opt: return None

    return (
        best_opt['symbol'], 
        float(best_opt['mark_price']), 
        float(best_opt['strike_price']), 
        best_opt['expiry_date'], 
        best_opt['product_id']
    )

def sync_delta_position():
    """Syncs local DB with actual Delta Exchange positions. Tracks CALL and PUT separately."""
    api_key = db.get_param('delta_api_key', '')
    if not api_key: return False
    
    # FETCH ALL POSITIONS (No filter) to prevent blindness
    path = "/v2/positions"
    url = f"https://api.india.delta.exchange{path}"
    
    try:
        headers = get_delta_auth_headers("GET", path)
        resp = requests.get(url, headers=headers, timeout=10)
        
        # If no-filter fails, try with filter
        if resp.status_code != 200:
            query = "?underlying_asset_symbol=BTC"
            url = f"{url}{query}"
            headers = get_delta_auth_headers("GET", path, query_string=query)
            resp = requests.get(url, headers=headers, timeout=10)

        if resp.status_code == 200:
            # Filter BTC positions in Python
            all_positions = resp.json().get('result', [])
            positions = [p for p in all_positions if p.get('product', {}).get('underlying_asset_symbol') == 'BTC' or 'BTC' in p.get('product', {}).get('symbol', '').upper()]
            
            # DEBUG: Log raw positions count
            raw_symbols = [p.get('product',{}).get('symbol') for p in positions]
            print(f"[DEBUG] Raw Positions Count: {len(positions)}")
            if len(positions) > 0:
                print(f"[DEBUG] Raw Symbols: {raw_symbols}")
                # Log to telegram once to help Dr. Saab see what's happening
                if not hasattr(sync_delta_position, "last_diag"): sync_delta_position.last_diag = 0
                if time.time() - sync_delta_position.last_diag > 300: # Every 5 mins
                    send_telegram_msg(f"🔍 SYNC DIAGNOSTIC: Found {len(positions)} positions on Exchange.\nSymbols: {raw_symbols}")
                    sync_delta_position.last_diag = time.time()

            call_symbol = "NONE"
            call_pid = ""
            put_symbol = "NONE"
            put_pid = ""
            
            for p in positions:
                size = abs(float(p.get('size', 0)))
                if size > 0:
                    symbol = p.get('product', {}).get('symbol', '')
                    pid = str(p.get('product_id', ''))
                    
                    symbol_up = symbol.upper()
                    # More robust matching patterns for Delta symbols like P-BTC-... or BTC-P-...
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
    SQUARES OFF a position. 
    If target_pid is provided, closes only that. 
    Otherwise, syncs and closes everything.
    Aggressive Retry: If it fails, it will be called again by Janitor in 15s.
    """
    mode = db.get_param('trade_mode', 'PAPER')
    from main import log_terminal, send_telegram_msg
    
    # 1. Sync first to see what's really open
    sync_delta_position()
    pids = []
    
    if target_pid:
        pids = [target_pid]
    else:
        c_pid = db.get_param("active_call_pid", "")
        p_pid = db.get_param("active_put_pid", "")
        if c_pid and c_pid != "NONE": pids.append(c_pid)
        if p_pid and p_pid != "NONE": pids.append(p_pid)
    
    # NUCLEAR FALLBACK: If sync says none but we might have zombies
    if not pids:
        try:
            path_pos = "/v2/positions"
            query_pos = "?underlying_asset_symbol=BTC"
            url_pos = f"https://api.india.delta.exchange{path_pos}{query_pos}"
            h_pos = get_delta_auth_headers("GET", path_pos, query_string=query_pos)
            r_pos = requests.get(url_pos, headers=h_pos, timeout=10)
            if r_pos.status_code == 200:
                raw_data = r_pos.json().get('result', [])
                pids = [str(p.get('product_id')) for p in raw_data if abs(float(p.get('size', 0))) > 0]
        except: pass

    if not pids:
        # Screen is truly clean
        db.set_param("local_trade_active", "NO")
        db.set_param("crypto_active_symbol", "NONE")
        db.set_param("active_call_symbol", "NONE")
        db.set_param("active_put_symbol", "NONE")
        return True
    
    success = True
    for pid in pids:
        log_crypto(f"Attempting Square Off for PID: {pid}")
        if mode == "LIVE":
            try:
                # Get current size
                url_pos = "https://api.india.delta.exchange/v2/positions"
                h_pos = get_delta_auth_headers("GET", "/v2/positions")
                r_pos = requests.get(url_pos, headers=h_pos, timeout=10)
                
                size = 0
                if r_pos.status_code == 200:
                    for p in r_pos.json().get('result', []):
                        if str(p.get('product_id')) == str(pid):
                            size = abs(float(p.get('size', 0)))
                            break
                
                if size == 0: continue 

                # Send Market Close Order
                url = "https://api.india.delta.exchange/v2/orders"
                payload_dict = {
                    "product_id": int(pid),
                    "size": float(size),
                    "side": "sell", # Standard for our LONG only strategy
                    "order_type": "market_order",
                    "reduce_only": True
                }
                import json
                payload = json.dumps(payload_dict)
                h_order = get_delta_auth_headers("POST", "/v2/orders", payload=payload)
                resp = requests.post(url, headers=h_order, data=payload, timeout=10)
                
                if resp.status_code in [200, 201]:
                    log_terminal(f"✅ Square Off SENT: {pid}", "TRADE")
                else:
                    success = False
                    err_msg = resp.json().get('error', {}).get('message', 'Unknown Error')
                    log_terminal(f"❌ Square Off FAILED for {pid}: {err_msg}", "ERROR")
                    send_telegram_msg(f"⚠️ FAILED TO CLOSE TRADE {pid}: {err_msg}. Will retry in 15s. Please check manually if persistent.")
            except Exception as e:
                success = False
                log_crypto(f"⚠️ Square Off EXCEPTION: {e}")
                send_telegram_msg(f"⚠️ EXCEPTION CLOSING TRADE: {e}")

    return success

def place_delta_bracket_orders(pid, qty, entry_price):
    """
    Places server-side Stop Loss and Take Profit orders on Delta Exchange.
    SL: -40% | TP: +100%
    Fix: Using 'market_order' per Delta V2 schema requirements.
    """
    url = "https://api.india.delta.exchange/v2/orders"
    
    # 1. Stop Loss Order (-40%)
    sl_price = round(entry_price * 0.60, 2)
    sl_payload = {
        "product_id": int(pid),
        "size": float(qty),
        "side": "sell",
        "order_type": "market_order",
        "stop_order_type": "stop_loss_order",
        "stop_price": str(sl_price),
        "reduce_only": True
    }
    
    # 2. Take Profit Order (+100%)
    tp_price = round(entry_price * 2.00, 2)
    tp_payload = {
        "product_id": int(pid),
        "size": float(qty),
        "side": "sell",
        "order_type": "market_order",
        "stop_order_type": "take_profit_order",
        "stop_price": str(tp_price),
        "reduce_only": True
    }
    
    import json
    for name, payload_dict in [("STOP LOSS", sl_payload), ("TAKE PROFIT", tp_payload)]:
        try:
            payload = json.dumps(payload_dict)
            headers = get_delta_auth_headers("POST", "/v2/orders", payload=payload)
            resp = requests.post(url, headers=headers, data=payload, timeout=10)
            if resp.status_code in [200, 201]:
                log_terminal(f"🛡️ {name} SET: @ {payload_dict['stop_price']} on Exchange", "INFO")
            else:
                log_terminal(f"⚠️ {name} FAILED: {resp.status_code} - {resp.text}", "ERROR")
        except Exception as e:
            log_terminal(f"⚠️ {name} EXCEPTION: {e}", "ERROR")

def get_dynamic_quantity(option_price):
    # Lego Block: Priority Lot Selection
    # STABILITY TEST: Using only 1 lot for now
    manual_lots = int(db.get_param('crypto_trade_size', '1'))
    return manual_lots

def execute_crypto_trade(asset, direction):
    """
    Executes a trade based on signal.
    Does NOT block if previous position is still closing.
    """
    from main import log_terminal, send_telegram_msg
    mode = db.get_param('trade_mode', 'PAPER')
    
    api_key = db.get_param('delta_api_key', '')
    if not api_key:
        send_telegram_msg("❌ CRITICAL: API Key missing in DB!")
        return

    log_crypto(f"SIGNAL RECEIVED: {direction} {asset}")
    
    # 1. Update Target Signal in DB (for Janitor to handle exits)
    db.set_param("signal_target", direction)
    
    # 2. FAIL-SAFE SYNC: If we can't see the screen, we don't trade!
    if not sync_delta_position():
        log_terminal("🛑 BLIND-FOLD SAFETY: Sync failed. Aborting entry to prevent over-trading!", "ERROR")
        return
        
    # 2.1 PENDING ORDER SAFETY
    if db.get_param("order_pending", "NO") == "YES":
        log_terminal("⏳ PENDING ORDER DETECTED: Waiting for previous order to fill/cancel before new trade.", "INFO")
        return

    # 2.2 LOCAL TRADE LOCK SAFETY (Double-Entry Prevention)
    if db.get_param("local_trade_active", "NO") == "YES":
        # Check if API also sees it. If API says NONE but Local says YES, we trust Local for 2 minutes (API Lag)
        # unless we are sure it was a failure.
        log_terminal("🛡️ LOCAL LOCK ACTIVE: System believes a trade is already running. Blocking new entry.", "ALERT")
        return

    # 2.3 TOTAL LOT GUARD
    sync_delta_position()
    manual_lots = int(db.get_param('crypto_trade_size', '3'))
    # Calculate total size across all positions
    total_open_size = 0
    # Re-fetch positions to be absolutely sure
    try:
        path = "/v2/positions"
        url = f"https://api.india.delta.exchange{path}?underlying_asset_symbol=BTC"
        headers = get_delta_auth_headers("GET", path, query_string="?underlying_asset_symbol=BTC")
        r = requests.get(url, headers=headers, timeout=5)
        if r.status_code == 200:
            for p in r.json().get('result', []):
                total_open_size += abs(float(p.get('size', 0)))
    except: pass
    
    if total_open_size >= manual_lots:
        log_terminal(f"🛑 CAPACITY FULL: Current Size {total_open_size} >= Target {manual_lots}. No more entries allowed.", "ALERT")
        db.set_param("local_trade_active", "YES") # Sync local lock
        return

    # 2.5 CLEAN SLATE RULE: Close EVERYTHING before a new entry
    # This is an absolute rule per Dr. Saab.
    has_call = db.get_param("active_call_symbol", "NONE") != "NONE"
    has_put = db.get_param("active_put_symbol", "NONE") != "NONE"

    if (direction == "BUY" and has_put) or (direction == "SELL" and has_call) or (has_call and has_put):
        log_terminal("🧹 CLEAN SLATE: Closing all existing positions before fresh entry...", "TRADE")
        square_off_crypto() # Closes everything
        time.sleep(2) # Wait for execution
        sync_delta_position()

    # Re-check status after clean slate
    has_call = db.get_param("active_call_symbol", "NONE") != "NONE"
    has_put = db.get_param("active_put_symbol", "NONE") != "NONE"

    if direction == "BUY" and has_call:
        log_terminal(f"STAY: Already have CALL active. Holding.", "INFO")
        return
    
    if direction == "SELL" and has_put:
        log_terminal(f"STAY: Already have PUT active. Holding.", "INFO")
        return

    # 3. Find Best Option to Open
    opt = find_gill_crypto_option(asset, direction)
    if not opt: 
        log_terminal(f"ERROR: Could not find suitable {direction} option.", "ERROR")
        return
        
    symbol, price, strike, expiry, pid = opt
    qty = get_dynamic_quantity(price)
    
    # 4. Execute Entry
    if mode == "LIVE":
        try:
            url = "https://api.india.delta.exchange/v2/orders"
            payload_dict = {
                "product_id": int(pid),
                "size": int(qty),
                "side": "buy",
                "order_type": "market_order"
            }
            import json
            payload = json.dumps(payload_dict)
            
            headers = get_delta_auth_headers("POST", "/v2/orders", payload=payload)
            resp = requests.post(url, headers=headers, data=payload, timeout=10)
            
            if resp.status_code in [200, 201]:
                log_terminal(f"LIVE ENTRY SUCCESS: {symbol} @ {price}", "TRADE")
                print(f"[DEBUG] Entry Payload: {payload}")
                print(f"[DEBUG] Entry Response: {resp.text}")
                # ACTIVATE LOCAL LOCK IMMEDIATELY
                db.set_param("local_trade_active", "YES")
                
                # --- NEW: Place Server-Side Bracket Orders ---
                place_delta_bracket_orders(pid, qty, price)
                
                # Brief wait before sync to allow exchange to update
                time.sleep(1)
                sync_delta_position()
            else:
                log_terminal(f"LIVE ENTRY FAILED: {resp.status_code} - {resp.text[:100]}", "ERROR")
        except Exception as e:
            log_terminal(f"ENTRY EXCEPTION: {e}", "ERROR")
    else:
        # Paper Trade
        log_terminal(f"PAPER ENTRY: {symbol} @ {price}", "TRADE")
        # Update DB for paper trade
        if direction == "BUY":
            db.set_param("active_call_symbol", symbol)
            db.set_param("active_call_pid", str(pid))
        else:
            db.set_param("active_put_symbol", symbol)
            db.set_param("active_put_pid", str(pid))
        db.set_param("crypto_active_symbol", symbol)

