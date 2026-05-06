import time
import datetime
import requests
import pandas as pd
import db
import logic
import delta_executor
import crypto_roller
import os
import sys
import socket
import traceback
from utils import log_terminal, send_telegram_msg

# --- FORCE IPv4 GLOBALLY ---
import requests.packages.urllib3.util.connection as urllib3_cn
def allowed_gai_family():
    return socket.AF_INET
urllib3_cn.allowed_gai_family = allowed_gai_family

def run_janitor():
    """
    STABLE 2.0 RECONCILER
    """
    # 1. Sync Reality from Exchange
    delta_executor.sync_delta_position()
    
    # 2. Get Current Signal
    asset = "BTC"
    signal = logic.get_supertrend_signal(asset)
    db.set_param("signal_target", signal) # Update Dashboard
    
    # 3. Get DB Reality
    call_active = db.get_param("active_call_symbol", "NONE") != "NONE"
    put_active = db.get_param("active_put_symbol", "NONE") != "NONE"
    
    # CASE: SIGNAL SELL BUT CALL OPEN
    if signal == "SELL" and call_active:
        log_terminal("JANITOR FLIP: Closing CALL to prepare for SELL entry.", "ALERT")
        delta_executor.square_off_crypto()
        
    # CASE: SIGNAL BUY BUT PUT OPEN
    elif signal == "BUY" and put_active:
        log_terminal("JANITOR FLIP: Closing PUT to prepare for BUY entry.", "ALERT")
        delta_executor.square_off_crypto()

    # CASE: SIGNAL WAIT BUT ANYTHING OPEN
    elif signal == "WAIT" and (call_active or put_active):
        log_terminal("JANITOR: Signal is WAIT. Closing all trades.", "ALERT")
        delta_executor.square_off_crypto()

    # CASE: QUANTITY GUARD (3 Lots Limit)
    try:
        manual_lots = int(db.get_param('crypto_trade_size', '3'))
        total_size = 0
        path = "/v2/positions"
        query = "?underlying_asset_symbol=BTC"
        url = f"https://api.india.delta.exchange{path}{query}"
        headers = delta_executor.get_delta_auth_headers("GET", path, query_string=query)
        resp = requests.get(url, headers=headers, timeout=5)
        if resp.status_code == 200:
            for p in resp.json().get('result', []):
                total_size += abs(float(p.get('size', 0)))
        
        if total_size > (manual_lots + 0.1):
            log_terminal(f"🚨 QUANTITY OVERLOAD: {total_size} > {manual_lots}. Clearing screen...", "ALERT")
            delta_executor.square_off_crypto()
    except: pass

    # CASE: ZOMBIE LOCK RECOVERY
    if db.get_param("local_trade_active", "NO") == "YES" and not call_active and not put_active:
        log_terminal("🚨 ZOMBIE LOCK: Memory was stuck. Releasing lock now.", "ALERT")
        db.set_param("local_trade_active", "NO")

def run_crypto_sar():
    """
    STABLE 2.0 EVALUATOR
    """
    if db.get_param('crypto_algo_running', 'OFF') == 'OFF': return
    
    # 1. Sync & Check Signal
    asset = "BTC"
    signal = logic.get_supertrend_signal(asset)
    db.set_param("signal_target", signal) # Update Dashboard
    
    # 2. Check Reality
    delta_executor.sync_delta_position()
    active_call = db.get_param("active_call_symbol", "NONE")
    active_put = db.get_param("active_put_symbol", "NONE")
    active_any = (active_call != "NONE" or active_put != "NONE")
    
    # Update Dashboard Status
    if active_call != "NONE" and active_put != "NONE":
        db.set_param("crypto_active_symbol", "HEDGED")
    elif active_call != "NONE":
        db.set_param("crypto_active_symbol", active_call)
    elif active_put != "NONE":
        db.set_param("crypto_active_symbol", active_put)
    else:
        db.set_param("crypto_active_symbol", "NONE")

    # 3. Decision
    if not active_any:
        if signal in ["BUY", "SELL"]:
            log_terminal(f"🎯 SIGNAL DETECTED: {signal}. Taking fresh entry.", "TRADE")
            delta_executor.execute_crypto_trade(asset, signal)
    else:
        # Maintenance
        crypto_roller.check_and_roll_crypto()

def main():
    # --- BULLETPROOF SINGLETON ---
    try:
        lock_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        lock_socket.bind(('127.0.0.1', 47200))
    except socket.error:
        print("🚨 BOT ALREADY RUNNING. EXITING.")
        sys.exit(1)

    print("="*60)
    print("      🚀 BHARAT ALGOVERSE v2.0 - STABLE SYSTEM 🚀      ")
    print("="*60)
    
    if not db.load_secrets(): sys.exit(1)
    
    db.set_param('st_period', '10')
    db.set_param('st_multiplier', '1.5')
    db.set_param('crypto_trade_size', '1')
    
    log_terminal("Stable System 2.0 Started.", "START")

    last_pulse = 0
    
    while True:
        try:
            run_janitor()
            run_crypto_sar()
            delta_executor.check_stop_loss()
            delta_executor.reconcile_bracket_orders()
            
            if time.time() - last_pulse > 1800:
                signal = logic.get_supertrend_signal("BTC")
                active = db.get_param('crypto_active_symbol', 'NONE')
                send_telegram_msg(f"✅ STABLE 2.0 PULSE: {signal} | Active: {active}")
                last_pulse = time.time()

            time.sleep(15)
        except KeyboardInterrupt: break
        except Exception as e:
            print(f"Main Loop Error: {e}")
            traceback.print_exc()
            time.sleep(10)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("="*60)
        print("🚨 CRITICAL SYSTEM CRASH 🚨")
        traceback.print_exc()
        print("="*60)
        sys.exit(1)
