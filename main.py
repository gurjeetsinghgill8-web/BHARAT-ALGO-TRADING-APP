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
# Daily loss limit removed per user request for aggressive options trading.


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
        
        # Lego Block 1: Whipsaw Protection (Signal Logic)
        signal = logic.get_signal(df) # Uses iloc[-2] internally
        price = df['close'].iloc[-2]
        
        # Periodic Signal Update in Terminal
        print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Closed Candle Signal: {signal} | Price: {price}")
        
        delta_executor.sync_delta_position()
        active_symbol = db.get_param("crypto_active_symbol", "")
        mode = db.get_param('trade_mode', 'PAPER')
        
        has_bullish = active_symbol.startswith("C-") or "-C-" in active_symbol or "CALL" in active_symbol.upper()
        has_bearish = active_symbol.startswith("P-") or "-P-" in active_symbol or "PUT" in active_symbol.upper()
        has_nothing = not active_symbol or active_symbol == "NONE"

        # Force Initial Entry Logic
        if has_nothing and signal != "WAIT":
            log_terminal(f"INITIAL ENTRY: {asset} is {signal}. Executing Trade.", "TRADE")
            delta_executor.execute_crypto_trade(asset, signal)
        elif signal == "BUY" and has_bearish:
            log_terminal(f"SAR FLIP: BUY BTC @ ${price}", "TRADE")
            delta_executor.execute_crypto_trade(asset, "BUY")
        elif signal == "SELL" and has_bullish:
            log_terminal(f"SAR FLIP: SELL BTC @ ${price}", "TRADE")
            delta_executor.execute_crypto_trade(asset, "SELL")

        # Periodic Heartbeat for Telegram (Every 30 mins)
        if not hasattr(run_crypto_sar, "last_status"): run_crypto_sar.last_status = 0
        if time.time() - run_crypto_sar.last_status > 1800:
            send_telegram_msg(f"✅ VPS Status Report [{mode}]: {asset} @ ${price} | Signal: {signal} | Position: {active_symbol or 'NONE'}")
            run_crypto_sar.last_status = time.time()

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
            # MASTER INTEGRATION LOOP
            # 1. Handle Nifty/Rollover logic if any
            executor.check_and_roll_nifty()
            
            # 2. Run Crypto SAR Engine (Blocks 1, 2, 3 integrated here)
            run_crypto_sar()
            
            # 3. Terminal Heartbeat (Lego Block 4)
            print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] 💓 [HEARTBEAT] VPS System Active. Monitoring {db.get_param('crypto_active_symbol', 'NONE')}")
            
            # 4. Telegram Status Report (Every 30 mins)
            if time.time() - last_status_msg > 1800:
                active = db.get_param('crypto_active_symbol', 'NONE')
                msg = f"✅ VPS Heartbeat: System Running.\n📡 Monitoring: {active}\n💰 Mode: {db.get_param('trade_mode', 'PAPER')}"
                send_telegram_msg(msg)
                last_status_msg = time.time()
                
            # 60-second cycle as requested for Lego Block 4
            time.sleep(60) 
        except KeyboardInterrupt: break
        except Exception as e:
            log_terminal(f"Master Error: {e}", "ERROR")
            time.sleep(10)

if __name__ == "__main__":
    main()
