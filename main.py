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
    
    # --- MANUAL ANCHOR OVERRIDE ---
    manual_ml = float(config.get_param("manual_magical_line", "0"))
    if manual_ml > 0: magical_line = manual_ml

    if magical_line == 0: return

    # Get LTP
    try:
        df, _ = delta_executor.fetch_delta_candles("BTC", "1m", limit=1)
        if df.empty: return
        ltp = float(df['close'].iloc[-1])
    except: return

    db.set_param("signal_target", "BUY" if ltp > magical_line else "SELL")
    
    # --- POSITION CHECK & FLIP LOGIC (STRICT EMERGENCY VERSION) ---
    pos = delta_executor.get_current_position()
    
    if pos:
        is_bullish = ltp > magical_line
        is_bearish = ltp < magical_line
        holding_put = (pos['type'] == 'PUT')
        holding_call = (pos['type'] == 'CALL')
        
        # 1. The 'DO NOTHING' Rule (Lead Engineer's Strict Order)
        if holding_put and is_bullish:
            log_terminal(f"🛡️ Self-Check: I hold PUT, LTP is ${ltp:,.2f} > Anchor. Holding correctly. No action.", "INFO")
            return
        
        if holding_call and is_bearish:
            log_terminal(f"🛡️ Self-Check: I hold CALL, LTP is ${ltp:,.2f} < Anchor. Holding correctly. No action.", "INFO")
            return

        # 2. The 'TRUE FLIP' Rule (Only if trend actually reversed AND 5-min stabilized)
        if (holding_put and is_bearish) or (holding_call and is_bullish):
            # 5-MINUTE COOLDOWN CHECK
            last_trade_time = float(config.get_param("last_trade_time", "0"))
            elapsed = time.time() - last_trade_time
            if elapsed < 300:
                log_terminal(f"⏳ FLIP LOCKED: Trend reversed but waiting for 5-min candle stabilization. ({int(300 - elapsed)}s left)", "INFO")
                return

            new_signal = "SELL" if holding_put else "BUY" 
            log_terminal(f"🔄 TRUE TREND FLIP: {pos['type']} -> {new_signal}. Squaring off.", "ALERT")
            delta_executor.square_off_crypto()
            delta_executor.execute_crypto_trade("BTC", new_signal) 
            config.set_param("last_trade_time", str(time.time()))
            return

    # 3. Fresh Entry (Only if no position exists)
    if not pos:
        signal = "BUY" if ltp > magical_line else "SELL"
        log_terminal(f"🎯 MAGICAL ENTRY: {signal} (LTP ${ltp:,.2f} vs Anchor ${magical_line:,.2f})", "TRADE")
        delta_executor.execute_crypto_trade("BTC", signal)
        config.set_param("last_trade_time", str(time.time()))

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
