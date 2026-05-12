import time
import datetime
import socket
import sys
import traceback
import requests
import family_db as db

try:
    from utils import send_telegram_msg, log_terminal
except:
    def send_telegram_msg(msg):
        token = db.get_param("telegram_bot_token")
        chat  = db.get_param("telegram_chat_id")
        if token and chat:
            try:
                requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                    json={"chat_id": chat, "text": msg}, timeout=5)
            except: pass
        print(f"[TG] {msg}")
    def log_terminal(msg, typ="INFO"): print(f"[{typ}] {msg}")


# ─── BTC Price ──────────────────────────────────────────────
def get_btc_ltp():
    for base in ["https://api.india.delta.exchange", "https://api.delta.exchange"]:
        try:
            resp = requests.get(f"{base}/v2/tickers?underlying_asset_symbols=BTC", timeout=5)
            if resp.status_code == 200:
                for t in resp.json().get("result", []):
                    sp = float(t.get("spot_price") or t.get("underlying_price") or 0)
                    if sp > 0:
                        return sp
        except: pass
    return 0.0


# ─── Magic Line ─────────────────────────────────────────────
_last_trade_time = 0

def record_trade():
    global _last_trade_time
    _last_trade_time = time.time()

def in_cooldown():
    elapsed = time.time() - _last_trade_time
    if elapsed < 300:
        print(f"[COOLDOWN] {int(300-elapsed)}s left")
        return True
    return False

def get_anchor():
    manual = float(db.get_param("manual_anchor", "0") or "0")
    if manual > 0:
        return manual, "MANUAL"
    auto = float(db.get_param("magical_line", "0") or "0")
    return auto, "AUTO (6PM)"


def update_anchor_6pm():
    now = datetime.datetime.now()
    last_date = db.get_param("last_anchor_date", "") or ""
    today = now.strftime("%Y-%m-%d")

    # 6 PM update
    if now.hour == 18 and now.minute < 5 and last_date != today:
        ltp = get_btc_ltp()
        if ltp > 0:
            db.set_param("magical_line", str(ltp))
            db.set_param("last_anchor_date", today)
            send_telegram_msg(
                f"🎯 MAGIC LINE UPDATED — 6:00 PM\n"
                f"Anchor : {ltp:,.2f}\n"
                f"Rule   : BTC > {ltp:,.0f} → SELL PUT\n"
                f"         BTC < {ltp:,.0f} → SELL CALL"
            )
        return

    # Cold start
    if float(db.get_param("magical_line", "0") or "0") == 0:
        ltp = get_btc_ltp()
        if ltp > 0:
            db.set_param("magical_line", str(ltp))
            send_telegram_msg(
                f"📍 BOT STARTED — Anchor Set\n"
                f"Anchor : {ltp:,.2f}\n"
                f"Note   : Updates every day at 6 PM\n"
                f"Rule   : BTC > {ltp:,.0f} → SELL PUT\n"
                f"         BTC < {ltp:,.0f} → SELL CALL"
            )


# ─── Import trading executor ────────────────────────────────
import importlib, sys as _sys

# Patch db module so delta_executor uses family_db
_sys.modules['db'] = family_db = importlib.import_module('family_db')

try:
    import delta_executor
except Exception as e:
    print(f"[EXECUTOR ERROR] {e}")
    delta_executor = None


def main():
    print("=" * 50)
    print("  BHARAT AI ALGO TRADER v5.2")
    print("  Magic Line Engine — Family Edition")
    print("=" * 50)

    if not db.is_setup_complete():
        print("[WAITING] Bot not set up yet. Open dashboard to enter credentials.")
        while not db.is_setup_complete():
            time.sleep(10)
        print("[READY] Credentials found! Starting trading...")

    anchor_now, anchor_type = get_anchor()
    ltp_now = get_btc_ltp()
    sl_pct  = db.get_param("sl_percent", "25")

    send_telegram_msg(
        f"🚀 BHARAT AI ALGO TRADER v5.2\n"
        f"Magic Line Engine Active!\n"
        f"Anchor : {anchor_now:,.0f} ({anchor_type})\n"
        f"BTC    : {ltp_now:,.0f}\n"
        f"SL     : {sl_pct}% premium protection\n"
        f"Rule   : BTC > Anchor → SELL PUT\n"
        f"         BTC < Anchor → SELL CALL\n\n"
        f"Good luck! 🍀"
    )

    last_pulse = 0

    while True:
        try:
            if db.get_param("crypto_algo_running", "OFF") == "OFF":
                print("[PAUSED] Bot is paused. Waiting...")
                time.sleep(30)
                continue

            update_anchor_6pm()

            anchor, anchor_type = get_anchor()
            ltp = get_btc_ltp()
            if ltp == 0 or anchor == 0:
                time.sleep(30)
                continue

            db.set_param("current_ltp", str(ltp))

            # Signal
            signal = "SELL" if ltp > anchor else "BUY"
            db.set_param("signal_target", signal)

            # Execute via delta_executor if available
            if delta_executor:
                delta_executor.sync_delta_position()
                active_call = db.get_param("active_call_symbol", "NONE")
                active_put  = db.get_param("active_put_symbol",  "NONE")
                active_any  = (active_call != "NONE" or active_put != "NONE")

                # DO NOTHING if position matches
                if signal == "SELL" and active_put != "NONE":
                    print(f"[HOLD] PUT held. LTP {ltp:,.0f} > Anchor {anchor:,.0f}")
                elif signal == "BUY" and active_call != "NONE":
                    print(f"[HOLD] CALL held. LTP {ltp:,.0f} < Anchor {anchor:,.0f}")
                elif active_any:
                    # Flip
                    if not in_cooldown():
                        print("[FLIP] Crossing anchor. Flipping position...")
                        delta_executor.square_off_crypto()
                        record_trade()
                elif not active_any and not in_cooldown():
                    # Fresh entry
                    opt = "PUT" if signal == "SELL" else "CALL"
                    print(f"[ENTRY] Selling {opt} | LTP {ltp:,.0f} vs Anchor {anchor:,.0f}")
                    delta_executor.execute_crypto_trade("BTC", signal)
                    record_trade()

                # Zombie lock check
                call_chk = db.get_param("active_call_symbol", "NONE")
                put_chk  = db.get_param("active_put_symbol", "NONE")
                lock     = db.get_param("local_trade_active", "NO")
                if (lock == "YES" or call_chk != "NONE" or put_chk != "NONE"):
                    try:
                        real_count = 0
                        for asset in ["BTC"]:
                            q = f"?underlying_asset_symbol={asset}"
                            from delta_executor import get_delta_auth_headers
                            r = requests.get(
                                f"https://api.india.delta.exchange/v2/positions{q}",
                                headers=get_delta_auth_headers("GET", "/v2/positions", query_string=q),
                                timeout=5
                            )
                            if r.status_code == 200:
                                real_count += sum(1 for p in r.json().get('result', [])
                                                   if abs(float(p.get('size', 0))) > 0)
                        if real_count == 0:
                            db.set_param("local_trade_active", "NO")
                            db.set_param("active_call_symbol", "NONE")
                            db.set_param("active_put_symbol",  "NONE")
                            db.set_param("crypto_active_symbol", "NONE")
                            db.set_param("unrealized_pnl", "0")
                            print("[ZOMBIE CLEARED] Exchange=0, DB reset")
                    except: pass

            # 5-min Heartbeat
            if time.time() - last_pulse > 300:
                call_s = db.get_param("active_call_symbol", "NONE")
                put_s  = db.get_param("active_put_symbol", "NONE")
                pos_str = f"CALL SHORT: {call_s}" if call_s != "NONE" else (
                           f"PUT SHORT: {put_s}" if put_s != "NONE" else "No Position (Flat)")
                upnl = db.get_param("unrealized_pnl", "0")
                sig_label = "SELL PUT" if signal == "SELL" else "SELL CALL"
                above_below = "ABOVE" if ltp > anchor else "BELOW"

                send_telegram_msg(
                    f"📊 LIVE UPDATE\n"
                    f"BTC     : {ltp:,.0f}\n"
                    f"Anchor  : {anchor:,.0f} ({anchor_type})\n"
                    f"Signal  : {sig_label}\n"
                    f"Position: {pos_str}\n"
                    f"P&L     : ${upnl}\n"
                    f"Logic   : BTC {above_below} anchor"
                )
                last_pulse = time.time()

            time.sleep(30)

        except KeyboardInterrupt:
            print("Bot stopped.")
            break
        except Exception as e:
            print(f"[ERROR] {e}")
            traceback.print_exc()
            time.sleep(15)


if __name__ == "__main__":
    main()
