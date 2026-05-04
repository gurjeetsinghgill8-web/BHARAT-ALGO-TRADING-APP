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
import traceback
from utils import log_terminal, send_telegram_msg

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


def run_recovery_mode(reason):
    """
    🆘 SELF-HEALING RECOVERY MODE
    Triggered when the system detects a catastrophic state or persistent API errors.
    1. Sends Alert. 2. Squares off everything. 3. Waits 5 mins. 4. Resumes fresh.
    """
    log_terminal(f"🆘 TRIGGERING AUTO-RECOVERY: {reason}", "ERROR")
    send_telegram_msg(f"🆘 AUTO-RECOVERY ACTIVATED!\nReason: {reason}\nAction: Closing all trades and cooling down for 5 mins.")
    
    # 1. Emergency Square Off
    delta_executor.square_off_crypto() 
    
    # 2. Reset DB to factory safe state
    db.set_param("active_call_symbol", "NONE")
    db.set_param("active_put_symbol", "NONE")
    db.set_param("signal_target", "WAIT")
    db.set_param("crypto_active_symbol", "NONE")
    
    # 3. Cooling Period
    log_terminal("System is Cooling Down... Will resume in 5 minutes.", "ALERT")
    time.sleep(300)
    log_terminal("Recovery Complete. System Resuming Normal Operation.", "START")
    send_telegram_msg("✅ Recovery Complete. System is now back online and waiting for fresh 5M signal.")

def run_janitor():
    """
    AGGRRESIVE JANITOR (The Reaper)
    Runs frequently to ensure any 'zombie' positions that should be closed are actually closed.
    Retries every 30 seconds until the screen is clean for the non-targeted side.
    """
    target = db.get_param("signal_target", "WAIT")
    delta_executor.sync_delta_position()
    
    call_active = db.get_param("active_call_symbol", "NONE") != "NONE"
    put_active = db.get_param("active_put_symbol", "NONE") != "NONE"
    
    if target == "BUY": # Only CALL should be open
        if put_active:
            log_terminal(f"JANITOR: Closing rogue PUT position {db.get_param('active_put_symbol')}...", "ALERT")
            delta_executor.square_off_crypto(db.get_param("active_put_pid"))
    elif target == "SELL": # Only PUT should be open
        if call_active:
            log_terminal(f"JANITOR: Closing rogue CALL position {db.get_param('active_call_symbol')}...", "ALERT")
            delta_executor.square_off_crypto(db.get_param("active_call_pid"))
    elif target == "WAIT": # Nothing should be open
        if call_active or put_active:
            log_terminal("JANITOR: Closing ALL positions (Signal WAIT)...", "ALERT")
            delta_executor.square_off_crypto()
            
    # --- EMERGENCY CLEANUP ---
    # If Local Lock is YES but sync sees NONE, we have a sync blindness.
    # Force a square off to clean the screen.
    if db.get_param("local_trade_active", "NO") == "YES" and not call_active and not put_active:
        log_terminal("🚨 JANITOR EMERGENCY: Local Lock active but Sync Blind. Forcing full square off...", "ALERT")
        delta_executor.square_off_crypto()

def run_crypto_sar():
    if db.get_param('crypto_algo_running', 'OFF') == 'OFF': return
    asset = db.get_param('crypto_asset', 'BTC')

    # STICKY SIGNAL RULE: Only check new entry signals on 5-minute boundaries
    now = datetime.datetime.now()
    is_boundary = (now.minute % 5 == 0)
    
    # We allow a small window (first 30s of the 5th minute) to trigger logic
    if not is_boundary:
        # Not a 5m boundary, just run janitor and skip entry logic
        run_janitor()
        return

    # To prevent multiple triggers within the same 5th minute
    if not hasattr(run_crypto_sar, "last_logic_minute"): run_crypto_sar.last_logic_minute = -1
    if run_crypto_sar.last_logic_minute == now.minute:
        # Already ran entry logic for this 5m candle
        run_janitor()
        return
        
    run_crypto_sar.last_logic_minute = now.minute
    
    st_period = int(float(db.get_param('st_period', 10)))
    st_multiplier = float(db.get_param('st_multiplier', 1.5))
    
    try:
        df, err_msg = delta_executor.fetch_delta_candles(asset, "5m", limit=100)
        if df.empty: 
            log_terminal(f"DATA ERROR: {asset} fetch failed.\nDetails: {err_msg}", "ERROR")
            return
        
        df = logic.calculate_supertrend(df, period=st_period, multiplier=st_multiplier)
        signal = logic.get_signal(df) 
        price = df['close'].iloc[-2]
        
        # 1. UPDATE TARGET EVERY TIME (So Janitor knows the truth)
        if signal != "WAIT":
            db.set_param("signal_target", "BUY" if signal == "BUY" else "SELL")
        else:
            db.set_param("signal_target", "WAIT")
        
        # 2. IMMEDIATE ENTRY IF EMPTY SCREEN
        active = db.get_param("crypto_active_symbol", "NONE")
        if active == "NONE" and not is_boundary:
            log_terminal(f"EMPTY SCREEN DETECTED: Taking immediate trade as per signal: {signal}", "TRADE")
            delta_executor.execute_crypto_trade(asset, signal)
            return

        if not is_boundary:
            run_janitor()
            return
            
        # 3. BOUNDARY SIGNAL LOGIC
        log_terminal(f"5M SIGNAL CHECK: {asset} @ ${price} | Signal: {signal}", "INFO")
        
        # Execute trade logic (Now decoupled and parallel)
        if signal != "WAIT":
            delta_executor.execute_crypto_trade(asset, signal)
        else:
            db.set_param("signal_target", "WAIT")
            run_janitor()

        # Periodic Heartbeat for Telegram (Every 30 mins)
        if not hasattr(run_crypto_sar, "last_status"): run_crypto_sar.last_status = 0
        if time.time() - run_crypto_sar.last_status > 1800:
            active = db.get_param("crypto_active_symbol", "NONE")
            mode = db.get_param('trade_mode', 'PAPER')
            send_telegram_msg(f"✅ VPS Status [{mode}]: {asset} @ ${price} | Signal: {signal} | Active: {active}")
            run_crypto_sar.last_status = time.time()

        crypto_roller.check_and_roll_crypto()
    except Exception as e:
        log_terminal(f"SAR Engine Error: {e}", "ERROR")

def main():
    # --- BULLETPROOF SINGLETON LOCK (Socket-based) ---
    # This prevents multiple instances even if file locks fail.
    try:
        lock_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        lock_socket.bind(('127.0.0.1', 47200)) # Unique port for BHARAT-ALGO
    except socket.error:
        print("🚨 CRITICAL: Bot is already running in another process. Exiting to prevent double-trading.")
        sys.exit(1)

    # Secondary File Lock (Keep for status tracking)
    lock_file = "bot.lock"
    with open(lock_file, "w") as f:
        f.write(str(os.getpid()))

    print("="*60)
    print("      🚀 BHARAT ALGOVERSE v2.0 - VPS COMMAND CENTER 🚀      ")
    print("="*60)
    
    try:
        if not db.load_secrets():
            print("CRITICAL: secrets.txt missing.")
            sys.exit(1)
            
        log_terminal("VPS System Started & Monitoring BTC....", "START")
        print("-" * 60)

        delta_executor.sync_delta_position()
        db.set_param('crypto_algo_running', 'ON')
        db.set_param('crypto_asset', 'BTC')
        
        last_status_msg = time.time()
        error_streak = 0
        
        while True:
            try:
                # 1. Run Janitor (The Cleaner) FIRST
                # This ensures the screen is clean and locks are released before checking signals
                run_janitor()
                
                # 2. Run Trading Engine (The Evaluator)
                run_crypto_sar()
                
                # 3. Check Stop Loss (The Safety)
                delta_executor.check_stop_loss()

                # 2. Check for Persistent API Errors (The 'Blindfold' issue)
                active = db.get_param('crypto_active_symbol', 'NONE')
                if active == "API_ERROR_LOCK":
                    error_streak += 1
                else:
                    error_streak = 0
                
                # If API fails 5 times in a row (approx 1.25 mins with 15s sleep), trigger recovery
                if error_streak >= 5:
                    run_recovery_mode("Persistent API Sync Failure (Blindfold)")
                    error_streak = 0
                
                # 3. Check for Position Mismatch (Hedged for too long)
                c_act = db.get_param("active_call_symbol", "NONE") != "NONE"
                p_act = db.get_param("active_put_symbol", "NONE") != "NONE"
                if c_act and p_act:
                    if not hasattr(main, "hedged_since"): main.hedged_since = time.time()
                    if time.time() - main.hedged_since > 180: # 3 minutes max hedge
                        run_recovery_mode("Position Mismatch (Hedged for too long)")
                        delattr(main, "hedged_since")
                elif hasattr(main, "hedged_since"):
                    delattr(main, "hedged_since")

                # Terminal Heartbeat
                target = db.get_param('signal_target', 'NONE')
                print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] 💓 [HEARTBEAT] Target: {target} | Active: {active}")
                
                # Telegram Status (Every 30 mins)
                if time.time() - last_status_msg > 1800:
                    mode = db.get_param('trade_mode', 'PAPER')
                    msg = f"✅ VPS Heartbeat: System Running.\n📡 Active: {active}\n🎯 Target: {target}\n💰 Mode: {mode}"
                    send_telegram_msg(msg)
                    last_status_msg = time.time()
                
                # Weekly Summary (Every Sunday at 20:00)
                now = datetime.datetime.now()
                if now.weekday() == 6 and now.hour == 20 and now.minute == 0:
                    if not hasattr(main, "last_weekly_report") or (now - main.last_weekly_report).days >= 1:
                        delta_executor.send_weekly_summary()
                        main.last_weekly_report = now
                        
                time.sleep(15) # Reduced to 15s for faster Janitor and Empty Screen checks
            except KeyboardInterrupt: break
            except Exception as e:
                log_terminal(f"Main Loop Error: {e}", "ERROR")
                time.sleep(10)
    finally:
        # Clean up lock file on exit
        if os.path.exists(lock_file):
            try: os.remove(lock_file)
            except: pass

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("="*60)
        print("🚨 CRITICAL SYSTEM CRASH 🚨")
        traceback.print_exc()
        print("="*60)
        # Try to log to terminal/telegram before dying
        try:
            from utils import log_terminal
            log_terminal(f"CRITICAL CRASH: {e}\nCheck terminal for stack trace.", "ERROR")
        except: pass
        sys.exit(1)
