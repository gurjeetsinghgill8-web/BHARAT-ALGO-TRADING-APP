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

def find_atm_strike(spot_price, options_list, offset=0):
    """
    Lego Block 3: ATM Strike Selection (Strike Picker)
    Finds the strike price with min difference from spot, plus an optional offset.
    offset=0: ATM, offset=1: Next OTM, etc.
    """
    if not options_list: return None
    # Sort by strike proximity
    options_list.sort(key=lambda x: abs(float(x.get('strike_price', 0)) - spot_price))
    
    # Return the strike with the requested offset
    if offset < len(options_list):
        return options_list[offset]
    return options_list[0]

def find_gill_crypto_option(asset, direction):
    from main import send_telegram_msg
    log_crypto(f"Scanning {direction} options for {asset} (Dynamic Rule)...")
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

    # 2. Lego Block 2: Expiry Rule (Dynamic from DB)
    exp_days = int(db.get_param('expiry_threshold', '1'))
    valid_options = filter_options_by_expiry(all_typed_options, days_threshold=exp_days)
                
    if not valid_options:
        log_crypto(f"WARNING: No options found with {exp_days}d expiry. Using nearest available.")
        valid_options = all_typed_options 

    # 3. Sort by expiry date (ascending) and pick the first (nearest) valid expiry
    valid_options.sort(key=lambda x: x.get('expiry_date', '9999-12-31'))
    best_expiry = valid_options[0].get('expiry_date')
    
    log_crypto(f"Selected Expiry: {best_expiry} (Target: {target_type})")
    
    # 4. Filter for options with that specific expiry
    near_options = [o for o in valid_options if o.get('expiry_date') == best_expiry]
    
    # 5. Get Spot Price
    spot_price = 0
    for o in near_options:
        spot_price = float(o.get('spot_price') or o.get('underlying_price') or 0)
        if spot_price > 0: break
    
    if spot_price == 0:
        log_crypto("Could not determine spot price.")
        return None
    
    # 6. Lego Block 3: Strike Selection (Dynamic Offset from DB)
    offset = int(db.get_param('strike_offset', '0'))
    best_opt = find_atm_strike(spot_price, near_options, offset=offset)
    
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

def send_daily_summary():
    from main import send_telegram_msg
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
    from main import send_telegram_msg
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

def square_off_crypto():
    sync_delta_position()
    symbol = db.get_param("crypto_active_symbol", "")
    pid = db.get_param("crypto_active_product_id", "")
    entry_price = float(db.get_param("crypto_active_entry_price", "0"))
    mode = db.get_param('trade_mode', 'PAPER')
    if not symbol or not pid: return
    
    log_crypto(f"SQUARING OFF: {symbol}")
    
    # 1. Fetch Position Size from Delta to close FULL amount
    size_to_close = 1 # Default
    if mode == "LIVE":
        try:
            url = "https://api.india.delta.exchange/v2/positions"
            headers = get_delta_auth_headers("GET", "/v2/positions")
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                for p in resp.json().get('result', []):
                    if str(p.get('product_id')) == str(pid):
                        size_to_close = abs(int(float(p.get('size', 0))))
                        break
        except: pass

    # 2. Fetch Exit Price
    exit_price = 0
    chain = fetch_delta_option_chain("BTC")
    for o in chain:
        if o['symbol'] == symbol:
            exit_price = float(o.get('mark_price', 0))
            break

    if mode == "LIVE":
        try:
            url = "https://api.india.delta.exchange/v2/orders"
            # Use size_to_close instead of hardcoded 1
            payload = '{"product_id":' + str(pid) + ',"size":' + str(size_to_close) + ',"side":"sell","order_type":"market_order","close_on_trigger":true}'
            headers = get_delta_auth_headers("POST", "/v2/orders", payload)
            requests.post(url, headers=headers, data=payload, timeout=10)
        except: pass
    
    # Log Trade
    if entry_price > 0 and exit_price > 0:
        pnl = (exit_price - entry_price) * size_to_close * 0.001
        db.log_trade(symbol, "EXIT", entry_price, exit_price, pnl)
        send_daily_summary()

    db.set_param("crypto_active_symbol", "")
    db.set_param("crypto_active_entry_price", "0")

def get_dynamic_quantity(option_price):
    # Lego Block: Priority Lot Selection
    # If user manually set lot size on dashboard, use it!
    manual_lots = int(db.get_param('crypto_trade_size', '1'))
    
    try:
        url = "https://api.india.delta.exchange/v2/wallet/balances"
        headers = get_delta_auth_headers("GET", "/v2/wallet/balances")
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            balances = resp.json().get('result', [])
            total_usdt = sum(float(b.get('balance', 0)) for b in balances if b.get('asset_symbol') in ['USDT', 'DETO'])
            
            # If we have balance, we check if manual_lots is within 20% risk
            # But Dr. Saab wants STRICT lots, so we prioritize his choice
            if manual_lots > 1:
                log_crypto(f"Using Dashboard Lot Size: {manual_lots}")
                return manual_lots
            
            # Fallback to 20% rule if no manual lots set
            trade_budget = max(total_usdt * 0.20, 2.50) # Min $2.50 (~₹210)
            qty = int(trade_budget / (option_price * 0.001))
            return max(qty, 1)
    except: pass
    return manual_lots

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
                log_terminal(f"LIVE ORDER SUCCESS: {symbol} @ {price} | Expiry: {expiry} (Qty: {qty})", "TRADE")
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
        log_terminal(f"PAPER TRADE PLACED: {symbol} @ {price} | Expiry: {expiry} (Qty: {qty})", "TRADE")
        db.set_param("crypto_active_symbol", symbol)
        db.set_param("crypto_active_product_id", str(pid))
        db.set_param("crypto_active_entry_price", str(price))
    
    log_crypto(f"Execution Step Finished for {symbol}")

