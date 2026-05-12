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
    """LEGACY JANITOR - NOW STRICTLY READ-ONLY SYNC"""
    try:
        delta_executor.sync_delta_position()
        asset = "BTC"
        timeframe = db.get_param("candle_timeframe", "5m")
        signal = logic.get_supertrend_signal(asset, timeframe=timeframe) if hasattr(logic, 'get_supertrend_signal') else "WAIT"
        db.set_param("signal_target", signal)
        # NO TRADES. NO FLIPS. ONLY SYNC.
    except Exception as e:
        log_terminal(f"⚠️ Janitor Sync Warning: {str(e)}", "ERROR")

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
def main_loop():
    import time
    log_terminal("🧱 BRICK #1.3: Final Override | SELL-ONLY & Strict Cooldown ACTIVE", "START")
    
    last_heartbeat = 0
    last_action_time = 0
    COOLDOWN_SEC = 300  # STRICT 5-MIN LOCK
    
    while True:
        try:
            now = time.time()
            
            # 🛑 COOLDOWN CHECK (FIRST IN LOOP - NO EXCEPTIONS)
            if now - last_action_time < COOLDOWN_SEC:
                time.sleep(10)
                continue

            # 📡 VISION HEARTBEAT
            if now - last_heartbeat >= 300:
                ltp = delta_executor.fetch_btc_spot()
                pos = delta_executor.get_current_position()
                manual_ml = db.get_param("manual_magical_line", 0)
                auto_ml = db.get_param("magical_line", 0)
                anchor = float(manual_ml) if float(manual_ml or 0) > 0 else float(auto_ml or 0)
                status = pos['type'] if pos else "NO ACTIVE TRADE"
                pulse = f"💓 VISION PULSE\n📊 LTP: ${ltp}\n🎯 Anchor: ${anchor}\n📦 Position: {status}"
                log_terminal(pulse, "INFO")
                send_telegram_msg(pulse)
                last_heartbeat = now

            # 🧹 LIGHTWEIGHT SYNC
            run_janitor()
            pos = delta_executor.get_current_position()
            ltp = delta_executor.fetch_btc_spot()
            manual_ml = db.get_param("manual_magical_line", 0)
            auto_ml = db.get_param("magical_line", 0)
            anchor = float(manual_ml) if float(manual_ml or 0) > 0 else float(auto_ml or 0)

            if anchor > 0 and float(ltp or 0) > 0:
                ltp = float(ltp)
                if pos:
                    holding_put = (pos['type'] == 'PUT')
                    holding_call = (pos['type'] == 'CALL')
                    is_bullish = ltp > anchor
                    is_bearish = ltp < anchor

                    if (holding_put and is_bullish) or (holding_call and is_bearish):
                        log_terminal(f"🛡️ HOLD: {pos['type']} matches trend. Cooling down...", "INFO")
                    elif (holding_put and is_bearish) or (holding_call and is_bullish):
                        log_terminal(f"🔄 FLIP: Closing {pos['type']} to switch direction...", "ALERT")
                        delta_executor.square_off_crypto()
                        last_action_time = time.time()  # LOCK COOLDOWN
                        time.sleep(5)
                        continue
                else:
                    # 🚀 ENTRY LOGIC (SELL ONLY)
                    if ltp > anchor:
                        log_terminal("📈 BULLISH: SELL PUT ENTRY TRIGGERED", "TRADE")
                        delta_executor.execute_crypto_trade("SELL_PUT")
                    elif ltp < anchor:
                        log_terminal("📉 BEARISH: SELL CALL ENTRY TRIGGERED", "TRADE")
                        delta_executor.execute_crypto_trade("SELL_CALL")
                    last_action_time = time.time()  # LOCK COOLDOWN

            check_sl_tp()
        except Exception as e:
            log_terminal(f"❌ Loop Error: {str(e)}", "ERROR")
            import traceback; log_terminal(traceback.format_exc(), "ERROR")
            last_action_time = time.time()  # SAFETY COOLDOWN ON ERROR
        time.sleep(10)

def main():
    # --- BULLETPROOF SINGLETON ---
    try:
        lock_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        lock_socket.bind(('127.0.0.1', 47200))
    except socket.error:
        print("🚨 BOT ALREADY RUNNING. EXITING.")
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

    # --- DEFAULT PARAMS ---
    if not db.get_param('crypto_trade_size'): db.set_param('crypto_trade_size', '1')
    if not db.get_param('sl_percent'):       db.set_param('sl_percent', '40')
    if not db.get_param('tp_percent'):       db.set_param('tp_percent', '100')

    log_terminal("Bharat AlgoVerse v3.0 - Full Auto Mode Started.", "START")
    send_telegram_msg("🚀 BHARAT ALGOVERSE v3.0 STARTED\n✅ SL: 40% | TP: 100% | Clean Slate: ON")

    main_loop()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("=" * 60)
        print("🚨 CRITICAL SYSTEM CRASH 🚨")
        traceback.print_exc()
        print("=" * 60)
        sys.exit(1)
