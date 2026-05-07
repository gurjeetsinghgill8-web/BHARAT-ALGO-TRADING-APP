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
    timeframe = db.get_param("candle_timeframe", "5m")
    signal = logic.get_supertrend_signal(asset, timeframe=timeframe)
    db.set_param("signal_target", signal)

    # 3. Get DB Reality
    call_active = db.get_param("active_call_symbol", "NONE") != "NONE"
    put_active  = db.get_param("active_put_symbol",  "NONE") != "NONE"
    strategy_type = db.get_param("crypto_strategy", "OPTION_SELLING")

    if strategy_type == "OPTION_SELLING":
        if signal == "SELL" and put_active:
            log_terminal("JANITOR FLIP: Closing PUT to prepare for SELL entry (Selling Strategy).", "ALERT")
            delta_executor.square_off_crypto()
        elif signal == "BUY" and call_active:
            log_terminal("JANITOR FLIP: Closing CALL to prepare for BUY entry (Selling Strategy).", "ALERT")
            delta_executor.square_off_crypto()
    else:
        if signal == "SELL" and call_active:
            log_terminal("JANITOR FLIP: Closing CALL to prepare for SELL entry (Buying Strategy).", "ALERT")
            delta_executor.square_off_crypto()
        elif signal == "BUY" and put_active:
            log_terminal("JANITOR FLIP: Closing PUT to prepare for BUY entry (Buying Strategy).", "ALERT")
            delta_executor.square_off_crypto()

    # CASE: SIGNAL WAIT BUT ANYTHING OPEN
    if signal == "WAIT" and (call_active or put_active):
        log_terminal("JANITOR: Signal is WAIT. Closing all trades.", "ALERT")
        delta_executor.square_off_crypto()

    # QUANTITY GUARD: Prevent over-trading
    try:
        manual_lots = int(db.get_param('crypto_trade_size', '1'))
        total_size = 0
        for asset_sym in ["BTC", "ETH"]:
            path  = "/v2/positions"
            query = f"?underlying_asset_symbol={asset_sym}"
            url   = f"https://api.india.delta.exchange{path}{query}"
            hdrs  = delta_executor.get_delta_auth_headers("GET", path, query_string=query)
            resp  = requests.get(url, headers=hdrs, timeout=5)
            if resp.status_code == 200:
                for p in resp.json().get('result', []):
                    total_size += abs(float(p.get('size', 0)))

        if total_size > (manual_lots + 0.1):
            log_terminal(f"🚨 QUANTITY OVERLOAD: {total_size} > {manual_lots}. Clearing screen...", "ALERT")
            delta_executor.square_off_crypto()
    except:
        pass

    # ZOMBIE LOCK RECOVERY
    if db.get_param("local_trade_active", "NO") == "YES" and not call_active and not put_active:
        log_terminal("🚨 ZOMBIE LOCK: Memory was stuck. Releasing lock now.", "ALERT")
        db.set_param("local_trade_active", "NO")

# ============================================================
# IN-CODE SL/TP MONITOR  (40% SL | 100% TP with Auto-Reinvest)
# ============================================================
def check_sl_tp():
    """
    Polls open positions every loop and triggers:
    - Market EXIT if loss >= 40%   → Hard Stop Loss
    - Market EXIT if profit >= 100% → Take Profit, then immediately re-enter same direction
    """
    mode = db.get_param('trade_mode', 'PAPER')
    if mode != "LIVE":
        return

    sl_pct = float(db.get_param('sl_percent', '40'))   # default 40%
    tp_pct = float(db.get_param('tp_percent', '100'))  # default 100%

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

                print(f"[SL/TP] {symbol} | PnL: {upnl:.2f} USDT ({pnl_pct:.1f}%)")
                db.set_param("unrealized_pnl", str(upnl))

                # --- STOP LOSS HIT ---
                if pnl_pct <= -sl_pct:
                    log_terminal(f"🚨 STOP LOSS HIT: {pnl_pct:.1f}% | Exiting {symbol}...", "ALERT")
                    send_telegram_msg(f"🔴 STOP LOSS TRIGGERED: {symbol} | Loss: {pnl_pct:.1f}%")
                    delta_executor.square_off_crypto(target_pid=pid)
                    return  # Janitor will handle next entry

                # --- TAKE PROFIT HIT ---
                if pnl_pct >= tp_pct:
                    log_terminal(f"💰 TAKE PROFIT HIT: {pnl_pct:.1f}% | Booking {symbol}...", "TRADE")
                    send_telegram_msg(f"✅ TAKE PROFIT HIT: {symbol} | Profit: {pnl_pct:.1f}% 🎯")

                    # 1. Exit the winning position
                    delta_executor.square_off_crypto(target_pid=pid)
                    time.sleep(2)

                    # 2. AUTO-REINVEST: Immediately take same direction again
                    current_signal = db.get_param("signal_target", "WAIT")
                    if current_signal in ["BUY", "SELL"]:
                        log_terminal(f"♻️ AUTO-REINVEST: Re-entering {current_signal} after TP...", "TRADE")
                        send_telegram_msg(f"♻️ AUTO-REINVEST: Taking fresh {current_signal} entry after TP!")
                        time.sleep(1)
                        delta_executor.sync_delta_position()
                        db.set_param("local_trade_active", "NO")  # Release lock for re-entry
                        delta_executor.execute_crypto_trade("BTC", current_signal)
                    return

        except Exception as e:
            print(f"[SL/TP ERROR] {e}")


# ============================================================
# MAIN EVALUATOR: Evaluates signal and places entries
# ============================================================
def run_crypto_sar():
    if db.get_param('crypto_algo_running', 'OFF') == 'OFF':
        return

    asset     = "BTC"
    timeframe = db.get_param("candle_timeframe", "5m")
    signal    = logic.get_supertrend_signal(asset, timeframe=timeframe)
    db.set_param("signal_target", signal)

    # Sync with exchange
    delta_executor.sync_delta_position()
    active_call = db.get_param("active_call_symbol", "NONE")
    active_put  = db.get_param("active_put_symbol",  "NONE")
    active_any  = (active_call != "NONE" or active_put != "NONE")

    # Update dashboard symbol
    if active_call != "NONE" and active_put != "NONE":
        db.set_param("crypto_active_symbol", "HEDGED")
    elif active_call != "NONE":
        db.set_param("crypto_active_symbol", active_call)
    elif active_put != "NONE":
        db.set_param("crypto_active_symbol", active_put)
    else:
        db.set_param("crypto_active_symbol", "NONE")

    # ---- CLEAN SLATE RULE: No trade before screen is EMPTY ----
    if not active_any:
        if signal in ["BUY", "SELL"]:
            log_terminal(f"🎯 SIGNAL DETECTED: {signal}. Taking fresh entry.", "TRADE")
            num_strikes = int(db.get_param('num_strikes', '1'))
            for i in range(num_strikes):
                delta_executor.execute_crypto_trade(asset, signal)
                if num_strikes > 1:
                    time.sleep(1)
    else:
        crypto_roller.check_and_roll_crypto()


# ============================================================
# MAIN
# ============================================================
def main():
    # --- BULLETPROOF SINGLETON ---
    instance = os.environ.get('BOT_INSTANCE', 'BUYING')
    lock_port = 47202 if instance == 'SELLING' else 47200
    
    try:
        lock_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        lock_socket.bind(('127.0.0.1', lock_port))
    except socket.error:
        print(f"🚨 BOT ({instance}) ALREADY RUNNING on port {lock_port}. EXITING.")
        sys.exit(1)

    print("=" * 60)
    print("     🚀 BHARAT ALGOVERSE v3.0 - FULL AUTO 🚀     ")
    print("=" * 60)
    print("  ✅ Clean Slate Enforcement: ON")
    print("  ✅ Stop Loss @ 40%: ON")
    print("  ✅ Take Profit @ 100% + Auto-Reinvest: ON")
    print("  ✅ Multi-Strike Support: ON")
    print("  ✅ Multi-Timeframe Support: ON")
    print("=" * 60)

    if not db.load_secrets():
        sys.exit(1)

    # --- DEFAULT PARAMS (only if not already set by dashboard) ---
    if not db.get_param('st_period'):        db.set_param('st_period', '10')
    if not db.get_param('st_multiplier'):    db.set_param('st_multiplier', '1.5')
    if not db.get_param('crypto_trade_size'): db.set_param('crypto_trade_size', '1')
    if not db.get_param('sl_percent'):       db.set_param('sl_percent', '40')
    if not db.get_param('tp_percent'):       db.set_param('tp_percent', '100')
    if not db.get_param('candle_timeframe'): db.set_param('candle_timeframe', '5m')
    if not db.get_param('num_strikes'):      db.set_param('num_strikes', '1')

    log_terminal("Bharat AlgoVerse v3.0 - Full Auto Mode Started.", "START")
    send_telegram_msg("🚀 BHARAT ALGOVERSE v3.0 STARTED\n✅ SL: 40% | TP: 100% + Auto-Reinvest | Clean Slate: ON")

    print("🛡️ SCANNING FOR ORPHANED TRADES...")
    delta_executor.reconcile_bracket_orders()

    last_pulse = 0

    while True:
        try:
            run_janitor()
            run_crypto_sar()
            check_sl_tp()            # <-- In-code SL/TP monitor
            delta_executor.reconcile_bracket_orders()

            # Telegram Pulse every 30 mins
            if time.time() - last_pulse > 1800:
                timeframe = db.get_param("candle_timeframe", "5m")
                signal    = logic.get_supertrend_signal("BTC", timeframe=timeframe)
                active    = db.get_param('crypto_active_symbol', 'NONE')
                upnl      = db.get_param('unrealized_pnl', '0')
                send_telegram_msg(
                    f"✅ BHARAT PULSE v3.0\n"
                    f"Signal: {signal} | Active: {active}\n"
                    f"Live PnL: ${upnl}\n"
                    f"Timeframe: {timeframe}"
                )
                last_pulse = time.time()

            time.sleep(15)

        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Main Loop Error: {e}")
            traceback.print_exc()
            time.sleep(10)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("=" * 60)
        print("🚨 CRITICAL SYSTEM CRASH 🚨")
        traceback.print_exc()
        print("=" * 60)
        sys.exit(1)
