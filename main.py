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
# MAGICAL LINE ENGINE: 6:00 PM Anchor Logic
# ============================================================
def check_magical_anchor():
    """
    Sets the Anchor Point (Magical Line) at 6:00 PM (18:00 IST).
    The anchor stays valid for 24 hours.
    """
    now = datetime.datetime.now()
    magical_line = float(db.get_param("magical_line", "0"))
    last_anchor_date = db.get_param("last_anchor_date", "")
    today_str = now.strftime("%Y-%m-%d")

    # 1. Daily 6:00 PM Update Rule
    if now.hour == 18 and now.minute == 0 and last_anchor_date != today_str:
        log_terminal("🕒 6:00 PM REACHED: Setting New Magical Line Anchor...", "START")
        try:
            df, _ = delta_executor.fetch_delta_candles("BTC", "1m", limit=1)
            if not df.empty:
                new_anchor = float(df['close'].iloc[-1])
                db.set_param("magical_line", str(new_anchor))
                db.set_param("last_anchor_date", today_str)
                send_telegram_msg(f"📍 *NEW MAGICAL ANCHOR SET*: ${new_anchor:,.2f}\nValid for next 24 hours.")
                return new_anchor
        except Exception as e:
            log_terminal(f"Anchor Update Error: {e}", "ERROR")

    # 2. Cold Start: If no anchor exists, set one immediately
    if magical_line == 0:
        log_terminal("❄️ COLD START: No Magical Line found. Anchoring now...", "START")
        df, _ = delta_executor.fetch_delta_candles("BTC", "1m", limit=1)
        if not df.empty:
            new_anchor = float(df['close'].iloc[-1])
            db.set_param("magical_line", str(new_anchor))
            return new_anchor
            
    return magical_line

def run_crypto_magical():
    if db.get_param('crypto_algo_running', 'OFF') == 'OFF':
        return

    # 1. Get Core Data
    magical_line = check_magical_anchor()
    if magical_line == 0:
        return

    try:
        df, _ = delta_executor.fetch_delta_candles("BTC", "1m", limit=1)
        if df.empty: return
        ltp = float(df['close'].iloc[-1])
    except: return

    # 2. Determine Signal (Magical Rule)
    # Price > Magical Line => BUY (Bullish -> Sell Put)
    # Price < Magical Line => SELL (Bearish -> Sell Call)
    signal = "BUY" if ltp > magical_line else "SELL"
    db.set_param("signal_target", signal)

    # 3. Sync & State Management
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

    # 4. Entry Logic (Clean Slate + Trend Following)
    if not active_any:
        log_terminal(f"🎯 MAGICAL SIGNAL: {signal} (LTP: {ltp} vs Anchor: {magical_line}). Taking fresh entry.", "TRADE")
        num_strikes = int(db.get_param('num_strikes', '1'))
        for i in range(num_strikes):
            delta_executor.execute_crypto_trade("BTC", signal)
            if num_strikes > 1: time.sleep(1)
    else:
        # Check for Flip (Price crossed Magical Line)
        pos_type = "BUY" if active_put != "NONE" else "SELL" # Because SELL PUT is BUY Signal
        if signal != pos_type:
            log_terminal(f"🔄 TREND REVERSAL: Price crossed Magical Line. Squaring off to flip.", "ALERT")
            send_telegram_msg(f"🔄 TREND REVERSAL: LTP {ltp} crossed Anchor {magical_line}. Flipping position!")
            delta_executor.square_off_crypto()
            time.sleep(2)
            # Re-entry will happen on next loop

# ============================================================
# MAIN
# ============================================================
def main():
    # --- BULLETPROOF SINGLETON ---
    try:
        lock_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        lock_socket.bind(('127.0.0.1', 47200))
    except socket.error:
        print("🚨 BOT ALREADY RUNNING. EXITING.")
        sys.exit(1)

    print("=" * 60)
    print("     🚀 BHARAT ALGOVERSE v3.0 - MAGICAL LINE 🚀     ")
    print("=" * 60)
    print("  ✅ Strategy: Magical Line (6 PM Anchor)")
    print("  ✅ Stop Loss @ 40%: ON")
    print("  ✅ Clean Slate: ON")
    print("=" * 60)

    if not db.load_secrets():
        sys.exit(1)

    log_terminal("Bharat AlgoVerse v3.0 - Magical Line Mode Started.", "START")
    send_telegram_msg("🚀 BHARAT ALGOVERSE STARTED\n📍 Strategy: Magical Line (6 PM Anchor)\n✅ SL: 40% | Clean Slate: ON")

    last_pulse = 0

    while True:
        try:
            run_janitor()
            run_crypto_magical()
            check_sl_tp()
            delta_executor.reconcile_bracket_orders()

            # Telegram Pulse every 30 mins
            if time.time() - last_pulse > 1800:
                magical_line = float(db.get_param("magical_line", "0"))
                active = db.get_param('crypto_active_symbol', 'NONE')
                upnl = db.get_param('unrealized_pnl', '0')
                send_telegram_msg(
                    f"✅ BHARAT PULSE (MAGICAL)\n"
                    f"Anchor: ${magical_line:,.0f} | Active: {active}\n"
                    f"Live PnL: ${upnl}"
                )
                last_pulse = time.time()

            time.sleep(30) # V3 Magical Loop

        except KeyboardInterrupt: break
        except Exception as e:
            print(f"Main Loop Error: {e}")
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
