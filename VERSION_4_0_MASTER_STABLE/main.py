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
# STEP 7 — GLOBAL COOLDOWN LOCK (5-minute)
# After ANY trade (entry/exit/flip), bot freezes for 300s
# ============================================================
_last_trade_time = 0   # Unix timestamp of last trade action

def record_trade_action(reason=""):
    """Call this after every entry, exit, or flip to start the cooldown."""
    global _last_trade_time
    _last_trade_time = time.time()
    log_terminal(f"⏱️ COOLDOWN STARTED (5 min) — Reason: {reason}", "INFO")

def is_in_cooldown():
    """Returns True if still within 300-second cooldown window."""
    elapsed = time.time() - _last_trade_time
    if elapsed < 300:
        remaining = int(300 - elapsed)
        log_terminal(f"🧊 COOLDOWN ACTIVE: {remaining}s remaining. Skipping this cycle.", "INFO")
        return True
    return False

# ============================================================
# STEP 9 — LTP FETCHER (for heartbeat + reasoning alerts)
# ============================================================
def get_btc_ltp():
    """
    Fetches live BTC spot price from Delta Exchange.
    Uses the SAME working approach as fetch_delta_option_chain in delta_executor.py
    — proven to work on this VPS.
    """
    base_urls = [
        "https://api.india.delta.exchange",
        "https://api.delta.exchange",
    ]
    for base in base_urls:
        try:
            # Method 1: BTC options tickers — spot_price is always in these (PROVEN WORKING)
            resp = requests.get(
                f"{base}/v2/tickers?underlying_asset_symbols=BTC",
                timeout=5
            )
            if resp.status_code == 200:
                for t in resp.json().get("result", []):
                    sp = float(t.get("spot_price") or t.get("underlying_price") or 0)
                    if sp > 0:
                        return sp

            # Method 2: Direct perpetual ticker
            for sym in ["BTCUSDT", "BTCUSD", "BTC_USDT"]:
                resp2 = requests.get(f"{base}/v2/tickers/{sym}", timeout=5)
                if resp2.status_code == 200:
                    result = resp2.json().get("result", {})
                    sp = float(result.get("spot_price") or result.get("mark_price") or
                               result.get("last_price") or 0)
                    if sp > 0:
                        return sp
        except Exception as e:
            print(f"[LTP FETCH ERROR] {base}: {e}")
            continue
    return 0.0

# ============================================================
# JANITOR: Syncs reality, enforces Clean Slate, guards quantity
# UPDATED: Step 6 DO NOTHING Rule + Step 8 True Flip Condition
# ============================================================
def run_janitor():
    global _last_trade_time

    # 1. Sync Reality from Exchange
    delta_executor.sync_delta_position()

    # 2. Get Current Signal (from configured timeframe)
    asset     = "BTC"
    timeframe = db.get_param("candle_timeframe", "5m")
    signal    = logic.get_supertrend_signal(asset, timeframe=timeframe)
    db.set_param("signal_target", signal)

    # 3. Get DB Reality
    call_active = db.get_param("active_call_symbol", "NONE") != "NONE"
    put_active  = db.get_param("active_put_symbol",  "NONE") != "NONE"

    # ──────────────────────────────────────────────────────
    # STEP 6 — "DO NOTHING" RULE
    # If position MATCHES the signal → HOLD, don't touch it
    # ──────────────────────────────────────────────────────
    # SELL signal = Market Bearish = We want PUT (selling PUT)
    # BUY signal  = Market Bullish = We want CALL (selling CALL)

    if signal == "SELL" and put_active:
        log_terminal("✋ DO NOTHING: Signal=SELL, PUT active → HOLD. No action needed.", "INFO")
        return  # STEP 6: Perfect match — do nothing

    if signal == "BUY" and call_active:
        log_terminal("✋ DO NOTHING: Signal=BUY, CALL active → HOLD. No action needed.", "INFO")
        return  # STEP 6: Perfect match — do nothing

    # ──────────────────────────────────────────────────────
    # STEP 8 — TRUE FLIP CONDITION
    # Only flip if: signal reversed AND 5 minutes have passed
    # ──────────────────────────────────────────────────────
    if signal == "SELL" and call_active:
        # Signal is SELL but we have a CALL — need to flip
        if is_in_cooldown():
            return  # Step 7+8: Wait for cooldown before flipping
        ltp = get_btc_ltp()
        anchor = float(db.get_param("manual_anchor", "0") or "0")
        reason_str = f"LTP {ltp:,.0f} < Anchor {anchor:,.0f}" if anchor > 0 else "Supertrend SELL"
        log_terminal(f"🔄 TRUE FLIP: Closing CALL → Opening PUT | Reason: {reason_str}", "ALERT")
        send_telegram_msg(
            f"🔄 FLIP TRIGGERED\n"
            f"Closing : CALL\n"
            f"Opening : PUT (SELL)\n"
            f"Reason  : {reason_str}\n"
            f"Cooldown: 5 min starts now"
        )
        delta_executor.square_off_crypto()
        record_trade_action("Flip CALL→PUT")

    elif signal == "BUY" and put_active:
        # Signal is BUY but we have a PUT — need to flip
        if is_in_cooldown():
            return  # Step 7+8: Wait for cooldown before flipping
        ltp = get_btc_ltp()
        anchor = float(db.get_param("manual_anchor", "0") or "0")
        reason_str = f"LTP {ltp:,.0f} > Anchor {anchor:,.0f}" if anchor > 0 else "Supertrend BUY"
        log_terminal(f"🔄 TRUE FLIP: Closing PUT → Opening CALL | Reason: {reason_str}", "ALERT")
        send_telegram_msg(
            f"🔄 FLIP TRIGGERED\n"
            f"Closing : PUT\n"
            f"Opening : CALL (BUY)\n"
            f"Reason  : {reason_str}\n"
            f"Cooldown: 5 min starts now"
        )
        delta_executor.square_off_crypto()
        record_trade_action("Flip PUT→CALL")

    elif signal == "WAIT" and (call_active or put_active):
        if is_in_cooldown():
            return
        log_terminal("🛑 JANITOR: Signal is WAIT. Closing all trades after cooldown clear.", "ALERT")
        delta_executor.square_off_crypto()
        record_trade_action("Signal=WAIT, closing all")

    # QUANTITY GUARD: Prevent over-trading
    try:
        manual_lots = int(db.get_param('crypto_trade_size', '1'))
        total_size  = 0
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
            log_terminal(f"🚨 QUANTITY OVERLOAD: {total_size} > {manual_lots}. Clearing...", "ALERT")
            delta_executor.square_off_crypto()
            record_trade_action("Quantity overload clear")
    except:
        pass

    # ZOMBIE LOCK RECOVERY
    if db.get_param("local_trade_active", "NO") == "YES" and not call_active and not put_active:
        log_terminal("🚨 ZOMBIE LOCK: Memory was stuck. Releasing lock now.", "ALERT")
        db.set_param("local_trade_active", "NO")


# ============================================================
# IN-CODE SL/TP MONITOR
# STEP 11 — SL Spike Guard (zero-price protection)
# ============================================================
def check_sl_tp():
    """
    Polls open positions and triggers:
    - Market EXIT if loss >= SL%   → Hard Stop Loss
    - Market EXIT if profit >= TP% → Take Profit + Auto-Reinvest
    STEP 11: Only fires if BOTH entry_price > 0 AND current_premium > 0
    """
    mode = db.get_param('trade_mode', 'PAPER')
    if mode != "LIVE":
        return

    sl_pct = float(db.get_param('sl_percent', '40'))
    tp_pct = float(db.get_param('tp_percent', '100'))

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

                upnl      = float(p.get('unrealized_pnl', 0))
                entry_val = float(p.get('entry_value', 1) or 1)
                pid       = p.get('product_id')
                symbol    = p.get('product', {}).get('symbol', str(pid))
                pnl_pct   = (upnl / abs(entry_val)) * 100

                # ── STEP 11: SL Spike Guard ──────────────────
                # Only act if both values are non-zero (real data)
                avg_entry = float(p.get('avg_entry_price', 0) or 0)
                mark_price = float(p.get('mark_price', 0) or 0)
                if avg_entry <= 0 or mark_price <= 0:
                    log_terminal(
                        f"🛡️ SL SPIKE GUARD: Skipping {symbol} — "
                        f"Entry={avg_entry}, Mark={mark_price} (API zero-price glitch)",
                        "INFO"
                    )
                    continue
                # ─────────────────────────────────────────────

                print(f"[SL/TP] {symbol} | PnL: {upnl:.2f} USDT ({pnl_pct:.1f}%)")
                db.set_param("unrealized_pnl", str(upnl))

                # --- STOP LOSS HIT ---
                if pnl_pct <= -sl_pct:
                    log_terminal(f"🚨 STOP LOSS HIT: {pnl_pct:.1f}% | Exiting {symbol}...", "ALERT")
                    send_telegram_msg(
                        f"🔴 STOP LOSS TRIGGERED\n"
                        f"Symbol : {symbol}\n"
                        f"Loss   : {pnl_pct:.1f}% (Limit: -{sl_pct}%)\n"
                        f"Action : Market Exit NOW"
                    )
                    delta_executor.square_off_crypto(target_pid=pid)
                    record_trade_action(f"SL hit {pnl_pct:.1f}%")
                    return

                # --- TAKE PROFIT HIT ---
                if pnl_pct >= tp_pct:
                    log_terminal(f"💰 TAKE PROFIT HIT: {pnl_pct:.1f}% | Booking {symbol}...", "TRADE")
                    send_telegram_msg(
                        f"✅ TAKE PROFIT HIT\n"
                        f"Symbol : {symbol}\n"
                        f"Profit : {pnl_pct:.1f}% (Target: +{tp_pct}%)\n"
                        f"Action : Booking & Re-entering"
                    )
                    delta_executor.square_off_crypto(target_pid=pid)
                    time.sleep(2)

                    current_signal = db.get_param("signal_target", "WAIT")
                    if current_signal in ["BUY", "SELL"]:
                        log_terminal(f"♻️ AUTO-REINVEST: Re-entering {current_signal} after TP...", "TRADE")
                        send_telegram_msg(f"♻️ AUTO-REINVEST: Fresh {current_signal} entry after TP!")
                        time.sleep(1)
                        delta_executor.sync_delta_position()
                        db.set_param("local_trade_active", "NO")
                        delta_executor.execute_crypto_trade("BTC", current_signal)
                        record_trade_action(f"TP reinvest {current_signal}")
                    return

        except Exception as e:
            print(f"[SL/TP ERROR] {e}")


# ============================================================
# MAIN EVALUATOR: Evaluates signal and places entries
# STEP 6: DO NOTHING if position matches signal
# STEP 7: Cooldown check before new entry
# STEP 10: Reasoning-based alerts
# ============================================================
def run_crypto_sar():
    if db.get_param('crypto_algo_running', 'OFF') == 'OFF':
        return

    asset     = "BTC"
    timeframe = db.get_param("candle_timeframe", "5m")
    signal    = logic.get_supertrend_signal(asset, timeframe=timeframe)
    db.set_param("signal_target", signal)

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

    # ── STEP 6: DO NOTHING if current position matches signal ──
    if signal == "SELL" and active_put != "NONE":
        log_terminal(f"✋ DO NOTHING (SAR): PUT {active_put} held, Signal=SELL — holding.", "INFO")
        return

    if signal == "BUY" and active_call != "NONE":
        log_terminal(f"✋ DO NOTHING (SAR): CALL {active_call} held, Signal=BUY — holding.", "INFO")
        return

    # ── Fresh entry only if screen is empty ────────────────────
    if not active_any:
        if signal in ["BUY", "SELL"]:
            # STEP 7: Cooldown check before fresh entry
            if is_in_cooldown():
                return

            # STEP 10: Reasoning-based alert
            ltp    = get_btc_ltp()
            anchor = float(db.get_param("manual_anchor", "0") or "0")
            option_type = "PUT (SELL)" if signal == "SELL" else "CALL (BUY)"
            if anchor > 0:
                direction_reason = f"LTP {ltp:,.0f} {'<' if signal=='SELL' else '>'} Anchor {anchor:,.0f}"
            else:
                direction_reason = f"Supertrend signal = {signal}"

            log_terminal(f"🎯 FRESH ENTRY: {option_type} | Reason: {direction_reason}", "TRADE")
            send_telegram_msg(
                f"🚀 ENTRY SIGNAL\n"
                f"Action : SELL {option_type}\n"
                f"Reason : {direction_reason}\n"
                f"LTP    : {ltp:,.0f}\n"
                f"TF     : {timeframe}"
            )

            num_strikes = int(db.get_param('num_strikes', '1'))
            for i in range(num_strikes):
                delta_executor.execute_crypto_trade(asset, signal)
                if num_strikes > 1:
                    time.sleep(1)
            record_trade_action(f"Fresh entry {signal}")
    else:
        crypto_roller.check_and_roll_crypto()


# ============================================================
# MAIN
# ============================================================
def main():
    # --- BULLETPROOF SINGLETON ---
    try:
        lock_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        lock_socket.bind(('127.0.0.1', 47200))
    except socket.error:
        print("BOT ALREADY RUNNING. EXITING.")
        sys.exit(1)

    print("=" * 60)
    print("  BHARAT ALGOVERSE v5.2 - FULL AUTO")
    print("=" * 60)
    print("  Step 0  : OTM Strike Enforcement   : ON")
    print("  Step 6  : DO NOTHING Rule           : ON")
    print("  Step 7  : 5-Min Global Cooldown     : ON")
    print("  Step 8  : True Flip Condition       : ON")
    print("  Step 9  : 5-Min Heartbeat           : ON")
    print("  Step 10 : Reasoning-Based Alerts    : ON")
    print("  Step 11 : SL Spike Guard            : ON")
    print("=" * 60)

    if not db.load_secrets():
        sys.exit(1)

    # --- DEFAULT PARAMS (only if not already set by dashboard) ---
    if not db.get_param('st_period'):         db.set_param('st_period', '10')
    if not db.get_param('st_multiplier'):     db.set_param('st_multiplier', '1.5')
    if not db.get_param('crypto_trade_size'): db.set_param('crypto_trade_size', '1')
    if not db.get_param('sl_percent'):        db.set_param('sl_percent', '40')
    if not db.get_param('tp_percent'):        db.set_param('tp_percent', '100')
    if not db.get_param('candle_timeframe'):  db.set_param('candle_timeframe', '5m')
    if not db.get_param('num_strikes'):       db.set_param('num_strikes', '1')
    if not db.get_param('strike_offset'):     db.set_param('strike_offset', '1')
    if not db.get_param('manual_anchor'):     db.set_param('manual_anchor', '0')

    sl_pct = db.get_param('sl_percent', '40')
    tp_pct = db.get_param('tp_percent', '100')
    tf     = db.get_param('candle_timeframe', '5m')

    log_terminal("Bharat AlgoVerse v5.2 - Full Auto Mode Started.", "START")
    send_telegram_msg(
        f"BHARAT ALGOVERSE v5.2 STARTED\n"
        f"SL: {sl_pct}% | TP: {tp_pct}%\n"
        f"Timeframe: {tf}\n"
        f"DO NOTHING Rule: ON\n"
        f"5-Min Cooldown: ON\n"
        f"OTM Enforcement: ON"
    )

    print("SCANNING FOR ORPHANED TRADES...")
    delta_executor.reconcile_bracket_orders()

    # STEP 9: 5-minute heartbeat (was 30 minutes before)
    last_pulse = 0

    while True:
        try:
            run_janitor()
            run_crypto_sar()
            check_sl_tp()
            delta_executor.reconcile_bracket_orders()

            # ── STEP 9: Telegram Heartbeat every 5 minutes ──────
            if time.time() - last_pulse > 300:
                timeframe  = db.get_param("candle_timeframe", "5m")
                signal_now = logic.get_supertrend_signal("BTC", timeframe=timeframe)
                active     = db.get_param('crypto_active_symbol', 'NONE')
                upnl_val   = db.get_param('unrealized_pnl', '0')
                anchor_val = db.get_param('manual_anchor', '0')
                ltp_now    = get_btc_ltp()

                # Build position status
                call_sym = db.get_param('active_call_symbol', 'NONE')
                put_sym  = db.get_param('active_put_symbol', 'NONE')
                if call_sym != 'NONE':
                    pos_str = f"CALL: {call_sym}"
                elif put_sym != 'NONE':
                    pos_str = f"PUT: {put_sym}"
                else:
                    pos_str = "NONE (Flat)"

                # Cooldown status
                cooldown_remaining = max(0, int(300 - (time.time() - _last_trade_time)))
                cd_str = f"{cooldown_remaining}s" if cooldown_remaining > 0 else "Ready"

                send_telegram_msg(
                    f"BHARAT PULSE v5.2\n"
                    f"LTP     : {ltp_now:,.0f}\n"
                    f"Anchor  : {float(anchor_val):,.0f} {'(Manual)' if float(anchor_val) > 0 else '(Auto)'}\n"
                    f"Signal  : {signal_now}\n"
                    f"Position: {pos_str}\n"
                    f"PnL     : ${upnl_val}\n"
                    f"TF      : {timeframe}\n"
                    f"Cooldown: {cd_str}"
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
        print("CRITICAL SYSTEM CRASH")
        traceback.print_exc()
        print("=" * 60)
        sys.exit(1)
