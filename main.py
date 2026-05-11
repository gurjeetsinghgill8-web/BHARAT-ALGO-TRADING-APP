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

def run_crypto_magical():
    magical_line = check_magical_anchor()
    
    # --- MANUAL ANCHOR OVERRIDE (LEGO Step 3) ---
    manual_ml = float(config.get_param("manual_magical_line", "0"))
    if manual_ml > 0:
        magical_line = manual_ml
        # log_terminal(f"⚓ MANUAL ANCHOR ACTIVE: ${magical_line:,.2f}", "INFO")

    if magical_line == 0: return

    # Get LTP
    try:
        df, _ = delta_executor.fetch_delta_candles("BTC", "1m", limit=1)
        if df.empty: return
        ltp = float(df['close'].iloc[-1])
    except: return

    # Determine Signal
    signal = "BUY" if ltp > magical_line else "SELL"
    db.set_param("signal_target", signal)

    # Check Positions
    delta_executor.sync_delta_position()
    active_call = db.get_param("active_call_symbol", "NONE")
    active_put  = db.get_param("active_put_symbol",  "NONE")
    active_any  = (active_call != "NONE" or active_put != "NONE")

    # Trend Reversal Flip
    if active_any:
        pos_type = "BUY" if active_put != "NONE" else "SELL"
        
        # --- SELF-CHECK (Emergency Directive) ---
        log_terminal(f"🤖 Self-Check: I hold {pos_type}, LTP is ${ltp:,.2f}, Anchor is ${magical_line:,.2f}.", "INFO")
        
        if signal != pos_type:
            # --- 5-MINUTE CANDLE LOCK (Directive 2) ---
            last_trade_time = float(config.get_param("last_trade_time", "0"))
            elapsed = time.time() - last_trade_time
            if elapsed < 300:
                log_terminal(f"⏳ FLIP LOCKED: Waiting for 5-min candle to close. ({int(300 - elapsed)}s left)", "INFO")
                return

            log_terminal(f"🔄 TREND FLIP triggered: {pos_type} -> {signal}. Squaring off.", "ALERT")
            delta_executor.square_off_crypto()
            config.set_param("last_trade_time", str(time.time())) # Start cooldown after flip
            return
        else:
            # log_terminal("✅ Trend matches position. Continuing to hold.", "INFO")
            pass

    # Fresh Entry
    if not active_any:
        log_terminal(f"🎯 MAGICAL ENTRY: {signal} (LTP {ltp} vs Anchor {magical_line})", "TRADE")
        delta_executor.execute_crypto_trade("BTC", signal)
        config.set_param("last_trade_time", str(time.time())) # Directive 1: Save entry timestamp

def check_sl_tp():
    mode = db.get_param('trade_mode', 'PAPER')
    if mode != "LIVE": return

    # --- DYNAMIC STOP-LOSS (LEGO Step 3) ---
    sl_percent = float(config.get_param("stop_loss_percentage", "25"))
    
    for asset in ["BTC", "ETH"]:
        try:
            path = "/v2/positions"
            query = f"?underlying_asset_symbol={asset}"
            url = f"https://api.india.delta.exchange{path}{query}"
            headers = delta_executor.get_delta_auth_headers("GET", path, query_string=query)
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                for p in resp.json().get('result', []):
                    size = abs(float(p.get('size', 0)))
                    if size == 0: continue
                    upnl = float(p.get('unrealized_pnl', 0))
                    entry_val = float(p.get('entry_value', 1) or 1)
                    pnl_pct = (upnl / abs(entry_val)) * 100
                    
                    if pnl_pct <= -sl_percent:
                        log_terminal(f"🚨 SL HIT: {pnl_pct:.1f}% (Threshold: {sl_percent}%)", "ALERT")
                        delta_executor.square_off_crypto(target_pid=p.get('product_id'))
        except: pass

def main_loop():
    try:
        lock_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        lock_socket.bind(('127.0.0.1', 47200))
    except:
        sys.exit(1)

    db.load_secrets()
    log_terminal("VERSION 4.0 ULTIMATE STABLE STARTED", "START")
    send_telegram_msg("🚀 BHARAT MAGICAL ENGINE V4.0 LOCKED\nStrategy: 6 PM Anchor | 5-Min Candle Lock")

    while True:
        try:
            run_crypto_magical()
            check_sl_tp()
            time.sleep(30)
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(10)

if __name__ == "__main__":
    main_loop()
