import time
import datetime
import traceback
import config
import delta_executor

# --- SUPER SAFE TELEGRAM ---
try:
    from utils import send_telegram_msg
except ImportError:
    def send_telegram_msg(msg):
        pass

def log_terminal(msg, level="INFO"):
    timestamp = datetime.datetime.now().strftime('%H:%M:%S')
    line = f"[{timestamp}] {msg}"
    print(line)
    try:
        with open("safelog.txt", "a") as f:
            f.write(line + "\n")
    except: pass

# --- BHARAT ALGO: ULTIMATE V5 ENGINE ---
def main_loop():
    startup = "🚀 BHARAT ALGO V5 STARTED (Manual UI + 5-Min Lock)"
    log_terminal(startup)
    try: send_telegram_msg(startup)
    except: pass

    while True:
        try:
            # 1. Fetch Market Data
            ltp = delta_executor.fetch_btc_spot()
            pos = delta_executor.get_current_position()
            
            # 2. UI Integrations (LEGO Part 3)
            manual_ml = float(config.get_param("manual_magical_line", "0"))
            auto_ml = float(config.get_param("magical_line", "0"))
            
            # Agar dashboard par manual line dali hai, toh usko priority do
            magical_line = manual_ml if manual_ml > 0 else auto_ml
            
            if magical_line > 0 and ltp > 0:
                if pos:
                    # 3. Dynamic Stop Loss Logic
                    entry_price = pos['entry_price']
                    sl_percent = float(config.get_param("stop_loss_percentage", "25"))
                    sl_threshold = entry_price * (1 + (sl_percent / 100))
                    
                    current_premium = delta_executor.fetch_premium(pos['symbol'])
                    
                    # Watchdog Check
                    if current_premium >= sl_threshold:
                        log_terminal(f"🚨 {sl_percent}% SL HIT! Premium {current_premium} >= {sl_threshold}")
                        try: send_telegram_msg(f"🚨 *WATCHDOG SL HIT ({sl_percent}%)*")
                        except: pass
                        delta_executor.square_off_crypto()
                        time.sleep(2)
                        continue

                    # 4. Strict Trend Flip Logic (Ping-Pong Guard)
                    is_bullish = ltp > magical_line
                    is_bearish = ltp < magical_line
                    holding_put = (pos['type'] == 'PUT')
                    holding_call = (pos['type'] == 'CALL')
                    
                    # DO NOTHING RULE (Trend Hold)
                    if holding_put and is_bullish:
                        log_terminal(f"🛡️ Self-Check: I hold PUT, LTP (${ltp}) is > Anchor. Holding correctly.")
                        continue
                    
                    if holding_call and is_bearish:
                        log_terminal(f"🛡️ Self-Check: I hold CALL, LTP (${ltp}) is < Anchor. Holding correctly.")
                        continue

                    # TRUE FLIP RULE
                    if (holding_put and is_bearish) or (holding_call and is_bullish):
                        # 5-Minute Time Lock Check
                        last_trade_time = float(config.get_param("last_trade_time", "0"))
                        if (time.time() - last_trade_time) < 300:
                            log_terminal("⏳ FLIP LOCKED: Waiting for 5-min stabilization.")
                            continue

                        # Execute True Flip
                        if holding_put and is_bearish:
                            log_terminal("📉 TRUE FLIP: PUT -> CALL")
                            delta_executor.square_off_crypto()
                            time.sleep(2)
                            delta_executor.execute_crypto_trade("SELL_CALL")
                            config.set_param("last_trade_time", str(time.time()))
                            
                        elif holding_call and is_bullish:
                            log_terminal("📈 TRUE FLIP: CALL -> PUT")
                            delta_executor.square_off_crypto()
                            time.sleep(2)
                            delta_executor.execute_crypto_trade("SELL_PUT")
                            config.set_param("last_trade_time", str(time.time()))
                        
                        continue
                        
                else:
                    # FRESH ENTRY
                    log_terminal(f"⏱️ HEARTBEAT | LTP: ${ltp} | Anchor: ${magical_line} | Waiting...")
                    
                    if ltp > magical_line:
                        log_terminal("🚀 ENTRY: SELL PUT")
                        delta_executor.execute_crypto_trade("SELL_PUT")
                        config.set_param("last_trade_time", str(time.time()))
                    elif ltp < magical_line:
                        log_terminal("🚀 ENTRY: SELL CALL")
                        delta_executor.execute_crypto_trade("SELL_CALL")
                        config.set_param("last_trade_time", str(time.time()))
            else:
                log_terminal("⏳ Waiting for Magical Line Data...")

        except Exception as e:
            err = traceback.format_exc()
            log_terminal(f"CRITICAL ERROR CATCHED:\n{err}")
            
        time.sleep(10) # Fast check cycle (10 sec) for Watchdog SL

if __name__ == "__main__":
    main_loop()
