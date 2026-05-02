import time
import datetime
import requests
import pandas as pd
import db
import logic
import executor
import delta_executor
import crypto_roller
import os
import sys
import socket

# --- FORCE IPv4 GLOBALLY (To match user's whitelist) ---
import requests.packages.urllib3.util.connection as urllib3_cn
def allowed_gai_family():
    return socket.AF_INET
urllib3_cn.allowed_gai_family = allowed_gai_family

# --- RISK CONFIG ---
DAILY_LOSS_LIMIT_PCT = 2.0

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
                            df = pd.DataFrame(data)
                            df = df.rename(columns={'o': 'open', 'h': 'high', 'l': 'low', 'c': 'close', 'v': 'volume'})
                            for col in ['open', 'high', 'low', 'close', 'volume']:
                                df[col] = pd.to_numeric(df[col])
                            return df, ""
                    else:
                        last_error = f"HTTP {resp.status_code} from {base} ({resp.text[:50]})"
                except Exception as e: 
                    last_error = str(e)
                    continue
    print(f"[DEBUG] Last Fetch Error: {last_error}")
    return pd.DataFrame(), last_error

def send_telegram_msg(message):
    bot_token = db.get_param('telegram_bot_token', '')
    chat_id = db.get_param('telegram_chat_id', '')
    if bot_token and chat_id:
        try:
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            payload = {"chat_id": chat_id, "text": f"🚀 BHARAT ALGO (VPS):\n{message}"}
            requests.post(url, json=payload, timeout=5)
        except: pass

def log_terminal(msg, type="INFO"):
    timestamp = datetime.datetime.now().strftime('%H:%M:%S')
    icon = "🔹"
    if type == "TRADE": icon = "🟢"
    if type == "ALERT": icon = "🚨"
    if type == "ERROR": icon = "❌"
    
    full_msg = f"[{timestamp}] {icon} {msg}"
    print(full_msg)
    
    if type in ["TRADE", "ALERT", "ERROR", "START"]:
        send_telegram_msg(full_msg)

def run_crypto_sar():
    if db.get_param('crypto_algo_running', 'OFF') == 'OFF': return
    asset = db.get_param('crypto_asset', 'BTC')

    # Use DB parameters or defaults (Matches Aggressive SAR requirements)
    st_period = int(float(db.get_param('st_period', 10)))
    st_multiplier = float(db.get_param('st_multiplier', 1.5))
    
    try:
        df, err_msg = fetch_delta_candles(asset, "5m", limit=100)
        if df.empty: 
            log_terminal(f"DATA ERROR: {asset} fetch failed.\nDetails: {err_msg}", "ERROR")
            return
        
        df = logic.calculate_supertrend(df, period=st_period, multiplier=st_multiplier)
        dir_col = f"SUPERTd_{st_period}_{st_multiplier}"
        last_st = df[dir_col].iloc[-1]
        price = df['close'].iloc[-1]
        
        # Periodic Signal Update in Terminal
        print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Signal: {'BULL' if last_st==1 else 'BEAR'} | Price: {price}")
        
        delta_executor.sync_delta_position()
        active_symbol = db.get_param("crypto_active_symbol", "")
        
        has_bullish = ("-C-" in active_symbol) or ("CALL" in active_symbol.upper())
        has_bearish = ("-P-" in active_symbol) or ("PUT" in active_symbol.upper())
        has_nothing = not active_symbol or "PAPER" in active_symbol

        if last_st == 1:
            if has_nothing or has_bearish:
                log_terminal(f"SAR FLIP: BUY BTC @ ${price}", "TRADE")
                delta_executor.execute_crypto_trade(asset, "BUY")
        elif last_st == -1:
            if has_nothing or has_bullish:
                log_terminal(f"SAR FLIP: SELL BTC @ ${price}", "TRADE")
                delta_executor.execute_crypto_trade(asset, "SELL")

        crypto_roller.check_and_roll_crypto()
    except Exception as e:
        log_terminal(f"SAR Engine Error: {e}", "ERROR")

def main():
    print("="*60)
    print("      🚀 BHARAT ALGOVERSE v2.0 - VPS COMMAND CENTER 🚀      ")
    print("="*60)
    
    if not db.load_secrets():
        print("CRITICAL: secrets.txt missing. Check GitHub report.")
        sys.exit(1)
        
    log_terminal("VPS System Started & Monitoring BTC....", "START")
    print("-" * 60)

    delta_executor.sync_delta_position()
    db.set_param('crypto_algo_running', 'ON')
    db.set_param('crypto_asset', 'BTC')
    
    last_heartbeat = time.time()
    last_status_msg = time.time()
    
    while True:
        try:
            executor.check_and_roll_nifty()
            run_crypto_sar()
            
            # Terminal Heartbeat (Every 1 min)
            if time.time() - last_heartbeat > 60:
                print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] [HEARTBEAT] VPS Active. Monitoring {db.get_param('crypto_active_symbol', 'NONE')}")
                last_heartbeat = time.time()
            
            # Telegram Status Report (Every 30 mins) - "Constant Visibility"
            if time.time() - last_status_msg > 1800:
                active = db.get_param('crypto_active_symbol', 'NONE')
                msg = f"✅ VPS Heartbeat: System Running.\n📡 Monitoring: {active}\n💰 Mode: {db.get_param('trade_mode', 'PAPER')}"
                send_telegram_msg(msg)
                last_status_msg = time.time()
                
            time.sleep(10)
        except KeyboardInterrupt: break
        except Exception as e:
            log_terminal(f"Master Error: {e}", "ERROR")
            time.sleep(10)

if __name__ == "__main__":
    main()
