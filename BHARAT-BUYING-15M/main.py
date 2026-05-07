import time
import db
import logic
import delta_executor
import os
import sys
import socket
import config
from utils import log_terminal, send_telegram_msg

# --- FORCE IPv4 GLOBALLY ---
import requests.packages.urllib3.util.connection as urllib3_cn
def allowed_gai_family():
    return socket.AF_INET
urllib3_cn.allowed_gai_family = allowed_gai_family

def run_janitor():
    """Syncs reality and ensures clean slate."""
    delta_executor.sync_delta_position()
    asset = "BTC"
    timeframe = config.TIMEFRAME
    signal = logic.get_supertrend_signal(asset, timeframe=timeframe)
    db.set_param("signal_target", signal)

    call_active = db.get_param("active_call_symbol", "NONE") != "NONE"
    put_active  = db.get_param("active_put_symbol",  "NONE") != "NONE"
    
    # Clean Slate Flip: If signal is opposite, close immediately
    if signal == "SELL" and call_active:
        log_terminal(f"🔄 JANITOR FLIP: Signal is {signal} but I have a CALL. Closing!", "ALERT")
        delta_executor.square_off_crypto()
    elif signal == "BUY" and put_active:
        log_terminal(f"🔄 JANITOR FLIP: Signal is {signal} but I have a PUT. Closing!", "ALERT")
        delta_executor.square_off_crypto()
    
    # Signal Wait: If signal is WAIT, close everything
    if signal == "WAIT" and (call_active or put_active):
        log_terminal("JANITOR: Signal is WAIT. Closing all trades.", "ALERT")
        delta_executor.square_off_crypto()

def run_crypto_engine():
    """Evaluates signal and executes immediate entry if empty."""
    asset = "BTC"
    signal = logic.get_supertrend_signal(asset, timeframe=config.TIMEFRAME)
    
    delta_executor.sync_delta_position()
    active_sym = db.get_param("crypto_active_symbol", "NONE")
    
    # --- IMMEDIATE ENTRY RULE (CRITICAL) ---
    # If active position is Empty/None AND signal is BUY/SELL, execute IMMEDIATELY.
    if active_sym in ["NONE", "None", "", "0", 0, None]:
        if signal in ["BUY", "SELL"]:
            log_terminal(f"🎯 HUNTER MODE: Signal is {signal}. Executing Immediate Entry.", "TRADE")
            delta_executor.execute_crypto_trade(asset, signal)

def main():
    # Singleton check using a port derived from the app port
    lock_port = 40000 + config.PORT 
    try:
        lock_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        lock_socket.bind(('127.0.0.1', lock_port))
    except:
        print(f"🚨 BOT ALREADY RUNNING (Lock Port {lock_port}). EXITING.")
        sys.exit(1)

    print("=" * 60)
    print(f"🚀 BHARAT BUYING ENGINE ({config.TIMEFRAME}) - SURGICAL OVERHAUL 🚀")
    print(f"   Port: {config.PORT} | TF: {config.TIMEFRAME} | DB: {config.DB_NAME}")
    print("=" * 60)

    if not db.load_secrets(): 
        print("❌ CRITICAL: Could not load secrets.txt")
        sys.exit(1)
    
    # Reset stale locks on startup
    db.set_param("local_trade_active", "NO")
    db.set_param("crypto_active_symbol", "NONE")
    
    log_terminal(f"Bharat Buying {config.TIMEFRAME} Engine Started.", "START")
    send_telegram_msg(f"🚀 {config.TELEGRAM_PREFIX} Engine Started\nMode: Buying | TF: {config.TIMEFRAME} | Deep ITM: {getattr(config, 'DEEP_ITM_LEVEL', 0)}")

    while True:
        try:
            run_janitor()
            run_crypto_engine()
            time.sleep(15) # Pulse check every 15 seconds
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Main Loop Error: {e}")
            time.sleep(10)

if __name__ == "__main__":
    main()
