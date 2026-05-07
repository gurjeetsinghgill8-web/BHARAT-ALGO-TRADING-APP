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
import json
import config
from utils import log_terminal, send_telegram_msg

# --- FORCE IPv4 GLOBALLY ---
import requests.packages.urllib3.util.connection as urllib3_cn
def allowed_gai_family():
    return socket.AF_INET
urllib3_cn.allowed_gai_family = allowed_gai_family

# ============================================================
# JANITOR: Syncs reality, enforces Clean Slate, guards quantity
# ============================================================
def run_janitor():
    # 1. Sync Reality from Exchange
    delta_executor.sync_delta_position()

    # 2. Get Current Signal (from configured timeframe)
    asset = "BTC"
    timeframe = config.TIMEFRAME
    signal = logic.get_supertrend_signal(asset, timeframe=timeframe)
    db.set_param("signal_target", signal)

    # 3. Get DB Reality
    call_active = db.get_param("active_call_symbol", "NONE") != "NONE"
    put_active  = db.get_param("active_put_symbol",  "NONE") != "NONE"

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

    # ZOMBIE LOCK RECOVERY
    if db.get_param("local_trade_active", "NO") == "YES" and not call_active and not put_active:
        db.set_param("local_trade_active", "NO")

# ============================================================
# IN-CODE SL/TP MONITOR  (40% SL | 100% TP)
# ============================================================
def check_sl_tp():
    mode = db.get_param('trade_mode', 'PAPER')
    if mode != "LIVE":
        return

    sl_pct = 40.0
    tp_pct = 100.0

    for asset_sym in ["BTC", "ETH"]:
        try:
            path  = "/v2/positions"
            query = f"?underlying_asset_symbol={asset_sym}"
            url   = f"https://api.india.delta.exchange{path}{query}"
            hdrs  = delta_executor.get_delta_auth_headers("GET", path, query_string=query)
            resp  = requests.get(url, headers=hdrs, timeout=10)

            if resp.status_code != 200:
                continue

            for p in resp.json().get('result', []):
                size = abs(float(p.get('size', 0)))
                if size == 0:
                    continue

                upnl        = float(p.get('unrealized_pnl', 0))
                entry_val   = float(p.get('entry_value', 1) or 1)
                pid         = p.get('product_id')
                symbol      = p.get('product', {}).get('symbol', str(pid))
                pnl_pct     = (upnl / abs(entry_val)) * 100

                # --- STOP LOSS HIT ---
                if pnl_pct <= -sl_pct:
                    log_terminal(f"🚨 STOP LOSS HIT: {pnl_pct:.1f}% | Exiting {symbol}...", "ALERT")
                    send_telegram_msg(f"🔴 STOP LOSS TRIGGERED: {symbol} | Loss: {pnl_pct:.1f}%")
                    delta_executor.square_off_crypto(target_pid=pid)
                    return

                # --- TAKE PROFIT HIT ---
                if pnl_pct >= tp_pct:
                    log_terminal(f"💰 TAKE PROFIT HIT: {pnl_pct:.1f}% | Booking {symbol}...", "TRADE")
                    send_telegram_msg(f"✅ TAKE PROFIT HIT: {symbol} | Profit: {pnl_pct:.1f}% 🎯")
                    delta_executor.square_off_crypto(target_pid=pid)
                    return

        except Exception as e:
            print(f"[SL/TP ERROR] {e}")

# ============================================================
# MAIN EVALUATOR: HUNTER MODE (Immediate Entry)
# ============================================================
def run_crypto_sar():
    # Forced ON
    db.set_param('crypto_algo_running', 'ON')

    asset     = "BTC"
    timeframe = config.TIMEFRAME
    signal    = logic.get_supertrend_signal(asset, timeframe=timeframe)
    db.set_param("signal_target", signal)

    # Sync with exchange
    delta_executor.sync_delta_position()
    active_call = db.get_param("active_call_symbol", "NONE")
    active_put  = db.get_param("active_put_symbol",  "NONE")
    active_any  = (active_call != "NONE" or active_put != "NONE")

    # ---- HUNTER MODE RULE: Entry if Empty ----
    if not active_any:
        if signal in ["BUY", "SELL"]:
            log_terminal(f"🎯 HUNTER MODE: Signal {signal}. Taking fresh 6-lot entry.", "TRADE")
            send_telegram_msg(f"🚨 HUNTER MODE: Forcing Immediate {signal} Entry.")
            delta_executor.execute_crypto_trade(asset, signal)
    else:
        # Check if we need to roll (V3 feature)
        crypto_roller.check_and_roll_crypto()

# ============================================================
# MAIN
# ============================================================
def main():
    # Singleton lock
    try:
        lock_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        lock_socket.bind(('127.0.0.1', 47200))
    except socket.error:
        print("🚨 BOT ALREADY RUNNING. EXITING.")
        sys.exit(1)

    print("=" * 60)
    print("     🚀 BHARAT ALGOVERSE v3.0 - STABLE MASTER 🚀     ")
    print("=" * 60)
    print(f"  ✅ Strategy: PURE BUYING (V3)")
    print(f"  ✅ Timeframe: {config.TIMEFRAME}")
    print(f"  ✅ Lot Size: {config.CRYPTO_LOT_SIZE}")
    print("=" * 60)

    if not db.load_secrets():
        print("❌ SECRETS.TXT MISSING!")
        sys.exit(1)

    # Reset locks
    db.set_param("local_trade_active", "NO")
    db.set_param("order_pending", "NO")
    
    # Defaults
    db.set_param('st_period', '10')
    db.set_param('st_multiplier', '1.5')
    db.set_param('crypto_trade_size', str(config.CRYPTO_LOT_SIZE))
    db.set_param('candle_timeframe', config.TIMEFRAME)

    log_terminal("Bharat AlgoVerse V3 Stable Started.", "START")
    send_telegram_msg("🚀 BHARAT V3 STABLE STARTED\n✅ Pure Buying | 5M | 6 Lots | Hunter Mode: ON")

    while True:
        try:
            run_janitor()
            run_crypto_sar()
            check_sl_tp()
            time.sleep(15)
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Main Loop Error: {e}")
            time.sleep(10)

if __name__ == "__main__":
    main()
