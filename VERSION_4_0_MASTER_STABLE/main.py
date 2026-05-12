import time
import datetime
import requests
import pandas as pd
import db
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
# GLOBAL COOLDOWN LOCK (5-minute)
# ============================================================
_last_trade_time = 0

def record_trade_action(reason=""):
    global _last_trade_time
    _last_trade_time = time.time()
    log_terminal(f"⏱️ COOLDOWN STARTED (5 min) — Reason: {reason}", "INFO")

def is_in_cooldown():
    elapsed = time.time() - _last_trade_time
    if elapsed < 300:
        remaining = int(300 - elapsed)
        log_terminal(f"🧊 COOLDOWN: {remaining}s remaining. Skipping cycle.", "INFO")
        return True
    return False

# ============================================================
# BTC LIVE PRICE (LTP)
# ============================================================
def get_btc_ltp():
    base_urls = [
        "https://api.india.delta.exchange",
        "https://api.delta.exchange",
    ]
    for base in base_urls:
        try:
            resp = requests.get(
                f"{base}/v2/tickers?underlying_asset_symbols=BTC",
                timeout=5
            )
            if resp.status_code == 200:
                for t in resp.json().get("result", []):
                    sp = float(t.get("spot_price") or t.get("underlying_price") or 0)
                    if sp > 0:
                        return sp
            for sym in ["BTCUSDT", "BTCUSD", "BTC_USDT"]:
                resp2 = requests.get(f"{base}/v2/tickers/{sym}", timeout=5)
                if resp2.status_code == 200:
                    result = resp2.json().get("result", {})
                    sp = float(result.get("spot_price") or result.get("mark_price") or
                               result.get("last_price") or 0)
                    if sp > 0:
                        return sp
        except Exception as e:
            print(f"[LTP ERROR] {base}: {e}")
            continue
    return 0.0

# ============================================================
# *** THE MAGIC LINE SYSTEM ***
# ============================================================

def get_anchor_price():
    """
    Returns active anchor price.
    Priority: manual_anchor (if > 0) → auto_anchor (6 PM IST daily)
    """
    manual = float(db.get_param('manual_anchor', '0') or '0')
    if manual > 0:
        return manual, "MANUAL"
    auto = float(db.get_param('auto_anchor', '0') or '0')
    return auto, "AUTO (6PM)"

def get_magic_line_signal(ltp, anchor):
    """
    THE ONLY TRADING LOGIC — NO SUPERTREND, NO CANDLES:

    LTP > Anchor → Market is ABOVE the magic line → SELL PUT
    LTP < Anchor → Market is BELOW the magic line → SELL CALL
    No anchor set  → WAIT
    """
    if anchor <= 0 or ltp <= 0:
        return "WAIT"
    if ltp > anchor:
        return "SELL"   # Sell PUT
    elif ltp < anchor:
        return "BUY"    # Sell CALL
    return "WAIT"

def update_auto_anchor():
    """
    Every day at 6:00 PM IST (18:00 IST = 12:30 UTC),
    fetch BTC price and set it as the Magic Line for next 24 hours.
    Uses the last available BTC spot price at that moment.
    """
    now_utc = datetime.datetime.utcnow()
    now_ist = now_utc + datetime.timedelta(hours=5, minutes=30)

    # Only trigger between 18:00 and 18:05 IST
    if not (now_ist.hour == 18 and now_ist.minute < 5):
        return

    # Check if already set today
    last_anchor_date = db.get_param('auto_anchor_date', '') or ''
    today_str = now_ist.strftime('%Y-%m-%d')
    if last_anchor_date == today_str:
        return  # Already set for today

    # Fetch current BTC price as the anchor
    try:
        ltp = get_btc_ltp()
        if ltp <= 0:
            # Fallback: try fetching from candle data
            df, _ = delta_executor.fetch_delta_candles("BTC", "5m", limit=3)
            if df is not None and not df.empty:
                ltp = float(df['close'].iloc[-1])

        if ltp > 0:
            db.set_param('auto_anchor', str(ltp))
            db.set_param('auto_anchor_date', today_str)
            log_terminal(f"🎯 MAGIC LINE AUTO-SET: {ltp:,.0f} (6 PM IST)", "INFO")
            send_telegram_msg(
                f"🎯 MAGIC LINE SET — 6:00 PM IST\n"
                f"Anchor : {ltp:,.2f}\n"
                f"Valid  : Next 24 hours\n"
                f"Rule   : LTP > {ltp:,.0f} → SELL PUT\n"
                f"         LTP < {ltp:,.0f} → SELL CALL"
            )
        else:
            log_terminal("⚠️ Auto-anchor failed — could not get BTC price at 6 PM", "ERROR")
    except Exception as e:
        print(f"[AUTO ANCHOR ERROR] {e}")


# ============================================================
# JANITOR: Syncs reality, enforces Clean Slate
# Uses MAGIC LINE signal — no Supertrend
# ============================================================
def run_janitor():
    global _last_trade_time

    # 1. Sync reality from exchange
    delta_executor.sync_delta_position()

    # 2. Get signal from Magic Line
    ltp = get_btc_ltp()
    anchor, anchor_type = get_anchor_price()
    signal = get_magic_line_signal(ltp, anchor)
    db.set_param("signal_target", signal)
    db.set_param("current_ltp", str(ltp))

    # 3. Get current positions
    call_active = db.get_param("active_call_symbol", "NONE") != "NONE"
    put_active  = db.get_param("active_put_symbol",  "NONE") != "NONE"

    # ── DO NOTHING RULE ──────────────────────────────────────
    # SELL signal = sell PUT → if PUT already held = DO NOTHING
    # BUY signal  = sell CALL → if CALL already held = DO NOTHING
    if signal == "SELL" and put_active:
        log_terminal(
            f"✋ DO NOTHING: LTP={ltp:,.0f} > Anchor={anchor:,.0f} "
            f"→ PUT held → HOLD", "INFO"
        )
        return

    if signal == "BUY" and call_active:
        log_terminal(
            f"✋ DO NOTHING: LTP={ltp:,.0f} < Anchor={anchor:,.0f} "
            f"→ CALL held → HOLD", "INFO"
        )
        return

    # ── TRUE FLIP (with 5-min cooldown) ──────────────────────
    if signal == "SELL" and call_active:
        if is_in_cooldown():
            return
        log_terminal(
            f"🔄 FLIP: LTP={ltp:,.0f} > Anchor={anchor:,.0f} "
            f"→ Closing CALL, Opening PUT", "ALERT"
        )
        send_telegram_msg(
            f"🔄 MAGIC LINE FLIP\n"
            f"LTP    : {ltp:,.0f}\n"
            f"Anchor : {anchor:,.0f} ({anchor_type})\n"
            f"Action : Close CALL → Open PUT SELL\n"
            f"Reason : LTP crossed ABOVE Magic Line"
        )
        delta_executor.square_off_crypto()
        record_trade_action("Flip CALL→PUT")

    elif signal == "BUY" and put_active:
        if is_in_cooldown():
            return
        log_terminal(
            f"🔄 FLIP: LTP={ltp:,.0f} < Anchor={anchor:,.0f} "
            f"→ Closing PUT, Opening CALL", "ALERT"
        )
        send_telegram_msg(
            f"🔄 MAGIC LINE FLIP\n"
            f"LTP    : {ltp:,.0f}\n"
            f"Anchor : {anchor:,.0f} ({anchor_type})\n"
            f"Action : Close PUT → Open CALL SELL\n"
            f"Reason : LTP crossed BELOW Magic Line"
        )
        delta_executor.square_off_crypto()
        record_trade_action("Flip PUT→CALL")

    elif signal == "WAIT" and (call_active or put_active):
        # WAIT = no anchor set yet (before 6 PM IST)
        # DO NOT CLOSE positions — just hold and wait for anchor
        log_terminal(
            "⏳ JANITOR WAIT: No anchor set yet. "
            "Holding position until 6 PM IST or manual anchor is set.", "INFO"
        )
        return  # HOLD — never disturb existing position without a clear signal

    # QUANTITY GUARD
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
            record_trade_action("Quantity overload")
    except:
        pass

    # ZOMBIE LOCK RECOVERY
    if db.get_param("local_trade_active", "NO") == "YES" and not call_active and not put_active:
        log_terminal("🚨 ZOMBIE LOCK: Releasing.", "ALERT")
        db.set_param("local_trade_active", "NO")


# ============================================================
# SL MONITOR — 25% Premium-Based
# For OPTION SELLING: SL hit if premium rises 25% above entry
# ============================================================
def check_sl_tp():
    mode = db.get_param('trade_mode', 'PAPER')
    if mode != "LIVE":
        return

    sl_pct = float(db.get_param('sl_percent', '25'))
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

                # SL Spike Guard: skip if prices are zero (API glitch)
                avg_entry  = float(p.get('avg_entry_price', 0) or 0)
                mark_price = float(p.get('mark_price', 0) or 0)
                if avg_entry <= 0 or mark_price <= 0:
                    log_terminal(f"🛡️ SL GUARD: Skipping — Entry={avg_entry}, Mark={mark_price}", "INFO")
                    continue

                pid    = p.get('product_id')
                symbol = p.get('product', {}).get('symbol', str(pid))

                # For OPTION SELLING: we SOLD at avg_entry premium
                # SL hits if current premium (mark_price) rises by sl_pct%
                premium_rise_pct = ((mark_price - avg_entry) / avg_entry) * 100

                # Also track via unrealized PnL for display
                upnl     = float(p.get('unrealized_pnl', 0))
                db.set_param("unrealized_pnl", str(upnl))

                print(f"[SL] {symbol} | Sold@{avg_entry:.1f} | Now@{mark_price:.1f} | Rise:{premium_rise_pct:.1f}% | PnL:{upnl:.2f}")

                # STOP LOSS: Premium rose by sl_pct% (we're losing money)
                if premium_rise_pct >= sl_pct:
                    log_terminal(
                        f"🚨 SL HIT: Premium rose {premium_rise_pct:.1f}% "
                        f"(Limit: {sl_pct}%) | Closing {symbol}", "ALERT"
                    )
                    send_telegram_msg(
                        f"🔴 STOP LOSS HIT\n"
                        f"Symbol  : {symbol}\n"
                        f"Sold @  : {avg_entry:.2f}\n"
                        f"Now  @  : {mark_price:.2f}\n"
                        f"Rise    : +{premium_rise_pct:.1f}% (Limit: {sl_pct}%)\n"
                        f"Action  : Buying back (closing short)"
                    )
                    delta_executor.square_off_crypto(target_pid=pid)
                    record_trade_action(f"SL hit +{premium_rise_pct:.1f}%")
                    return

                # TAKE PROFIT: Premium dropped by tp_pct% (option decayed — profit!)
                premium_drop_pct = ((avg_entry - mark_price) / avg_entry) * 100
                if premium_drop_pct >= tp_pct:
                    log_terminal(f"💰 TP HIT: Premium dropped {premium_drop_pct:.1f}% | Booking {symbol}", "TRADE")
                    send_telegram_msg(
                        f"✅ TAKE PROFIT HIT\n"
                        f"Symbol  : {symbol}\n"
                        f"Sold @  : {avg_entry:.2f}\n"
                        f"Now  @  : {mark_price:.2f}\n"
                        f"Drop    : -{premium_drop_pct:.1f}% (Target: {tp_pct}%)\n"
                        f"Action  : Buying back (booking profit)"
                    )
                    delta_executor.square_off_crypto(target_pid=pid)
                    record_trade_action(f"TP hit -{premium_drop_pct:.1f}%")
                    return

        except Exception as e:
            print(f"[SL/TP ERROR] {e}")


# ============================================================
# MAIN EVALUATOR — MAGIC LINE SIGNAL ONLY
# ============================================================
def run_crypto_sar():
    if db.get_param('crypto_algo_running', 'OFF') == 'OFF':
        return

    ltp    = get_btc_ltp()
    anchor, anchor_type = get_anchor_price()
    signal = get_magic_line_signal(ltp, anchor)
    db.set_param("signal_target", signal)
    db.set_param("current_ltp", str(ltp))

    delta_executor.sync_delta_position()
    active_call = db.get_param("active_call_symbol", "NONE")
    active_put  = db.get_param("active_put_symbol",  "NONE")
    active_any  = (active_call != "NONE" or active_put != "NONE")

    # Update dashboard display
    if active_call != "NONE" and active_put != "NONE":
        db.set_param("crypto_active_symbol", "HEDGED")
    elif active_call != "NONE":
        db.set_param("crypto_active_symbol", active_call)
    elif active_put != "NONE":
        db.set_param("crypto_active_symbol", active_put)
    else:
        db.set_param("crypto_active_symbol", "NONE")

    # DO NOTHING: position matches signal → HOLD
    if signal == "SELL" and active_put != "NONE":
        log_terminal(f"✋ HOLD PUT: LTP={ltp:,.0f} > Anchor={anchor:,.0f}", "INFO")
        return
    if signal == "BUY" and active_call != "NONE":
        log_terminal(f"✋ HOLD CALL: LTP={ltp:,.0f} < Anchor={anchor:,.0f}", "INFO")
        return

    # Fresh entry only when screen is empty
    if not active_any:
        if signal == "WAIT":
            log_terminal(
                f"⏳ WAITING: Anchor={anchor:,.0f} — "
                "Set anchor manually on dashboard or wait for 6 PM IST auto-anchor.", "INFO"
            )
            return

        if signal in ["BUY", "SELL"]:
            if is_in_cooldown():
                return

            option_type = "PUT (SELL)" if signal == "SELL" else "CALL (SELL)"
            direction   = "ABOVE" if signal == "SELL" else "BELOW"

            log_terminal(
                f"🎯 MAGIC LINE ENTRY: {option_type} | "
                f"LTP={ltp:,.0f} {direction} Anchor={anchor:,.0f}", "TRADE"
            )
            send_telegram_msg(
                f"🚀 MAGIC LINE ENTRY\n"
                f"Action : SELL {option_type}\n"
                f"LTP    : {ltp:,.0f}\n"
                f"Anchor : {anchor:,.0f} ({anchor_type})\n"
                f"Rule   : LTP {direction} Magic Line"
            )

            num_strikes = int(db.get_param('num_strikes', '1'))
            for i in range(num_strikes):
                delta_executor.execute_crypto_trade("BTC", signal)
                if num_strikes > 1:
                    time.sleep(1)
            record_trade_action(f"Fresh entry SELL {option_type}")


# ============================================================
# MAIN
# ============================================================
def main():
    # BULLETPROOF SINGLETON
    try:
        lock_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        lock_socket.bind(('127.0.0.1', 47200))
    except socket.error:
        print("BOT ALREADY RUNNING. EXITING.")
        sys.exit(1)

    print("=" * 60)
    print("  BHARAT ALGOVERSE v5.2 — MAGIC LINE EDITION")
    print("=" * 60)
    print("  Signal Engine   : MAGIC LINE (6 PM Anchor)")
    print("  Supertrend      : REMOVED")
    print("  Entry Type      : OPTION SELLING (side=sell)")
    print("  Exit Type       : BUY BACK (side=buy)")
    print("  DO NOTHING Rule : ON")
    print("  5-Min Cooldown  : ON")
    print("  SL Monitoring   : 25% Premium Rise")
    print("=" * 60)

    if not db.load_secrets():
        sys.exit(1)

    # Set defaults
    if not db.get_param('crypto_trade_size'): db.set_param('crypto_trade_size', '1')
    if not db.get_param('sl_percent'):        db.set_param('sl_percent', '25')
    if not db.get_param('tp_percent'):        db.set_param('tp_percent', '100')
    if not db.get_param('num_strikes'):       db.set_param('num_strikes', '1')
    if not db.get_param('strike_offset'):     db.set_param('strike_offset', '1')
    if not db.get_param('manual_anchor'):     db.set_param('manual_anchor', '0')
    if not db.get_param('auto_anchor'):       db.set_param('auto_anchor', '0')

    sl_pct = db.get_param('sl_percent', '25')
    anchor_val, anchor_type = get_anchor_price()
    ltp_now = get_btc_ltp()

    log_terminal("Bharat AlgoVerse v5.2 — Magic Line Edition Started.", "START")
    send_telegram_msg(
        f"BHARAT ALGOVERSE v5.2 STARTED\n"
        f"Engine  : MAGIC LINE (No Supertrend)\n"
        f"SL      : {sl_pct}% premium rise\n"
        f"Anchor  : {anchor_val:,.0f} ({anchor_type})\n"
        f"LTP Now : {ltp_now:,.0f}\n"
        f"Selling : PUT if LTP > Anchor | CALL if LTP < Anchor"
    )

    delta_executor.reconcile_bracket_orders()

    last_pulse = 0

    while True:
        try:
            # Auto-set anchor at 6 PM IST every day
            update_auto_anchor()

            run_janitor()
            run_crypto_sar()
            check_sl_tp()
            delta_executor.reconcile_bracket_orders()

            # 5-minute heartbeat
            if time.time() - last_pulse > 300:
                ltp_now      = get_btc_ltp()
                anchor_now, anchor_type_now = get_anchor_price()
                signal_now   = get_magic_line_signal(ltp_now, anchor_now)
                active        = db.get_param('crypto_active_symbol', 'NONE')
                upnl_val     = db.get_param('unrealized_pnl', '0')
                call_sym     = db.get_param('active_call_symbol', 'NONE')
                put_sym      = db.get_param('active_put_symbol',  'NONE')

                if call_sym != 'NONE':
                    pos_str = f"CALL SHORT: {call_sym}"
                elif put_sym != 'NONE':
                    pos_str = f"PUT SHORT: {put_sym}"
                else:
                    pos_str = "NONE (Flat)"

                cd_remaining = max(0, int(300 - (time.time() - _last_trade_time)))
                cd_str = f"{cd_remaining}s remaining" if cd_remaining > 0 else "Ready"

                direction_hint = ""
                if anchor_now > 0 and ltp_now > 0:
                    if ltp_now > anchor_now:
                        direction_hint = f"LTP {ltp_now:,.0f} ABOVE line → SELL PUT"
                    else:
                        direction_hint = f"LTP {ltp_now:,.0f} BELOW line → SELL CALL"

                send_telegram_msg(
                    f"BHARAT PULSE v5.2\n"
                    f"LTP     : {ltp_now:,.0f}\n"
                    f"Anchor  : {anchor_now:,.0f} ({anchor_type_now})\n"
                    f"Signal  : {signal_now}\n"
                    f"Position: {pos_str}\n"
                    f"PnL     : ${upnl_val}\n"
                    f"Cooldown: {cd_str}\n"
                    f"Logic   : {direction_hint}"
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
