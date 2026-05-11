import time
import datetime
import socket
import sys
import traceback
import db
import delta_executor
import logic
import requests
import config

try:
    from utils import send_telegram_msg, log_terminal
except ImportError:
    def send_telegram_msg(msg): print(f"TG: {msg}")
    def log_terminal(msg, type="INFO"): print(f"[{type}] {msg}")

# ============================================================
# MAGICAL LINE LOGIC (6:00 PM ANCHOR)
# ============================================================

def check_magical_anchor():
    now = datetime.datetime.now()
    magical_line = float(db.get_param("magical_line", "0"))
    last_anchor_date = db.get_param("last_anchor_date", "")
    today_str = now.strftime("%Y-%m-%d")

    # Daily 6 PM Update
    if now.hour == 18 and now.minute == 0 and last_anchor_date != today_str:
        log_terminal("🕒 6:00 PM: Setting New Magical Anchor...", "START")
        try:
            df, _ = delta_executor.fetch_delta_candles("BTC", "1m", limit=1)
            if not df.empty:
                new_anchor = float(df['close'].iloc[-1])
                db.set_param("magical_line", str(new_anchor))
                db.set_param("last_anchor_date", today_str)
                send_telegram_msg(f"📍 NEW ANCHOR: ${new_anchor:,.2f}")
                return new_anchor
        except: pass

    # Cold Start
    if magical_line == 0:
        df, _ = delta_executor.fetch_delta_candles("BTC", "1m", limit=1)
        if not df.empty:
            new_anchor = float(df['close'].iloc[-1])
            db.set_param("magical_line", str(new_anchor))
            return new_anchor
            
    return magical_line

def main_loop():
    try:
        lock_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        lock_socket.bind(('127.0.0.1', 47200))
    except:
        sys.exit(1)

    db.load_secrets()
    log_terminal("VERSION 5.0 ULTIMATE STABLE STARTED", "START")
    send_telegram_msg("🚀 BHARAT MAGICAL ENGINE V5.0 LOCKED\nStatus: LEGO Step 3 Complete")

    while True:
        try:
            # 1. Market Data aur Position Check
            ltp = delta_executor.fetch_btc_spot()
            pos = delta_executor.get_current_position()
            
            # 2. Magical Line (Anchor) Logic
            magical_line = check_magical_anchor()
            
            # --- MANUAL ANCHOR OVERRIDE (LEGO Step 3) ---
            manual_ml = float(config.get_param("manual_magical_line", "0"))
            if manual_ml > 0:
                magical_line = manual_ml
            
            if magical_line == 0 or ltp == 0:
                log_terminal("⏳ Waiting for Market Data / Anchor...", "INFO")
                time.sleep(10)
                continue

            db.set_param("signal_target", "BUY" if ltp > magical_line else "SELL")

            # --- POSITION CHECK & FLIP LOGIC ---
            if pos:
                # --- DYNAMIC STOP-LOSS WATCHDOG (LEGO Step 3) ---
                sl_percent = float(config.get_param("stop_loss_percentage", "25"))
                
                # Fetch current positions to check SL
                path = "/v2/positions"
                query = "?underlying_asset_symbol=BTC"
                headers = delta_executor.get_delta_auth_headers("GET", path, query_string=query)
                resp = requests.get(f"https://api.india.delta.exchange{path}{query}", headers=headers, timeout=10)
                if resp.status_code == 200:
                    for p in resp.json().get('result', []):
                        size = abs(float(p.get('size', 0)))
                        if size == 0: continue
                        upnl = float(p.get('unrealized_pnl', 0))
                        entry_val = float(p.get('entry_value', 1) or 1)
                        pnl_pct = (upnl / abs(entry_val)) * 100
                        
                        # SL Check: Trigger if PnL % is worse than -sl_percent
                        if pnl_pct <= -sl_percent:
                            log_terminal(f"🚨 SL HIT: {pnl_pct:.1f}% (Limit: {sl_percent}%)", "ALERT")
                            delta_executor.square_off_crypto(target_pid=p.get('product_id'))
                            config.set_param("last_trade_time", str(time.time()))
                            pos = None # Mark as closed for this loop
                            break
                
                if not pos: continue # Position was just closed by SL

                # --- TREND FLIP LOGIC (STRICT PRESERVATION) ---
                is_bullish = ltp > magical_line
                is_bearish = ltp < magical_line
                holding_put = (pos['type'] == 'PUT')
                holding_call = (pos['type'] == 'CALL')
                
                if holding_put and is_bullish:
                    log_terminal(f"🛡️ Self-Check: I hold PUT, LTP is > Anchor. Holding correctly.", "INFO")
                    time.sleep(30)
                    continue
                
                if holding_call and is_bearish:
                    log_terminal(f"🛡️ Self-Check: I hold CALL, LTP is < Anchor. Holding correctly.", "INFO")
                    time.sleep(30)
                    continue

                if (holding_put and is_bearish) or (holding_call and is_bullish):
                    last_trade_time = float(config.get_param("last_trade_time", "0"))
                    if (time.time() - last_trade_time) < 300:
                        log_terminal(f"⏳ FLIP LOCKED: Waiting for 5-min stabilization.", "INFO")
                        time.sleep(30)
                        continue

                    if holding_put and is_bearish:
                        delta_executor.square_off_crypto()
                        time.sleep(2)
                        delta_executor.execute_crypto_trade("SELL_CALL")
                    elif holding_call and is_bullish:
                        delta_executor.square_off_crypto()
                        time.sleep(2)
                        delta_executor.execute_crypto_trade("SELL_PUT")
                        
                    config.set_param("last_trade_time", str(time.time()))
                    continue

            # 3. Fresh Entry
            if not pos:
                signal = "SELL_PUT" if ltp > magical_line else "SELL_CALL"
                log_terminal(f"🎯 MAGICAL ENTRY: {signal} (LTP ${ltp:,.2f} vs Anchor ${magical_line:,.2f})", "TRADE")
                delta_executor.execute_crypto_trade(signal)
                config.set_param("last_trade_time", str(time.time()))

            time.sleep(30)
        except Exception as e:
            print(f"Error: {e}")
            traceback.print_exc()
            time.sleep(10)

if __name__ == "__main__":
    main_loop()
