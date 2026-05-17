import time
import datetime
import socket
import sys
import os
import signal
import atexit
import traceback
import requests
import db
import delta_executor

try:
    from utils import send_telegram_msg, log_terminal
except ImportError:
    def send_telegram_msg(msg): print(f"TG: {msg}")
    def log_terminal(msg, typ="INFO"): print(f"[{typ}] {msg}")

# ============================================================
# SMART PID LOCK — Self-healing (replaces dumb socket lock)
# ============================================================
LOCK_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bot_running.lock')

def _acquire_lock():
    """Check if another instance is truly running. If stale lock found, auto-clear it."""
    if os.path.exists(LOCK_FILE):
        try:
            with open(LOCK_FILE, 'r') as f:
                old_pid = int(f.read().strip())
            # Check if that PID is actually still alive
            os.kill(old_pid, 0)  # Sends no signal — just checks if process exists
            # If we reach here, process IS running
            print(f"BOT ALREADY RUNNING (PID {old_pid}). EXITING.")
            sys.exit(1)
        except (ValueError, ProcessLookupError, PermissionError):
            # Stale lock — old process is DEAD. Safe to clear and continue.
            print(f"[LOCK] Stale lock found (PID dead). Auto-clearing and starting fresh.")
            os.remove(LOCK_FILE)

    # Write our PID
    with open(LOCK_FILE, 'w') as f:
        f.write(str(os.getpid()))
    print(f"[LOCK] Lock acquired (PID {os.getpid()})")

def _release_lock():
    """Remove lock file on clean exit."""
    try:
        if os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)
            print("[LOCK] Lock released.")
    except Exception:
        pass

def _signal_handler(sig, frame):
    """Handle SIGTERM/SIGINT gracefully — release lock before dying."""
    _release_lock()
    sys.exit(0)

# ============================================================
# GLOBAL 5-MIN COOLDOWN (V5.2 Safety)
# ============================================================
_last_trade_time = 0

def record_trade_action(reason=""):
    global _last_trade_time
    _last_trade_time = time.time()
    log_terminal(f"⏱️ COOLDOWN 5min — {reason}", "INFO")

def is_in_cooldown():
    elapsed = time.time() - _last_trade_time
    if elapsed < 300:
        log_terminal(f"🧊 COOLDOWN: {int(300-elapsed)}s remaining.", "INFO")
        return True
    return False

# ============================================================
# BTC LTP — PROVEN METHOD (V5.2)
# ============================================================
def get_btc_ltp():
    for base in ["https://api.india.delta.exchange", "https://api.delta.exchange"]:
        try:
            resp = requests.get(f"{base}/v2/tickers?underlying_asset_symbols=BTC", timeout=5)
            if resp.status_code == 200:
                for t in resp.json().get("result", []):
                    sp = float(t.get("spot_price") or t.get("underlying_price") or 0)
                    if sp > 0:
                        return sp
        except Exception as e:
            print(f"[LTP] {e}")
    # Fallback: use candle close
    try:
        df, _ = delta_executor.fetch_delta_candles("BTC", "1m", limit=1)
        if df is not None and not df.empty:
            return float(df['close'].iloc[-1])
    except:
        pass
    return 0.0

# ============================================================
# *** MAGICAL LINE — SUNDAY STABLE LOGIC (Preserved) ***
# ============================================================
def get_magical_line():
    """
    Returns the active anchor/magical line price.
    Priority: manual_anchor (dashboard) → magical_line (auto/6PM)

    COLD START RULE (Sunday stable):
      If no anchor set yet → use CURRENT price as temporary anchor.
      This means bot starts IMMEDIATELY without waiting for 6 PM.

    6 PM RULE:
      Every day at 6:00 PM IST, update the anchor to fresh closing price.
    """
    # 1. Manual anchor from dashboard overrides everything
    manual = float(db.get_param("manual_anchor", "0") or "0")
    if manual > 0:
        return manual, "MANUAL"

    # 2. Check if stored magical_line exists
    magical_line = float(db.get_param("magical_line", "0") or "0")

    # 3. 6 PM IST daily update
    now = datetime.datetime.now()  # Local time (VPS is IST)
    last_anchor_date = db.get_param("last_anchor_date", "") or ""
    today_str = now.strftime("%Y-%m-%d")

    if now.hour == 18 and now.minute < 5 and last_anchor_date != today_str:
        log_terminal("🕒 6:00 PM IST: Updating Magic Line anchor...", "START")
        try:
            ltp = get_btc_ltp()
            if ltp > 0:
                db.set_param("magical_line", str(ltp))
                db.set_param("last_anchor_date", today_str)
                db.set_param("auto_anchor", str(ltp))
                send_telegram_msg(
                    f"🎯 MAGIC LINE UPDATED — 6:00 PM IST\n"
                    f"Anchor : {ltp:,.2f}\n"
                    f"Valid  : Next 24 hours\n"
                    f"Rule   : LTP > {ltp:,.0f} → SELL PUT\n"
                    f"         LTP < {ltp:,.0f} → SELL CALL"
                )
                return ltp, "6PM AUTO"
        except Exception as e:
            print(f"[6PM ANCHOR ERROR] {e}")

    # 4. COLD START: No anchor yet → set current price immediately
    #    (Sunday stable behavior — bot starts right away)
    if magical_line == 0:
        log_terminal("❄️ COLD START: Setting anchor from current BTC price...", "INFO")
        try:
            ltp = get_btc_ltp()
            if ltp > 0:
                db.set_param("magical_line", str(ltp))
                db.set_param("auto_anchor", str(ltp))
                send_telegram_msg(
                    f"📍 COLD START ANCHOR SET\n"
                    f"Anchor : {ltp:,.2f}\n"
                    f"Note   : Will update to 6 PM price at 18:00 IST\n"
                    f"Rule   : LTP > {ltp:,.0f} → SELL PUT\n"
                    f"         LTP < {ltp:,.0f} → SELL CALL"
                )
                return ltp, "COLD START"
        except Exception as e:
            print(f"[COLD START ANCHOR ERROR] {e}")

    return magical_line, "AUTO (6PM)"


# ============================================================
# MAIN TRADING LOOP — MAGICAL LINE ENGINE
# ============================================================
def run_crypto_magical():
    if db.get_param('crypto_algo_running', 'OFF') == 'OFF':
        return

    # Get anchor and LTP
    magical_line, anchor_type = get_magical_line()
    if magical_line == 0:
        log_terminal("⏳ No anchor yet. Retrying...", "INFO")
        return

    ltp = get_btc_ltp()
    if ltp == 0:
        log_terminal("⚠️ Could not fetch BTC price. Skipping.", "WARN")
        return

    db.set_param("current_ltp", str(ltp))
    db.set_param("auto_anchor", str(magical_line))

    # SIGNAL: LTP vs Magic Line
    # ──────────────────────────────────────────────────────
    # LTP > Anchor → Price ABOVE the magic line → SELL PUT
    #   (Market is bullish, so we sell put — OTM below)
    # LTP < Anchor → Price BELOW the magic line → SELL CALL
    #   (Market is bearish, so we sell call — OTM above)
    # ──────────────────────────────────────────────────────
    signal = "SELL" if ltp > magical_line else "BUY"
    db.set_param("signal_target", signal)

    # Sync positions from exchange
    delta_executor.sync_delta_position()
    active_call = db.get_param("active_call_symbol", "NONE")
    active_put  = db.get_param("active_put_symbol",  "NONE")
    active_any  = (active_call != "NONE" or active_put != "NONE")

    # Update dashboard symbol
    if active_call != "NONE":
        db.set_param("crypto_active_symbol", active_call)
    elif active_put != "NONE":
        db.set_param("crypto_active_symbol", active_put)
    else:
        db.set_param("crypto_active_symbol", "NONE")

    # ── DO NOTHING: Position matches signal → HOLD ──────────
    # signal=SELL → we want PUT short → if PUT active = HOLD
    # signal=BUY  → we want CALL short → if CALL active = HOLD
    if signal == "SELL" and active_put != "NONE":
        log_terminal(f"✋ HOLD PUT SHORT: LTP {ltp:,.0f} > Anchor {magical_line:,.0f} → Selling PUT is correct", "INFO")
        return
    if signal == "BUY" and active_call != "NONE":
        log_terminal(f"✋ HOLD CALL SHORT: LTP {ltp:,.0f} < Anchor {magical_line:,.0f} → Selling CALL is correct", "INFO")
        return

    # ── FLIP: Position is WRONG direction ───────────────────
    if active_any:
        if is_in_cooldown():
            return
        pos_type = "BUY" if active_call != "NONE" else "SELL"
        if signal != pos_type:
            flip_from = "CALL" if active_call != "NONE" else "PUT"
            flip_to   = "PUT" if signal == "SELL" else "CALL"
            log_terminal(f"🔄 FLIP: LTP crossed anchor. Closing {flip_from} → Opening {flip_to}", "ALERT")
            send_telegram_msg(
                f"🔄 MAGIC LINE FLIP\n"
                f"LTP    : {ltp:,.0f}\n"
                f"Anchor : {magical_line:,.0f} ({anchor_type})\n"
                f"Close  : {flip_from} → Open : {flip_to} SELL\n"
                f"Cooldown: 5 min"
            )
            delta_executor.square_off_crypto()
            record_trade_action(f"Flip {flip_from}→{flip_to}")
        return

    # ── FRESH ENTRY: Screen is empty ────────────────────────
    if not active_any:
        if is_in_cooldown():
            return
        opt_type  = "PUT (SELL)" if signal == "SELL" else "CALL (SELL)"
        ltp_pos   = "ABOVE" if signal == "SELL" else "BELOW"
        log_terminal(f"🎯 ENTRY: SELL {opt_type} | LTP {ltp:,.0f} {ltp_pos} Anchor {magical_line:,.0f}", "TRADE")
        send_telegram_msg(
            f"🚀 MAGIC LINE ENTRY\n"
            f"Action : SELL {opt_type}\n"
            f"LTP    : {ltp:,.0f}\n"
            f"Anchor : {magical_line:,.0f} ({anchor_type})\n"
            f"Rule   : LTP {ltp_pos} Anchor"
        )
        num_strikes = int(db.get_param('num_strikes', '1'))
        for i in range(num_strikes):
            delta_executor.execute_crypto_trade("BTC", signal)
            if num_strikes > 1:
                time.sleep(1)
        record_trade_action(f"Fresh entry SELL {opt_type}")


# ============================================================
# SL MONITOR — 25% Premium Rise (V5.2)
# ============================================================
def check_sl_tp():
    mode = db.get_param('trade_mode', 'PAPER')
    if mode != "LIVE":
        return

    sl_pct = float(db.get_param('sl_percent', '25'))

    for asset in ["BTC", "ETH"]:
        try:
            path  = "/v2/positions"
            query = f"?underlying_asset_symbol={asset}"
            url   = f"https://api.india.delta.exchange{path}{query}"
            hdrs  = delta_executor.get_delta_auth_headers("GET", path, query_string=query)
            resp  = requests.get(url, headers=hdrs, timeout=10)
            if resp.status_code != 200:
                continue

            for p in resp.json().get('result', []):
                size = abs(float(p.get('size', 0)))
                if size == 0:
                    continue

                avg_entry  = float(p.get('avg_entry_price', 0) or 0)
                mark_price = float(p.get('mark_price', 0) or 0)

                # SL Spike Guard
                if avg_entry <= 0 or mark_price <= 0:
                    continue

                pid    = p.get('product_id')
                symbol = p.get('product', {}).get('symbol', str(pid))
                upnl   = float(p.get('unrealized_pnl', 0))
                db.set_param("unrealized_pnl", str(upnl))

                # For SOLD options: SL = premium rose by sl_pct%
                premium_rise_pct = ((mark_price - avg_entry) / avg_entry) * 100
                print(f"[SL] {symbol} | Sold@{avg_entry:.1f} Now@{mark_price:.1f} Rise:{premium_rise_pct:.1f}% PnL:{upnl:.2f}")

                if premium_rise_pct >= sl_pct:
                    log_terminal(f"🚨 SL HIT: +{premium_rise_pct:.1f}% | Closing {symbol}", "ALERT")
                    send_telegram_msg(
                        f"🔴 STOP LOSS HIT\n"
                        f"Symbol : {symbol}\n"
                        f"Sold @ : {avg_entry:.2f}\n"
                        f"Now  @ : {mark_price:.2f}\n"
                        f"Rise   : +{premium_rise_pct:.1f}% (Limit: {sl_pct}%)"
                    )
                    delta_executor.square_off_crypto(target_pid=pid)
                    record_trade_action(f"SL +{premium_rise_pct:.1f}%")
                    return

        except Exception as e:
            print(f"[SL ERROR] {e}")


# ============================================================
# MAIN
# ============================================================
def main():
    # — Smart PID Lock (self-healing) —
    _acquire_lock()
    atexit.register(_release_lock)        # Clean up on normal exit
    signal.signal(signal.SIGTERM, _signal_handler)  # Clean up on systemd stop
    signal.signal(signal.SIGINT,  _signal_handler)  # Clean up on Ctrl+C

    print("=" * 55)
    print("  BHARAT MAGICAL ENGINE v5.2")
    print("=" * 55)
    print("  Signal   : LTP vs 6PM Anchor (Magic Line)")
    print("  Entry    : OPTION SELLING (side=sell)")
    print("  SL       : 25% premium rise")
    print("  ColdStart: Anchor set from current price")
    print("  Cooldown : 5 minutes between trades")
    print("=" * 55)

    if not db.load_secrets():
        sys.exit(1)

    # Defaults
    if not db.get_param('crypto_trade_size'): db.set_param('crypto_trade_size', '1')
    if not db.get_param('sl_percent'):        db.set_param('sl_percent', '25')
    if not db.get_param('num_strikes'):       db.set_param('num_strikes', '1')
    if not db.get_param('expiry_threshold'): db.set_param('expiry_threshold', '1')
    if not db.get_param('trade_mode'):        db.set_param('trade_mode', 'LIVE')
    if not db.get_param('crypto_algo_running'): db.set_param('crypto_algo_running', 'ON')

    anchor_now, anchor_type = get_magical_line()
    ltp_now = get_btc_ltp()
    sl_pct  = db.get_param('sl_percent', '25')

    log_terminal("Bharat Magical Engine v5.2 Started.", "START")
    send_telegram_msg(
        f"🚀 BHARAT MAGICAL ENGINE v5.2\n"
        f"Anchor : {anchor_now:,.0f} ({anchor_type})\n"
        f"LTP    : {ltp_now:,.0f}\n"
        f"SL     : {sl_pct}% premium rise\n"
        f"Rule   : LTP > Anchor → SELL PUT\n"
        f"         LTP < Anchor → SELL CALL"
    )

    delta_executor.reconcile_bracket_orders()

    last_pulse = 0

    while True:
        try:
            run_crypto_magical()
            check_sl_tp()
            delta_executor.reconcile_bracket_orders()

            # ── ZOMBIE LOCK DETECTOR ──────────────────────────────
            # If exchange has 0 positions but DB thinks trade is active
            # → clear the zombie lock so engine can re-enter
            try:
                lock_active = db.get_param("local_trade_active", "NO")
                call_sym_chk = db.get_param("active_call_symbol", "NONE")
                put_sym_chk  = db.get_param("active_put_symbol", "NONE")
                if lock_active == "YES" or call_sym_chk != "NONE" or put_sym_chk != "NONE":
                    # Verify against exchange
                    real_count = 0
                    for asset in ["BTC", "ETH"]:
                        q = f"?underlying_asset_symbol={asset}"
                        r = requests.get(
                            f"https://api.india.delta.exchange/v2/positions{q}",
                            headers=delta_executor.get_delta_auth_headers("GET", "/v2/positions", query_string=q),
                            timeout=5
                        )
                        if r.status_code == 200:
                            real_count += sum(1 for p in r.json().get('result', []) if abs(float(p.get('size', 0))) > 0)
                    if real_count == 0:
                        log_terminal("🧹 ZOMBIE CLEARED: Exchange=0 positions, DB reset.", "ALERT")
                        db.set_param("local_trade_active", "NO")
                        db.set_param("active_call_symbol", "NONE")
                        db.set_param("active_put_symbol",  "NONE")
                        db.set_param("crypto_active_symbol", "NONE")
                        db.set_param("unrealized_pnl", "0")
                        send_telegram_msg(
                            "🧹 ZOMBIE LOCK CLEARED\n"
                            "Exchange: 0 positions\n"
                            "DB reset: Clean slate\n"
                            "Engine will re-enter on next cycle."
                        )
            except Exception as ze:
                print(f"[ZOMBIE CHECK] {ze}")

            # ── DASHBOARD SETTINGS WATCHER ────────────────────────
            # When Dr. Saab saves settings on dashboard → notify Telegram
            try:
                saved_at = db.get_param("settings_updated_at", "0") or "0"
                last_notified = db.get_param("settings_notified_at", "0") or "0"
                if saved_at != "0" and saved_at != last_notified:
                    anchor_d  = float(db.get_param("manual_anchor", "0") or "0")
                    lots_d    = db.get_param("crypto_trade_size", "1")
                    sl_d      = db.get_param("sl_percent", "25")
                    tp_d      = db.get_param("tp_percent", "100")
                    expiry_d  = db.get_param("expiry_threshold", "1")
                    offset_d  = db.get_param("strike_offset", "1")
                    anchor_txt = f"{anchor_d:,.0f} (MANUAL)" if anchor_d > 0 else "AUTO (6PM)"
                    send_telegram_msg(
                        f"⚙️ DASHBOARD SETTINGS SAVED\n"
                        f"Anchor    : {anchor_txt}\n"
                        f"Lots      : {lots_d}\n"
                        f"SL        : {sl_d}%\n"
                        f"TP        : {tp_d}%\n"
                        f"Expiry min: {expiry_d} days\n"
                        f"OTM Level : +{offset_d}"
                    )
                    db.set_param("settings_notified_at", saved_at)
            except Exception as se:
                print(f"[SETTINGS WATCH] {se}")

            # 5-min Telegram heartbeat
            if time.time() - last_pulse > 300:
                ltp_now    = get_btc_ltp()
                anchor_now, anchor_type = get_magical_line()
                # CORRECT: SELL if LTP>anchor (sell PUT) | BUY if LTP<anchor (sell CALL)
                signal_now = "SELL" if ltp_now > anchor_now else "BUY"
                signal_label = "SELL PUT" if signal_now == "SELL" else "SELL CALL"
                active     = db.get_param('crypto_active_symbol', 'NONE')
                upnl_val   = db.get_param('unrealized_pnl', '0')
                call_sym   = db.get_param('active_call_symbol', 'NONE')
                put_sym    = db.get_param('active_put_symbol',  'NONE')

                if call_sym != 'NONE':
                    pos_str = f"CALL SHORT: {call_sym}"
                elif put_sym != 'NONE':
                    pos_str = f"PUT SHORT: {put_sym}"
                else:
                    pos_str = "NONE (Flat)"

                cd_left = max(0, int(300 - (time.time() - _last_trade_time)))
                cd_str  = f"{cd_left}s" if cd_left > 0 else "Ready"

                direction_hint = ""
                if anchor_now > 0 and ltp_now > 0:
                    if ltp_now > anchor_now:
                        direction_hint = "LTP ABOVE anchor → SELL PUT"
                    else:
                        direction_hint = "LTP BELOW anchor → SELL CALL"

                send_telegram_msg(
                    f"BHARAT PULSE v5.2\n"
                    f"LTP     : {ltp_now:,.0f}\n"
                    f"Anchor  : {anchor_now:,.0f} ({anchor_type})\n"
                    f"Signal  : {signal_label}\n"
                    f"Position: {pos_str}\n"
                    f"PnL     : ${upnl_val}\n"
                    f"Cooldown: {cd_str}\n"
                    f"Logic   : {direction_hint}"
                )
                last_pulse = time.time()

            time.sleep(30)

        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Error: {e}")
            traceback.print_exc()
            time.sleep(10)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("CRASH:")
        traceback.print_exc()
        sys.exit(1)
